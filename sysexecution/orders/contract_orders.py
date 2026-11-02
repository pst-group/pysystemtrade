from dataclasses import dataclass
import datetime

from sysexecution.orders.base_orders import (
    Order,
    resolve_inputs_to_order,
    orderType,
)
from sysexecution.orders.named_order_objects import no_order_id, no_children, no_parent

from sysexecution.trade_qty import tradeQuantity
from syslogging import (
    CONTRACT_ORDER_ID_LOG_LABEL,
    INSTRUMENT_CODE_LOG_LABEL,
    INSTRUMENT_ORDER_ID_LABEL,
    STRATEGY_NAME_LOG_LABEL,
)

from sysobjects.production.tradeable_object import (
    futuresContractStrategy,
    instrumentStrategy,
    futuresContract,
)
from syscore.genutils import (
    if_empty_string_return_object,
    if_object_matches_return_empty_string,
)
from syscore.constants import success


class contractOrderType(orderType):
    def allowed_types(self):
        return ["best", "market", "limit", "balance_trade", "", "panic"]


best_order_type = contractOrderType("best")
balance_order_type = contractOrderType("balance_trade")
panic_order_type = contractOrderType("panic")
limit_order_type = contractOrderType("limit")

NO_CONTROLLING_ALGO = None


class contractOrder(Order):
    def __init__(
        self,
        *args,
        fill: tradeQuantity = None,
        filled_price: float = None,
        fill_datetime: datetime.datetime = None,
        locked=False,
        order_id: int = no_order_id,
        parent: int = no_parent,
        children: list = no_children,
        active: bool = True,
        order_type: contractOrderType = contractOrderType("best"),
        limit_price: float = None,
        reference_price: float = None,
        generated_datetime: datetime.datetime = None,
        manual_fill: bool = False,
        manual_trade: bool = False,
        roll_order: bool = False,
        inter_spread_order: bool = False,
        algo_to_use: str = "",
        reference_of_controlling_algo: str = None,
        **kwargs_ignored,
    ):
        """
        :param args: Either a single argument 'strategy/instrument/contract_order_id' str, or strategy, instrument, contract_order_id; followed by trade
        i.e. contractOrder(strategy, instrument, contractid, trade,  **kwargs) or 'strategy/instrument/contract_order_id', trade, type, **kwargs)

        Contract_id can either be a single str or a list of str for spread orders, all YYYYMM
        If expressed inside a longer string, separate contract str by '_'

        i.e. contractOrder('a strategy', 'an instrument', '201003', 6,  **kwargs)
         same as contractOrder('a strategy/an instrument/201003', 6,  **kwargs)
        contractOrder('a strategy', 'an instrument', ['201003', '201406'], [6,-6],  **kwargs)
          same as contractOrder('a strategy/an instrument/201003_201406', [6,-6],  **kwargs)

        :param fill: fill done so far, list of int
        :param locked: if locked an order can't be modified, bool
        :param order_id: ID given to orders once in the stack, do not use when creating order
        :param modification_status: NOT USED
        :param modification_quantity: NOT USED
        :param parent: int, order ID of parent order in upward stack
        :param children: list of int, order IDs of child orders in downward stack
        :param active: bool, inactive orders have been filled or cancelled
        :param algo_to_use: str, full pathname of method to use to execute order.
        :param reference_of_controlling_algo: str, the key of the controlling algo. If None not currently controlled.
        :param limit_price: float, limit orders only
        :param reference_price: float, used to benchmark order (usually price from previous days close)
        :param filled_price: float, used for execution calculations and p&l
        :param fill_datetime: datetime used for p&l
        :param generated_datetime: datetime order generated
        :param manual_fill: bool, fill entered manually
        :param manual_trade: bool, trade entered manually
        :param roll_order: bool, part of a (or if a spread an entire) roll order. Passive rolls will be False
        :param calendar_spread_order: bool, a calendar spread (intra-market) order
        :param inter_spread_order: bool, part of an instrument order that is a spread across multiple markets
        """

        key_arguments = from_contract_order_args_to_resolved_args(args, fill=fill)

        resolved_trade = key_arguments.trade
        resolved_fill = key_arguments.fill
        tradeable_object = key_arguments.tradeable_object

        if len(resolved_trade) == 1:
            calendar_spread_order = False
        else:
            calendar_spread_order = True

        if generated_datetime is None:
            generated_datetime = datetime.datetime.now()

        order_info = dict(
            algo_to_use=algo_to_use,
            reference_price=reference_price,
            limit_price=limit_price,
            manual_trade=manual_trade,
            manual_fill=manual_fill,
            roll_order=roll_order,
            calendar_spread_order=calendar_spread_order,
            inter_spread_order=inter_spread_order,
            generated_datetime=generated_datetime,
            reference_of_controlling_algo=reference_of_controlling_algo,
        )

        super().__init__(
            tradeable_object,
            trade=resolved_trade,
            fill=resolved_fill,
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
    def from_dict(contractOrder, order_as_dict):
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
        order_type = order_as_dict.pop("order_type", None)
        order_type = contractOrderType(order_type)

        order_info = order_as_dict

        order = contractOrder(
            key,
            trade,
            fill=fill,
            locked=locked,
            order_id=order_id,
            parent=parent,
            children=children,
            active=active,
            fill_datetime=fill_datetime,
            filled_price=filled_price,
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
    def contract_date(self):
        return self.tradeable_object.contract_date

    @property
    def contract_date_key(self):
        return self.tradeable_object.contract_date_key

    @property
    def futures_contract(self) -> futuresContract:
        return self.tradeable_object.futures_contract

    @property
    def instrument_strategy(self) -> instrumentStrategy:
        return self.tradeable_object.instrument_strategy

    @property
    def algo_to_use(self):
        return self.order_info["algo_to_use"]

    @algo_to_use.setter
    def algo_to_use(self, algo_to_use):
        self.order_info["algo_to_use"] = algo_to_use

    @property
    def generated_datetime(self):
        return self.order_info["generated_datetime"]

    @property
    def reference_price(self):
        return self.order_info["reference_price"]

    @reference_price.setter
    def reference_price(self, reference_price):
        self.order_info["reference_price"] = reference_price

    @property
    def limit_price(self):
        return self.order_info["limit_price"]

    @limit_price.setter
    def limit_price(self, limit_price):
        self.order_info["limit_price"] = limit_price

    @property
    def manual_trade(self):
        return bool(self.order_info["manual_trade"])

    @property
    def manual_fill(self):
        return bool(self.order_info["manual_fill"])

    @manual_fill.setter
    def manual_fill(self, manual_fill):
        self.order_info["manual_fill"] = manual_fill

    @property
    def roll_order(self):
        return bool(self.order_info["roll_order"])

    @property
    def calendar_spread_order(self):
        return bool(self.order_info["calendar_spread_order"])

    @property
    def reference_of_controlling_algo(self):
        return self.order_info["reference_of_controlling_algo"]

    def is_order_controlled_by_algo(self):
        return (
            self.order_info["reference_of_controlling_algo"] is not NO_CONTROLLING_ALGO
        )

    def add_controlling_algo_ref(self, control_algo_ref):
        if self.reference_of_controlling_algo == control_algo_ref:
            # irrelevant, already controlled
            return success
        if self.is_order_controlled_by_algo():
            raise Exception(
                "Already controlled by %s" % self.reference_of_controlling_algo
            )
        self.order_info["reference_of_controlling_algo"] = control_algo_ref

        return success

    def release_order_from_algo_control(self):
        self.order_info["reference_of_controlling_algo"] = NO_CONTROLLING_ALGO

    @property
    def panic_order(self):
        type = self.order_type
        return type == panic_order_type

    @property
    def inter_spread_order(self):
        return bool(self.order_info["inter_spread_order"])

    def log_attributes(self):
        """
        Returns a dict of contract_order log attributes

        :return: dict
        """
        return {
            STRATEGY_NAME_LOG_LABEL: self.strategy_name,
            INSTRUMENT_CODE_LOG_LABEL: self.instrument_code,
            CONTRACT_ORDER_ID_LOG_LABEL: if_object_matches_return_empty_string(
                self.order_id, no_order_id
            ),
            INSTRUMENT_ORDER_ID_LABEL: if_object_matches_return_empty_string(
                self.parent, no_parent
            ),
        }


@dataclass
class contractOrderKeyArguments:
    tradeable_object: futuresContractStrategy
    trade: tradeQuantity
    fill: tradeQuantity = None

    def resolve_inputs_to_order_with_key_arguments(self):
        resolved_trade, resolved_fill = resolve_inputs_to_order(
            trade=self.trade, fill=self.fill
        )

        self.fill = resolved_fill
        self.trade = resolved_trade

    def sort_inputs_by_contract_date_order(self):
        sort_order = self.tradeable_object.sort_idx_for_contracts()
        self.trade.sort_with_idx(sort_order)
        self.fill.sort_with_idx(sort_order)

        self.tradeable_object.sort_contracts_with_idx(sort_order)


def from_contract_order_args_to_resolved_args(
    args: tuple, fill: tradeQuantity
) -> contractOrderKeyArguments:
    # different ways of specifying tradeable object
    key_arguments = split_contract_order_args(args, fill)

    # ensure everything has the right type
    key_arguments.resolve_inputs_to_order_with_key_arguments()

    # ensure contracts and lists all match
    key_arguments.sort_inputs_by_contract_date_order()

    return key_arguments


def split_contract_order_args(
    args: tuple, fill: tradeQuantity
) -> contractOrderKeyArguments:
    if len(args) == 2:
        tradeable_object = futuresContractStrategy.from_key(args[0])
        trade = args[1]
    elif len(args) == 4:
        strategy = args[0]
        instrument = args[1]
        contract_id = args[2]
        trade = args[3]
        tradeable_object = futuresContractStrategy(strategy, instrument, contract_id)
    else:
        raise Exception(
            "contractOrder(strategy, instrument, contractid, trade,  **kwargs) or ('strategy/instrument/contract_order_id', trade, **kwargs) "
        )

    key_arguments = contractOrderKeyArguments(
        tradeable_object=tradeable_object, trade=trade, fill=fill
    )

    return key_arguments
