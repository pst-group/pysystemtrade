"""
Interactive tool to do the following:

Look at the instrument, order and broker stack
Do standard things to the instrument, order and broker stack (normally automated)


"""

from typing import Tuple
from sysexecution.orders.named_order_objects import missing_order, no_children
from syscore.interactive.input import (
    get_input_from_user_and_convert_to_type,
    true_if_answer_is_yes,
)
from syscore.interactive.date_input import get_datetime_input
from syscore.interactive.menus import (
    interactiveMenu,
    print_menu_of_values_and_get_response,
)
from syscore.interactive.display import set_pd_print_options

from sysdata.data_blob import dataBlob
from sysproduction.data.positions import diagPositions
from sysproduction.data.optimal_positions import dataOptimalPositions
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysproduction.data.strategies import get_valid_strategy_name_from_user
from sysproduction.data.contracts import (
    get_valid_instrument_code_and_contractid_from_user,
)
from sysproduction.data.controls import dataLocks
from sysproduction.data.prices import get_valid_instrument_code_from_user, diagPrices

from sysexecution.stack_handler.stack_handler import stackHandler
from sysexecution.stack_handler.balance_trades import stackHandlerCreateBalanceTrades
from sysexecution.stack_handler.spawn_children_from_instrument_orders import (
    map_instrument_order_type_to_contract_order_type,
)
from sysexecution.orders.broker_orders import (
    brokerOrder,
    balance_order_type as broker_balance_order_type,
)
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.instrument_orders import (
    instrumentOrder,
    market_order_type,
    instrumentOrderType,
    balance_order_type as instrument_balance_order_type,
)
from sysexecution.algos.allocate_algo_to_order import get_list_of_algos
from sysbrokers.IB.ib_connection import connectionIB
from syscore.constants import arg_not_supplied
from syscore.exceptions import missingData

from sysobjects.contracts import futuresContract


def interactive_order_stack():
    # Avoids pressing enter when running from script
    ib_conn = arg_not_supplied
    interactive_order_stack_with_ib_conn(ib_conn)


def interactive_order_stack_with_ib_conn(ib_conn: connectionIB = arg_not_supplied):
    with dataBlob(log_name="Interactive-Order-Stack", ib_conn=ib_conn) as data:
        set_pd_print_options()
        menu = interactiveMenu(
            top_level_menu_of_options, nested_menu_of_options, dict_of_functions, data
        )
        menu.run_menu()


top_level_menu_of_options = {
    0: "View",
    1: "Create orders",
    2: "Fills and completions",
    3: "Netting, cancellation and locks",
    4: "Delete and clean",
}

nested_menu_of_options = {
    0: {
        0: "View specific order",
        1: "View instrument order stack",
        2: "View contract order stack",
        3: "View broker order stack (stored local DB)",
        4: "View IB orders and fills",
        9: "View positions",
    },
    1: {
        10: "Spawn contract orders from instrument orders",
        11: "Create force roll contract orders",
        12: "Create (and try to execute...) IB broker orders",
        13: "Balance trade: Create a series of trades and immediately fill them (not actually executed)",
        14: "Balance instrument trade: Create a trade just at the strategy level and fill (not actually executed)",
        15: "Manual trade: Create a series of trades to be executed",
        16: "Cash FX trade",
    },
    2: {
        20: "Manually fill broker or contract order",
        21: "Get broker fills from IB",
        22: "Pass fills upwards from broker to contract order",
        23: "Pass fills upwards from contract to instrument order",
        24: "Handle completed orders",
    },
    3: {
        30: "Cancel broker order",
        31: "Net instrument orders",
        32: "Lock/unlock order",
        33: "Lock/unlock instrument code",
        34: "Unlock all instruments",
        35: "Remove Algo lock on contract order",
    },
    4: {
        40: "Delete entire stack (CAREFUL!)",
        41: "Delete specific order ID (CAREFUL!)",
        42: "End of day process (cancel orders, mark all orders as complete, delete orders)",
    },
}


def view_instrument_stack(data):
    stack_handler = stackHandler(data)
    print("\nINSTRUMENT STACK \n")
    view_generic_stack(stack_handler.instrument_stack)


def view_contract_stack(data):
    stack_handler = stackHandler(data)

    order_ids = stack_handler.contract_stack.get_list_of_order_ids()
    print("\nCONTRACT STACK \n")
    for order_id in order_ids:
        order = stack_handler.contract_stack.get_order_with_id_from_stack(order_id)
        print(order)


