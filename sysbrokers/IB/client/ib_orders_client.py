from ib_async import TagValue
from ib_async.order import (
    MarketOrder as ibMarketOrder,
    LimitOrder as ibLimitOrder,
    Trade as ibTrade,
    Order as ibOrder,
    StopOrder as ibStopOrder,
)

from syscore.exceptions import missingContract
from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order
from sysbrokers.IB.client.ib_contracts_client import ibContractsClient
from sysbrokers.IB.ib_translate_broker_order_objects import (
    tradeWithContract,
    listOfTradesWithContracts,
)
from sysbrokers.IB.ib_positions import (
    resolveBS_for_list,
)
from sysbrokers.IB.ib_contracts import ibcontractWithLegs
from sysexecution.trade_qty import tradeQuantity
from sysexecution.orders.broker_orders import (
    brokerOrderType,
    market_order_type,
    limit_order_type,
    snap_mkt_type,
    snap_mid_type,
    snap_prim_type,
    adaptive_mkt_type,
    stop_loss_order_type,
)

from sysobjects.contracts import futuresContract

# we don't include ibClient since we get that through contracts client


class ibOrdersClient(ibContractsClient):
    def broker_get_orders(
        self, account_id: str = arg_not_supplied
    ) -> listOfTradesWithContracts:
        """
        Get all active trades, orders and return them with the information needed

        :return: list
        """
        self.refresh()

        ## Seems to make it more likely we get open orders back
        self.ib.reqAllOpenOrders()
        trades_in_broker_format = self.ib.trades()
        if account_id is not arg_not_supplied:
            trades_in_broker_format_this_account = [
                trade
                for trade in trades_in_broker_format
                if trade.order.account == account_id
            ]
        else:
            trades_in_broker_format_this_account = trades_in_broker_format

        trades_in_broker_format_with_legs = [
            self.add_contract_legs_to_order(raw_order_from_ib)
            for raw_order_from_ib in trades_in_broker_format_this_account
        ]

        trade_list = listOfTradesWithContracts(trades_in_broker_format_with_legs)

        return trade_list

    def add_contract_legs_to_order(
        self, raw_order_from_ib: ibTrade
    ) -> tradeWithContract:
        combo_legs = getattr(raw_order_from_ib.contract, "comboLegs", [])
        legs_data = []
        for leg in combo_legs:
            contract_for_leg = self.ib_get_contract_with_conId(
                raw_order_from_ib.contract.symbol, leg.conId
            )
            legs_data.append(contract_for_leg)

        ibcontract_with_legs = ibcontractWithLegs(
            raw_order_from_ib.contract, legs=legs_data
        )
        trade_with_contract = tradeWithContract(ibcontract_with_legs, raw_order_from_ib)

        return trade_with_contract

    def broker_submit_order(
        self,
        futures_contract_with_ib_data: futuresContract,
        trade_list: tradeQuantity,
        account_id: str = arg_not_supplied,
        order_type: brokerOrderType = market_order_type,
        limit_price: float = None,
        what_if: bool = False,
    ) -> tradeWithContract:
        """

        :param ibcontract: contract_object_with_ib_data: contract where instrument has ib metadata
        :param trade: int
        :param account: str
        :param order_type: str, market or limit
        :param limit_price: None or float

        :return: brokers trade object

        """

        try:
            ibcontract_with_legs = self.ib_futures_contract_with_legs(
                futures_contract_with_ib_data=futures_contract_with_ib_data,
                trade_list_for_multiple_legs=trade_list,
            )
        except missingContract:
            return missing_order

        ibcontract = ibcontract_with_legs.ibcontract

        ib_order = self._build_ib_order(
            trade_list=trade_list,
            account_id=account_id,
            order_type=order_type,
            limit_price=limit_price,
        )
        if ib_order is missing_order:
            return missing_order

        if what_if:
            order_object = self.ib.whatIfOrder(ibcontract, ib_order)
        else:
            order_object = self.ib.placeOrder(ibcontract, ib_order)

        trade_with_contract = tradeWithContract(ibcontract_with_legs, order_object)

        return trade_with_contract

    def _build_ib_order(
        self,
        trade_list: tradeQuantity,
        account_id: str = "",
        order_type: brokerOrderType = market_order_type,
        limit_price: float = None,
    ) -> ibOrder:
        ib_BS_str, ib_qty = resolveBS_for_list(trade_list)

        if order_type == market_order_type:
            ib_order = ibMarketOrder(ib_BS_str, ib_qty)
        elif order_type == limit_order_type:
            if limit_price is None:
                self.log.critical("Need to have limit price with limit order!")
                return missing_order
            else:
                ib_order = ibLimitOrder(ib_BS_str, ib_qty, limit_price)
        elif order_type == stop_loss_order_type:
            if limit_price is None:
                self.log.critical("Need to have limit price with limit order!")
                return missing_order
            else:
                ib_order = ibStopOrder(ib_BS_str, ib_qty, limit_price)

        elif order_type == snap_mkt_type:
            ## auxPrice is the offset so this will submit an order buy at the best offer, etc
            ## Works like a market order but works for instruments with no streaming data
            ib_order = ibOrder(
                orderType="SNAP MKT",
                action=ib_BS_str,
                totalQuantity=ib_qty,
                auxPrice=0.0,
            )
        elif order_type == snap_mid_type:
            ## auxPrice is the offset so this will submit an order buy at the best offer, etc
            ## Works like a market order but works for instruments with no streaming data
            ib_order = ibOrder(
                orderType="SNAP MID",
                action=ib_BS_str,
                totalQuantity=ib_qty,
                auxPrice=0.0,
            )
        elif order_type == snap_prim_type:
            ## auxPrice is the offset so this will submit an order buy at the best offer, etc
            ## Works like a market order but works for instruments with no streaming data
            ib_order = ibOrder(
                orderType="SNAP PRIM",
                action=ib_BS_str,
                totalQuantity=ib_qty,
                auxPrice=0.0,
            )
        elif order_type == adaptive_mkt_type:
            # Uses a black-box algo w/ stated aim of balancing execution speed & price
            # See https://investors.interactivebrokers.com/en/index.php?f=19091
            ib_order = ibMarketOrder(ib_BS_str, ib_qty)
            ib_order.algoStrategy = "Adaptive"
            # Patient is usually pretty fast. Alternatives are Normal and Urgent
            ib_order.algoParams = [TagValue("adaptivePriority", "Patient")]
        else:
            self.log.critical("Order type %s not recognised!" % order_type)
            return missing_order

        if account_id is not arg_not_supplied:
            ib_order.account = account_id

        return ib_order

    def ib_cancel_order(self, original_order_object: ibOrder):
        new_trade_object = self.ib.cancelOrder(original_order_object)

        return new_trade_object

    def modify_limit_price_given_original_objects(
        self,
        original_order_object: ibOrder,
        original_contract_object_with_legs: ibcontractWithLegs,
        new_limit_price: float,
    ) -> tradeWithContract:
        original_contract_object = original_contract_object_with_legs.ibcontract
        original_order_object.lmtPrice = new_limit_price

        new_trade_object = self.ib.placeOrder(
            original_contract_object, original_order_object
        )

        new_trade_with_contract = tradeWithContract(
            original_contract_object_with_legs, new_trade_object
        )

        return new_trade_with_contract
