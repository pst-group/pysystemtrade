"""
Update historical data per contract from interactive brokers data, dump into mongodb
"""

import time
import datetime

from copy import copy
from typing import List, Tuple

from syscore.constants import arg_not_supplied, success, failure
from syscore.exceptions import missingData
from syscore.pandas.merge_data_keeping_past_data import SPIKE_IN_DATA, mergeError
from syscore.dateutils import DAILY_PRICE_FREQ, Frequency
from syscore.pandas.frequency import merge_data_with_different_freq

from sysdata.data_blob import dataBlob
from sysdata.tools.manual_price_checker import manual_price_checker
from sysdata.tools.cleaner import priceFilterConfig, get_config_for_price_filtering

from syslogdiag.email_via_db_interface import send_production_mail_msg
from syslogging.logger import get_logger

from sysobjects.contracts import futuresContract
from sysobjects.futures_per_contract_prices import futuresContractPrices

from sysproduction.data.prices import diagPrices, updatePrices
from sysproduction.data.broker import dataBroker
from sysproduction.data.instruments import diagInstruments
from sysproduction.data.contracts import dataContracts

NO_SPIKE_CHECKING = 99999999999.0


def update_historical_prices():
    """
    Do a daily update for futures contract prices, using IB historical data

    :return: Nothing
    """
    with dataBlob(log_name="Update-Historical-Prices") as data:
        update_historical_price_object = updateHistoricalPrices(data)
        update_historical_price_object.update_historical_prices()
    return success


class updateHistoricalPrices(object):
    def __init__(self, data):
        self.data = data

    def update_historical_prices(self, download_by_zone: dict = arg_not_supplied):
        data = self.data
        update_historical_prices_with_data(data, download_by_zone=download_by_zone)


def update_historical_prices_with_data(
    data: dataBlob, download_by_zone: dict = arg_not_supplied
):
    if download_by_zone is arg_not_supplied:
        download_all_instrument_prices_now(data)
    else:
        manage_download_over_multiple_time_zones(
            data=data, download_by_zone=download_by_zone
        )


def download_all_instrument_prices_now(data: dataBlob):
    data.log.debug("Downloading everything")

    price_data = diagPrices(data)

    list_of_instrument_codes = price_data.get_list_of_instruments_in_multiple_prices()
    update_historical_prices_for_list_of_instrument_codes(
        data=data,
        list_of_instrument_codes=list_of_instrument_codes,
    )


def manage_download_over_multiple_time_zones(data: dataBlob, download_by_zone: dict):
    """
    Example download_by_zone = {'ASIA': '07:00', 'EMEA': '18:00', 'US': '20:00'}

    """
    data.log.debug(
        "Passed multiple time zones: %s, if started before first time will download at specified times"
        % str(download_by_zone)
    )
    dict_of_instrument_codes_by_timezone = get_dict_of_instrument_codes_by_timezone(
        data, download_by_zone=download_by_zone
    )

    manage_download_given_dict_of_instrument_codes(
        data=data,
        dict_of_instrument_codes_by_timezone=dict_of_instrument_codes_by_timezone,
        download_by_zone=download_by_zone,
    )


def get_dict_of_instrument_codes_by_timezone(
    data: dataBlob, download_by_zone: dict
) -> dict:
    """
    Example download_by_zone = {'Asia': '07:00', 'EMEA': '18:00', 'US': '20:00'}

    """

    price_data = diagPrices(data)
    list_of_instrument_codes = price_data.get_list_of_instruments_in_multiple_prices()

    regions = list(download_by_zone.keys())
    dict_by_region = dict(
        [
            (
                region,
                get_list_of_instruments_in_region(
                    region=region,
                    data=data,
                    list_of_instrument_codes=list_of_instrument_codes,
                ),
            )
            for region in regions
        ]
    )

    return dict_by_region


def get_list_of_instruments_in_region(
    region: str, data: dataBlob, list_of_instrument_codes: list
) -> list:
    diag_instruments = diagInstruments(data)

    list_of_codes_in_region = [
        instrument_code
        for instrument_code in list_of_instrument_codes
        if diag_instruments.get_region(instrument_code) == region
    ]

    return list_of_codes_in_region