def view_broker_stack(data):
    stack_handler = stackHandler(data)
    print("\nBroker stack (from database): \n")
    view_generic_stack(stack_handler.broker_stack)


def view_generic_stack(stack):
    order_ids = stack.get_list_of_order_ids()
    for order_id in order_ids:
        print(stack.get_order_with_id_from_stack(order_id))


def view_broker_order_list(data):
    data_broker = dataBroker(data)
    broker_orders = data_broker.get_list_of_orders()
    print("\n\nOrders received from broker API\n")
    for order in broker_orders:
        print(order)
    print("\n\nStored (orders made in this session):\n")
    broker_orders = data_broker.get_list_of_stored_orders()
    for order in broker_orders:
        print(order.full_repr())


def spawn_contracts_from_instrument_orders(data):
    stack_handler = stackHandler(data)

    print(
        "This will create contract orders for any instrument orders that don't have them"
    )
    print("Instrument orders:")
    view_instrument_stack(data)
    order_id = get_input_from_user_and_convert_to_type(
        "Which instrument order ID",
        type_expected=int,
        default_value="ALL",
        default_str="All",
    )
    check_ans = true_if_answer_is_yes("Are you sure?")
    if not check_ans:
        return None

    if order_id == "ALL":
        stack_handler.spawn_children_from_new_instrument_orders()
    else:
        stack_handler.spawn_children_from_instrument_order_id(order_id)

    print(
        "If you are trading manually, you should now view the contract order stack and trade."
    )
    print("Then create manual fills for contract orders")


def create_balance_trade(data):
    print(
        "Most likely use case here is that IB has closed one of your positions as close to the expiry"
    )
    print(
        "Or an edge case in which an order was submitted and then filled whilst you were not monitoring fills"
    )
    print("Or perhaps you are trading manually")
    print("Trades have to be attributed to a strategy (even roll trades)")

    broker_order = get_broker_order_details_for_balance_trade(data)

    if broker_order:
        print(broker_order)
        ans = input("Are you sure? (Y/other)")
        if ans != "Y":
            return

        stack_handler = stackHandlerCreateBalanceTrades(data)

        stack_handler.create_balance_trade(broker_order)


def get_broker_order_details_for_balance_trade(data: dataBlob) -> brokerOrder | None:
    ans = true_if_answer_is_yes(
        "Auto close an existing position (if not, manually enter details)?"
    )
    if ans:
        (
            instrument_code,
            contract_date_yyyy_mm,
            fill_qty,
        ) = get_futures_contract_and_qty_to_close_position(data)
    else:
        (
            instrument_code,
            contract_date_yyyy_mm,
            fill_qty,
        ) = manually_get_futures_contract_and_qty(data)

    default_price = default_price_for_contract(
        data, futuresContract(instrument_code, contract_date_yyyy_mm)
    )
    filled_price = get_input_from_user_and_convert_to_type(
        "Filled price",
        type_expected=float,
        allow_default=True,
        default_value=default_price,
    )
    fill_datetime = get_datetime_input(
        "Fill datetime", allow_default_datetime_of_now=True
    )
    commission = get_input_from_user_and_convert_to_type(
        "Commission", type_expected=float, allow_default=True, default_value=0.0
    )

    try:
        strategy_name = get_valid_strategy_name_from_user(
            data=data, source="positions", backup_source="config"
        )
    except missingData as md:
        print(f"Problem getting strategy name: {md}\n")
        return None

    default_account = data.config.get_element("broker_account")
    broker_account = get_input_from_user_and_convert_to_type(
        "Account ID",
        type_expected=str,
        allow_default=True,
        default_value=default_account,
    )

    broker_order = brokerOrder(
        strategy_name,
        instrument_code,
        contract_date_yyyy_mm,
        fill_qty,
        fill=fill_qty,
        algo_used="balance_trade",
        order_type=broker_balance_order_type,
        filled_price=filled_price,
        fill_datetime=fill_datetime,
        broker_account=broker_account,
        commission=commission,
        manual_fill=True,
        active=False,
    )

    return broker_order


