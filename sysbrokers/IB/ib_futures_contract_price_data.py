from syscore.dateutils import Frequency, DAILY_PRICE_FREQ
from syscore.exceptions import missingContract, missingData
from sysdata.data_blob import dataBlob

from sysbrokers.IB.ib_futures_contracts_data import ibFuturesContractData
from sysbrokers.IB.ib_instruments_data import ibFuturesInstrumentData
from sysbrokers.IB.ib_translate_broker_order_objects import sign_from_BS, ibBrokerOrder
from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.client.ib_price_client import tickerWithBS, ibPriceClient
from sysbrokers.broker_futures_contract_price_data import brokerFuturesContractPriceData

from sysexecution.tick_data import tickerObject
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.trade_qty import tradeQuantity

from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.contracts import futuresContract, listOfFuturesContracts

from syslogging.logger import get_logger


class ibTickerObject(tickerObject):
    def __init__(self, ticker_with_BS: tickerWithBS, broker_client: ibPriceClient):
        ticker = ticker_with_BS.ticker
        BorS = ticker_with_BS.BorS

        # qty can just be +1 or -1 size of trade doesn't matter to ticker
        qty = sign_from_BS(BorS)
        super().__init__(ticker, qty=qty)
        self._broker_client = broker_client

    def refresh(self):
        self._broker_client.refresh()

    def bid(self):
        return self.ticker.bid

    def ask(self):
        return self.ticker.ask

    def bid_size(self):
        return self.ticker.bidSize

    def ask_size(self):
        return self.ticker.askSize


