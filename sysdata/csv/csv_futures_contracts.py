from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from sysdata.futures.contracts import futuresContractData, listOfFuturesContracts
from syslogging.logger import get_logger
import pandas as pd


class csvFuturesContractData(futuresContractData):
    """
    Only used for backup purposes at the moment

    Therefore, there is no 'read' or other methods as yet

    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvFuturesContractData")
    ):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            raise Exception("Need to pass datapath")

        self._datapath = datapath

    def __repr__(self):
        return "Instruments data from %s" % self.datapath

    @property
    def datapath(self):
        return self._datapath

    def _filename_for_instrument_code(self, instrument_code: str):
        return resolve_path_and_filename_for_package(
            self.datapath, "%s.csv" % instrument_code
        )

    def write_contract_list_as_df(
        self, instrument_code: str, contract_list: listOfFuturesContracts
    ):
        list_of_expiry = [x.expiry_date.as_str() for x in contract_list]
        list_of_contract_date = [x.date_str for x in contract_list]
        list_of_sampling = [x.currently_sampling for x in contract_list]

        df = pd.DataFrame(
            dict(
                date=list_of_contract_date,
                sampling=list_of_sampling,
                expiry=list_of_expiry,
            )
        )
        filename = self._filename_for_instrument_code(instrument_code)
        df.to_csv(filename)

    def get_list_of_contract_dates_for_instrument_code(self, instrument_code):
        raise NotImplementedError

    def get_all_contract_objects_for_instrument_code(self, instrument_code):
        raise NotImplementedError("used for backup only no read methods")

    def _delete_contract_data_without_any_warning_be_careful(
        self, instrument_code, contract_date
    ):
        raise NotImplementedError(".csv are read only")

    def is_contract_in_data(self, instrument_code, contract_date):
        raise NotImplementedError("used for backup only no read methods")

    def _add_contract_object_without_checking_for_existing_entry(self, contract_object):
        raise NotImplementedError(
            ".csv can only write contract list en bloc use write_contract_list_as_df"
        )

    def _get_contract_data_without_checking(
        self, instrument_code: str, contract_date: str
    ):
        raise NotImplementedError("used for backup only no read methods")
