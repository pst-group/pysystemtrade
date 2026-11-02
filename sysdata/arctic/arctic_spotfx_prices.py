from sysdata.fx.spotfx import fxPricesData
from sysobjects.spot_fx_prices import fxPrices
from sysdata.arctic.arctic_connection import arcticData
from syslogging import CURRENCY_CODE_LOG_LABEL
from syslogging.logger import get_logger
import pandas as pd

SPOTFX_COLLECTION = "spotfx_prices"


class arcticFxPricesData(fxPricesData):
    """
    Class to read / write fx prices
    """

    def __init__(self, mongo_db=None, log=get_logger("arcticFxPricesData")):
        super().__init__(log=log)
        self._arctic = arcticData(SPOTFX_COLLECTION, mongo_db=mongo_db)

    @property
    def arctic(self):
        return self._arctic

    def __repr__(self):
        return repr(self._arctic)

    def get_list_of_fxcodes(self) -> list:
        return self.arctic.get_keynames()

    def _get_fx_prices_without_checking(self, currency_code: str) -> fxPrices:
        fx_data = self.arctic.read(currency_code)

        fx_prices = fxPrices(fx_data[fx_data.columns[0]])

        return fx_prices

    def _delete_fx_prices_without_any_warning_be_careful(self, currency_code: str):
        self.arctic.delete(currency_code)
        self.log.debug(
            "Deleted fX prices for %s from %s" % (currency_code, str(self)),
            **{CURRENCY_CODE_LOG_LABEL: currency_code, "method": "temp"},
        )

    def _add_fx_prices_without_checking_for_existing_entry(
        self, currency_code: str, fx_price_data: fxPrices
    ):
        fx_price_data_aspd = pd.DataFrame(fx_price_data)
        fx_price_data_aspd.columns = ["price"]
        fx_price_data_aspd = fx_price_data_aspd.astype(float)

        self.arctic.write(currency_code, fx_price_data_aspd)
        self.log.debug(
            "Wrote %s lines of prices for %s to %s"
            % (len(fx_price_data), currency_code, str(self)),
            **{CURRENCY_CODE_LOG_LABEL: currency_code, "method": "temp"},
        )
