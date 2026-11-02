CONTRACT_COLLECTION = "futures_contracts"

from syscore.constants import arg_not_supplied
from sysdata.futures.contracts import futuresContractData
from sysobjects.contracts import (
    contract_key_from_code_and_id,
    futuresContract,
    get_code_and_id_from_contract_key,
    key_contains_instrument_code,
    listOfFuturesContracts,
)
from syslogging.logger import get_logger
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey


class mongoFuturesContractData(futuresContractData):
    """
    Read and write data class to get futures contract data

    We store instrument code, and contract date data (date, expiry, roll cycle)

    """

    def __init__(
        self, mongo_db=arg_not_supplied, log=get_logger("mongoFuturesContractData")
    ):
        super().__init__(log=log)
        mongo_data = mongoDataWithSingleKey(
            CONTRACT_COLLECTION, "contract_key", mongo_db=mongo_db
        )
        self._mongo_data = mongo_data

    def __repr__(self):
        return "mongoFuturesContractData %s" % str(self.mongo_data)

    @property
    def mongo_data(self):
        return self._mongo_data

    def is_contract_in_data(self, instrument_code: str, contract_date_str: str) -> bool:
        key = contract_key_from_code_and_id(instrument_code, contract_date_str)
        return self.mongo_data.key_is_in_data(key)

    def _get_list_of_all_contract_keys(self) -> list:
        return self.mongo_data.get_list_of_keys()

    def get_list_of_all_instruments_with_contracts(self) -> list:
        list_of_keys = self._get_list_of_all_contract_keys()
        list_of_split_keys = [
            get_code_and_id_from_contract_key(key) for key in list_of_keys
        ]
        list_of_instruments = [
            instrument_code for instrument_code, _ in list_of_split_keys
        ]
        unique_list_of_instruments = list(set(list_of_instruments))

        return unique_list_of_instruments

    def get_all_contract_objects_for_instrument_code(
        self, instrument_code: str
    ) -> listOfFuturesContracts:
        list_of_keys = self._get_all_contract_keys_for_instrument_code(instrument_code)
        list_of_objects = [
            self._get_contract_data_from_key_without_checking(key)
            for key in list_of_keys
        ]
        list_of_futures_contracts = listOfFuturesContracts(list_of_objects)

        return list_of_futures_contracts

    def _get_all_contract_keys_for_instrument_code(self, instrument_code: str) -> list:
        list_of_all_contract_keys = self._get_list_of_all_contract_keys()
        list_of_relevant_keys = [
            contract_key
            for contract_key in list_of_all_contract_keys
            if key_contains_instrument_code(contract_key, instrument_code)
        ]

        return list_of_relevant_keys

    def get_list_of_contract_dates_for_instrument_code(
        self, instrument_code: str
    ) -> list:
        list_of_keys = self._get_all_contract_keys_for_instrument_code(instrument_code)
        list_of_split_keys = [
            get_code_and_id_from_contract_key(key) for key in list_of_keys
        ]
        list_of_contract_id = [contract_id for _, contract_id in list_of_split_keys]

        return list_of_contract_id

    def _get_contract_data_without_checking(
        self, instrument_code: str, contract_id: str
    ) -> futuresContract:
        key = contract_key_from_code_and_id(instrument_code, contract_id)
        contract_object = self._get_contract_data_from_key_without_checking(key)

        return contract_object

    def _get_contract_data_from_key_without_checking(self, key: str) -> futuresContract:
        result_dict = self.mongo_data.get_result_dict_for_key_without_key_value(key)

        contract_object = futuresContract.create_from_dict(result_dict)

        return contract_object

    def _delete_contract_data_without_any_warning_be_careful(
        self, instrument_code: str, contract_date: str
    ):
        key = contract_key_from_code_and_id(instrument_code, contract_date)
        self.mongo_data.delete_data_without_any_warning(key)

    def _add_contract_object_without_checking_for_existing_entry(
        self, contract_object: futuresContract
    ):
        contract_object_as_dict = contract_object.as_dict()
        key = contract_object.key
        self.mongo_data.add_data(key, contract_object_as_dict, allow_overwrite=True)
