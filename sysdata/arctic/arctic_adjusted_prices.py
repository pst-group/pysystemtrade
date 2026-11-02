from sysdata.futures.adjusted_prices import (
    futuresAdjustedPricesData,
)
from sysobjects.adjusted_prices import futuresAdjustedPrices
from sysdata.arctic.arctic_connection import arcticData
from syslogging.logger import get_logger
import pandas as pd

ADJPRICE_COLLECTION = "futures_adjusted_prices"


class arcticFuturesAdjustedPricesData(futuresAdjustedPricesData):
    """
    Class to read / write multiple futures price data to and from arctic
    """

    def __init__(self, mongo_db=None, log=get_logger("arcticFuturesAdjustedPrices")):
        super().__init__(log=log)

        self._arctic = arcticData(ADJPRICE_COLLECTION, mongo_db=mongo_db)

    def __repr__(self):
        return repr(self._arctic)

    @property
    def arctic(self):
        return self._arctic

    def get_list_of_instruments(self) -> list:
        return self.arctic.get_keynames()

    def _get_adjusted_prices_without_checking(
        self, instrument_code: str
    ) -> futuresAdjustedPrices:
        data = self.arctic.read(instrument_code)

        instrpricedata = futuresAdjustedPrices(data[data.columns[0]])

        return instrpricedata

    def _delete_adjusted_prices_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        self.arctic.delete(instrument_code)
        self.log.debug(
            "Deleted adjusted prices for %s from %s" % (instrument_code, str(self)),
            instrument_code=instrument_code,
        )

    def _add_adjusted_prices_without_checking_for_existing_entry(
        self, instrument_code: str, adjusted_price_data: futuresAdjustedPrices
    ):
        adjusted_price_data_aspd = pd.DataFrame(adjusted_price_data)
        adjusted_price_data_aspd.columns = ["price"]
        adjusted_price_data_aspd = adjusted_price_data_aspd.astype(float)
        self.arctic.write(instrument_code, adjusted_price_data_aspd)
        self.log.debug(
            "Wrote %s lines of prices for %s to %s"
            % (len(adjusted_price_data), instrument_code, str(self)),
            instrument_code=instrument_code,
        )
