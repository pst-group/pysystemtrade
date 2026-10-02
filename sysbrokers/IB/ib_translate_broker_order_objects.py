import datetime


from collections import namedtuple
from dateutil.tz import tz

from ib_async import Trade as ibTrade
from sysbrokers.IB.ib_contracts import ibcontractWithLegs, ibContract
from sysbrokers.broker_trade import brokerTrade
from syscore.exceptions import missingData
from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order
from sysexecution.orders.base_orders import resolve_multi_leg_price_to_single_price

from sysobjects.spot_fx_prices import currencyValue
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.trade_qty import tradeQuantity


class ibOrderCouldntCreateException(Exception):
    pass


class tradeWithContract(brokerTrade):
    def __init__(self, ibcontract_with_legs: ibcontractWithLegs, trade_object: ibTrade):
        self._ibcontract_with_legs = ibcontract_with_legs
        self._trade = trade_object

    def __repr__(self):
        return str(self.trade) + " " + str(self.ibcontract_with_legs)

    @property
    def ibcontract_with_legs(self) -> ibcontractWithLegs:
        return self._ibcontract_with_legs

    @property
    def trade(self) -> ibTrade:
        return self._trade

    @property
    def ib_instrument_code(self):
        return self.trade.contract.symbol

    @property
    def ib_contract(self) -> ibContract:
        return self.trade.contract


class ibBrokerOrder(brokerOrder):
    @classmethod
    def from_broker_trade_object(
        ibBrokerOrder, extracted_trade_data, instrument_code=arg_not_supplied
    ):
        sec_type = extracted_trade_data.contract.ib_sectype

        if sec_type not in ["FUT", "BAG"]:
            # Doesn't handle non futures trades, just ignores them
            return missing_order

        strategy_name = ""
        if instrument_code is arg_not_supplied:
            instrument_code = extracted_trade_data.contract.ib_instrument_code
        contract_id_list = extracted_trade_data.contract.ib_contract_id

        algo_comment = extracted_trade_data.algo_msg
        order_type = extracted_trade_data.order.type
        limit_price = extracted_trade_data.order.limit_price
        broker_account = extracted_trade_data.order.account
        broker_permid = extracted_trade_data.order.perm_id

        broker_objects = dict(
            order=extracted_trade_data.order.order_object,
            trade=extracted_trade_data.trade_object,
            contract=extracted_trade_data.contract.contract_object,
        )

        leg_ratios = extracted_trade_data.contract.leg_ratios

        # sometimes this is negative
        unsigned_remain_qty_scalar = extracted_trade_data.order.remain_qty

        # when it's negative this is often zero
        unsigned_total_qty_scalar = extracted_trade_data.order.total_qty
        if unsigned_remain_qty_scalar < 0:
            total_qty = None
        else:
            # remain is not used... but the option is here
            # remain_qty_scalar = unsigned_remain_qty_scalar * extracted_trade_data.order.order_sign
            # remain_qty_list = [int(remain_qty_scalar * ratio) for ratio in leg_ratios]
            # remain_qty = tradeQuantity(remain_qty_list)

            total_qty_scalar = (
                unsigned_total_qty_scalar * extracted_trade_data.order.order_sign
            )
            total_qty_list = [int(total_qty_scalar * ratio) for ratio in leg_ratios]

            total_qty = tradeQuantity(total_qty_list)

        try:
            fill_totals = extract_totals_from_fill_data(extracted_trade_data.fills)
        except missingData:
            fill_datetime = None
            fill = total_qty.zero_version()
            filled_price_list = []
            commission = None
            broker_tempid = extracted_trade_data.order.order_id
            broker_clientid = extracted_trade_data.order.client_id
        else:
            (
                broker_clientid,
                broker_tempid,
                filled_price_dict,
                fill_datetime,
                commission,
                signed_qty_dict,
            ) = fill_totals

            filled_price_list = [
                filled_price_dict.get(contractid, None)
                for contractid in contract_id_list
            ]
            fill_list = [
                signed_qty_dict.get(contractid, None) for contractid in contract_id_list
            ]
            missing_fill = [
                fill_price_item is None or fill is None
                for fill_price_item, fill in zip(filled_price_list, fill_list)
            ]
            if any(missing_fill):
                fill = None
                filled_price_list = []
            else:
                fill_list = [int(fill) for fill in fill_list]
                fill = tradeQuantity(fill_list)

        if total_qty is None:
            total_qty = fill

        fill_price = resolve_multi_leg_price_to_single_price(
            trade_list=total_qty, price_list=filled_price_list
        )

        broker_order = ibBrokerOrder(
            strategy_name,
            instrument_code,
            contract_id_list,
            total_qty,
            fill=fill,
            order_type=order_type,
            limit_price=limit_price,
            filled_price=fill_price,
            algo_comment=algo_comment,
            fill_datetime=fill_datetime,
            broker_account=broker_account,
            commission=commission,
            leg_filled_price=filled_price_list,
            broker_permid=broker_permid,
            broker_tempid=broker_tempid,
            broker_clientid=broker_clientid,
        )

        broker_order.broker_objects = broker_objects

        return broker_order

    @property
    def broker_objects(self):
        return getattr(self, "_broker_objects", None)

    @broker_objects.setter
    def broker_objects(self, broker_objects):
        self._broker_objects = broker_objects


