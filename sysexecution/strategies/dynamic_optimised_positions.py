"""
Strategy specific execution code

For dynamic optimised position we

These are 'virtual' orders, because they are per instrument. We translate that to actual contracts downstream

Desired virtual orders have to be labelled with the desired type: limit, market,best-execution
"""

import datetime
from copy import copy
from typing import List
from dataclasses import dataclass

from sysdata.data_blob import dataBlob

from sysexecution.orders.instrument_orders import instrumentOrder, best_order_type
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.strategies.strategy_order_handling import orderGeneratorForStrategy
from sysobjects.production.tradeable_object import instrumentStrategy
from sysobjects.production.optimal_positions import (
    optimalPositionWithDynamicCalculations,
)
from sysquant.estimators.correlations import correlationEstimate
from sysobjects.production.position_limits import NO_LIMIT
from sysobjects.production.override import (
    Override,
    CLOSE_OVERRIDE,
    NO_TRADE_OVERRIDE,
    REDUCE_ONLY_OVERRIDE,
)

from sysproduction.data.controls import dataPositionLimits
from sysproduction.data.optimal_positions import dataOptimalPositions
from sysproduction.data.controls import diagOverrides

from sysproduction.data.capital import capital_for_strategy
from sysproduction.data.risk import (
    get_correlation_matrix_for_instrument_returns,
    get_annualised_stdev_perc_of_instruments,
    covariance_from_stdev_and_correlation,
    get_perc_of_strategy_capital_for_instrument_per_contract,
)
from sysproduction.data.prices import get_cash_cost_in_base_for_instrument

from sysquant.estimators.covariance import covarianceEstimate
from sysquant.estimators.mean_estimator import meanEstimates
from sysquant.optimisation.weights import portfolioWeights

from systems.provided.dynamic_small_system_optimise.optimisation import (
    objectiveFunctionForGreedy,
    constraintsForDynamicOpt,
)
from systems.provided.dynamic_small_system_optimise.buffering import (
    speedControlForDynamicOpt,
)
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
    calculate_cost_per_notional_weight_as_proportion_of_capital,
)

ARBITRARILY_LARGE_CONTRACT_LIMIT = 999999999


class orderGeneratorForDynamicPositions(orderGeneratorForStrategy):
    def get_required_orders(self) -> listOfOrders:
        strategy_name = self.strategy_name

        optimised_positions_data = (
            self.calculate_write_and_return_optimised_positions_data()
        )
        current_positions = self.get_actual_positions_for_strategy()

        list_of_trades = list_of_trades_given_optimised_and_actual_positions(
            self.data,
            strategy_name=strategy_name,
            optimised_positions_data=optimised_positions_data,
            current_positions=current_positions,
        )

        return list_of_trades

    def calculate_write_and_return_optimised_positions_data(self) -> dict:
        ## We bring in
        previous_positions = self.get_actual_positions_for_strategy()
        raw_optimal_position_data = self.get_raw_optimal_position_data()

        data = self.data
        strategy_name = self.strategy_name

        optimised_positions_data = calculate_optimised_positions_data(
            data,
            strategy_name=strategy_name,
            previous_positions=previous_positions,
            raw_optimal_position_data=raw_optimal_position_data,
        )

        self.write_optimised_positions_data(optimised_positions_data)

        return optimised_positions_data

    def get_raw_optimal_position_data(self) -> dict:
        # This is the 'raw' data, positions pre-optimisation
        # dict of optimalPositionWithReference

        data = self.data
        strategy_name = self.strategy_name

        optimal_position_data = dataOptimalPositions(data)

        list_of_instruments = optimal_position_data.get_list_of_instruments_for_strategy_with_optimal_position(
            strategy_name, raw_positions=True
        )

        list_of_instrument_strategies = [
            instrumentStrategy(
                strategy_name=strategy_name, instrument_code=instrument_code
            )
            for instrument_code in list_of_instruments
        ]

        raw_optimal_positions = dict(
            [
                (
                    instrument_strategy.instrument_code,
                    optimal_position_data.get_current_optimal_position_for_instrument_strategy(
                        instrument_strategy, raw_positions=True
                    ),
                )
                for instrument_strategy in list_of_instrument_strategies
            ]
        )

        return raw_optimal_positions

    def write_optimised_positions_data(self, optimised_positions_data: dict):
        write_optimised_positions_data(
            self.data,
            strategy_name=self.strategy_name,
            optimised_positions_data=optimised_positions_data,
        )


