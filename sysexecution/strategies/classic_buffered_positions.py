"""
Strategy specific execution code

For the classic buffered strategy we just compare actual positions with optimal positions, and generate orders
  accordingly

These are 'virtual' orders, because they are per instrument. We translate that to actual contracts downstream

Desired virtual orders have to be labelled with the desired type: limit, market,best-execution
"""

from collections import namedtuple

from sysdata.data_blob import dataBlob

from sysexecution.orders.instrument_orders import instrumentOrder, best_order_type
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.strategies.strategy_order_handling import orderGeneratorForStrategy

from sysobjects.production.tradeable_object import instrumentStrategy

from sysproduction.data.optimal_positions import dataOptimalPositions

optimalPositions = namedtuple(
    "optimalPositions",
    [
        "upper_positions",
        "lower_positions",
        "reference_prices",
        "reference_contracts",
        "ref_dates",
    ],
)


class orderGeneratorForBufferedPositions(orderGeneratorForStrategy):
    def get_required_orders(self) -> listOfOrders:
        strategy_name = self.strategy_name

        optimal_positions = self.get_optimal_positions()
        actual_positions = self.get_actual_positions_for_strategy()

        list_of_trades = list_of_trades_given_optimal_and_actual_positions(
            self.data, strategy_name, optimal_positions, actual_positions
        )

        return list_of_trades

    def get_optimal_positions(self) -> optimalPositions:
        data = self.data
        strategy_name = self.strategy_name

        optimal_position_data = dataOptimalPositions(data)

        list_of_instruments = optimal_position_data.get_list_of_instruments_for_strategy_with_optimal_position(
            strategy_name
        )

        list_of_instrument_strategies = [
            instrumentStrategy(
                strategy_name=strategy_name, instrument_code=instrument_code
            )
            for instrument_code in list_of_instruments
        ]

        optimal_positions = dict(
            [
                (
                    instrument_strategy.instrument_code,
                    optimal_position_data.get_current_optimal_position_for_instrument_strategy(
                        instrument_strategy
                    ),
                )
                for instrument_strategy in list_of_instrument_strategies
            ]
        )

        ref_dates = dict(
            [
                (instrument_code, opt_position.date)
                for instrument_code, opt_position in optimal_positions.items()
            ]
        )

        upper_positions = dict(
            [
                (instrument_code, opt_position.upper_position)
                for instrument_code, opt_position in optimal_positions.items()
            ]
        )
        lower_positions = dict(
            [
                (instrument_code, opt_position.lower_position)
                for instrument_code, opt_position in optimal_positions.items()
            ]
        )

        reference_prices = dict(
            [
                (instrument_code, opt_position.reference_price)
                for instrument_code, opt_position in optimal_positions.items()
            ]
        )

        reference_contracts = dict(
            [
                (instrument_code, opt_position.reference_contract)
                for instrument_code, opt_position in optimal_positions.items()
            ]
        )

        optimal_positions = optimalPositions(
            upper_positions=upper_positions,
            lower_positions=lower_positions,
            reference_prices=reference_prices,
            reference_contracts=reference_contracts,
            ref_dates=ref_dates,
        )
        return optimal_positions


def list_of_trades_given_optimal_and_actual_positions(
    data: dataBlob,
    strategy_name: str,
    optimal_positions: optimalPositions,
    actual_positions: dict,
) -> listOfOrders:
    upper_positions = optimal_positions.upper_positions
    list_of_instruments = upper_positions.keys()
    trade_list = [
        trade_given_optimal_and_actual_positions(
            data, strategy_name, instrument_code, optimal_positions, actual_positions
        )
        for instrument_code in list_of_instruments
    ]

    trade_list = listOfOrders(trade_list)

    return trade_list


def trade_given_optimal_and_actual_positions(
    data: dataBlob,
    strategy_name: str,
    instrument_code: str,
    optimal_positions: optimalPositions,
    actual_positions: dict,
) -> instrumentOrder:
    upper_for_instrument = optimal_positions.upper_positions[instrument_code]
    lower_for_instrument = optimal_positions.lower_positions[instrument_code]
    actual_for_instrument = actual_positions.get(instrument_code, 0.0)

    if actual_for_instrument < lower_for_instrument:
        required_position = round(lower_for_instrument)
    elif actual_for_instrument > upper_for_instrument:
        required_position = round(upper_for_instrument)
    else:
        required_position = actual_for_instrument

    # Might seem weird to have a zero order, but since orders can be updated
    # it makes sense

    trade_required = required_position - actual_for_instrument

    reference_contract = optimal_positions.reference_contracts[instrument_code]
    reference_price = optimal_positions.reference_prices[instrument_code]

    ref_date = optimal_positions.ref_dates[instrument_code]

    # No limit orders, just best execution
    order_required = instrumentOrder(
        strategy_name,
        instrument_code,
        trade_required,
        order_type=best_order_type,
        reference_price=reference_price,
        reference_contract=reference_contract,
        reference_datetime=ref_date,
    )

    data.log.debug(
        "Upper %.2f Lower %.2f Current %d Required position %d Required trade %d Reference price %f  for contract %s"
        % (
            upper_for_instrument,
            lower_for_instrument,
            actual_for_instrument,
            required_position,
            trade_required,
            reference_price,
            reference_contract,
        ),
        **order_required.log_attributes(),
        method="temp",
    )

    return order_required
