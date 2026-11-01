import datetime
from types import SimpleNamespace

import pytest
import yaml

from sysbrokers.IB import ib_trading_hours
from syscore.constants import arg_not_supplied
from sysdata.config.configdata import Config
from sysobjects.production.trading_hours.intersection_of_weekly_and_specific_trading_hours import (
    intersection_of_any_weekly_and_list_of_normal_trading_hours,
)
from sysobjects.production.trading_hours.weekly_trading_hours_any_day import (
    weekdayDictOfListOfTradingHoursAnyDay,
)


@pytest.fixture
def convert(monkeypatch):
    def convert(
        source,
        schedule,
        target="America/Los_Angeles",
        offset=arg_not_supplied,
        configured=True,
    ):
        settings = {}
        if offset is not arg_not_supplied:
            settings["GMT_offset_hours"] = offset
        if configured:
            settings["local_timezone"] = target
        config = SimpleNamespace(
            **settings,
            get_element_or_default=lambda name, default: settings.get(name, default),
        )
        monkeypatch.setattr(ib_trading_hours, "get_production_config", lambda: config)
        details = SimpleNamespace(timeZoneId=source, tradingHours=schedule)
        return ib_trading_hours.get_trading_hours_from_contract_details(details)

    return convert


@pytest.fixture
def configured_convert(monkeypatch, tmp_path):
    monkeypatch.setenv("PYSYS_PRIVATE_CONFIG_DIR", str(tmp_path))

    def convert(private_settings, system_settings=None):
        (tmp_path / "private_config.yaml").write_text(yaml.safe_dump(private_settings))
        config = Config(system_settings or {})
        config.fill_with_defaults()
        monkeypatch.setattr(ib_trading_hours, "get_production_config", lambda: config)
        details = SimpleNamespace(
            timeZoneId="GB-Eire", tradingHours="20260713:1200-20260713:1800"
        )
        return ib_trading_hours.get_trading_hours_from_contract_details(details)

    return convert


def assert_windows(actual, expected):
    assert [
        (window.opening_time.isoformat(), window.closing_time.isoformat())
        for window in actual
    ] == expected
    assert all(
        window.opening_time.tzinfo is None and window.closing_time.tzinfo is None
        for window in actual
    )


@pytest.mark.parametrize(
    "day,opening,closing",
    [
        ("20260306", "05:00", "09:00"),
        ("20260310", "06:00", "10:00"),
        ("20260330", "05:00", "09:00"),
        ("20261024", "05:00", "09:00"),
        ("20261026", "06:00", "10:00"),
        ("20261102", "05:00", "09:00"),
    ],
)
def test_london_and_pacific_change_clocks_on_different_dates(
    convert, day, opening, closing
):
    date = datetime.datetime.strptime(day, "%Y%m%d").date().isoformat()
    result = convert("GB-Eire", f"{day}:1200-{day}:1800")
    assert_windows(result, [(f"{date}T{opening}:00", f"{date}T{closing}:00")])


@pytest.mark.parametrize("day", ["20260112", "20260713"])
@pytest.mark.parametrize(
    "source,opening,closing",
    [("US/Eastern", "07:00", "13:00"), ("US/Central", "08:00", "14:00")],
)
def test_us_exchange_and_pacific_offsets_track_each_session_date(
    convert, day, source, opening, closing
):
    date = datetime.datetime.strptime(day, "%Y%m%d").date().isoformat()
    result = convert(source, f"{day}:0900-{day}:1700")
    assert_windows(result, [(f"{date}T{opening}:00", f"{date}T{closing}:00")])


