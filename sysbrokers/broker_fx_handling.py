from syscore.constants import arg_not_supplied
from sysdata.base_data import baseData
from sysdata.data_blob import dataBlob
from sysbrokers.broker_trade import brokerTrade

from syslogging.logger import get_logger


### generic base class for FX handling
class brokerFxHandlingData(baseData):
    def __init__(self, data: dataBlob, log=get_logger("brokerFXHandlingData")):
        super().__init__(log=log)
        self._data = data

    def broker_fx_balances(self, account_id: str = arg_not_supplied) -> dict:
        raise NotImplementedError

    def broker_fx_market_order(
        self,
        trade: float,
        ccy1: str,
        account_id: str = arg_not_supplied,
        ccy2: str = "USD",
    ) -> brokerTrade:
        raise NotImplementedError

    @property
    def data(self) -> dataBlob:
        return self._data