def calculate_optimised_positions_data(
    data: dataBlob,
    previous_positions: dict,
    strategy_name: str,
    raw_optimal_position_data: dict,
) -> dict:
    data_for_objective = get_data_for_objective_instance(
        data,
        strategy_name=strategy_name,
        previous_positions=previous_positions,
        raw_optimal_position_data=raw_optimal_position_data,
    )

    objective_function = get_objective_instance(
        data=data, data_for_objective=data_for_objective
    )

    optimised_positions_data = get_optimised_positions_data_dict_given_optimisation(
        data_for_objective=data_for_objective, objective_function=objective_function
    )

    return optimised_positions_data


@dataclass
class dataForObjectiveInstance:
    positions_optimal: portfolioWeights
    covariance_matrix: covarianceEstimate
    per_contract_value: portfolioWeights
    costs: meanEstimates
    reference_prices: dict
    reference_contracts: dict
    reference_dates: dict
    previous_positions: portfolioWeights
    maximum_position_contracts: portfolioWeights
    constraints: constraintsForDynamicOpt
    speed_control: speedControlForDynamicOpt

    @property
    def weights_prior(self) -> portfolioWeights:
        return get_weights_given_positions(
            self.previous_positions, self.per_contract_value
        )

    @property
    def maximum_position_weights(self) -> portfolioWeights:
        return get_weights_given_positions(
            self.previous_positions, self.per_contract_value
        )

    @property
    def weights_optimal(self) -> portfolioWeights:
        return get_weights_given_positions(
            self.positions_optimal, self.per_contract_value
        )


def get_data_for_objective_instance(
    data: dataBlob,
    strategy_name: str,
    previous_positions: dict,
    raw_optimal_position_data: dict,
) -> dataForObjectiveInstance:
    list_of_instruments = list(raw_optimal_position_data.keys())
    data.log.debug("Getting data for optimisation")

    previous_positions_as_weights_object = portfolioWeights(previous_positions)
    previous_positions_as_weights_object = (
        previous_positions_as_weights_object.with_zero_weights_for_missing_keys(
            list_of_instruments
        )
    )

    positions_optimal = portfolioWeights(
        [
            (instrument_code, raw_position_entry.optimal_position)
            for instrument_code, raw_position_entry in raw_optimal_position_data.items()
        ]
    )

    reference_prices = dict(
        [
            (instrument_code, raw_position_entry.reference_price)
            for instrument_code, raw_position_entry in raw_optimal_position_data.items()
        ]
    )

    reference_contracts = dict(
        [
            (instrument_code, raw_position_entry.reference_contract)
            for instrument_code, raw_position_entry in raw_optimal_position_data.items()
        ]
    )

    reference_dates = dict(
        [
            (instrument_code, raw_position_entry.reference_date)
            for instrument_code, raw_position_entry in raw_optimal_position_data.items()
        ]
    )

    data.log.debug("Getting maximum positions")
    maximum_position_contracts = get_maximum_position_contracts(
        data, strategy_name=strategy_name, list_of_instruments=list_of_instruments
    )

    data.log.debug("Getting covariance matrix")

    data.log.debug("Getting per contract values")
    per_contract_value = get_per_contract_values(
        data, strategy_name=strategy_name, list_of_instruments=list_of_instruments
    )

    data.log.debug("Getting costs")
    costs = calculate_costs_per_portfolio_weight(
        data,
        per_contract_value=per_contract_value,
        strategy_name=strategy_name,
        list_of_instruments=list_of_instruments,
    )

    constraints = get_constraints(
        data, strategy_name=strategy_name, list_of_instruments=list_of_instruments
    )

    covariance_matrix = get_covariance_matrix_for_instrument_returns_for_optimisation(
        data, list_of_instruments=list_of_instruments
    )

    speed_control = get_speed_control(data)

    data_for_objective = dataForObjectiveInstance(
        positions_optimal=positions_optimal,
        per_contract_value=per_contract_value,
        covariance_matrix=covariance_matrix,
        costs=costs,
        reference_dates=reference_dates,
        reference_prices=reference_prices,
        reference_contracts=reference_contracts,
        previous_positions=previous_positions_as_weights_object,
        maximum_position_contracts=maximum_position_contracts,
        constraints=constraints,
        speed_control=speed_control,
    )

    return data_for_objective


def get_maximum_position_contracts(
    data, strategy_name: str, list_of_instruments: list
) -> portfolioWeights:
    maximum_position_contracts = dict(
        [
            (
                instrument_code,
                get_maximum_position_contracts_for_instrument_strategy(
                    data,
                    instrument_strategy=instrumentStrategy(
                        strategy_name=strategy_name, instrument_code=instrument_code
                    ),
                ),
            )
            for instrument_code in list_of_instruments
        ]
    )

    return portfolioWeights(maximum_position_contracts)