@pytest.mark.parametrize(
    "source,day,opening,closing",
    [
        ("US/Eastern", "20260112", "2026-01-12T15:00:00", "2026-01-12T21:00:00"),
        ("US/Eastern", "20260713", "2026-07-13T14:00:00", "2026-07-13T20:00:00"),
        ("US/Central", "20260112", "2026-01-12T16:00:00", "2026-01-12T22:00:00"),
        ("US/Central", "20260713", "2026-07-13T15:00:00", "2026-07-13T21:00:00"),
        ("Australia/NSW", "20260112", "2026-01-11T23:00:00", "2026-01-12T05:00:00"),
        ("Australia/NSW", "20260713", "2026-07-13T00:00:00", "2026-07-13T06:00:00"),
        ("MET", "20260713", "2026-07-13T08:00:00", "2026-07-13T14:00:00"),
        ("Japan", "20260713", "2026-07-13T01:00:00", "2026-07-13T07:00:00"),
        ("Hongkong", "20260713", "2026-07-13T02:00:00", "2026-07-13T08:00:00"),
        ("GMT", "20260713", "2026-07-13T10:00:00", "2026-07-13T16:00:00"),
    ],
)
def test_named_zones_include_opposite_seasons_and_iana_aliases(
    convert, source, day, opening, closing
):
    result = convert(source, f"{day}:0900-{day}:1700", target="UTC")
    assert_windows(result, [(opening, closing)])


def test_japan_conversion_can_move_the_whole_session_to_previous_date(convert):
    result = convert("Japan", "20260713:0900-20260713:1500")
    assert_windows(result, [("2026-07-12T18:00:00", "2026-07-12T22:00:00")])


def test_japan_overnight_session_preserves_its_explicit_closing_date(convert):
    result = convert("Japan", "20260713:1630-20260714:0600")
    assert_windows(result, [("2026-07-13T01:30:00", "2026-07-13T13:00:00")])


def test_each_date_in_one_schedule_uses_its_own_offsets(convert):
    result = convert(
        "GB-Eire",
        "20261024:1200-20261024:1800;20261026:1200-20261026:1800;"
        "20261102:1200-20261102:1800",
    )
    assert_windows(
        result,
        [
            ("2026-10-24T05:00:00", "2026-10-24T09:00:00"),
            ("2026-10-26T06:00:00", "2026-10-26T10:00:00"),
            ("2026-11-02T05:00:00", "2026-11-02T09:00:00"),
        ],
    )


@pytest.mark.parametrize("second_start", ["1300", "20260713:1300"])
def test_split_sessions_and_closed_days_keep_the_break(convert, second_start):
    result = convert(
        "UTC",
        f"20260712:CLOSED;20260713:0800-20260713:1200," f"{second_start}-20260713:1800",
        target="UTC",
    )
    assert_windows(
        result,
        [
            ("2026-07-13T09:00:00", "2026-07-13T11:00:00"),
            ("2026-07-13T14:00:00", "2026-07-13T17:00:00"),
        ],
    )


@pytest.mark.parametrize("duration", ["0930", "1000", "1100"])
def test_short_sessions_have_no_permitted_interval_after_buffer(convert, duration):
    assert convert("UTC", f"20260713:0900-20260713:{duration}", target="UTC") == []


@pytest.mark.parametrize(
    "schedule,expected",
    [
        (
            "20260308:0000-20260308:0500",
            [("2026-03-08T06:00:00", "2026-03-08T08:00:00")],
        ),
        (
            "20261101:0000-20261101:0400",
            [("2026-11-01T05:00:00", "2026-11-01T08:00:00")],
        ),
    ],
)
def test_buffer_is_one_elapsed_hour_across_source_transition(
    convert, schedule, expected
):
    assert_windows(convert("US/Eastern", schedule, target="UTC"), expected)


@pytest.mark.parametrize(
    "schedule",
    [
        "20261101:0130-20261101:0600",
        "20261101:0000-20261101:0130",
        "20260308:0230-20260308:0600",
        "20260308:0000-20260308:0230",
    ],
)
def test_ambiguous_or_nonexistent_source_endpoint_is_rejected(convert, schedule):
    with pytest.raises(ValueError):
        convert("US/Eastern", schedule, target="UTC")


