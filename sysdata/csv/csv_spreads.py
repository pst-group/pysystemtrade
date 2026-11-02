import pandas as pd

from sysdata.futures.spreads import spreadsForInstrumentData

from sysobjects.spreads import spreadsForInstrument
from syscore.fileutils import (
    resolve_path_and_filename_for_package,
    files_with_extension_in_pathname,
)
from syscore.pandas.pdutils import pd_readcsv
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

DATE_INDEX_NAME = "DATETIME"
SPREAD_COLUMN_NAME = "spread"


class csvSpreadsForInstrumentData(spreadsForInstrumentData):
    """

    Class for spreads write / to from csv
    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvSpreadsForInstrumentData")
    ):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            raise Exception("Need to provide datapath")

        self._datapath = datapath

    def __repr__(self):
        return "csvSpreadsForInstrumentData accessing %s" % self._datapath

    @property
    def datapath(self):
        return self._datapath

    def get_list_of_instruments(self) -> list:
        return files_with_extension_in_pathname(self.datapath, ".csv")

    def _get_spreads_without_checking(
        self, instrument_code: str
    ) -> spreadsForInstrument:
        filename = self._filename_given_instrument_code(instrument_code)

        try:
            spreads_from_pd = pd_readcsv(filename, date_index_name=DATE_INDEX_NAME)
        except OSError:
            self.log.warning("Can't find spread file %s" % filename)
            return spreadsForInstrument()

        spreads_as_series = pd.Series(spreads_from_pd[SPREAD_COLUMN_NAME])
        spreads = spreadsForInstrument(spreads_as_series)

        return spreads

    def _delete_spreads_without_any_warning_be_careful(self, instrument_code: str):
        raise NotImplementedError(
            "You can't delete data stored as a csv - Add to overwrite existing or delete file manually"
        )

    def _add_spreads_without_checking_for_existing_entry(
        self, instrument_code: str, spreads: spreadsForInstrument
    ):
        # Ensures the file will be written with a column header
        spreads_as_dataframe = pd.DataFrame(spreads)
        spreads_as_dataframe.columns = [SPREAD_COLUMN_NAME]

        filename = self._filename_given_instrument_code(instrument_code)
        spreads.to_csv(filename, index_label=DATE_INDEX_NAME)

    def _filename_given_instrument_code(self, instrument_code: str):
        return resolve_path_and_filename_for_package(
            self.datapath, "%s.csv" % (instrument_code)
        )
