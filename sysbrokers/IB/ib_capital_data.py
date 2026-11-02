from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.client.ib_accounting_client import ibAccountingClient
from sysbrokers.broker_capital_data import brokerCapitalData
from sysdata.data_blob import dataBlob
from syscore.constants import arg_not_supplied

from sysobjects.spot_fx_prices import listOfCurrencyValues

from syslogging.logger import get_logger


class ibCapitalData(brokerCapitalData):
    def __init__(
        self,
        ibconnection: connectionIB,
        data: dataBlob,
        log=get_logger("ibCapitalData"),
    ):
        super().__init__(log=log, data=data)
        self._ibconnection = ibconnection

    @property
    def ibconnection(self) -> connectionIB:
        return self._ibconnection

    @property
    def ib_client(self) -> ibAccountingClient:
        client = getattr(self, "_ib_client", None)
        if client is None:
            client = self._ib_client = ibAccountingClient(
                ibconnection=self.ibconnection, log=self.log
            )

        return client

    def __repr__(self):
        return "IB capital data"

    def get_account_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        return self.ib_client.broker_get_account_value_across_currency(
            account_id=account_id
        )

    def get_excess_liquidity_value_across_currency(
        self, account_id: str = arg_not_supplied
    ) -> listOfCurrencyValues:
        return self.ib_client.broker_get_excess_liquidity_value_across_currency(
            account_id=account_id
        )

    """
    Can add other functions not in parent class to get IB specific stuff which could be required for
      strategy decomposition
    """
