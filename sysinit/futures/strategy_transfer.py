"""
Code to transfer positions and/or capital from one strategy to another

"""

from syscore.constants import arg_not_supplied
from sysproduction.data.positions import diagPositions
from sysproduction.data.prices import diagPrices
from sysexecution.stack_handler.balance_trades import stackHandlerCreateBalanceTrades
from sysexecution.orders.instrument_orders import instrumentOrder, transfer_order_type
from sysdata.data_blob import dataBlob


def transfer_positions_between_strategies(
    old_strategy: str, new_strategy: str, instruments_to_transfer=arg_not_supplied
):
    data = dataBlob()
    old_positions = get_old_strategy_positions(data, old_strategy)
    if instruments_to_transfer is arg_not_supplied:
        instruments_to_transfer = list(old_positions.keys())

    ___ = [
        transfer_position_instrument(
            data,
            old_strategy=old_strategy,
            new_strategy=new_strategy,
            instrument_code=instrument_code,
            old_positions=old_positions,
        )
        for instrument_code in instruments_to_transfer
    ]


def get_old_strategy_positions(data: dataBlob, old_strategy: str):
    diag_positions = diagPositions(data)
    old_positions = diag_positions.get_dict_of_actual_positions_for_strategy(
        old_strategy
    )

    return old_positions


def transfer_position_instrument(
    data,
    old_strategy: str,
    new_strategy: str,
    instrument_code: str,
    old_positions: dict,
):
    current_position = old_positions[instrument_code]
    filled_price = get_last_price(data, instrument_code)
    balance_trade(
        data,
        strategy_name=old_strategy,
        instrument_code=instrument_code,
        filled_price=filled_price,
        fill_qty=-current_position,
    )

    balance_trade(
        data,
        strategy_name=new_strategy,
        instrument_code=instrument_code,
        filled_price=filled_price,
        fill_qty=current_position,
    )


def get_last_price(data: dataBlob, instrument_code: str):
    diag_prices = diagPrices(data)
    prices = diag_prices.get_adjusted_prices(instrument_code)

    return prices.ffill().values[-1]


def balance_trade(
    data, strategy_name: str, instrument_code: str, fill_qty: int, filled_price: float
):
    instrument_order = instrumentOrder(
        strategy_name,
        instrument_code,
        fill_qty,
        fill=fill_qty,
        order_type=transfer_order_type,
        filled_price=filled_price,
    )

    stack_handler = stackHandlerCreateBalanceTrades(data)

    stack_handler.create_balance_instrument_trade(instrument_order)
