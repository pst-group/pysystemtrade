import pandas as pd
from sysdata.production.historic_contract_positions import contractPositionData
from sysobjects.contracts import futuresContract
from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

DATE_INDEX_NAME = "DATETIME"


class csvContractPositionData(contractPositionData):
    """

    Class for contract_positions write to / read from csv
    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvContractPositionData")
    ):
        super().__init__(log=log)

        if datapath is None:
            raise Exception("Need to provide datapath")

        self._datapath = datapath

    def __repr__(self):
        return "csvContractPositionData accessing %s" % self._datapath

    def _write_updated_position_series_for_contract_object(
        self, contract_object: futuresContract, updated_series: pd.Series
    ):
        position_df = pd.DataFrame(updated_series)
        filename = self._filename_given_contract(contract_object)
        position_df.to_csv(filename, index_label=DATE_INDEX_NAME)

    def _filename_given_contract(self, contract: futuresContract):
        return resolve_path_and_filename_for_package(
            self._datapath, "%s_%s.csv" % (contract.instrument_code, contract.date_str)
        )