def create_broker_order_from_trade_with_contract(
    trade_with_contract_from_ib: tradeWithContract, instrument_code: str
) -> ibBrokerOrder:
    # pretty horrible code to convert IB order and contract objects into my
    # world

    # we do this in two stages to make the abstraction marginally better (to
    # be honest, to reflect legacy history)
    extracted_trade_info = extract_trade_info(trade_with_contract_from_ib)

    # and stage two
    ib_broker_order = ibBrokerOrder.from_broker_trade_object(
        extracted_trade_info, instrument_code=instrument_code
    )

    # this can go wrong eg for FX
    if ib_broker_order is missing_order:
        raise ibOrderCouldntCreateException()

    ib_broker_order._order_info["broker_tempid"] = create_tempid_from_broker_details(
        ib_broker_order
    )

    return ib_broker_order


def create_tempid_from_broker_details(
    broker_order_from_trade_object: ibBrokerOrder,
) -> str:
    tempid = "%s/%s/%s" % (
        broker_order_from_trade_object.broker_account,
        broker_order_from_trade_object.broker_clientid,
        broker_order_from_trade_object.broker_tempid,
    )
    return tempid


def extract_totals_from_fill_data(list_of_fills):
    """
    Sum up info over fills
    :return: average_filled_price, commission (as list of tuples), total quantity filled

    """
    contract_id_list = [fill.contract_id for fill in list_of_fills]
    unique_contract_id_list = sorted(set(contract_id_list))

    if len(list_of_fills) == 0:
        # broker_clientid, broker_tempid, filled_price_dict, fill_datetime, commission_list, signed_qty_dict
        raise missingData

    fill_data_by_contract = {}
    for contractid in unique_contract_id_list:
        list_of_fills_for_contractid = [
            fill for fill in list_of_fills if fill.contract_id == contractid
        ]
        extracted_totals = extract_totals_from_fill_data_for_contract_id(
            list_of_fills_for_contractid
        )
        fill_data_by_contract[contractid] = extracted_totals

    # Returns tuple broker_clientid, broker_tempid, filled_price,
    # fill_datetime, commission (as list of tuples), signed_qty
    first_contract = unique_contract_id_list[0]
    # should all be the same
    broker_clientid = fill_data_by_contract[first_contract][0]
    # should all be the same
    broker_tempid = fill_data_by_contract[first_contract][1]
    filled_price_dict = dict(
        [
            (contractid, fill_data_for_contractid[2])
            for contractid, fill_data_for_contractid in fill_data_by_contract.items()
        ]
    )
    # should all be the same
    fill_datetime = fill_data_by_contract[first_contract][3]
    commission_list_of_lists = [
        fill_data_for_contract[4]
        for fill_data_for_contract in fill_data_by_contract.values()
    ]
    commission_list = (
        None
        if any(commission is None for commission in commission_list_of_lists)
        else sum(commission_list_of_lists, [])
    )
    signed_qty_dict = dict(
        [
            (contractid, fill_data_for_contractid[5])
            for contractid, fill_data_for_contractid in fill_data_by_contract.items()
        ]
    )

    return (
        broker_clientid,
        broker_tempid,
        filled_price_dict,
        fill_datetime,
        commission_list,
        signed_qty_dict,
    )


