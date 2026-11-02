import pandas as pd
from sysdata.futures.multiple_prices import futuresMultiplePricesData
from sysobjects.multiple_prices import (
    futuresMultiplePrices,
    list_of_contract_column_names,
)

from syscore.fileutils import (
    resolve_path_and_filename_for_package,
    files_with_extension_in_pathname,
)
from syscore.pandas.pdutils import pd_readcsv
from syscore.genutils import str_of_int
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

CSV_MULTIPLE_PRICE_DIRECTORY = "data.futures.multiple_prices_csv"
DATE_INDEX_NAME = "DATETIME"


class csvFuturesMultiplePricesData(futuresMultiplePricesData):
    """

    Class for roll calendars write / to from csv
    """

    def __init__(
        self,
        datapath: str = arg_not_supplied,
        log=get_logger("csvFuturesMultiplePricesData"),
    ):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            datapath = CSV_MULTIPLE_PRICE_DIRECTORY

        self._datapath = datapath

    def __repr__(self):
        return "csvFuturesMultiplePricesData accessing %s" % self.datapath

    @property
    def datapath(self):
        return self._datapath

    def get_list_of_instruments(self):
        return files_with_extension_in_pathname(self.datapath, ".csv")

    def _get_multiple_prices_without_checking(
        self, instrument_code: str
    ) -> futuresMultiplePrices:
        instr_all_price_data = self._read_instrument_prices(instrument_code)
        for contract_col_name in list_of_contract_column_names:
            instr_all_price_data[contract_col_name] = instr_all_price_data[
                contract_col_name
            ].apply(str_of_int)

        return futuresMultiplePrices(instr_all_price_data)

    def _delete_multiple_prices_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError(
            "You can't delete multiple prices stored as a csv - Add to overwrite existing or delete file manually"
        )

    def _add_multiple_prices_without_checking_for_existing_entry(
        self, instrument_code: str, multiple_price_data: futuresMultiplePrices
    ):
        filename = self._filename_given_instrument_code(instrument_code)
        multiple_price_data.to_csv(filename, index_label=DATE_INDEX_NAME)

        self.log.debug(
            "Written multiple prices for %s to %s" % (instrument_code, filename),
            instrument_code=instrument_code,
        )

    def _read_instrument_prices(self, instrument_code: str) -> pd.DataFrame:
        filename = self._filename_given_instrument_code(instrument_code)

        try:
            instr_all_price_data = pd_readcsv(filename, date_index_name=DATE_INDEX_NAME)
        except OSError:
            self.log.warning(
                "Can't find multiple price file %s or error reading" % filename,
                instrument_code=instrument_code,
            )
            return futuresMultiplePrices.create_empty()

        return instr_all_price_data

    def _filename_given_instrument_code(self, instrument_code: str):
        filename = resolve_path_and_filename_for_package(
            self.datapath, "%s.csv" % (instrument_code)
        )

        return filename
