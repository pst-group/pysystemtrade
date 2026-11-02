from sysdata.data_blob import dataBlob
from sysdata.fx.spotfx import fxPricesData
from sysobjects.spot_fx_prices import fxPrices
from syslogging.logger import get_logger


class brokerFxPricesData(fxPricesData):
    def __init__(self, data: dataBlob, log=get_logger("brokerFxPricesData")):
        super().__init__(log=log)
        self._data = data

    def get_list_of_fxcodes(self) -> list:
        raise NotImplementedError

    def _get_fx_prices_without_checking(self, currency_code: str) -> fxPrices:
        raise NotImplementedError

    def update_fx_prices(self, *args, **kwargs):
        raise NotImplementedError("Broker is a read only source of prices")

    def add_fx_prices(self, *args, **kwargs):
        raise NotImplementedError("Broker is a read only source of prices")

    def _delete_fx_prices_without_any_warning_be_careful(self, *args, **kwargs):
        raise NotImplementedError("Broker is a read only source of prices")

    def _add_fx_prices_without_checking_for_existing_entry(self, *args, **kwargs):
        raise NotImplementedError("Broker is a read only source of prices")

    @property
    def data(self) -> dataBlob:
        return self._data