@pytest.mark.parametrize(
    "schedule",
    ["20261101:0730-20261101:1400", "20261101:0300-20261101:1030"],
)
def test_ambiguous_buffered_target_endpoint_is_rejected(convert, schedule):
    with pytest.raises(ValueError):
        convert("UTC", schedule)


@pytest.mark.parametrize(
    "source",
    ["", "Not/AZone", "EST", "CST", "MST", "PST", "EST (Eastern Standard Time)"],
)
def test_unknown_or_ambiguous_source_zone_is_not_guessed(convert, source):
    with pytest.raises(ValueError):
        convert(source, "20260713:0900-20260713:1700")


@pytest.mark.parametrize(
    "target", ["", "Not/AZone", "EST", "CST", "MST", "PST", False, 0]
)
def test_invalid_configured_zone_does_not_fall_back_to_numeric_offset(convert, target):
    with pytest.raises(ValueError):
        convert("US/Eastern", "20260713:0900-20260713:1700", target=target)


@pytest.mark.parametrize(
    "schedule",
    [
        "20260713:UNKNOWN",
        "20261313:0900-20261313:1700",
        "20260713:0900-1700",
        "20260713:1700-20260713:0900",
        "20260713:0900-20260713:0900",
        "20260713:2500-20260714:0300",
    ],
)
def test_malformed_or_reversed_session_is_rejected(convert, schedule):
    with pytest.raises(ValueError):
        convert("US/Eastern", schedule)


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize(
    "source,offset,opening,closing",
    [
        ("US/Eastern", -7, "08:00", "14:00"),
        ("US/Central", -8, "08:00", "14:00"),
        ("EST", -7, "08:00", "14:00"),
        ("EST (Eastern Standard Time)", -7, "08:00", "14:00"),
        ("", 0, "10:00", "16:00"),
        ("", 5.5, "15:30", "21:30"),
    ],
)
def test_unconfigured_or_null_keeps_legacy_offsets(
    convert, configured, source, offset, opening, closing
):
    result = convert(
        source,
        "20260713:0900-20260713:1700",
        target=None,
        offset=offset,
        configured=configured,
    )
    assert_windows(result, [(f"2026-07-13T{opening}:00", f"2026-07-13T{closing}:00")])


@pytest.mark.parametrize("offset", [arg_not_supplied, None])
@pytest.mark.parametrize("configured", [False, True])
def test_unset_offset_keeps_legacy_zero_default(convert, offset, configured):
    result = convert(
        "",
        "20260713:0900-20260713:1700",
        target=None,
        offset=offset,
        configured=configured,
    )
    assert_windows(result, [("2026-07-13T10:00:00", "2026-07-13T16:00:00")])


@pytest.mark.parametrize("offset", [arg_not_supplied, None])
def test_named_timezone_accepts_only_unset_offset(convert, offset):
    result = convert("US/Eastern", "20260713:0900-20260713:1700", offset=offset)
    assert_windows(result, [("2026-07-13T07:00:00", "2026-07-13T13:00:00")])


@pytest.mark.parametrize("offset", [0, -7, 5.5, False])
def test_named_timezone_and_explicit_offset_conflict(convert, offset):
    with pytest.raises(ValueError, match=r"local_timezone.*GMT_offset_hours"):
        convert("US/Eastern", "20260713:0900-20260713:1700", offset=offset)


@pytest.mark.parametrize(
    "settings,opening,closing",
    [
        ({}, "13:00", "17:00"),
        ({"GMT_offset_hours": None}, "13:00", "17:00"),
        ({"GMT_offset_hours": 0}, "13:00", "17:00"),
        ({"GMT_offset_hours": -7}, "06:00", "10:00"),
        ({"local_timezone": "America/Los_Angeles"}, "05:00", "09:00"),
        (
            {"local_timezone": "America/Los_Angeles", "GMT_offset_hours": None},
            "05:00",
            "09:00",
        ),
    ],
)
def test_real_private_config_and_packaged_defaults(
    configured_convert, settings, opening, closing
):
    assert_windows(
        configured_convert(settings),
        [(f"2026-07-13T{opening}:00", f"2026-07-13T{closing}:00")],
    )


