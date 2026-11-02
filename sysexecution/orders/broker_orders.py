import datetime

from syscore.exceptions import fillExceedsTrade
from sysexecution.orders.named_order_objects import (
    missing_order,
    no_order_id,
    no_children,
    no_parent,
)

from sysexecution.orders.base_orders import (
    orderType,
)
from sysexecution.orders.base_orders import Order
from sysexecution.trade_qty import tradeQuantity
from sysobjects.fills import fill_from_order, Fill
from sysexecution.orders.contract_orders import (
    contractOrder,
    from_contract_order_args_to_resolved_args,
)
from sysexecution.orders.instrument_orders import instrumentOrder

from syslogging import (
    BROKER_ORDER_ID_LOG_LABEL,
    CONTRACT_ORDER_ID_LOG_LABEL,
    INSTRUMENT_CODE_LOG_LABEL,
    STRATEGY_NAME_LOG_LABEL,
)
from sysobjects.production.tradeable_object import instrumentStrategy, futuresContract

from syscore.genutils import (
    if_empty_string_return_object,
    if_object_matches_return_empty_string,
)
from syscore.constants import success


class brokerOrderType(orderType):
    def allowed_types(self):
        return [
            "market",
            "limit",
            "balance_trade",
            "snap_mkt",
            "snap_mid",
            "snap_prim",
            "adaptive_mkt",
            "stop_loss",
        ]


stop_loss_order_type = brokerOrderType("stop_loss")
market_order_type = brokerOrderType("market")
limit_order_type = brokerOrderType("limit")

## internal
balance_order_type = brokerOrderType("balance_trade")

## special order types, may not be implemented by all brokers
snap_mkt_type = brokerOrderType("snap_mkt")
snap_mid_type = brokerOrderType("snap_mid")
snap_prim_type = brokerOrderType("snap_prim")
adaptive_mkt_type = brokerOrderType("adaptive_mkt")