class ibFuturesContractPriceData(brokerFuturesContractPriceData):
    """
    Implementation of a data source for IB futures contract prices
    """

    def __init__(
        self,
        ibconnection: connectionIB,
        data: dataBlob,
        log=get_logger("ibFuturesContractPriceData"),
    ):
        super().__init__(log=log, data=data)
        self._ibconnection = ibconnection

    def __repr__(self):
        return "IB Futures per contract price data %s" % str(self.ib_client)

    @property
    def ibconnection(self) -> connectionIB:
        return self._ibconnection

    @property
    def ib_client(self) -> ibPriceClient:
        client = getattr(self, "_ib_client", None)
        if client is None:
            client = self._ib_client = ibPriceClient(
                ibconnection=self.ibconnection, log=self.log
            )

        return client

    @property
    def futures_contract_data(self) -> ibFuturesContractData:
        return self.data.broker_futures_contract

    @property
    def futures_instrument_data(self) -> ibFuturesInstrumentData:
        return self.data.broker_futures_instrument

    def has_merged_price_data_for_contract(
        self, futures_contract: futuresContract
    ) -> bool:
        """
        Does IB have data for a given contract?

        Overridden because we will have a problem matching expiry dates to nominal yyyymm dates
        :param contract_object:
        :return: bool
        """
        try:
            futures_contract_with_IB_data = (
                self.futures_contract_data.get_contract_object_with_IB_data(
                    futures_contract
                )
            )
        except missingContract:
            return False
        else:
            return True

    def get_list_of_instrument_codes_with_merged_price_data(self) -> list:
        # return list of instruments for which pricing is configured
        list_of_instruments = self.futures_instrument_data.get_list_of_instruments()

        return list_of_instruments

    def contracts_with_merged_price_data_for_instrument_code(
        self, instrument_code: str, allow_expired=True
    ) -> listOfFuturesContracts:
        futures_instrument_with_ib_data = (
            self.futures_instrument_data.get_futures_instrument_object_with_IB_data(
                instrument_code
            )
        )
        list_of_date_str = self.ib_client.broker_get_futures_contract_list(
            futures_instrument_with_ib_data, allow_expired=allow_expired
        )

        list_of_contracts = [
            futuresContract(instrument_code, date_str) for date_str in list_of_date_str
        ]

        list_of_contracts = listOfFuturesContracts(list_of_contracts)

        return list_of_contracts

    def get_contracts_with_merged_price_data(self):
        raise NotImplementedError("Do not use get_contracts_with_price_data with IB")

    def get_prices_at_frequency_for_potentially_expired_contract_object(
        self, contract: futuresContract, freq: Frequency = DAILY_PRICE_FREQ
    ) -> futuresContractPrices:
        price_data = self._get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
            contract, frequency=freq, allow_expired=True
        )
        return price_data

    def _get_merged_prices_for_contract_object_no_checking(
        self, contract_object: futuresContract
    ) -> futuresContractPrices:
        raise Exception("Have to get prices from IB with specific frequency")

    def get_prices_at_frequency_for_contract_object(
        self,
        contract_object: futuresContract,
        frequency: Frequency,
        return_empty: bool = True,
    ):
        ## Override this because don't want to check for existing data first

        try:
            prices = self._get_prices_at_frequency_for_contract_object_no_checking(
                futures_contract_object=contract_object, frequency=frequency
            )
        except missingData:
            if return_empty:
                return futuresContractPrices.create_empty()
            else:
                raise

        return prices

    def _get_prices_at_frequency_for_contract_object_no_checking(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ) -> futuresContractPrices:
        return self._get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
            futures_contract_object=futures_contract_object,
            frequency=frequency,
            allow_expired=False,
        )

    def _get_prices_at_frequency_for_contract_object_no_checking_with_expiry_flag(
        self,
        futures_contract_object: futuresContract,
        frequency: Frequency,
        allow_expired: bool = False,
    ) -> futuresContractPrices:
        """
        Get historical prices at a particular frequency

        We override this method, rather than _get_prices_at_frequency_for_contract_object_no_checking
        Because the list of dates returned by contracts_with_price_data is likely to not match (expiries)

        :param futures_contract_object:  futuresContract
        :param frequency: str; one of D, H, 15M, 5M, M, 10S, S
        :return: data
        """

        try:
            contract_object_with_ib_broker_config = (
                self.futures_contract_data.get_contract_object_with_IB_data(
                    futures_contract_object, allow_expired=allow_expired
                )
            )
        except missingContract:
            self.log.warning(
                "Can't get data for %s" % str(futures_contract_object),
                **futures_contract_object.log_attributes(),
                method="temp",
            )
            raise missingData

        price_data = self._get_prices_at_frequency_for_ibcontract_object_no_checking(
            contract_object_with_ib_broker_config,
            freq=frequency,
            allow_expired=allow_expired,
        )

        return price_data

    def _get_prices_at_frequency_for_ibcontract_object_no_checking(
        self,
        contract_object_with_ib_broker_config,
        freq: Frequency,
        allow_expired: bool = False,
    ) -> futuresContractPrices:
        log_attrs = {
            **contract_object_with_ib_broker_config.log_attributes(),
            "method": "temp",
        }

        try:
            price_data = self.ib_client.broker_get_historical_futures_data_for_contract(
                contract_object_with_ib_broker_config,
                bar_freq=freq,
                allow_expired=allow_expired,
            )
        except missingData:
            self.log.warning(
                "Something went wrong getting IB price data for %s"
                % str(contract_object_with_ib_broker_config),
                **log_attrs,
            )
            raise

        if len(price_data) == 0:
            self.log.warning(
                "No IB price data found for %s"
                % str(contract_object_with_ib_broker_config),
                **log_attrs,
            )
            return futuresContractPrices.create_empty()

        return futuresContractPrices(price_data)

    def get_ticker_object_for_order(self, order: contractOrder) -> tickerObject:
        futures_contract = order.futures_contract
        trade_list_for_multiple_legs = order.trade

        ticker = self.get_ticker_object_for_contract_and_trade_qty(
            futures_contract=futures_contract,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
        )

        return ticker

    def get_ticker_object_for_contract(
        self, futures_contract: futuresContract
    ) -> tickerObject:
        return self.get_ticker_object_for_contract_and_trade_qty(
            futures_contract=futures_contract
        )

    def get_ticker_object_for_contract_and_trade_qty(
        self,
        futures_contract: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ) -> tickerObject:
        try:
            contract_object_with_ib_data = (
                self.futures_contract_data.get_contract_object_with_IB_data(
                    futures_contract
                )
            )
        except missingContract as e:
            self.log.warning(
                "Can't get data for %s" % str(futures_contract),
                **futures_contract.log_attributes(),
                method="temp",
            )
            raise e

        ticker_with_bs = self.ib_client.get_ticker_object_with_BS(
            contract_object_with_ib_data,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
        )

        ticker_object = ibTickerObject(ticker_with_bs, self.ib_client)

        return ticker_object

    def cancel_market_data_for_contract(self, contract: futuresContract):
        try:
            contract_object_with_ib_data = (
                self.futures_contract_data.get_contract_object_with_IB_data(contract)
            )
        except missingContract:
            self.log.warning(
                "Can't get data for %s" % str(contract),
                **contract.log_attributes(),
                method="temp",
            )
            return futuresContractPrices.create_empty()

        self.ib_client.cancel_market_data_for_contract(contract_object_with_ib_data)

    def cancel_market_data_for_order(self, order: ibBrokerOrder):
        contract_object = order.futures_contract
        trade_list_for_multiple_legs = order.trade

        try:
            contract_object_with_ib_data = (
                self.futures_contract_data.get_contract_object_with_IB_data(
                    contract_object
                )
            )
        except missingContract:
            self.log.warning(
                "Can't get data for %s" % str(contract_object),
                **order.log_attributes(),
                method="temp",
            )
            return futuresContractPrices.create_empty()

        self.ib_client.cancel_market_data_for_contract_and_trade_qty(
            contract_object_with_ib_data,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
        )
