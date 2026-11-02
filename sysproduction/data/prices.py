import datetime

import numpy as np

from syscore.exceptions import missingData
from syscore.constants import arg_not_supplied
from syscore.dateutils import Frequency, from_config_frequency_to_frequency, n_days_ago

from sysobjects.contracts import futuresContract
from sysobjects.dict_of_futures_per_contract_prices import (
    dictFuturesContractPrices,
    get_last_matched_date_and_prices_for_contract_list,
)
from sysobjects.spreads import spreadsForInstrument

from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.multiple_prices import futuresMultiplePrices
from sysobjects.adjusted_prices import futuresAdjustedPrices

from sysdata.futures.spreads import spreadsForInstrumentData

from sysdata.futures.multiple_prices import futuresMultiplePricesData
from sysdata.futures.adjusted_prices import futuresAdjustedPricesData
from sysdata.futures.futures_per_contract_prices import futuresContractPriceData

from sysdata.data_blob import dataBlob

from sysobjects.multiple_prices import price_name
from sysobjects.contract_dates_and_expiries import listOfContractDateStr
from sysproduction.data.currency_data import dataCurrency
from sysproduction.data.config import get_list_of_stale_instruments

from sysproduction.data.generic_production_data import productionDataLayerGeneric


## default for spike checking
from sysproduction.data.instruments import diagInstruments, get_block_size
from sysproduction.data.production_data_objects import (
    get_class_for_data_type,
    FUTURES_CONTRACT_PRICE_DATA,
    FUTURES_ADJUSTED_PRICE_DATA,
    FUTURES_MULTIPLE_PRICE_DATA,
    FUTURES_CONTRACT_DATA,
    HISTORIC_SPREAD_DATA,
)

VERY_BIG_NUMBER = 999999.0