class brokerOrder(Order):
    def __init__(
        self,
        *args,
        fill: tradeQuantity = None,
        filled_price: float = None,
        fill_datetime: datetime.datetime = None,
        leg_filled_price: list = [],
        locked: bool = False,
        order_id: int = no_order_id,
        parent: int = no_parent,
        children: list = no_children,
        active: bool = True,
        order_type: brokerOrderType = brokerOrderType("market"),
        algo_used: str = "",
        algo_comment: str = "",
        limit_price: float = None,
        submit_datetime: datetime.datetime = None,
        side_price: float = None,
        mid_price: float = None,
        offside_price: float = None,
        roll_order: bool = False,
        broker: str = "",
        broker_account: str = "",
        broker_clientid: str = "",
        broker_permid: str = "",
        broker_tempid: str = "",
        commission: float = 0.0,
        manual_fill: bool = False,
        **kwargs_ignored,
    ):
        """

        :param args: Either a single argument 'strategy/instrument/contract_id' str, or strategy, instrument, contract_id; followed by trade
        i.e. brokerOrder(strategy, instrument, contractid, trade,  **kwargs) or 'strategy/instrument/contract_id', trade, type, **kwargs)

        Contract_id can either be a single str or a list of str for spread orders, all YYYYMM
        If expressed inside a longer string, separate contract str by '_'

        i.e. brokerOrder('a strategy', 'an instrument', '201003', 6,  **kwargs)
         same as brokerOrder('a strategy/an instrument/201003', 6,  **kwargs)
        brokerOrder('a strategy', 'an instrument', ['201003', '201406'], [6,-6],  **kwargs)
          same as brokerOrder('a strategy/an instrument/201003_201406', [6,-6],  **kwargs)
        :param fill:  fill done so far, list of int
        :param locked: bool, is order locked
        :param order_id: int, my ref number
        :param modification_status: NOT USED
        :param modification_quantity: NOT USED
        :param parent: int or not supplied, parent order
        :param children: list of int or not supplied, child order ids (FUNCTIONALITY NOT USED HERE)
        :param active: bool, is order active or has been filled/cancelled
        :param algo_used: Name of the algo I used to generate the order
        :param order_type: market or limit order (other types may be supported in future)
        :param limit_price: if relevant, float
        :param filled_price: float
        :param submit_datetime: datetime
        :param fill_datetime: datetime
        :param side_price: Price on the 'side' we are submitting eg offer if buying, when order submitted
        :param mid_price: Average of bid and offer when we are submitting
        :param algo_comment: Any comment made by the algo, eg 'Aggressive', 'Passive'...
        :param broker: str, name of broker
        :param broker_account: str, brokerage account
        :param broker_clientid: int, client ID used to generate order
        :param commission: float
        :param broker_permid: Brokers permanent ref number
        :param broker_tempid: Brokers temporary ref number
        :param manual_fill: bool, was fill entered manually rather than being picked up from IB

        """

        key_arguments = from_contract_order_args_to_resolved_args(args, fill=fill)

        resolved_trade = key_arguments.trade
        resolved_fill = key_arguments.fill
        tradeable_object = key_arguments.tradeable_object

        if len(resolved_trade) == 1:
            calendar_spread_order = False
        else:
            calendar_spread_order = True

        order_info = dict(
            algo_used=algo_used,
            submit_datetime=submit_datetime,
            limit_price=limit_price,
            manual_fill=manual_fill,
            calendar_spread_order=calendar_spread_order,
            side_price=side_price,
            mid_price=mid_price,
            offside_price=offside_price,
            algo_comment=algo_comment,
            broker=broker,
            broker_account=broker_account,
            broker_permid=broker_permid,
            broker_tempid=broker_tempid,
            broker_clientid=broker_clientid,
            commission=commission,
            roll_order=roll_order,
            leg_filled_price=leg_filled_price,
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
    def instrument_strategy(self) -> instrumentStrategy:
        return self.tradeable_object.instrument_strategy

    @property
    def contract_date_key(self):
        return self.tradeable_object.contract_date_key

    @property
    def limit_price(self):
        return self.order_info["limit_price"]

    @limit_price.setter
    def limit_price(self, limit_price):
        self.order_info["limit_price"] = limit_price

    @property
    def algo_used(self):
        return self.order_info["algo_used"]

    @property
    def calendar_spread_order(self):
        return self.order_info["calendar_spread_order"]

    @property
    def submit_datetime(self):
        return self.order_info["submit_datetime"]

    @submit_datetime.setter
    def submit_datetime(self, submit_datetime):
        self.order_info["submit_datetime"] = submit_datetime

    @property
    def manual_fill(self):
        return bool(self.order_info["manual_fill"])

    @manual_fill.setter
    def manual_fill(self, manual_fill):
        self.order_info["manual_fill"] = manual_fill

    @property
    def side_price(self):
        return self.order_info["side_price"]

    @property
    def mid_price(self):
        return self.order_info["mid_price"]

    @property
    def offside_price(self):
        return self.order_info["offside_price"]

    @property
    def algo_comment(self):
        return self.order_info["algo_comment"]

    @algo_comment.setter
    def algo_comment(self, comment):
        self.order_info["algo_comment"] = comment

    @property
    def broker(self):
        return self.order_info["broker"]

    @property
    def broker_account(self):
        return self.order_info["broker_account"]

    @property
    def broker_permid(self):
        return self.order_info["broker_permid"]

    @broker_permid.setter
    def broker_permid(self, permid):
        self.order_info["broker_permid"] = permid

    @property
    def broker_clientid(self):
        return self.order_info["broker_clientid"]

    @broker_clientid.setter
    def broker_clientid(self, broker_clientid):
        self.order_info["broker_clientid"] = broker_clientid

    @property
    def broker_tempid(self):
        return self.order_info["broker_tempid"]

    @broker_tempid.setter
    def broker_tempid(self, broker_tempid):
        self.order_info["broker_tempid"] = broker_tempid

    @property
    def commission(self):
        return self.order_info["commission"]

    @commission.setter
    def commission(self, comm):
        self.order_info["commission"] = comm

    @property
    def futures_contract(self):
        return futuresContract(
            instrument_object=self.instrument_code,
            contract_date_object=self.contract_date,
        )

    @property
    def leg_filled_price(self):
        return self.order_info["leg_filled_price"]

    @leg_filled_price.setter
    def leg_filled_price(self, leg_filled_price: list):
        self.order_info["leg_filled_price"] = leg_filled_price

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
        order_type = brokerOrderType(order_as_dict.pop("order_type", None))

        order_info = order_as_dict

        order = brokerOrder(
            key,
            trade,
            fill=fill,
            locked=locked,
            order_id=order_id,
            parent=parent,
            children=children,
            active=active,
            filled_price=filled_price,
            fill_datetime=fill_datetime,
            order_type=order_type,
            **order_info,
        )

        return order

    def log_attributes(self):
        """
        Returns a dict of broker_order log attributes

        :return: dict
        """
        broker_order = self
        return {
            STRATEGY_NAME_LOG_LABEL: broker_order.strategy_name,
            INSTRUMENT_CODE_LOG_LABEL: broker_order.instrument_code,
            CONTRACT_ORDER_ID_LOG_LABEL: if_object_matches_return_empty_string(
                broker_order.parent, no_parent
            ),
            BROKER_ORDER_ID_LOG_LABEL: if_object_matches_return_empty_string(
                broker_order.order_id, no_order_id
            ),
        }

    def add_execution_details_from_matched_broker_order(self, matched_broker_order):
        fill_qty_okay = self.trade.fill_less_than_or_equal_to_desired_trade(
            matched_broker_order.fill
        )
        if not fill_qty_okay:
            raise fillExceedsTrade
        self.fill_order(
            matched_broker_order.fill,
            filled_price=matched_broker_order.filled_price,
            fill_datetime=matched_broker_order.fill_datetime,
        )
        self.commission = matched_broker_order.commission
        self.broker_permid = matched_broker_order.broker_permid
        self.algo_comment = matched_broker_order.algo_comment
        self.leg_filled_price = matched_broker_order.leg_filled_price

        return success


def create_new_broker_order_from_contract_order(
    contract_order: contractOrder,
    order_type: brokerOrderType = brokerOrderType("market"),
    limit_price: float = None,
    submit_datetime: datetime.datetime = None,
    side_price: float = None,
    mid_price: float = None,
    offside_price: float = None,
    algo_comment: str = "",
    broker: str = "",
    broker_account: str = "",
    broker_clientid: str = "",
    broker_permid: str = "",
    broker_tempid: str = "",
) -> brokerOrder:
    broker_order = brokerOrder(
        contract_order.key,
        contract_order.trade,
        parent=contract_order.order_id,
        algo_used=contract_order.algo_to_use,
        order_type=order_type,
        limit_price=limit_price,
        side_price=side_price,
        offside_price=offside_price,
        mid_price=mid_price,
        broker=broker,
        broker_account=broker_account,
        broker_clientid=broker_clientid,
        submit_datetime=submit_datetime,
        algo_comment=algo_comment,
        broker_permid=broker_permid,
        broker_tempid=broker_tempid,
        roll_order=contract_order.roll_order,
        manual_fill=contract_order.manual_fill,
    )

    return broker_order


## Not very pretty but only used for diagnostic TCA
class brokerOrderWithParentInformation(brokerOrder):
    @classmethod
    def create_augmented_order(
        self,
        order: brokerOrder,
        instrument_order: instrumentOrder,
        contract_order: contractOrder,
    ):
        # Price when the trade was generated. We use the contract order price since
        #  the instrument order price may refer to a different contract
        order.parent_reference_price = contract_order.reference_price

        # when the trade was originally generated, this is the instrument order
        # used to measure effects of delay eg from close
        order.parent_reference_datetime = instrument_order.reference_datetime

        # instrument order prices may refer to a different contract
        # so we use the contract order limit
        order.parent_limit_price = contract_order.limit_price

        order.buy_or_sell = order.trade.buy_or_sell()

        return order


def single_fill_from_broker_order(order: brokerOrder, contract_str: str):
    list_of_dates = order.contract_date.list_of_date_str
    if len(list_of_dates) == 1:
        # single leg
        return fill_from_order(order)

    if len(order.leg_filled_price) == 0:
        return missing_order

    index_of_date = list_of_dates.index(contract_str)
    trade_qty = order.trade[index_of_date]
    fill_price = order.leg_filled_price[index_of_date]

    fill = Fill(order.fill_datetime, trade_qty, fill_price)

    return fill