def get_maximum_position_contracts_for_instrument_strategy(
    data: dataBlob, instrument_strategy: instrumentStrategy
) -> int:
    override = get_override_for_instrument_strategy(data, instrument_strategy)
    if override == CLOSE_OVERRIDE:
        return 0

    position_limit_data = dataPositionLimits(data)
    maximum = (
        position_limit_data.get_maximum_position_contracts_for_instrument_strategy(
            instrument_strategy
        )
    )

    if maximum is NO_LIMIT:
        return ARBITRARILY_LARGE_CONTRACT_LIMIT

    return maximum


def get_per_contract_values(
    data: dataBlob, strategy_name: str, list_of_instruments: list
) -> portfolioWeights:
    per_contract_values = portfolioWeights(
        [
            (
                instrument_code,
                get_perc_of_strategy_capital_for_instrument_per_contract(
                    data, strategy_name=strategy_name, instrument_code=instrument_code
                ),
            )
            for instrument_code in list_of_instruments
        ]
    )

    return per_contract_values


def calculate_costs_per_portfolio_weight(
    data: dataBlob,
    per_contract_value: meanEstimates,
    strategy_name: str,
    list_of_instruments: list,
) -> meanEstimates:
    costs = meanEstimates(
        [
            (
                instrument_code,
                get_cost_per_notional_weight_as_proportion_of_capital(
                    data=data,
                    per_contract_value=per_contract_value,
                    strategy_name=strategy_name,
                    instrument_code=instrument_code,
                ),
            )
            for instrument_code in list_of_instruments
        ]
    )

    return costs


def get_cost_per_notional_weight_as_proportion_of_capital(
    data: dataBlob,
    per_contract_value: meanEstimates,
    strategy_name: str,
    instrument_code: str,
) -> float:
    capital = capital_for_strategy(data, strategy_name=strategy_name)

    cost_per_contract = get_cash_cost_in_base_for_instrument(
        data=data, instrument_code=instrument_code
    )
    cost_multiplier = 1.0  #### applied elsewhere
    notional_value_per_contract_as_proportion_of_capital = per_contract_value[
        instrument_code
    ]

    cost_per_notional_weight_as_proportion_of_capital = calculate_cost_per_notional_weight_as_proportion_of_capital(
        cost_per_contract=cost_per_contract,
        cost_multiplier=cost_multiplier,
        notional_value_per_contract_as_proportion_of_capital=notional_value_per_contract_as_proportion_of_capital,
        capital=capital,
    )

    return cost_per_notional_weight_as_proportion_of_capital


def get_constraints(data, strategy_name: str, list_of_instruments: list):
    no_trade_keys = get_no_trade_keys(
        data, strategy_name=strategy_name, list_of_instruments=list_of_instruments
    )

    reduce_only_keys = get_reduce_only_keys(
        data, strategy_name=strategy_name, list_of_instruments=list_of_instruments
    )

    constraints = constraintsForDynamicOpt(
        no_trade_keys=no_trade_keys, reduce_only_keys=reduce_only_keys
    )

    return constraints


def get_no_trade_keys(
    data: dataBlob, strategy_name: str, list_of_instruments: list
) -> list:
    no_trade_keys = [
        instrument_code
        for instrument_code in list_of_instruments
        if get_override_for_instrument_strategy(
            data,
            instrument_strategy=instrumentStrategy(
                instrument_code=instrument_code, strategy_name=strategy_name
            ),
        )
        == NO_TRADE_OVERRIDE
    ]

    return no_trade_keys


def get_reduce_only_keys(
    data: dataBlob, strategy_name: str, list_of_instruments: list
) -> list:
    no_trade_keys = [
        instrument_code
        for instrument_code in list_of_instruments
        if get_override_for_instrument_strategy(
            data,
            instrument_strategy=instrumentStrategy(
                instrument_code=instrument_code, strategy_name=strategy_name
            ),
        )
        == REDUCE_ONLY_OVERRIDE
    ]

    return no_trade_keys


def get_override_for_instrument_strategy(
    data: dataBlob, instrument_strategy: instrumentStrategy
) -> Override:
    diag_overrides = diagOverrides(data)
    override = diag_overrides.get_cumulative_override_for_instrument_strategy(
        instrument_strategy
    )

    return override


