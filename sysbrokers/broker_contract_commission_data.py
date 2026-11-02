from sysdata.futures.contracts import futuresContractData
from sysdata.data_blob import dataBlob
from sysobjects.contracts import futuresContract

from syslogging.logger import get_logger
from sysobjects.spot_fx_prices import currencyValue


class brokerFuturesContractCommissionData(futuresContractData):
    def __init__(
        self, data: dataBlob, log=get_logger("brokerFuturesContractCommissionData")
    ):
        super().__init__(log=log)
        self._data = data

    def get_commission_for_contract(self, contract: futuresContract) -> currencyValue:
        raise NotImplementedError

    @property
    def data(self):
        return self._data
