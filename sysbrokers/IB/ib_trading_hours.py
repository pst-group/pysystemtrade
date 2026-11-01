import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.tz import datetime_ambiguous, datetime_exists
from ib_async import ContractDetails as ibContractDetails

from sysdata.config.private_config import (
    get_private_config_dir,
)
from sysobjects.production.trading_hours.trading_hours import (
    tradingHours,
    listOfTradingHours,
)
from syscore.fileutils import (
    does_resolved_filename_exist,
    resolve_path_and_filename_for_package,
)
from sysdata.config.production_config import get_production_config
from sysdata.production.trading_hours import read_trading_hours

IB_CONFIG_TRADING_HOURS_FILE = "sysbrokers.IB.ib_config_trading_hours.yaml"
PRIVATE_CONFIG_TRADING_HOURS_FILE = "private_config_trading_hours.yaml"


def get_saved_trading_hours():
    private_path = resolve_path_and_filename_for_package(
        get_private_config_dir(), PRIVATE_CONFIG_TRADING_HOURS_FILE
    )
    if does_resolved_filename_exist(private_path):
        return read_trading_hours(private_path)
    else:
        default_path = resolve_path_and_filename_for_package(
            IB_CONFIG_TRADING_HOURS_FILE
        )
        return read_trading_hours(default_path)


def get_trading_hours_from_contract_details(
    ib_contract_details: ibContractDetails,
) -> listOfTradingHours:
    try:
        time_zone_id = ib_contract_details.timeZoneId
        production_config = get_production_config()
        local_timezone = production_config.get_element_or_default(
            "local_timezone", None
        )
        if local_timezone is not None:
            if (
                production_config.get_element_or_default("GMT_offset_hours", None)
                is not None
            ):
                raise ValueError(
                    "Set only one of local_timezone and GMT_offset_hours; "
                    "remove GMT_offset_hours or set it to null to use local_timezone"
                )
            return _parse_trading_hours_with_timezones(
                ib_contract_details.tradingHours, time_zone_id, local_timezone
            )

        time_zone_adjustment = get_time_difference(time_zone_id)

        trading_hours_string = ib_contract_details.tradingHours
        list_of_open_times = parse_trading_hours_string(
            trading_hours_string, adjustment_hours=time_zone_adjustment
        )
    except Exception as e:
        raise e

    return list_of_open_times


NO_ADJUSTMENTS = 0, 0
CLOSED_ALL_DAY = object()


def _parse_trading_hours_with_timezones(
    trading_hours_string: str, source_timezone: str, local_timezone: str
) -> listOfTradingHours:
    source_zone = _get_trading_timezone(source_timezone)
    local_zone = _get_trading_timezone(local_timezone)
    opening_times = []
    for day_record in trading_hours_string.split(";"):
        if not day_record:
            continue
        day, sessions = day_record.split(":", 1)
        if sessions == "CLOSED":
            continue
        datetime.datetime.strptime(day, "%Y%m%d")
        for session in sessions.split(","):
            start, end = session.split("-")
            if ":" not in start:
                start = "%s:%s" % (day, start)
            opening = _parse_trading_time_in_timezone(start, source_zone)
            closing = _parse_trading_time_in_timezone(end, source_zone)
            if closing <= opening:
                raise ValueError(
                    "IB trading session must close after it opens: %s" % session
                )

            # Keep the conservative buffer in elapsed hours, including clock changes.
            opening += datetime.timedelta(hours=1)
            closing -= datetime.timedelta(hours=1)
            if closing <= opening:
                continue
            opening_times.append(
                tradingHours(
                    _as_naive_trading_time(opening, local_zone),
                    _as_naive_trading_time(closing, local_zone),
                )
            )

    return listOfTradingHours(opening_times)


def _get_trading_timezone(time_zone_id: str) -> ZoneInfo:
    if not isinstance(time_zone_id, str) or not time_zone_id:
        raise ValueError("Trading hours require an explicit IANA timezone")
    if time_zone_id in ("EST", "CST", "MST", "PST"):
        raise ValueError(
            "Ambiguous timezone %s; use an explicit IANA timezone" % time_zone_id
        )
    try:
        return ZoneInfo(time_zone_id)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(
            "Unknown trading-hours timezone %r; check the name and timezone data"
            % time_zone_id
        ) from error


