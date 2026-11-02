from sysobjects.spot_fx_prices import listOfCurrencyValues

from syscore.constants import arg_not_supplied

from sysdata.production.capital import capitalData
from syslogging.logger import get_logger
from sysdata.data_blob import dataBlob


class brokerCapitalData(capitalData):
    def __init__(self, data: dataBlob, log=get_logger("brokerCapitalData")):
        super().__init__(log=log)
        self._data = data

    def get_account_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        raise NotImplementedError

    def get_excess_liquidity_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        raise NotImplementedError

    @property
    def data(self) -> dataBlob:
        return self._data