def get_covariance_matrix_for_instrument_returns_for_optimisation(
    data: dataBlob, list_of_instruments: list
) -> covarianceEstimate:
    corr_matrix = get_correlation_matrix_for_instrument_returns(
        data, list_of_instruments
    )

    stdev_estimate = get_annualised_stdev_perc_of_instruments(
        data, instrument_list=list_of_instruments
    )
    covariance = covariance_from_stdev_and_correlation(
        stdev_estimate=stdev_estimate, correlation_estimate=corr_matrix
    )

    return covariance


def get_correlation_matrix_with_shrinkage(
    data, list_of_instruments: list
) -> correlationEstimate:
    # FIXME feels like this ought to be done inside the DO code as violates DRY
    system_config = get_config_parameters(data)
    shrinkage_corr = system_config["shrink_instrument_returns_correlation"]
    corr_matrix = get_correlation_matrix_for_instrument_returns(
        data, list_of_instruments
    )

    corr_matrix_shrunk = copy(
        corr_matrix.shrink_to_offdiag(shrinkage_corr=shrinkage_corr, offdiag=0.0)
    )

    return corr_matrix_shrunk


def get_speed_control(data):
    system_config = get_config_parameters(data)

    try:
        trade_shadow_cost = system_config["shadow_cost"]
        tracking_error_buffer = system_config["tracking_error_buffer"]
        cost_multiplier = system_config["cost_multiplier"]
    except KeyError:
        raise Exception(
            "config.small_system doesn't include buffer or shadow cost or cost_multiplier: you've probably messed up your private_config"
        )

    data.log.debug(
        "Shadow cost %f multiply by cost multiplier %f) = %f"
        % (trade_shadow_cost, cost_multiplier, trade_shadow_cost * cost_multiplier)
    )
    data.log.debug("Tracking error buffer %f" % tracking_error_buffer)

    speed_control = speedControlForDynamicOpt(
        trade_shadow_cost=trade_shadow_cost * cost_multiplier,
        tracking_error_buffer=tracking_error_buffer,
    )

    return speed_control


def get_config_parameters(data: dataBlob) -> dict:
    config = data.config
    system_config = config.get_element("small_system")
    return system_config


def get_objective_instance(
    data: dataBlob, data_for_objective: dataForObjectiveInstance
) -> objectiveFunctionForGreedy:
    objective_function = objectiveFunctionForGreedy(
        log=data.log,
        contracts_optimal=data_for_objective.positions_optimal,
        covariance_matrix=data_for_objective.covariance_matrix,
        costs=data_for_objective.costs,
        speed_control=data_for_objective.speed_control,
        previous_positions=data_for_objective.previous_positions,
        constraints=data_for_objective.constraints,
        maximum_positions=data_for_objective.maximum_position_contracts,
        per_contract_value=data_for_objective.per_contract_value,
    )

    return objective_function


def get_optimised_positions_data_dict_given_optimisation(
    data_for_objective: dataForObjectiveInstance,
    objective_function: objectiveFunctionForGreedy,
) -> dict:
    optimised_positions = objective_function.optimise_positions()
    optimised_positions = optimised_positions.replace_weights_with_ints()

    optimised_position_weights = get_weights_given_positions(
        optimised_positions, per_contract_value=data_for_objective.per_contract_value
    )
    instrument_list: List[str] = objective_function.keys_with_valid_data

    minima_weights = portfolioWeights.from_weights_and_keys(
        list_of_keys=instrument_list,
        list_of_weights=list(objective_function.minima_as_np),
    )
    maxima_weights = portfolioWeights.from_weights_and_keys(
        list_of_keys=instrument_list,
        list_of_weights=list(objective_function.maxima_as_np),
    )
    starting_weights = portfolioWeights.from_weights_and_keys(
        list_of_keys=instrument_list,
        list_of_weights=list(objective_function.starting_weights_as_np),
    )

    data_dict = dict(
        [
            (
                instrument_code,
                get_optimal_position_entry_with_calcs_for_code(
                    instrument_code=instrument_code,
                    data_for_objective=data_for_objective,
                    optimised_position_weights=optimised_position_weights,
                    optimised_positions=optimised_positions,
                    maxima_weights=maxima_weights,
                    starting_weights=starting_weights,
                    minima_weights=minima_weights,
                ),
            )
            for instrument_code in instrument_list
        ]
    )

    return data_dict


def get_positions_given_weights(
    weights: portfolioWeights, per_contract_value: portfolioWeights
) -> portfolioWeights:
    positions = weights / per_contract_value
    positions = positions.replace_weights_with_ints()

    return positions