def manually_get_futures_contract_and_qty(data: dataBlob) -> Tuple[str, str, int]:
    data_contracts = dataContracts(data)

    (
        instrument_code,
        contract_date_yyyy_mm,
    ) = get_valid_instrument_code_and_contractid_from_user(data)

    actual_expiry_date = data_contracts.get_actual_expiry(
        instrument_code, contract_date_yyyy_mm
    )
    actual_contract_date = actual_expiry_date.as_str()

    print("Actual contract expiry is %s" % str(actual_contract_date))

    fill_qty = get_input_from_user_and_convert_to_type(
        "Quantity ", type_expected=int, allow_default=False
    )

    return instrument_code, contract_date_yyyy_mm, fill_qty


def get_futures_contract_and_qty_to_close_position(
    data: dataBlob,
) -> Tuple[str, str, int]:
    diag_positions = diagPositions(data)
    contract_positions = diag_positions.get_all_current_contract_positions()
    print("Current contract positions in DB")
    print(contract_positions)

    while True:
        position_index = get_input_from_user_and_convert_to_type(
            "Which position to close?", type_expected=int, allow_default=False
        )
        if position_index not in range(len(contract_positions)):
            print("Not a valid row")
            continue
        else:
            break

    relevant_row = contract_positions[position_index]
    instrument_code = relevant_row.instrument_code
    contract_date_yyyy_mm = relevant_row.date_str
    fill_qty = int(-relevant_row.position)

    return instrument_code, contract_date_yyyy_mm, fill_qty


def default_price_for_contract(data: dataBlob, futures_contract: futuresContract):
    diag_prices = diagPrices(data)
    default_prices = diag_prices.get_merged_prices_for_contract_object(futures_contract)
    default_price = default_prices.return_final_prices().values[-1]

    return default_price


def create_instrument_balance_trade(data):
    print("Use to fix breaks between instrument strategy and contract level positions")
    strategy_name = get_valid_strategy_name_from_user(data=data, source="positions")
    instrument_code = get_valid_instrument_code_from_user(data)
    fill_qty = get_input_from_user_and_convert_to_type(
        "Quantity ", type_expected=int, allow_default=False
    )

    default_price = default_price_for_instrument(data, instrument_code)
    filled_price = get_input_from_user_and_convert_to_type(
        "Filled price",
        type_expected=float,
        allow_default=True,
        default_value=default_price,
    )
    fill_datetime = get_datetime_input(
        "Fill datetime", allow_default_datetime_of_now=True
    )

    instrument_order = instrumentOrder(
        strategy_name,
        instrument_code,
        fill_qty,
        fill=fill_qty,
        order_type=instrument_balance_order_type,
        filled_price=filled_price,
        fill_datetime=fill_datetime,
    )

    print(instrument_order)
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None

    stack_handler = stackHandlerCreateBalanceTrades(data)

    stack_handler.create_balance_instrument_trade(instrument_order)


def default_price_for_instrument(data: dataBlob, instrument_code: str) -> float:
    diag_prices = diagPrices(data)
    default_price = diag_prices.get_current_priced_contract_prices_for_instrument(
        instrument_code
    )

    return default_price.values[-1]


def create_manual_trade(data):
    print(
        "Create a trade which will then be executed by the system (so don't use this if you are doing your trades manually)"
    )
    print(
        "Use case is testing, or forcing an emergency close early (perhaps roll related)"
    )

    instrument_order = enter_manual_instrument_order(data)

    ans = input(
        "Would you also like to create a contract order (if not stack generator will auto generate)? (y/other)"
    )
    if ans == "y":
        contract_order = enter_manual_contract_order(data, instrument_order)
    else:
        contract_order = None

    print(instrument_order)
    print(contract_order)

    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None

    stack_handler = stackHandler(data)
    instrument_order_id = (
        stack_handler.instrument_stack.put_manual_order_on_stack_and_return_order_id(
            instrument_order
        )
    )
    if not isinstance(instrument_order_id, int):
        print(
            "Error condition %s couldn't place instrument order; not doing contract order either"
            % str(instrument_order_id)
        )
        return None
    if contract_order is not None:
        contract_order.parent = instrument_order_id
        contract_order_id = stack_handler.contract_stack.put_order_on_stack(
            contract_order
        )
        if not isinstance(contract_order_id, int):
            print(
                "Error condition %s couldn't place contract order; see if you can spawn it manually"
            )
            return None
        stack_handler.instrument_stack.add_children_to_order_without_existing_children(
            instrument_order_id, [contract_order_id]
        )

    print(
        "For instant execution, you may want to do menu [1] create orders, menu [12] create broker orders"
    )

    return None


