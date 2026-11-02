from syscore.exceptions import ContractNotFound
from sysdata.base_data import baseData
from sysobjects.contracts import futuresContract, listOfFuturesContracts
from sysobjects.contract_dates_and_expiries import listOfContractDateStr

USE_CHILD_CLASS_ERROR = "You need to use a child class of futuresContractData"

from syslogging import CONTRACT_DATE_LOG_LABEL, INSTRUMENT_CODE_LOG_LABEL
from syslogging.logger import get_logger


class futuresContractData(baseData):
    """
    Read and write data class to get futures contract data

    We'd inherit from this class for a specific implementation

    We store instrument code, and contract date data (date, expiry, roll cycle)

    If you want more information about a given instrument you have to read it in using futuresInstrumentData
    """

    def __init__(self, log=get_logger("futuresInstrumentData")):
        super().__init__(log=log)

    def __repr__(self):
        return "Individual futures contract data - DO NOT USE"

    def __getitem__(self, key_tuple: tuple):
        (instrument_code, contract_date) = key_tuple
        return self.get_contract_object(instrument_code, contract_date)

    def get_contract_object(
        self, instrument_code: str, contract_id: str
    ) -> futuresContract:
        if self.is_contract_in_data(instrument_code, contract_id):
            return self._get_contract_data_without_checking(
                instrument_code, contract_id
            )
        else:
            raise ContractNotFound(
                "Contract %s/%s not found" % (instrument_code, contract_id)
            )

    def delete_contract_data(
        self, instrument_code: str, contract_date: str, are_you_sure=False
    ):
        log_attrs = {
            INSTRUMENT_CODE_LOG_LABEL: instrument_code,
            CONTRACT_DATE_LOG_LABEL: contract_date,
            "method": "temp",
        }
        if are_you_sure:
            if self.is_contract_in_data(instrument_code, contract_date):
                self._delete_contract_data_without_any_warning_be_careful(
                    instrument_code, contract_date
                )
                self.log.info(
                    "Deleted contract %s/%s" % (instrument_code, contract_date),
                    **log_attrs,
                )
            else:
                # doesn't exist anyway
                self.log.warning("Tried to delete non existent contract", **log_attrs)
        else:
            self.log.error(
                "You need to call delete_contract_data with a flag to be sure",
                **log_attrs,
            )

    def delete_all_contracts_for_instrument(
        self, instrument_code: str, areyoureallysure=False
    ):
        if not areyoureallysure:
            raise Exception(
                "You have to be sure to delete all contracts for an instrument!"
            )

        list_of_dates = self.get_list_of_contract_dates_for_instrument_code(
            instrument_code
        )
        for contract_date in list_of_dates:
            self.delete_contract_data(instrument_code, contract_date, are_you_sure=True)

    def add_contract_data(
        self, contract_object: futuresContract, ignore_duplication: bool = False
    ):
        instrument_code = contract_object.instrument_code
        contract_date = contract_object.date_str

        log_attrs = {**contract_object.log_attributes(), "method": "temp"}

        if self.is_contract_in_data(instrument_code, contract_date):
            if ignore_duplication:
                pass
            else:
                self.log.warning(
                    "There is already %s in the data, you have to delete it first"
                    % (contract_object.key),
                    **log_attrs,
                )
                return None

        self._add_contract_object_without_checking_for_existing_entry(contract_object)
        self.log.info(
            "Added contract %s %s" % (instrument_code, contract_date), **log_attrs
        )

    def get_list_of_contract_dates_for_instrument_code(
        self, instrument_code: str, allow_expired: bool = False
    ) -> listOfContractDateStr:
        raise NotImplementedError

    def get_all_contract_objects_for_instrument_code(
        self, instrument_code: str
    ) -> listOfFuturesContracts:
        raise NotImplementedError

    def _get_contract_data_without_checking(
        self, instrument_code: str, contract_date: str
    ) -> futuresContract:
        raise NotImplementedError

    def _delete_contract_data_without_any_warning_be_careful(
        self, instrument_code: str, contract_date: str
    ):
        raise NotImplementedError

    def get_list_of_all_instruments_with_contracts(self) -> list:
        raise NotImplementedError

    def is_contract_in_data(self, instrument_code: str, contract_date_str: str) -> bool:
        raise NotImplementedError

    def _add_contract_object_without_checking_for_existing_entry(
        self, contract_object: futuresContract
    ):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)