@pytest.mark.parametrize(
    "private_settings,system_settings",
    [
        ({"GMT_offset_hours": 0}, {"local_timezone": "America/Los_Angeles"}),
        ({"local_timezone": "America/Los_Angeles"}, {"GMT_offset_hours": -7}),
        (
            {"GMT_offset_hours": 0},
            {"local_timezone": "America/Los_Angeles", "GMT_offset_hours": None},
        ),
        (
            {},
            {"base_config": {"GMT_offset_hours": 0}, "local_timezone": "UTC"},
        ),
    ],
)
def test_conflicts_from_native_config_layers_are_not_hidden(
    configured_convert, private_settings, system_settings
):
    with pytest.raises(ValueError, match=r"local_timezone.*GMT_offset_hours"):
        configured_convert(private_settings, system_settings)


@pytest.mark.parametrize("target", [None, "America/Los_Angeles"])
def test_closed_days_return_no_windows(convert, target):
    assert convert("US/Eastern", "20260711:CLOSED;20260712:CLOSED", target=target) == []


def test_saved_weekly_restriction_still_narrows_converted_session(convert):
    hours = convert("US/Eastern", "20260713:0900-20260713:1700")
    saved = weekdayDictOfListOfTradingHoursAnyDay.from_simple_dict(["08:00", "12:00"])
    result = intersection_of_any_weekly_and_list_of_normal_trading_hours(hours, saved)
    assert_windows(result, [("2026-07-13T08:00:00", "2026-07-13T12:00:00")])
    assert_windows(hours, [("2026-07-13T07:00:00", "2026-07-13T13:00:00")])


def test_overnight_session_still_intersects_the_correct_weekdays(convert):
    hours = convert("US/Central", "20260713:2000-20260714:1000")
    assert_windows(hours, [("2026-07-13T19:00:00", "2026-07-14T07:00:00")])
    saved = weekdayDictOfListOfTradingHoursAnyDay.from_simple_dict(
        {"Monday": ["20:00", "22:00"], "Tuesday": ["05:00", "06:00"]}
    )
    result = intersection_of_any_weekly_and_list_of_normal_trading_hours(hours, saved)
    assert_windows(
        result,
        [
            ("2026-07-13T20:00:00", "2026-07-13T22:00:00"),
            ("2026-07-14T05:00:00", "2026-07-14T06:00:00"),
        ],
    )


def test_client_keeps_raw_timezone_key_for_saved_restrictions(convert, monkeypatch):
    from sysbrokers.IB.client.ib_contracts_client import ibContractsClient

    schedule = "20260713:0900-20260713:1700"
    convert("US/Eastern", schedule)
    details = SimpleNamespace(timeZoneId="US/Eastern", tradingHours=schedule)
    contract = SimpleNamespace(log_attributes=lambda: {})
    saved = weekdayDictOfListOfTradingHoursAnyDay.from_simple_dict(["08:00", "12:00"])
    # No connection or client constructor: all broker/file inputs are supplied here.
    client = ibContractsClient.__new__(ibContractsClient)
    monkeypatch.setattr(client, "ib_get_contract_details", lambda _: details)
    monkeypatch.setattr(
        client, "get_all_saved_weekly_trading_hours", lambda: {"US/Eastern": saved}
    )

    assert_windows(
        client.ib_get_trading_hours_from_IB(contract),
        [("2026-07-13T07:00:00", "2026-07-13T13:00:00")],
    )
    assert client.ib_get_timezoneid(contract) == "US/Eastern"
    assert (
        client.ib_get_saved_weekly_trading_hours_for_timezone_of_contract(contract)
        is saved
    )