def enter_manual_instrument_order(data):
    strategy_name = get_valid_strategy_name_from_user(data=data, source="positions")
    instrument_code = get_valid_instrument_code_from_user(data)
    qty = get_input_from_user_and_convert_to_type(
        "Quantity (-ve for sell, +ve for buy?)", type_expected=int, allow_default=False
    )
    possible_order_types = market_order_type.allowed_types()
    order_type = input("Order type (one of %s)?" % str(possible_order_types))
    limit_price = get_input_from_user_and_convert_to_type(
        "Limit price? (if you put None you can still add one to the contract order)",
        type_expected=float,
        default_value=None,
        default_str="None",
    )
    if limit_price is None:
        limit_contract = None
    else:
        print("Enter contractid that limit price is referenced to")
        _, contract_date = get_valid_instrument_code_and_contractid_from_user(
            data, instrument_code=instrument_code
        )
        limit_contract = contract_date

    instrument_order = instrumentOrder(
        strategy_name,
        instrument_code,
        qty,
        order_type=instrumentOrderType(order_type),
        limit_price=limit_price,
        limit_contract=limit_contract,
        manual_trade=True,
        roll_order=False,
    )

    return instrument_order


def enter_manual_contract_order(data, instrument_order):
    strategy_name = instrument_order.strategy_name
    instrument_code = instrument_order.instrument_code
    qty = instrument_order.trade

    leg_count = get_input_from_user_and_convert_to_type(
        "How many legs?", type_expected=int, default_value=1
    )
    contract_id_list = []
    for leg_idx in range(leg_count):
        print("Choose contract for leg %d" % leg_idx)
        _, contract_date = get_valid_instrument_code_and_contractid_from_user(
            data, instrument_code=instrument_code
        )
        contract_id_list.append(contract_date)

    trade_qty_list = []
    for trade_idx in range(leg_count):
        trade_qty = get_input_from_user_and_convert_to_type(
            "Enter quantity for leg %d" % trade_idx,
            type_expected=int,
            allow_default=False,
        )
        trade_qty_list.append(trade_qty)

    if sum(trade_qty_list) != sum(qty):
        print(
            "Sum of instrument quantity %s is different from sum of contract quantity %s"
            % (str(qty), str(trade_qty_list))
        )
        print("It's unlikely you meant to do this...")

    NO_ALGO = "None: allow system to allocate"
    list_of_algos = get_list_of_algos(data)
    algo_to_use = print_menu_of_values_and_get_response(
        list_of_algos, default_str=NO_ALGO
    )
    if algo_to_use == NO_ALGO:
        algo_to_use = ""

    limit_price = get_input_from_user_and_convert_to_type(
        "Limit price? (will override instrument order limit price, will be ignored by some algo types",
        type_expected=float,
        default_value=None,
        default_str="None",
    )

    order_type = map_instrument_order_type_to_contract_order_type(
        instrument_order.order_type
    )
    contract_order = contractOrder(
        strategy_name,
        instrument_code,
        contract_id_list,
        trade_qty_list,
        algo_to_use=algo_to_use,
        order_type=order_type,
        reference_price=None,
        limit_price=limit_price,
        manual_trade=True,
    )

    return contract_order


def generate_generic_manual_fill(data):
    stack = resolve_stack(data, exclude_instrument_stack=True)
    view_generic_stack(stack)
    order_id = get_input_from_user_and_convert_to_type(
        "Enter order ID", default_value="", default_str="Cancel"
    )
    if order_id == "":
        return None
    order = stack.get_order_with_id_from_stack(order_id)
    if order is missing_order:
        print("Order doesn't exist on stack")
        return None
    if len(order.trade) > 1:
        print("Can't manually fill spread orders; delete and replace with legs")
        return None
    if not no_children:
        print(
            "Don't manually fill order with children: can cause problems! Manually fill the child instead"
        )
        return None
    print("Order now %s" % str(order))
    fill_qty = get_input_from_user_and_convert_to_type(
        "Quantity to fill (must be less than or equal to %s)" % str(order.trade),
        type_expected=int,
        allow_default=True,
        default_value=order.trade,
    )
    if isinstance(fill_qty, int):
        fill_qty = [fill_qty]
    filled_price = get_input_from_user_and_convert_to_type(
        "Filled price", type_expected=float, allow_default=False
    )
    fill_datetime = get_datetime_input(
        "Fill datetime", allow_default_datetime_of_now=True
    )

    order = stack.get_order_with_id_from_stack(order_id)

    order.fill_order(
        fill_qty=fill_qty, filled_price=filled_price, fill_datetime=fill_datetime
    )

    stack.mark_as_manual_fill_for_order_id(order_id)

    stack_handler = stackHandler()
    if type(order) is brokerOrder:
        ## pass up and change positions
        stack_handler.apply_broker_order_fills_to_database(order_id, order)
    else:
        stack_handler.apply_contract_order_fill_to_database(order)

    order = stack.get_order_with_id_from_stack(order_id)
    print("Order now %s" % str(order))
    print("If stack process not running, your next job will be to pass fills upwards")