def extract_totals_from_fill_data_for_contract_id(list_of_fills_for_contractid):
    """
    Sum up info over fills

    :param list_of_fills: list of named tuples
    :return: broker_clientid, broker_tempid, filled_price, fill_datetime, commission (as list of tuples)
    """
    qty_and_price_and_datetime_and_id = [
        (
            fill.cum_qty,
            fill.avg_price,
            fill.time,
            fill.temp_id,
            fill.client_id,
            fill.signed_qty,
        )
        for fill in list_of_fills_for_contractid
    ]

    # sort by total quantity
    qty_and_price_and_datetime_and_id.sort(key=lambda x: x[0])

    final_fill = qty_and_price_and_datetime_and_id[-1]
    (
        _,
        filled_price,
        fill_datetime,
        broker_tempid,
        broker_clientid,
        signed_qty,
    ) = final_fill

    commission = (
        None
        if any(fill.commission is None for fill in list_of_fills_for_contractid)
        else [
            currencyValue(fill.commission_ccy, fill.commission)
            for fill in list_of_fills_for_contractid
        ]
    )

    return (
        broker_clientid,
        broker_tempid,
        filled_price,
        fill_datetime,
        commission,
        signed_qty,
    )


def extract_trade_info(placed_broker_trade_object):
    trade_to_process = placed_broker_trade_object.trade
    legs = placed_broker_trade_object.ibcontract_with_legs.legs
    order_info = extract_order_info(trade_to_process)
    contract_info = extract_contract_info(trade_to_process, legs)
    fill_info = extract_fill_info(trade_to_process)

    algo_msg = " ".join([str(log_entry) for log_entry in trade_to_process.log])
    active = trade_to_process.isActive()

    tradeInfo = namedtuple(
        "tradeInfo",
        ["order", "contract", "fills", "algo_msg", "active", "trade_object"],
    )
    trade_info = tradeInfo(
        order_info, contract_info, fill_info, algo_msg, active, trade_to_process
    )

    return trade_info


def extract_order_info(trade_to_process):
    order = trade_to_process.order

    account = order.account
    perm_id = order.permId
    client_id = order.clientId
    limit_price = order.lmtPrice
    order_sign = sign_from_BS(order.action)
    order_type = resolve_order_type(order.orderType)
    order_id = order.orderId
    remain_qty = trade_to_process.remaining()
    total_qty = trade_to_process.order.totalQuantity

    orderInfo = namedtuple(
        "orderInfo",
        [
            "account",
            "perm_id",
            "limit_price",
            "order_sign",
            "type",
            "remain_qty",
            "order_object",
            "client_id",
            "order_id",
            "total_qty",
        ],
    )
    order_info = orderInfo(
        account=account,
        perm_id=perm_id,
        limit_price=limit_price,
        order_sign=order_sign,
        type=order_type,
        remain_qty=remain_qty,
        order_object=order,
        client_id=client_id,
        order_id=order_id,
        total_qty=total_qty,
    )

    return order_info


def extract_contract_info(trade_to_process, legs):
    contract = trade_to_process.contract
    ib_instrument_code = contract.symbol
    ib_sectype = contract.secType

    is_combo_legs = not legs == []
    if is_combo_legs:
        ib_contract_id, leg_ratios = get_combo_info(contract, legs)
    else:
        ib_contract_id = [contract.lastTradeDateOrContractMonth]
        leg_ratios = [1]

    contractInfo = namedtuple(
        "contractInfo",
        [
            "ib_instrument_code",
            "ib_contract_id",
            "ib_sectype",
            "contract_object",
            "legs",
            "leg_ratios",
        ],
    )
    contract_info = contractInfo(
        ib_instrument_code=ib_instrument_code,
        ib_contract_id=ib_contract_id,
        ib_sectype=ib_sectype,
        contract_object=contract,
        legs=legs,
        leg_ratios=leg_ratios,
    )

    return contract_info


