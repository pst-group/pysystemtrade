import datetime

from syscore.genutils import (
    if_empty_string_return_object,
    if_object_matches_return_empty_string,
)

from sysexecution.orders.base_orders import (
    Order,
    tradeQuantity,
    orderType,
)
from sysexecution.orders.named_order_objects import no_order_id, no_children, no_parent
from syslogging import (
    INSTRUMENT_CODE_LOG_LABEL,
    INSTRUMENT_ORDER_ID_LABEL,
    STRATEGY_NAME_LOG_LABEL,
)

from sysobjects.production.tradeable_object import instrumentStrategy


class instrumentOrderType(orderType):
    def allowed_types(self):
        return [
            "best",
            "market",
            "limit",
            "Zero-roll-order",
            "balance_trade",
            "panic",
            "transfer_trade",
        ]


zero_roll_order_type = instrumentOrderType("Zero-roll-order")
balance_order_type = instrumentOrderType("balance_trade")
transfer_order_type = instrumentOrderType("transfer_trade")
market_order_type = instrumentOrderType("market")
best_order_type = instrumentOrderType("best")
limit_order_type = instrumentOrderType("limit")


class instrumentOrder(Order):
    def __init__(
        self,
        *args,
        fill: tradeQuantity = None,
        filled_price: float = None,
        fill_datetime: datetime.datetime = None,
        locked: bool = False,
        order_id: int = no_order_id,
        parent: int = no_parent,
        children: list = no_children,
        active: bool = True,
        order_type: instrumentOrderType = best_order_type,
        limit_price: float = None,
        limit_contract: str = None,
        reference_datetime: datetime.datetime = None,
        reference_price: float = None,
        reference_contract: str = None,
        generated_datetime: datetime.datetime = None,
        manual_trade: bool = False,
        roll_order: bool = False,
        **kwargs_not_used,
    ):
        """

        :param args: Either a single argument 'strategy/instrument' str, or strategy, instrument; followed by trade
        i.e. instrumentOrder(strategy, instrument, trade,  **kwargs) or 'strategy/instrument', trade, type, **kwargs)

        :param fill: fill done so far, int
        :param locked: if locked an order can't be modified, bool
        :param order_id: ID given to orders once in the stack, do not use when creating order
        :param modification_status: NOT USED
        :param modification_quantity: NOT USED
        :param parent: int, order ID of parent order in upward stack
        :param children: list of int, order IDs of child orders in downward stack
        :param active: bool, inactive orders have been filled or cancelled
        :param order_type: str, type of execution required
        :param limit_price: float, limit orders only
        :param limit_contract: YYYYMM string, contract that limit price references
        :param reference_price: float, used for execution calculations
        :param reference_contract: YYYYMM string, contract that relates to reference price
        :param filled_price: float, used for execution calculations and p&l
        :param reference_datetime: datetime, when reference price captured
        :param fill_datetime: datetime used for p&l
        :param generated_datetime: when order generated
        :param manual_trade: bool, was trade iniated manually
        :param roll_order: bool, is this a roll order

        """
        """

        :param trade: float
        :param args: Either 2: strategy, instrument; or 1: instrumentTradeableObject
        :param type: str
        """
        if len(args) == 2:
            tradeable_object = instrumentStrategy.from_key(args[0])
            trade = args[1]
        else:
            strategy = args[0]
            instrument = args[1]
            trade = args[2]
            tradeable_object = instrumentStrategy(strategy, instrument)

        if generated_datetime is None:
            generated_datetime = datetime.datetime.now()

        order_info = dict(
            limit_contract=limit_contract,
            limit_price=limit_price,
            reference_contract=reference_contract,
            reference_price=reference_price,
            manual_trade=manual_trade,
            roll_order=roll_order,
            reference_datetime=reference_datetime,
            generated_datetime=generated_datetime,
        )

        super().__init__(
            tradeable_object,
            trade=trade,
            fill=fill,
            filled_price=filled_price,
            fill_datetime=fill_datetime,
            locked=locked,
            order_id=order_id,
            parent=parent,
            children=children,
            active=active,
            order_type=order_type,
            **order_info,
        )

    @classmethod
    def from_dict(instrumentOrder, order_as_dict):
        trade = order_as_dict.pop("trade")
        key = order_as_dict.pop("key")
        fill = order_as_dict.pop("fill")
        filled_price = order_as_dict.pop("filled_price")
        fill_datetime = order_as_dict.pop("fill_datetime")
        locked = order_as_dict.pop("locked")
        order_id = if_empty_string_return_object(
            order_as_dict.pop("order_id"), no_order_id
        )
        parent = if_empty_string_return_object(order_as_dict.pop("parent"), no_parent)
        children = if_empty_string_return_object(
            order_as_dict.pop("children"), no_children
        )
        active = order_as_dict.pop("active")
        order_type = instrumentOrderType(order_as_dict.pop("order_type", None))

        order_info = order_as_dict

        order = instrumentOrder(
            key,
            trade,
            fill=fill,
            locked=locked,
            order_id=order_id,
            parent=parent,
            children=children,
            fill_datetime=fill_datetime,
            filled_price=filled_price,
            active=active,
            order_type=order_type,
            **order_info,
        )

        return order

    @property
    def strategy_name(self):
        return self.tradeable_object.strategy_name

    @property
    def instrument_code(self):
        return self.tradeable_object.instrument_code

    @property
    def instrument_strategy(self):
        return self.tradeable_object

    @property
    def limit_contract(self):
        return self.order_info["limit_contract"]

    @limit_contract.setter
    def limit_contract(self, limit_contract):
        self.order_info["limit_contract"] = limit_contract

    @property
    def limit_price(self):
        return self.order_info["limit_price"]

    @limit_price.setter
    def limit_price(self, limit_price):
        self.order_info["limit_price"] = limit_price

    @property
    def reference_contract(self):
        return self.order_info["reference_contract"]

    @reference_contract.setter
    def reference_contract(self, reference_contract):
        self.order_info["reference_contract"] = reference_contract

    @property
    def reference_price(self):
        return self.order_info["reference_price"]

    @reference_price.setter
    def reference_price(self, reference_price):
        self.order_info["reference_price"] = reference_price

    @property
    def reference_datetime(self):
        return self.order_info["reference_datetime"]

    @property
    def generated_datetime(self):
        return self.order_info["generated_datetime"]

    @property
    def manual_trade(self):
        return bool(self.order_info["manual_trade"])

    @property
    def roll_order(self):
        return bool(self.order_info["roll_order"])

    def log_attributes(self):
        """
        Returns a dict of instrument_order log attributes

        :return: dict
        """
        return {
            STRATEGY_NAME_LOG_LABEL: self.strategy_name,
            INSTRUMENT_CODE_LOG_LABEL: self.instrument_code,
            INSTRUMENT_ORDER_ID_LABEL: if_object_matches_return_empty_string(
                self.order_id, no_order_id
            ),
        }