def generate_ib_orders(data):
    stack_handler = stackHandler(data)

    print("This will create broker orders and submit to IB")
    print("Contract orders:")
    view_contract_stack(data)
    contract_order_id = get_input_from_user_and_convert_to_type(
        "Which contract order ID?",
        type_expected=int,
        default_value="ALL",
        default_str="for all",
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None

    if contract_order_id == "ALL":
        stack_handler.create_broker_orders_from_contract_orders()
    else:
        stack_handler.create_broker_order_for_contract_order(contract_order_id)

    print(
        "If stack process not running, your next job will be to get the fills from IB"
    )


def create_fx_trade(data):
    data_broker = dataBroker(data)
    fx_balance = data_broker.broker_fx_balances()
    print("Current FX balances")
    print(fx_balance)
    print(
        "Remember to check how much you need for margin as you will be charged interest if insufficient"
    )
    default_account = data_broker.get_broker_account()
    broker_account = get_input_from_user_and_convert_to_type(
        "Account ID",
        type_expected=str,
        allow_default=True,
        default_value=default_account,
    )

    invalid = True
    while invalid:
        print("First currency")
        ccy1 = get_input_from_user_and_convert_to_type(
            "First currency",
            type_expected=str,
            allow_default=True,
            default_value=None,
            default_str="Cancel",
        )
        if ccy1 is None:
            return None
        ccy2 = get_input_from_user_and_convert_to_type(
            "Second currency", type_expected=str, default_value="USD"
        )
        if ccy1 == ccy2:
            print("%s==%s. Not allowed!" % (ccy1, ccy2))
            continue
        qty = get_input_from_user_and_convert_to_type(
            "Amount of trade in %s%s" % (ccy1, ccy2),
            type_expected=int,
            allow_default=False,
        )
        if qty < 0:
            print("Selling %d of %s, buying %s" % (qty, ccy1, ccy2))
        elif qty > 0:
            print("Buying %d of %s, selling %s" % (qty, ccy1, ccy2))

        ans = input("Are you sure that's right? Y-yes / other")
        if ans != "Y":
            continue
        else:
            break

    result = data_broker.broker_fx_market_order(
        qty, ccy1, account_id=broker_account, ccy2=ccy2
    )
    print("%s" % result)


def get_fills_from_broker(data):
    stack_handler = stackHandler(data)

    print("This will get any fills from the broker, and write them to the broker stack")
    print("Broker orders: (in database)")
    view_broker_stack(data)
    broker_order_id = get_input_from_user_and_convert_to_type(
        "Which broker order ID?",
        type_expected=int,
        default_value="ALL",
        default_str="for all",
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    if broker_order_id == "ALL":
        stack_handler.pass_fills_from_broker_to_broker_stack()
    else:
        stack_handler.apply_broker_fill_from_broker_to_broker_database(broker_order_id)

    print(
        "If stack process not running, your next job will be to pass fills from broker to contract stack"
    )


def pass_fills_upwards_from_broker(data):
    stack_handler = stackHandler(data)

    print(
        "This will process any fills applied to broker orders and pass them up to contract orders"
    )
    view_contract_stack(data)

    contract_order_id = get_input_from_user_and_convert_to_type(
        "Which order ID?", type_expected=int, default_value="ALL", default_str="for all"
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    if contract_order_id == "ALL":
        stack_handler.pass_fills_from_broker_up_to_contract()
    else:
        stack_handler.apply_broker_fills_to_contract_order(contract_order_id)

    print(
        "If stack process not running, your next job will be to pass fills from contract to instrument"
    )


def pass_fills_upwards_from_contracts(data):
    stack_handler = stackHandler(data)

    print(
        "This will process any fills applied to contract orders and pass them up to instrument orders"
    )
    view_contract_stack(data)
    contract_order_id = get_input_from_user_and_convert_to_type(
        "Which order ID?", type_expected=int, default_value="ALL", default_str="for all"
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    if contract_order_id == "ALL":
        stack_handler.pass_fills_from_contract_up_to_instrument()
    else:
        stack_handler.apply_contract_fill_to_instrument_order(contract_order_id)

    print(
        "If stack process not running, your next job will be to handle completed orders"
    )


def generate_force_roll_orders(data):
    stack_handler = stackHandler(data)

    print("This will generate force roll orders")
    instrument_code = input("Which instrument? <RETURN for default: All instruments>")
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    if instrument_code == "":
        stack_handler.generate_force_roll_orders()
    else:
        stack_handler.generate_force_roll_orders_for_instrument(instrument_code)


def handle_completed_orders(data):
    stack_handler = stackHandler(data)

    print("This will process any completed orders (all fills present)")
    view_instrument_stack(data)
    instrument_order_id = get_input_from_user_and_convert_to_type(
        "Which instrument order ID?",
        type_expected=int,
        default_value="ALL",
        default_str="All",
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None

    if instrument_order_id == "ALL":
        stack_handler.handle_completed_orders()
    else:
        stack_handler.handle_completed_instrument_order(instrument_order_id)


def order_view(data):
    stack = resolve_stack(data)
    if stack is None:
        return None
    view_generic_stack(stack)
    order_id = get_input_from_user_and_convert_to_type(
        "Order ID?", type_expected=int, allow_default=False
    )
    order = stack.get_order_with_id_from_stack(order_id)
    print("%s" % order.full_repr())

    return None


def order_locking(data):
    stack = resolve_stack(data)
    if stack is None:
        return None
    view_generic_stack(stack)
    order_id = get_input_from_user_and_convert_to_type(
        "Order ID ", type_expected=int, allow_default=False
    )
    order = stack.get_order_with_id_from_stack(order_id)
    print(order)

    if order.is_order_locked():
        ans = input("Unlock order? <y/other>")
        if ans == "y":
            stack._unlock_order_on_stack(order_id)
        else:
            return None

    else:
        ans = input("Lock order? <y/other>")
        if ans == "y":
            stack._lock_order_on_stack(order_id)
        else:
            return None

    return None


def clear_algo_on_order(data):
    stack_handler = stackHandler(data)
    stack = stack_handler.contract_stack
    view_generic_stack(stack)
    order_id = get_input_from_user_and_convert_to_type(
        "Order ID ", type_expected=int, allow_default=False
    )
    order = stack.get_order_with_id_from_stack(order_id)
    print("Controlled by %s; releasing now" % str(order.reference_of_controlling_algo))
    stack.release_order_from_algo_control(order_id)
    print("Released")


def resolve_stack(data, exclude_instrument_stack=False):
    stack_handler = stackHandler(data)
    if exclude_instrument_stack:
        request_str = "Broker stack [1], or Contract stack [2]?"
    else:
        request_str = "Broker stack [1], Contract stack [2] or instrument stack [3]?"

    ans = get_input_from_user_and_convert_to_type(
        request_str, type_expected=int, default_value=0, default_str="Exit"
    )
    if ans == 1:
        stack = stack_handler.broker_stack
    elif ans == 2:
        stack = stack_handler.contract_stack
    elif ans == 3 and not exclude_instrument_stack:
        stack = stack_handler.instrument_stack
    else:
        return None
    return stack


def delete_specific_order(data):
    stack = resolve_stack(data)
    if stack is None:
        return None
    view_generic_stack(stack)
    order_id = get_input_from_user_and_convert_to_type(
        "Order ID ", type_expected=int, allow_default=False
    )
    order = stack.get_order_with_id_from_stack(order_id)
    print(order)
    print("This will delete the order from the stack!")
    print("Make sure parents and children are also deleted or weird stuff will happen")
    ans = input("This will delete the order from the stack! Are you sure? (Y/other)")
    if ans == "Y":
        stack._remove_order_with_id_from_stack_no_checking(order_id)
        print(
            "Make sure parents and children are also deleted or weird stuff will happen"
        )

    return None


def delete_entire_stack(data):
    stack = resolve_stack(data)
    if stack is None:
        return None
    ans = input("This will delete the entire order stack! Are you sure? (Y/other)")
    if ans == "Y":
        stack._delete_entire_stack_without_checking_only_use_when_debugging()
    return None


def view_positions(data):
    data_broker = dataBroker(data)

    diag_positions = diagPositions(data)
    data_optimal = dataOptimalPositions(data)
    ans0 = data_optimal.get_pd_of_position_breaks()
    ans1 = diag_positions.get_all_current_strategy_instrument_positions()
    ans2 = diag_positions.get_all_current_contract_positions_with_db_expiries()
    ans3 = data_broker.get_all_current_contract_positions()
    print("Optimal vs actual")
    print(ans0.sort_values("breaks"))
    print("Strategy positions")
    print(ans1.as_pd_df().sort_values("instrument_code"))
    print("\n Contract level positions")
    print(ans2.as_pd_df().sort_values(["instrument_code", "contract_date"]))
    breaks = diag_positions.get_list_of_breaks_between_contract_and_strategy_positions()
    if len(breaks) > 0:
        print("\nBREAKS between strategy and contract positions: %s\n" % str(breaks))
    else:
        print("(No breaks positions consistent)")
    print("\n Broker positions")
    print(ans3.as_pd_df().sort_values(["instrument_code", "contract_date"]))
    breaks = data_broker.get_list_of_breaks_between_broker_and_db_contract_positions()
    if len(breaks) > 0:
        print(
            "\nBREAKS between broker and DB stored contract positions: %s\n"
            % str(breaks)
        )
    else:
        print("(No breaks positions consistent)")
    return None


def end_of_day(data):
    print(
        "Will cancel all broker orders, get outstanding fills, mark all orders as complete, update positions, remove everything from stack"
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    stack_handler = stackHandler(data)
    stack_handler.safe_stack_removal()

    return None


def not_defined(data):
    print("Function not yet defined")


def cancel_broker_order(data):
    view_broker_order_list(data)
    view_broker_stack(data)
    stack_handler = stackHandler(data)
    broker_order_id = get_input_from_user_and_convert_to_type(
        "Which order ID?", type_expected=int, default_value="ALL", default_str="for all"
    )
    ans = input("Are you sure? (Y/other)")
    if ans != "Y":
        return None
    if broker_order_id == "ALL":
        stack_handler.try_and_cancel_all_broker_orders_and_return_list_of_orders()
    else:
        stack_handler.cancel_broker_order_with_id_and_return_order(broker_order_id)


def instrument_locking(data):
    data_locks = dataLocks(data)
    list_of_locks = data_locks.get_list_of_locked_instruments()
    print("Locked %s" % list_of_locks)
    instrument_code = get_valid_instrument_code_from_user(data)
    if data_locks.is_instrument_locked(instrument_code):
        print("Unlock (careful probably locked for a reason, position mismatch!)")
        ans = input("[Y]es/no ?")
        if ans == "Y":
            data_locks.remove_lock_for_instrument(instrument_code)
    else:
        print("Lock (Won't create new orders until unlocked!)")
        ans = input("[Y]es/no ?")
        if ans == "Y":
            data_locks.add_lock_for_instrument(instrument_code)


def all_instrument_unlock(data):
    data_locks = dataLocks(data)
    list_of_locks = data_locks.get_list_of_locked_instruments()
    print("Locked %s" % list_of_locks)
    ans = input("Unlock everything [Y]es/no ?")
    if ans == "Y":
        stack_handler = stackHandler(data)
        stack_handler.clear_position_locks_no_checks()


dict_of_functions = {
    0: order_view,
    1: view_instrument_stack,
    2: view_contract_stack,
    3: view_broker_stack,
    4: view_broker_order_list,
    9: view_positions,
    10: spawn_contracts_from_instrument_orders,
    11: generate_force_roll_orders,
    12: generate_ib_orders,
    13: create_balance_trade,
    14: create_instrument_balance_trade,
    15: create_manual_trade,
    16: create_fx_trade,
    20: generate_generic_manual_fill,
    21: get_fills_from_broker,
    22: pass_fills_upwards_from_broker,
    23: pass_fills_upwards_from_contracts,
    24: handle_completed_orders,
    30: cancel_broker_order,
    31: not_defined,
    32: order_locking,
    33: instrument_locking,
    34: all_instrument_unlock,
    35: clear_algo_on_order,
    40: delete_entire_stack,
    41: delete_specific_order,
    42: end_of_day,
}


if __name__ == "__main__":
    interactive_order_stack()
