from dataclasses import dataclass
import pandas as pd

from sysdata.fx.spotfx import fxPricesData
from sysobjects.spot_fx_prices import fxPrices
from syscore.fileutils import (
    resolve_path_and_filename_for_package,
    files_with_extension_in_pathname,
)
from syscore.constants import arg_not_supplied
from syscore.pandas.pdutils import pd_readcsv, DEFAULT_DATE_FORMAT_FOR_CSV
from syslogging import CURRENCY_CODE_LOG_LABEL
from syslogging.logger import get_logger

FX_PRICES_DIRECTORY = "data.futures.fx_prices_csv"


@dataclass
class ConfigCsvFXPrices:
    """
        :param price_column: Column where spot FX prices are
    :param date_column: Column where dates are
    :param date_format: Format for dates https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior

    """

    date_column: str = "DATETIME"
    date_format: str = DEFAULT_DATE_FORMAT_FOR_CSV
    price_column: str = "PRICE"


class csvFxPricesData(fxPricesData):
    """

    Class for fx prices write / to from csv
    """

    def __init__(
        self,
        datapath=arg_not_supplied,
        log=get_logger("csvFxPricesData"),
        config: ConfigCsvFXPrices = arg_not_supplied,
    ):
        """
        Get FX data from a .csv file

        :param datapath: Path where csv files are located
        :param log: logging object
        """

        super().__init__(log=log)

        if datapath is arg_not_supplied:
            datapath = FX_PRICES_DIRECTORY

        if config is arg_not_supplied:
            config = ConfigCsvFXPrices()

        self._datapath = datapath
        self._config = config

    def __repr__(self):
        return "csvFxPricesData accessing %s" % self._datapath

    @property
    def datapath(self):
        return self._datapath

    @property
    def config(self):
        return self._config

    def get_list_of_fxcodes(self) -> list:
        return files_with_extension_in_pathname(self._datapath, ".csv")

    def _get_fx_prices_without_checking(self, code: str) -> fxPrices:
        filename = self._filename_given_fx_code(code)
        config = self.config
        price_column = config.price_column
        date_column = config.date_column
        date_format = config.date_format

        try:
            fx_data = pd_readcsv(
                filename, date_format=date_format, date_index_name=date_column
            )
        except OSError:
            self.log.warning(
                "Can't find currency price file %s" % filename,
                **{CURRENCY_CODE_LOG_LABEL: code},
            )
            return fxPrices.create_empty()

        fx_data = pd.Series(fx_data[price_column])

        fx_data = fxPrices(fx_data.sort_index())

        return fx_data

    def _delete_fx_prices_without_any_warning_be_careful(self, code: str):
        raise NotImplementedError(
            "You can't delete adjusted prices stored as a csv - Add to overwrite existing or delete file manually"
        )

    def _add_fx_prices_without_checking_for_existing_entry(
        self, code: str, fx_price_data: fxPrices
    ):
        filename = self._filename_given_fx_code(code)
        config = self.config
        price_column = config.price_column
        date_column = config.date_column
        date_format = config.date_format

        fx_price_data.name = price_column
        fx_price_data.to_csv(
            filename, index_label=date_column, date_format=date_format, header=True
        )

        self.log.debug(
            "Wrote currency prices to %s for %s" % (filename, code),
            **{CURRENCY_CODE_LOG_LABEL: code},
        )

    def _filename_given_fx_code(self, code: str):
        return resolve_path_and_filename_for_package(self._datapath, "%s.csv" % (code))