def get_combo_info(contract, legs):
    ib_contract_id = [leg.lastTradeDateOrContractMonth for leg in legs]
    leg_ratios = [
        get_leg_ratio_for_leg(contract_id, contract, legs)
        for contract_id in ib_contract_id
    ]

    return ib_contract_id, leg_ratios


def get_leg_ratio_for_leg(contract_id, contract, legs):
    ib_contract_id = [leg.lastTradeDateOrContractMonth for leg in legs]
    ib_conId = [leg.conId for leg in legs]
    idx = ib_contract_id.index(contract_id)
    conId = ib_conId[idx]

    contract_conId_list = [combo_leg.conId for combo_leg in contract.comboLegs]
    relevant_combo_leg_idx = contract_conId_list.index(conId)

    relevant_combo_leg = contract.comboLegs[relevant_combo_leg_idx]
    action = relevant_combo_leg.action
    ratio = relevant_combo_leg.ratio
    trade_sign = sign_from_BS(action)

    return trade_sign * ratio


def extract_contract_spread_info(trade_to_process):
    contract = trade_to_process.contract
    ib_instrument_code = contract.symbol
    ib_contract_id = contract.lastTradeDateOrContractMonth
    ib_sectype = contract.secType

    contractInfo = namedtuple(
        "contractInfo",
        ["ib_instrument_code", "ib_contract_id", "ib_sectype", "contract_object"],
    )
    contract_info = contractInfo(
        ib_instrument_code=ib_instrument_code,
        ib_contract_id=ib_contract_id,
        ib_sectype=ib_sectype,
        contract_object=contract,
    )

    return contract_info


def extract_fill_info(trade_to_process):
    all_fills = trade_to_process.fills
    fill_info = [extract_single_fill(single_fill) for single_fill in all_fills]
    fill_info_without_bags = [
        single_fill for single_fill in fill_info if single_fill is not None
    ]

    return fill_info_without_bags


def extract_single_fill(single_fill):
    is_bag_fill = single_fill.contract.secType == "BAG"
    if is_bag_fill:
        return None
    report = single_fill.commissionReport
    # ib_async creates an empty report with commission=0 before the callback.
    # A matching report, including a genuine zero fee, is distinct from that.
    commission = (
        report.commission
        if report.execId
        and report.execId == single_fill.execution.execId
        and report.currency
        else None
    )
    commission_ccy = report.currency
    cum_qty = single_fill.execution.cumQty
    sign = sign_from_BOT_SEL(single_fill.execution.side)
    signed_qty = cum_qty * sign
    price = single_fill.execution.price
    avg_price = single_fill.execution.avgPrice

    # move to local time and strip TZ info
    time = single_fill.execution.time.astimezone(tz.tzlocal())
    time = datetime.datetime.fromtimestamp(time.timestamp())
    temp_id = single_fill.execution.orderId
    client_id = single_fill.execution.clientId
    contract_month = single_fill.contract.lastTradeDateOrContractMonth

    singleFill = namedtuple(
        "singleFill",
        [
            "commission",
            "commission_ccy",
            "cum_qty",
            "price",
            "avg_price",
            "time",
            "temp_id",
            "client_id",
            "signed_qty",
            "contract_id",
        ],
    )

    single_fill = singleFill(
        commission,
        commission_ccy,
        cum_qty,
        price,
        avg_price,
        time,
        temp_id,
        client_id,
        signed_qty,
        contract_month,
    )

    return single_fill


def resolve_order_type(ib_order_type):
    lookup_dict = dict(MKT="market")
    my_order_type = lookup_dict.get(ib_order_type, "")

    return my_order_type


def sign_from_BS(action):
    if action == "SELL":
        return -1
    return 1


def sign_from_BOT_SEL(action):
    if action == "BOT":
        return 1
    return -1


class listOfTradesWithContracts(list):
    pass