def manage_download_given_dict_of_instrument_codes(
    data: dataBlob, dict_of_instrument_codes_by_timezone: dict, download_by_zone: dict
):
    """
    Example download_by_zone = {'Asia': '07:00', 'EMEA': '18:00', 'US': '20:00'}
            dict_of_instrument_codes_by_timezone = {'Asia': ['JGB','SPX,...], 'EMEA': [...]... }
    """

    finished = False
    download_time_manager = downloadTimeManager(
        dict_of_instrument_codes_by_timezone=dict_of_instrument_codes_by_timezone,
        download_by_zone=download_by_zone,
    )
    while not finished:
        if download_time_manager.nothing_to_download_but_not_finished():
            ## No rush...
            time.sleep(60)
            continue

        if download_time_manager.finished_downloading_everything():
            ## NOTE this means we could go beyond the STOP time in the report, since this i
            ##    happening outside of the python process manager
            data.log.debug("All instruments downloaded today, finished")
            break

        ## Something to download - this will return the first if more than one
        ##  eg. because we have missed a download
        (
            list_of_instruments_to_download_now,
            region,
        ) = download_time_manager.list_of_instruments_and_region_to_download_now()

        data.log.debug(
            "Now it's time to download region %s: %s"
            % (region, str(list_of_instruments_to_download_now))
        )
        update_historical_prices_for_list_of_instrument_codes(
            data, list_of_instrument_codes=list_of_instruments_to_download_now
        )
        download_time_manager.mark_region_as_download_completed(region)
        data.log.debug("Finished downloading region %s" % region)


class downloadTimeManager:
    def __init__(
        self, dict_of_instrument_codes_by_timezone: dict, download_by_zone: dict
    ):
        # keys of each dict must match
        self._download_times_by_zone = download_by_zone
        self._dict_of_instrument_codes_by_timezone = (
            dict_of_instrument_codes_by_timezone
        )
        region_list = list(download_by_zone.keys())
        self._init_progress_dict(region_list)

    def _init_progress_dict(self, region_list: List[str]):
        progress_dict = dict([(region, False) for region in region_list])
        self._progress_dict = progress_dict

    def nothing_to_download_but_not_finished(self) -> bool:
        all_finished = self.finished_downloading_everything()
        if all_finished:
            return False

        (
            list_of_instruments,
            region,
        ) = self.list_of_instruments_and_region_to_download_now()

        if len(list_of_instruments) == 0:
            ## nothing to do right now
            return True
        else:
            return False

    def list_of_instruments_and_region_to_download_now(self) -> Tuple[list, str]:
        for region in self.list_of_regions:
            if self.can_region_be_downloaded_now(region):
                return self.dict_of_instrument_codes_by_timezone[region], region

        return [], ""

    def can_region_be_downloaded_now(self, region: str) -> bool:
        already_done = self.progress_dict[region]
        if already_done:
            return False

        time_to_start = self.is_it_time_to_start_region(region)

        return time_to_start

    def is_it_time_to_start_region(self, region: str) -> bool:
        time_to_start = self.time_to_start_downloading(region)
        now = datetime.datetime.now().time()
        return now >= time_to_start

    def time_to_start_downloading(self, region: str) -> datetime.time:
        time_str = self.download_times_by_zone[region]
        time_object = datetime.datetime.strptime(time_str, "%H:%M").time()

        return time_object

    def mark_region_as_download_completed(self, region: str):
        ## we don't use the getter here as we don't want to use a setter to update
        progress_dict = self._progress_dict
        progress_dict[region] = region
        self._progress_dict = progress_dict  ## not strictly required, but...

    def finished_downloading_everything(self) -> bool:
        list_of_progress_bool = self.list_of_progress
        which_regions_are_finished = [
            progress_for_region for progress_for_region in list_of_progress_bool
        ]
        all_finished = all(which_regions_are_finished)

        return all_finished

    @property
    def list_of_regions(self) -> List[str]:
        return list(self.progress_dict.keys())

    @property
    def list_of_progress(self) -> List[bool]:
        return list(self.progress_dict.values())

    @property
    def progress_dict(self) -> dict:
        return self._progress_dict

    @property
    def download_times_by_zone(self) -> dict:
        return self._download_times_by_zone

    @property
    def dict_of_instrument_codes_by_timezone(self) -> dict:
        return self._dict_of_instrument_codes_by_timezone


def update_historical_prices_for_list_of_instrument_codes(
    data: dataBlob, list_of_instrument_codes: List[str]
):
    cleaning_config = get_config_for_price_filtering(data)

    for instrument_code in list_of_instrument_codes:
        data.log.debug(
            "Updating log attributes",
            method="clear",
            instrument_code=instrument_code,
        )
        update_historical_prices_for_instrument(
            instrument_code,
            data,
            cleaning_config=cleaning_config,
            interactive_mode=False,
        )


## This is also called by the interactive update
def update_historical_prices_for_instrument(
    instrument_code: str,
    data: dataBlob,
    cleaning_config: priceFilterConfig = arg_not_supplied,
    interactive_mode: bool = False,
):
    """
    Do a daily update for futures contract prices, using IB historical data

    :param instrument_code: str
    :param data: dataBlob
    :return: None
    """
    diag_contracts = dataContracts(data)
    all_contracts_list = diag_contracts.get_all_contract_objects_for_instrument_code(
        instrument_code
    )
    contract_list = all_contracts_list.currently_sampling()

    if len(contract_list) == 0:
        data.log.warning("No contracts marked for sampling for %s" % instrument_code)
        return failure

    for contract_object in contract_list:
        data.update_log(get_logger(data.log.name, contract_object.log_attributes()))
        update_historical_prices_for_instrument_and_contract(
            contract_object,
            data,
            cleaning_config=cleaning_config,
            interactive_mode=interactive_mode,
        )

    return success