def get_weights_given_positions(
    positions: portfolioWeights, per_contract_value: portfolioWeights
) -> portfolioWeights:
    weights = positions * per_contract_value

    return weights


def get_optimal_position_entry_with_calcs_for_code(
    instrument_code: str,
    data_for_objective: dataForObjectiveInstance,
    optimised_position_weights: portfolioWeights,
    optimised_positions: portfolioWeights,
    minima_weights: portfolioWeights,
    maxima_weights: portfolioWeights,
    starting_weights: portfolioWeights,
) -> optimalPositionWithDynamicCalculations:
    return optimalPositionWithDynamicCalculations(
        date=datetime.datetime.now(),
        reference_price=data_for_objective.reference_prices[instrument_code],
        reference_contract=data_for_objective.reference_contracts[instrument_code],
        reference_date=data_for_objective.reference_dates[instrument_code],
        optimal_position=data_for_objective.positions_optimal[instrument_code],
        weight_per_contract=data_for_objective.per_contract_value[instrument_code],
        previous_position=data_for_objective.previous_positions[instrument_code],
        previous_weight=data_for_objective.weights_prior[instrument_code],
        reduce_only=instrument_code in data_for_objective.constraints.reduce_only_keys,
        dont_trade=instrument_code in data_for_objective.constraints.no_trade_keys,
        position_limit_contracts=data_for_objective.maximum_position_contracts[
            instrument_code
        ],
        position_limit_weight=data_for_objective.maximum_position_weights[
            instrument_code
        ],
        optimum_weight=data_for_objective.weights_optimal[instrument_code],
        minimum_weight=minima_weights[instrument_code],
        maximum_weight=maxima_weights[instrument_code],
        start_weight=starting_weights[instrument_code],
        optimised_weight=optimised_position_weights[instrument_code],
        optimised_position=optimised_positions[instrument_code],
    )


def write_optimised_positions_data(
    data: dataBlob, strategy_name: str, optimised_positions_data: dict
):
    for instrument_code, optimised_position_entry in optimised_positions_data.items():
        write_optimised_positions_data_for_code(
            data,
            strategy_name=strategy_name,
            instrument_code=instrument_code,
            optimised_position_entry=optimised_position_entry,
        )


def write_optimised_positions_data_for_code(
    data: dataBlob,
    strategy_name: str,
    instrument_code: str,
    optimised_position_entry: optimalPositionWithDynamicCalculations,
):
    data_optimal_positions = dataOptimalPositions(data)
    instrument_strategy = instrumentStrategy(
        instrument_code=instrument_code, strategy_name=strategy_name
    )

    data.log.debug(
        "Adding optimal position for %s: %s"
        % (str(instrument_strategy), optimised_position_entry.verbose_repr())
    )
    data_optimal_positions.update_optimal_position_for_instrument_strategy(
        instrument_strategy=instrument_strategy, position_entry=optimised_position_entry
    )


def list_of_trades_given_optimised_and_actual_positions(
    data: dataBlob,
    strategy_name: str,
    optimised_positions_data: dict,
    current_positions: dict,
) -> listOfOrders:
    list_of_instruments = optimised_positions_data.keys()
    trade_list = [
        trade_given_optimal_and_actual_positions(
            data,
            strategy_name=strategy_name,
            instrument_code=instrument_code,
            optimised_position_entry=optimised_positions_data[instrument_code],
            current_position=current_positions.get(instrument_code, 0),
        )
        for instrument_code in list_of_instruments
    ]

    trade_list = listOfOrders(trade_list)

    return trade_list


def trade_given_optimal_and_actual_positions(
    data: dataBlob,
    strategy_name: str,
    instrument_code: str,
    optimised_position_entry: optimalPositionWithDynamicCalculations,
    current_position: int,
) -> instrumentOrder:
    optimised_position = optimised_position_entry.optimised_position

    trade_required = optimised_position - current_position

    reference_contract = optimised_position_entry.reference_contract
    reference_price = optimised_position_entry.reference_price
    reference_date = optimised_position_entry.reference_date

    # No limit orders, just best execution
    order_required = instrumentOrder(
        strategy_name,
        instrument_code,
        trade_required,
        order_type=best_order_type,
        reference_price=reference_price,
        reference_contract=reference_contract,
        reference_datetime=reference_date,
    )

    data.log.debug(
        "Current %d Required position %d Required trade %d Reference price %f  for contract %s"
        % (
            current_position,
            optimised_position,
            trade_required,
            reference_price,
            reference_contract,
        ),
        **order_required.log_attributes(),
        method="temp",
    )

    return order_required
