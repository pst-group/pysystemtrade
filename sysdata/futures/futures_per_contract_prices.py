from syscore.exceptions import missingData
from syscore.dateutils import Frequency, MIXED_FREQ
from syscore.pandas.merge_data_keeping_past_data import SPIKE_IN_DATA, mergeError

from sysdata.base_data import baseData

from sysobjects.contracts import futuresContract, listOfFuturesContracts
from sysobjects.contract_dates_and_expiries import listOfContractDateStr
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.dict_of_futures_per_contract_prices import dictFuturesContractPrices

from syslogging.logger import get_logger

BASE_CLASS_ERROR = "You have used a base class for futures price data; you need to use a class that inherits with a specific data source"

VERY_BIG_NUMBER = 999999.0


#### Three types of price data: at a specific frequency, and 'merged' (no specific frequency, covers all bases)
####   and 'all' (both types)


class futuresContractPriceData(baseData):
    """
    Extends the baseData object to a data source that reads in and writes prices for specific futures contracts

    This would normally be extended further for information from a specific source eg quandl, arctic

    Access via: object.get_prices_for_instrumentCode_and_contractDate('EDOLLAR','201702']
     or object.get_prices_for_contract_object(futuresContract(....))
    """

    def __init__(self, log=get_logger("futuresContractPriceData")):
        super().__init__(log=log)

    def __repr__(self):
        return "Individual futures contract price data - DO NOT USE"

    def __getitem__(self, contract_object: futuresContract) -> futuresContractPrices:
        """
        convenience method to get the price, make it look like a dict

        """

        return self.get_merged_prices_for_contract_object(contract_object)

    def keys(self) -> listOfFuturesContracts:
        """
        list of things in this data set (futures contracts, instruments...)

        :returns: list of str

        """
        return self.get_contracts_with_merged_price_data()

    def get_list_of_instrument_codes_with_merged_price_data(self) -> list:
        """

        :return: list of str
        """

        list_of_contracts_with_price_data = self.get_contracts_with_merged_price_data()
        unique_list_of_instruments = (
            list_of_contracts_with_price_data.unique_list_of_instrument_codes()
        )

        return unique_list_of_instruments

    def get_list_of_instrument_codes_with_price_data_at_frequency(
        self, frequency: Frequency
    ) -> list:
        """

        :return: list of str
        """

        list_of_contracts_with_price_data = (
            self.get_contracts_with_price_data_for_frequency(frequency=frequency)
        )
        unique_list_of_instruments = (
            list_of_contracts_with_price_data.unique_list_of_instrument_codes()
        )

        return unique_list_of_instruments

    def has_merged_price_data_for_contract(
        self, contract_object: futuresContract
    ) -> bool:
        list_of_contracts = self.get_contracts_with_merged_price_data()
        if contract_object in list_of_contracts:
            return True
        else:
            return False

    def has_price_data_for_contract_at_frequency(
        self, contract_object: futuresContract, frequency: Frequency
    ) -> bool:
        list_of_contracts = self.get_contracts_with_price_data_for_frequency(
            frequency=frequency
        )
        if contract_object in list_of_contracts:
            return True
        else:
            return False

    def contracts_with_merged_price_data_for_instrument_code(
        self, instrument_code: str
    ) -> listOfFuturesContracts:
        """
        Valid contracts

        :param instrument_code: str
        :return: list of contract_date
        """

        list_of_contracts_with_price_data = self.get_contracts_with_merged_price_data()
        list_of_contracts_for_instrument = (
            list_of_contracts_with_price_data.contracts_in_list_for_instrument_code(
                instrument_code
            )
        )

        return list_of_contracts_for_instrument

    def contracts_with_price_data_at_frequency_for_instrument_code(
        self, instrument_code: str, frequency: Frequency
    ) -> listOfFuturesContracts:
        """
        Valid contracts

        :param instrument_code: str
        :return: list of contract_date
        """

        list_of_contracts_with_price_data = (
            self.get_contracts_with_price_data_for_frequency(frequency=frequency)
        )
        list_of_contracts_for_instrument = (
            list_of_contracts_with_price_data.contracts_in_list_for_instrument_code(
                instrument_code
            )
        )

        return list_of_contracts_for_instrument

    def contract_dates_with_merged_price_data_for_instrument_code(
        self, instrument_code: str
    ) -> listOfContractDateStr:
        """

        :param instrument_code:
        :return: list of str
        """

        list_of_contracts_with_price_data = (
            self.contracts_with_merged_price_data_for_instrument_code(instrument_code)
        )

        list_of_contract_date_str = list_of_contracts_with_price_data.list_of_dates()

        return list_of_contract_date_str

    def contract_dates_with_price_data_at_frequency_for_instrument_code(
        self, instrument_code: str, frequency: Frequency
    ) -> listOfContractDateStr:
        """

        :param instrument_code:
        :return: list of str
        """

        list_of_contracts_with_price_data = (
            self.contracts_with_price_data_at_frequency_for_instrument_code(
                instrument_code=instrument_code, frequency=frequency
            )
        )

        list_of_contract_date_str = list_of_contracts_with_price_data.list_of_dates()

        return list_of_contract_date_str

    def get_merged_prices_for_instrument(
        self, instrument_code: str
    ) -> dictFuturesContractPrices:
        """
        Get all the prices for this code, returned as dict

        :param instrument_code: str
        :return: dictFuturesContractPrices
        """

        list_of_contracts = self.contracts_with_merged_price_data_for_instrument_code(
            instrument_code
        )
        dict_of_prices = dictFuturesContractPrices(
            [
                (
                    contract.date_str,
                    self.get_merged_prices_for_contract_object(contract),
                )
                for contract in list_of_contracts
            ]
        )

        return dict_of_prices

    def get_prices_at_frequency_for_instrument(
        self, instrument_code: str, frequency: Frequency
    ) -> dictFuturesContractPrices:
        """
        Get all the prices for this code, returned as dict

        :param instrument_code: str
        :return: dictFuturesContractPrices
        """

        list_of_contracts = (
            self.contracts_with_price_data_at_frequency_for_instrument_code(
                instrument_code=instrument_code, frequency=frequency
            )
        )
        dict_of_prices = dictFuturesContractPrices(
            [
                (
                    contract.date_str,
                    self.get_prices_at_frequency_for_contract_object(
                        contract, frequency=frequency
                    ),
                )
                for contract in list_of_contracts
            ]
        )

        return dict_of_prices

    def get_merged_prices_for_contract_object(
        self, contract_object: futuresContract, return_empty: bool = True
    ) -> futuresContractPrices:
        """
        get all prices without worrying about frequency

        :param contract_object:  futuresContract
        :return: data
        """

        if self.has_merged_price_data_for_contract(contract_object):
            prices = self._get_merged_prices_for_contract_object_no_checking(
                contract_object
            )
        else:
            if return_empty:
                return futuresContractPrices.create_empty()
            else:
                raise missingData

        return prices

    def get_prices_at_frequency_for_contract_object(
        self,
        contract_object: futuresContract,
        frequency: Frequency,
        return_empty: bool = True,
    ) -> futuresContractPrices:
        """
        get some prices at a given frequency

        :param contract_object:  futuresContract
        :param frequency: str; one of D, H, 5M, M, 10S, S
        :return: data
        """

        if self.has_price_data_for_contract_at_frequency(
            contract_object, frequency=frequency
        ):
            return self._get_prices_at_frequency_for_contract_object_no_checking(
                contract_object, frequency=frequency
            )
        else:
            if return_empty:
                return futuresContractPrices.create_empty()
            else:
                raise missingData

    def write_merged_prices_for_contract_object(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
        ignore_duplication=False,
    ):
        """
        Write some prices

        :param futures_contract_object:
        :param futures_price_data:
        :param ignore_duplication: bool, to stop us overwriting existing prices
        :return: None
        """
        not_ignoring_duplication = not ignore_duplication
        if not_ignoring_duplication:
            if self.has_merged_price_data_for_contract(futures_contract_object):
                self.log.warning(
                    "There is already existing data for %s"
                    % futures_contract_object.key,
                    **futures_contract_object.log_attributes(),
                    method="temp",
                )
                return None

        self._write_merged_prices_for_contract_object_no_checking(
            futures_contract_object, futures_price_data
        )

    def write_prices_at_frequency_for_contract_object(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
        frequency: Frequency,
        ignore_duplication=False,
    ):
        """
        Write some prices

        :param futures_contract_object:
        :param futures_price_data:
        :param ignore_duplication: bool, to stop us overwriting existing prices
        :return: None
        """
        not_ignoring_duplication = not ignore_duplication
        if not_ignoring_duplication:
            if self.has_price_data_for_contract_at_frequency(
                contract_object=futures_contract_object, frequency=frequency
            ):
                self.log.warning(
                    "There is already existing data for %s"
                    % futures_contract_object.key,
                    **futures_contract_object.log_attributes(),
                    method="temp",
                )
                return None

        self._write_prices_at_frequency_for_contract_object_no_checking(
            futures_contract_object=futures_contract_object,
            futures_price_data=futures_price_data,
            frequency=frequency,
        )

    def update_prices_at_frequency_for_contract(
        self,
        contract_object: futuresContract,
        new_futures_per_contract_prices: futuresContractPrices,
        frequency: Frequency,
        check_for_spike: bool = True,
        max_price_spike: float = VERY_BIG_NUMBER,
    ) -> int:
        log_attrs = {**contract_object.log_attributes(), "method": "temp"}

        if len(new_futures_per_contract_prices) == 0:
            self.log.debug("No new data", **log_attrs)
            return 0

        if frequency is MIXED_FREQ:
            old_prices = self.get_merged_prices_for_contract_object(contract_object)
        else:
            old_prices = self.get_prices_at_frequency_for_contract_object(
                contract_object, frequency=frequency
            )

        merged_prices = old_prices.add_rows_to_existing_data(
            new_futures_per_contract_prices,
            check_for_spike=check_for_spike,
            max_price_spike=max_price_spike,
        )

        if merged_prices is SPIKE_IN_DATA:
            self.log.debug(
                "Price has moved too much - will need to manually check - no price update done",
                **log_attrs,
            )
            return SPIKE_IN_DATA

        old_prices = old_prices[~old_prices.index.duplicated(keep="first")]
        rows_added = len(merged_prices) - len(old_prices)

        if rows_added < 0:
            self.log.critical("Can't remove prices something gone wrong!", **log_attrs)
            raise mergeError("Merged prices have fewer rows than old prices!")

        elif rows_added == 0:
            if len(old_prices) == 0:
                self.log.debug("No existing or additional data", **log_attrs)
                return 0
            else:
                self.log.debug(
                    "No additional data since %s " % str(old_prices.index[-1]),
                    **log_attrs,
                )
            return 0

        # We have guaranteed no duplication
        if frequency is MIXED_FREQ:
            self.write_merged_prices_for_contract_object(
                contract_object, merged_prices, ignore_duplication=True
            )
        else:
            self.write_prices_at_frequency_for_contract_object(
                contract_object,
                merged_prices,
                frequency=frequency,
                ignore_duplication=True,
            )

        self.log.debug("Added %d additional rows of data" % rows_added)

        return rows_added

    def delete_merged_prices_for_contract_object(
        self, futures_contract_object: futuresContract, areyousure=False
    ):
        """

        :param futures_contract_object:
        :return:
        """

        if not areyousure:
            raise Exception("You have to be sure to delete prices_for_contract_object!")

        if self.has_merged_price_data_for_contract(futures_contract_object):
            self._delete_merged_prices_for_contract_object_with_no_checks_be_careful(
                futures_contract_object
            )
        else:
            self.log.warning(
                "Tried to delete non existent contract",
                **futures_contract_object.log_attributes(),
                method="temp",
            )

    def delete_prices_at_frequency_for_contract_object(
        self,
        futures_contract_object: futuresContract,
        frequency: Frequency,
        areyousure=False,
    ):
        """

        :param futures_contract_object:
        :return:
        """

        if not areyousure:
            raise Exception("You have to be sure to delete prices_for_contract_object!")

        if self.has_price_data_for_contract_at_frequency(
            futures_contract_object, frequency=frequency
        ):
            self._delete_prices_at_frequency_for_contract_object_with_no_checks_be_careful(
                futures_contract_object=futures_contract_object, frequency=frequency
            )
        else:
            self.log.warning(
                "Tried to delete non existent contract at frequency %s" % frequency,
                **futures_contract_object.log_attributes(),
                method="temp",
            )

    def delete_merged_prices_for_instrument_code(
        self, instrument_code: str, areyousure=False
    ):
        # We don't pass areyousure, otherwise if we weren't sure would get
        # multiple exceptions
        if not areyousure:
            raise Exception(
                "You have to be sure to delete_merged_prices_for_instrument!"
            )

        all_contracts_to_delete = (
            self.contracts_with_merged_price_data_for_instrument_code(instrument_code)
        )
        for contract in all_contracts_to_delete:
            self.delete_merged_prices_for_contract_object(contract, areyousure=True)

    def delete_prices_at_frequency_for_instrument_code(
        self, instrument_code: str, frequency: Frequency, areyousure=False
    ):
        # We don't pass areyousure, otherwise if we weren't sure would get
        # multiple exceptions
        if not areyousure:
            raise Exception(
                "You have to be sure to delete_prices_at_frequency_for_instrument!"
            )

        all_contracts_to_delete = (
            self.contracts_with_price_data_at_frequency_for_instrument_code(
                instrument_code=instrument_code, frequency=frequency
            )
        )

        for contract in all_contracts_to_delete:
            self.delete_prices_at_frequency_for_contract_object(
                futures_contract_object=contract, frequency=frequency, areyousure=True
            )

    def get_contracts_with_merged_price_data(self) -> listOfFuturesContracts:
        raise NotImplementedError(BASE_CLASS_ERROR)

    def get_contracts_with_price_data_for_frequency(
        self, frequency: Frequency
    ) -> listOfFuturesContracts:
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _delete_merged_prices_for_contract_object_with_no_checks_be_careful(
        self, futures_contract_object: futuresContract
    ):
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _delete_prices_at_frequency_for_contract_object_with_no_checks_be_careful(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ):
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _write_merged_prices_for_contract_object_no_checking(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
    ):
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _write_prices_at_frequency_for_contract_object_no_checking(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
        frequency: Frequency,
    ):
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _get_merged_prices_for_contract_object_no_checking(
        self, contract_object: futuresContract
    ) -> futuresContractPrices:
        raise NotImplementedError(BASE_CLASS_ERROR)

    def _get_prices_at_frequency_for_contract_object_no_checking(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ) -> futuresContractPrices:
        raise NotImplementedError(BASE_CLASS_ERROR)