def update_historical_prices_for_instrument_and_contract(
    contract_object: futuresContract,
    data: dataBlob,
    cleaning_config: priceFilterConfig = arg_not_supplied,
    interactive_mode: bool = False,
):
    diag_prices = diagPrices(data)
    intraday_frequency = diag_prices.get_intraday_frequency_for_historical_download()
    daily_frequency = DAILY_PRICE_FREQ

    list_of_frequencies = [intraday_frequency, daily_frequency]

    for frequency in list_of_frequencies:
        get_and_add_prices_for_frequency(
            data,
            contract_object,
            frequency=frequency,
            cleaning_config=cleaning_config,
            interactive_mode=interactive_mode,
        )

    write_merged_prices_for_contract(
        data, contract_object=contract_object, list_of_frequencies=list_of_frequencies
    )

    return success


def get_and_add_prices_for_frequency(
    data: dataBlob,
    contract_object: futuresContract,
    frequency: Frequency,
    cleaning_config: priceFilterConfig,
    interactive_mode: bool = False,
):
    broker_data_source = dataBroker(data)

    try:
        broker_prices = (
            broker_data_source.get_cleaned_prices_at_frequency_for_contract_object(
                contract_object, frequency, cleaning_config=cleaning_config
            )
        )
    except missingData:
        data.log.warning(
            "Something went wrong with getting prices for %s to check"
            % str(contract_object)
        )
        return failure

    if len(broker_prices) == 0:
        print("No broker prices found for %s nothing to check" % str(contract_object))
        return success

    if interactive_mode:
        print("\n\nManually checking prices for %s\n\n" % str(contract_object))
        max_price_spike = cleaning_config.max_price_spike

        price_data = diagPrices(data)
        old_prices = price_data.get_prices_at_frequency_for_contract_object(
            contract_object, frequency=frequency
        )
        new_prices_checked = manual_price_checker(
            old_prices,
            broker_prices,
            column_to_check="FINAL",
            delta_columns=["OPEN", "HIGH", "LOW"],
            type_new_data=futuresContractPrices,
            max_price_spike=max_price_spike,
        )
        check_for_spike = False
    else:
        new_prices_checked = copy(broker_prices)
        check_for_spike = True

    error_or_rows_added = price_updating_or_errors(
        data=data,
        frequency=frequency,
        contract_object=contract_object,
        new_prices_checked=new_prices_checked,
        check_for_spike=check_for_spike,
        cleaning_config=cleaning_config,
    )
    if error_or_rows_added is failure:
        return failure

    data.log.debug(
        "Added %d rows at frequency %s for %s"
        % (error_or_rows_added, frequency, str(contract_object))
    )
    return success


def price_updating_or_errors(
    data: dataBlob,
    frequency: Frequency,
    contract_object: futuresContract,
    new_prices_checked: futuresContractPrices,
    cleaning_config: priceFilterConfig,
    check_for_spike: bool = True,
):
    price_updater = updatePrices(data)

    try:
        error_or_rows_added = price_updater.update_prices_at_frequency_for_contract(
            contract_object=contract_object,
            new_prices=new_prices_checked,
            frequency=frequency,
            check_for_spike=check_for_spike,
            max_price_spike=cleaning_config.max_price_spike,
        )
    except mergeError:
        data.log.warning("Something went wrong when adding rows")
        return failure

    if error_or_rows_added is SPIKE_IN_DATA:
        report_price_spike(data, contract_object)
        return failure

    return error_or_rows_added


def report_price_spike(data: dataBlob, contract_object: futuresContract):
    # SPIKE
    # Need to email user about this as will need manually checking
    msg = (
        "Spike found in prices for %s: need to manually check by running interactive_manual_check_historical_prices"
        % str(contract_object)
    )
    data.log.warning(msg)
    try:
        send_production_mail_msg(
            data, msg, "Price Spike %s" % contract_object.instrument_code
        )
    except BaseException:
        data.log.warning(
            "Couldn't send email about price spike for %s" % str(contract_object)
        )


def write_merged_prices_for_contract(
    data: dataBlob, contract_object: futuresContract, list_of_frequencies: list
):
    ## note list of frequencies must have daily as last or groupby won't work with volume

    assert list_of_frequencies[-1] == DAILY_PRICE_FREQ

    diag_prices = diagPrices(data)
    price_updater = updatePrices(data)

    list_of_data = [
        diag_prices.get_prices_at_frequency_for_contract_object(
            contract_object,
            frequency=frequency,
        )
        for frequency in list_of_frequencies
    ]

    merged_prices = merge_data_with_different_freq(list_of_data)

    if len(merged_prices) > 0:
        price_updater.overwrite_merged_prices_for_contract(
            contract_object=contract_object,
            new_prices=futuresContractPrices(merged_prices),
        )


if __name__ == "__main__":
    update_historical_prices()