def _parse_trading_time_in_timezone(
    phrase: str, time_zone: ZoneInfo
) -> datetime.datetime:
    local_time = datetime.datetime.strptime(phrase, "%Y%m%d:%H%M")
    if local_time.strftime("%Y%m%d:%H%M") != phrase:
        raise ValueError("Expected a dated IB trading time, got %r" % phrase)
    return _unique_trading_time_in_utc(local_time, time_zone)


def _unique_trading_time_in_utc(
    local_time: datetime.datetime, time_zone: ZoneInfo
) -> datetime.datetime:
    aware_time = local_time.replace(tzinfo=time_zone)
    if not datetime_exists(aware_time):
        raise ValueError("Nonexistent trading time %s in %s" % (local_time, time_zone))
    if datetime_ambiguous(aware_time):
        raise ValueError("Ambiguous trading time %s in %s" % (local_time, time_zone))
    return aware_time.astimezone(datetime.timezone.utc)


def _as_naive_trading_time(
    utc_time: datetime.datetime, time_zone: ZoneInfo
) -> datetime.datetime:
    local_time = utc_time.astimezone(time_zone).replace(tzinfo=None)
    # Native local-naive comparisons cannot distinguish the two repeated-hour folds.
    _unique_trading_time_in_utc(local_time, time_zone)
    return local_time


def parse_trading_hours_string(
    trading_hours_string: str,
    adjustment_hours: int = 0,
) -> listOfTradingHours:
    day_by_day = trading_hours_string.split(";")
    list_of_open_times = [
        parse_trading_for_day(string_for_day, adjustment_hours=adjustment_hours)
        for string_for_day in day_by_day
    ]

    list_of_open_times = [
        open_time for open_time in list_of_open_times if open_time is not CLOSED_ALL_DAY
    ]

    list_of_open_times = listOfTradingHours(list_of_open_times)

    return list_of_open_times


def parse_trading_for_day(
    string_for_day: str, adjustment_hours: int = 0
) -> tradingHours:
    start_and_end = string_for_day.split("-")
    if len(start_and_end) == 1:
        # closed
        return CLOSED_ALL_DAY

    start_phrase = start_and_end[0]
    end_phrase = start_and_end[1]

    # Doesn't deal with DST. We will be conservative and only trade 1 hour
    # after and 1 hour before
    adjust_start = 1
    adjust_end = -1

    start_dt = parse_phrase(
        start_phrase, adjustment_hours=adjustment_hours, additional_adjust=adjust_start
    )

    end_dt = parse_phrase(
        end_phrase, adjustment_hours=adjustment_hours, additional_adjust=adjust_end
    )

    return tradingHours(start_dt, end_dt)


def parse_phrase(
    phrase: str, adjustment_hours: int = 0, additional_adjust: int = 0
) -> datetime.datetime:
    total_adjustment = adjustment_hours + additional_adjust
    original_time = datetime.datetime.strptime(phrase, "%Y%m%d:%H%M")
    adjustment = datetime.timedelta(hours=total_adjustment)

    return original_time + adjustment


def get_GMT_offset_hours():
    GMT_offset_hours = get_production_config().get_element_or_default(
        "GMT_offset_hours", None
    )
    return 0 if GMT_offset_hours is None else GMT_offset_hours


def get_time_difference(time_zone_id: str) -> int:
    # Doesn't deal with DST. We will be conservative and only trade 1 hour
    # after and 1 hour before
    # confusingly, IB seem to have changed their time zone codes in 2020
    # some of these are legacy codes which could be removed
    time_diff_dict = {
        "CST (Central Standard Time)": 6,
        "MET (Middle Europe Time)": -1,
        "EST (Eastern Standard Time)": 5,
        "JST (Japan Standard Time)": -9,
        "US/Eastern": 5,
        "MET": -1,
        "EST": 5,
        "JST": -9,
        "Japan": -9,
        "US/Central": 6,
        "GB-Eire": 0,
        "Hongkong": -8,
        "Australia/NSW": -11,
        "": 0,
    }
    GMT_offset_hours = get_GMT_offset_hours()
    for k, v in time_diff_dict.items():
        time_diff_dict[k] = v + GMT_offset_hours
    diff_hours = time_diff_dict.get(time_zone_id, None)
    if diff_hours is None:
        raise Exception("Time zone '%s' not found!" % time_zone_id)

    return diff_hours