class diagPrices(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_list(
            [
                get_class_for_data_type(FUTURES_CONTRACT_PRICE_DATA),
                get_class_for_data_type(FUTURES_ADJUSTED_PRICE_DATA),
                get_class_for_data_type(FUTURES_CONTRACT_DATA),
                get_class_for_data_type(HISTORIC_SPREAD_DATA),
                get_class_for_data_type(FUTURES_MULTIPLE_PRICE_DATA),
            ]
        )
        return data

    def get_intraday_frequency_for_historical_download(self) -> Frequency:
        config = self.data.config
        intraday_frequency_as_str = config.get_element("intraday_frequency")
        try:
            intraday_frequency = from_config_frequency_to_frequency(
                intraday_frequency_as_str
            )
        except missingData:
            error_msg = (
                "Intraday frequency of %s is not recognised as a valid frequency"
                % str(intraday_frequency_as_str)
            )
            self.log.critical(error_msg)
            raise

        return intraday_frequency

    def get_adjusted_prices(self, instrument_code: str) -> futuresAdjustedPrices:
        adjusted_prices = self.db_futures_adjusted_prices_data.get_adjusted_prices(
            instrument_code
        )

        return adjusted_prices

    def get_list_of_instruments_in_multiple_prices(
        self, ignore_stale: bool = True
    ) -> list:
        list_of_instruments = (
            self.db_futures_multiple_prices_data.get_list_of_instruments()
        )
        if ignore_stale:
            list_of_instruments = self.remove_stale_instruments(list_of_instruments)

        return list_of_instruments

    def get_multiple_prices(self, instrument_code: str) -> futuresMultiplePrices:
        multiple_prices = self.db_futures_multiple_prices_data.get_multiple_prices(
            instrument_code
        )

        return multiple_prices

    def get_merged_prices_for_contract_object(
        self, contract_object: futuresContract
    ) -> futuresContractPrices:
        prices = (
            self.db_futures_contract_price_data.get_merged_prices_for_contract_object(
                contract_object
            )
        )

        return prices

    def get_prices_at_frequency_for_contract_object(
        self, contract_object: futuresContract, frequency: Frequency
    ) -> futuresContractPrices:
        prices = self.db_futures_contract_price_data.get_prices_at_frequency_for_contract_object(
            contract_object, frequency=frequency
        )

        return prices

    def get_current_priced_contract_prices_for_instrument(
        self, instrument_code: str
    ) -> futuresContractPrices:
        multiple_prices = self.get_multiple_prices(instrument_code)
        current_priced_contract_prices = multiple_prices[price_name]

        return current_priced_contract_prices

    def get_list_of_instruments_with_contract_prices(
        self, ignore_stale: bool = True
    ) -> list:
        unique_list_of_instruments = self.db_futures_contract_price_data.get_list_of_instrument_codes_with_merged_price_data()

        if ignore_stale:
            unique_list_of_instruments = self.remove_stale_instruments(
                unique_list_of_instruments
            )

        return unique_list_of_instruments

    def contract_dates_with_price_data_for_instrument_code(
        self, instrument_code: str
    ) -> listOfContractDateStr:
        list_of_contract_date_str = self.db_futures_contract_price_data.contract_dates_with_merged_price_data_for_instrument_code(
            instrument_code
        )

        return list_of_contract_date_str

    def get_last_matched_date_and_prices_for_contract_list(
        self,
        instrument_code: str,
        list_of_contract_date_str: list,
        contracts_to_match=arg_not_supplied,
    ) -> (datetime.datetime, list):
        """
        Get a list of matched prices; i.e. from a date when we had both forward and current prices
        If we don't have all the prices, will do the best it can

        :param instrument_code:
        :param contract_list: contract date_str to get prices for
        :param contracts_to_match: (default: contract_list) contracts to match against each other
        :return: list of prices, in same order as contract_list
        """
        if contracts_to_match is arg_not_supplied:
            contracts_to_match = list_of_contract_date_str

        dict_of_prices = self.get_dict_of_prices_for_contract_list(
            instrument_code, list_of_contract_date_str
        )

        (
            last_matched_date,
            last_matched_prices,
        ) = get_last_matched_date_and_prices_for_contract_list(
            dict_of_prices, contracts_to_match, list_of_contract_date_str
        )

        return last_matched_date, last_matched_prices

    def get_dict_of_prices_for_contract_list(
        self, instrument_code: str, list_of_contract_date_str: list
    ) -> dictFuturesContractPrices:
        dict_of_prices = {}
        for contract_date_str in list_of_contract_date_str:
            # Could blow up here if don't have prices for a contract??
            contract = futuresContract(instrument_code, contract_date_str)
            prices = self.get_merged_prices_for_contract_object(contract)
            dict_of_prices[contract_date_str] = prices

        dict_of_prices = dictFuturesContractPrices(dict_of_prices)

        return dict_of_prices

    def get_spreads(self, instrument_code: str) -> spreadsForInstrument:
        return self.db_spreads_for_instrument_data.get_spreads(instrument_code)

    def get_list_of_instruments_with_spread_data(
        self, ignore_stale: bool = True
    ) -> list:
        list_of_instruments = (
            self.db_spreads_for_instrument_data.get_list_of_instruments()
        )
        if ignore_stale:
            list_of_instruments = self.remove_stale_instruments(list_of_instruments)

        return list_of_instruments

    def remove_stale_instruments(self, list_of_instruments: list) -> list:
        stale_instruments = self.get_stale_instruments()
        list_of_instruments = [
            instrument_code
            for instrument_code in list_of_instruments
            if not instrument_code in stale_instruments
        ]

        return list_of_instruments

    def get_stale_instruments(self) -> list:
        return get_list_of_stale_instruments()

    @property
    def db_futures_adjusted_prices_data(self) -> futuresAdjustedPricesData:
        return self.data.db_futures_adjusted_prices

    @property
    def db_futures_multiple_prices_data(self) -> futuresMultiplePricesData:
        return self.data.db_futures_multiple_prices

    @property
    def db_futures_contract_price_data(self) -> futuresContractPriceData:
        return self.data.db_futures_contract_price

    @property
    def db_spreads_for_instrument_data(self) -> spreadsForInstrumentData:
        return self.data.db_spreads_for_instrument


class updatePrices(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_list(
            [
                get_class_for_data_type(FUTURES_CONTRACT_PRICE_DATA),
                get_class_for_data_type(FUTURES_MULTIPLE_PRICE_DATA),
                get_class_for_data_type(FUTURES_CONTRACT_DATA),
                get_class_for_data_type(FUTURES_ADJUSTED_PRICE_DATA),
                get_class_for_data_type(HISTORIC_SPREAD_DATA),
            ]
        )

        return data

    def overwrite_merged_prices_for_contract(
        self,
        contract_object: futuresContract,
        new_prices: futuresContractPrices,
    ):
        self.db_futures_contract_price_data.write_merged_prices_for_contract_object(
            contract_object, futures_price_data=new_prices, ignore_duplication=True
        )

    def overwrite_prices_at_frequency_for_contract(
        self,
        contract_object: futuresContract,
        new_prices: futuresContractPrices,
        frequency: Frequency,
    ):
        self.db_futures_contract_price_data.write_prices_at_frequency_for_contract_object(
            futures_contract_object=contract_object,
            futures_price_data=new_prices,
            frequency=frequency,
            ignore_duplication=True,
        )

    def update_prices_at_frequency_for_contract(
        self,
        contract_object: futuresContract,
        frequency: Frequency,
        new_prices: futuresContractPrices,
        check_for_spike: bool = True,
        max_price_spike: float = VERY_BIG_NUMBER,
    ) -> int:
        error_or_rows_added = (
            self.db_futures_contract_price_data.update_prices_at_frequency_for_contract(
                contract_object=contract_object,
                new_futures_per_contract_prices=new_prices,
                frequency=frequency,
                check_for_spike=check_for_spike,
                max_price_spike=max_price_spike,
            )
        )
        return error_or_rows_added

    def add_multiple_prices(
        self,
        instrument_code: str,
        updated_multiple_prices: futuresMultiplePrices,
        ignore_duplication=True,
    ):
        self.db_futures_multiple_prices_data.add_multiple_prices(
            instrument_code,
            updated_multiple_prices,
            ignore_duplication=ignore_duplication,
        )

    def add_adjusted_prices(
        self,
        instrument_code: str,
        updated_adjusted_prices: futuresAdjustedPrices,
        ignore_duplication=True,
    ):
        self.db_futures_adjusted_prices_data.add_adjusted_prices(
            instrument_code,
            updated_adjusted_prices,
            ignore_duplication=ignore_duplication,
        )

    def delete_merged_contract_prices_for_instrument_code(
        self, instrument_code: str, are_you_sure: bool = False
    ):
        self.db_futures_contract_price_data.delete_merged_prices_for_instrument_code(
            instrument_code, areyousure=are_you_sure
        )

    def delete_contract_prices_at_frequency_for_instrument_code(
        self, instrument_code: str, frequency: Frequency, are_you_sure: bool = False
    ):
        self.db_futures_contract_price_data.delete_prices_at_frequency_for_instrument_code(
            instrument_code, frequency=frequency, areyousure=are_you_sure
        )

    def delete_adjusted_prices(self, instrument_code: str, are_you_sure: bool = False):
        self.db_futures_adjusted_prices_data.delete_adjusted_prices(
            instrument_code, are_you_sure=are_you_sure
        )

    def delete_multiple_prices(self, instrument_code: str, are_you_sure: bool = False):
        self.db_futures_multiple_prices_data.delete_multiple_prices(
            instrument_code, are_you_sure=are_you_sure
        )

    def add_spread_entry(self, instrument_code: str, spread: float):
        self.db_spreads_for_instrument_data.add_spread_entry(
            instrument_code, spread=spread
        )

    def delete_spreads(self, instrument_code: str, are_you_sure: bool = False):
        self.db_spreads_for_instrument_data.delete_spreads(
            instrument_code, are_you_sure=are_you_sure
        )

    @property
    def db_futures_adjusted_prices_data(self) -> futuresAdjustedPricesData:
        return self.data.db_futures_adjusted_prices

    @property
    def db_futures_multiple_prices_data(self) -> futuresMultiplePricesData:
        return self.data.db_futures_multiple_prices

    @property
    def db_futures_contract_price_data(self) -> futuresContractPriceData:
        return self.data.db_futures_contract_price

    @property
    def db_spreads_for_instrument_data(self) -> spreadsForInstrumentData:
        return self.data.db_spreads_for_instrument


INSTRUMENT_CODE_SOURCE_CONFIG = "config"


def get_valid_instrument_code_from_user(
    data: dataBlob = arg_not_supplied,
    allow_all: bool = False,
    allow_exit: bool = False,
    all_code="ALL",
    exit_code="",
    source="multiple",
) -> str:
    if data is arg_not_supplied:
        data = dataBlob()
    instrument_code_list = get_list_of_instruments(data, source=source)
    invalid_input = True
    input_prompt = "Instrument code?"
    if allow_all:
        input_prompt = input_prompt + "(Return for ALL)"
    elif allow_exit:
        input_prompt = input_prompt + "(Return to EXIT)"
    while invalid_input:
        instrument_code = input(input_prompt)

        if allow_all:
            if instrument_code == "" or instrument_code == "ALL":
                return all_code
        elif allow_exit:
            if instrument_code == "":
                return exit_code

        if instrument_code in instrument_code_list:
            break

        print(
            "%s is not in list %s derived from source: %s"
            % (instrument_code, instrument_code_list, source)
        )

    return instrument_code


def get_list_of_instruments(
    data: dataBlob = arg_not_supplied, source="multiple"
) -> list:
    price_data = diagPrices(data)
    if source == "multiple":
        instrument_list = price_data.get_list_of_instruments_in_multiple_prices()
    elif source == "single":
        instrument_list = price_data.get_list_of_instruments_with_contract_prices()
    elif source == INSTRUMENT_CODE_SOURCE_CONFIG:
        instrument_data = diagInstruments(data)
        instrument_list = instrument_data.get_list_of_instruments()
    else:
        raise Exception(
            "%s not recognised must be multiple or single or config" % source
        )

    instrument_list.sort()

    return instrument_list


def recent_average_price(data: dataBlob, instrument_code: str) -> float:
    diag_prices = diagPrices(data)
    prices = diag_prices.get_adjusted_prices(instrument_code)
    if len(prices) == 0:
        return np.nan
    one_year_ago = n_days_ago(365)
    recent_prices = prices[one_year_ago:]

    return recent_prices.mean(skipna=True)


def get_current_price_of_instrument(data, instrument_code):
    price_series = get_price_series(data, instrument_code)
    if len(price_series) == 0:
        return np.nan

    current_price = price_series.values[-1]

    return current_price


def get_price_series(data, instrument_code):
    diag_prices = diagPrices(data)
    price_series = diag_prices.get_adjusted_prices(instrument_code)

    return price_series


def get_current_price_series(data, instrument_code):
    diag_prices = diagPrices(data)
    return diag_prices.get_current_priced_contract_prices_for_instrument(
        instrument_code
    )


def get_cash_cost_in_base_for_instrument(data: dataBlob, instrument_code: str):
    diag_instruments = diagInstruments(data)
    costs_object = diag_instruments.get_cost_object(instrument_code)
    blocks_traded = 1
    block_price_multiplier = get_block_size(data, instrument_code)
    price = recent_average_price(data, instrument_code)
    cost_instrument_ccy = costs_object.calculate_cost_instrument_currency(
        blocks_traded=blocks_traded,
        block_price_multiplier=block_price_multiplier,
        price=price,
    )
    fx = last_currency_fx(data, instrument_code)
    cost_base_ccy = cost_instrument_ccy * fx

    return cost_base_ccy


def last_currency_fx(data: dataBlob, instrument_code: str) -> float:
    data_currency = dataCurrency(data)
    diag_instruments = diagInstruments(data)
    currency = diag_instruments.get_currency(instrument_code)
    fx_rate = data_currency.get_last_fx_rate_to_base(currency)

    return fx_rate


def modify_price_when_contract_has_changed(
    data: dataBlob,
    instrument_code: str,
    new_contract_date: str,
    original_contract_date: str,
    original_price: float,
) -> float:
    if original_contract_date == new_contract_date:
        return original_price

    diag_prices = diagPrices(data)
    contract_list = [original_contract_date, new_contract_date]
    (
        _last_matched_date,
        list_of_matching_prices,
    ) = diag_prices.get_last_matched_date_and_prices_for_contract_list(
        instrument_code, contract_list
    )
    differential = list_of_matching_prices[1] - list_of_matching_prices[0]

    if np.isnan(differential):
        # can't adjust
        # note need to test code there may be other ways in which this fails
        raise missingData

    adjusted_price = original_price + differential

    return adjusted_price
