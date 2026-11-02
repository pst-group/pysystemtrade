from typing import Callable
from dataclasses import dataclass

import numpy as np

from syscore.constants import arg_not_supplied

from syslogging.logger import get_logger

from sysquant.estimators.covariance import covarianceEstimate
from sysquant.estimators.mean_estimator import meanEstimates
from sysquant.optimisation.weights import portfolioWeights
from systems.provided.dynamic_small_system_optimise.buffering import (
    speedControlForDynamicOpt,
    calculate_adjustment_factor,
    adjust_weights_with_factor,
)
from systems.provided.dynamic_small_system_optimise.data_for_optimisation import (
    dataForOptimisation,
)
from systems.provided.dynamic_small_system_optimise.greedy_algo import (
    greedy_algo_across_integer_values,
)


@dataclass
class constraintsForDynamicOpt:
    reduce_only_keys: list = arg_not_supplied
    no_trade_keys: list = arg_not_supplied
    long_only_keys: list = arg_not_supplied


class objectiveFunctionForGreedy:
    def __init__(
        self,
        contracts_optimal: portfolioWeights,
        covariance_matrix: covarianceEstimate,
        per_contract_value: portfolioWeights,
        costs: meanEstimates,
        speed_control: speedControlForDynamicOpt,
        previous_positions: portfolioWeights = arg_not_supplied,
        constraints: constraintsForDynamicOpt = arg_not_supplied,
        maximum_positions: portfolioWeights = arg_not_supplied,
        log=get_logger("objectiveFunctionForGreedy"),
        constraint_function: Callable = arg_not_supplied,
    ):
        self.covariance_matrix = covariance_matrix
        self.per_contract_value = per_contract_value
        self.costs = costs

        self.speed_control = speed_control
        self.constraints = constraints

        weights_optimal = contracts_optimal * per_contract_value

        self.weights_optimal = weights_optimal
        self.contracts_optimal = contracts_optimal

        if previous_positions is arg_not_supplied:
            weights_prior = arg_not_supplied
        else:
            previous_positions = previous_positions.with_zero_weights_instead_of_nan()
            weights_prior = previous_positions * per_contract_value

        self.weights_prior = weights_prior
        self.previous_positions = previous_positions

        if maximum_positions is arg_not_supplied:
            maximum_position_weights = arg_not_supplied
        else:
            maximum_position_weights = maximum_positions * per_contract_value

        self.maximum_position_weights = maximum_position_weights

        self.maximum_positions = maximum_positions
        self.constraint_function = constraint_function
        self.log = log

    def optimise_positions(self) -> portfolioWeights:
        optimal_weights = self.optimise_weights()
        optimal_positions = optimal_weights / self.per_contract_value

        optimal_positions = optimal_positions.replace_weights_with_ints()

        return optimal_positions

    def optimise_weights(self) -> portfolioWeights:
        optimal_weights_without_missing_items_as_np = self.optimise_np_for_valid_keys()

        optimal_weights_without_missing_items_as_list = list(
            optimal_weights_without_missing_items_as_np
        )

        optimal_weights = portfolioWeights.from_weights_and_keys(
            list_of_keys=self.keys_with_valid_data,
            list_of_weights=optimal_weights_without_missing_items_as_list,
        )

        optimal_weights_for_all_keys = (
            optimal_weights.with_zero_weights_for_missing_keys(
                list(self.weights_optimal.keys())
            )
        )

        return optimal_weights_for_all_keys

    def optimise_np_for_valid_keys(self) -> np.array:
        tracking_error_of_prior_smaller_than_buffer = (
            self.is_tracking_error_of_prior_smaller_than_buffer()
        )

        if tracking_error_of_prior_smaller_than_buffer:
            return self.weights_prior_as_np_replace_nans_with_zeros

        weights_as_np = self.optimise_np_with_large_tracking_error()

        return weights_as_np

    def is_tracking_error_of_prior_smaller_than_buffer(self) -> bool:
        ## is the prior portfolio pretty close to optimal already??
        if self.no_prior_positions_provided:
            return False

        tracking_error = self.tracking_error_of_prior_weights()
        tracking_error_buffer = self.speed_control.tracking_error_buffer
        tracking_error_smaller_than_buffer = tracking_error < tracking_error_buffer

        if tracking_error_smaller_than_buffer:
            self.log.debug(
                "Tracking error of current positions vs unrounded optimal is %.4f "
                "smaller than buffer %.4f, no trades needed"
                % (tracking_error, tracking_error_buffer)
            )
        else:
            self.log.debug(
                "Tracking error of current positions vs unrounded optimal is %.4f "
                "larger than buffer %.4f" % (tracking_error, tracking_error_buffer)
            )

        return tracking_error_smaller_than_buffer

    def tracking_error_of_prior_weights(self) -> float:
        prior_weights = self.weights_prior_as_np_replace_nans_with_zeros
        tracking_error = self.tracking_error_against_optimal(prior_weights)

        return tracking_error

    def optimise_np_with_large_tracking_error(self) -> np.array:
        optimised_weights_as_np = self.get_optimisation_results_raw()
        self.log_optimised_results(
            optimised_weights_as_np, "Optimised (before adjustment)"
        )

        optimised_weights_as_np_track_adjusted = (
            self.adjust_weights_for_size_of_tracking_error(optimised_weights_as_np)
        )

        self.log_optimised_results(
            optimised_weights_as_np_track_adjusted, "Optimised (after adjustment)"
        )

        return optimised_weights_as_np_track_adjusted

    def get_optimisation_results_raw(self):
        optimised_weights_as_np = greedy_algo_across_integer_values(self)

        if all(optimised_weights_as_np == 0):
            # pretty unlikely
            self.log.error("All zeros in optimisation, using prior weights")
            return self.weights_prior_as_np_replace_nans_with_zeros

        return optimised_weights_as_np

    def log_optimised_results(
        self, optimised_weights_as_np: np.array, label: str = "Optimised"
    ):
        tracking_error = self.tracking_error_against_optimal(optimised_weights_as_np)
        costs = self.calculate_costs(optimised_weights_as_np)

        self.log.debug(
            "%s weights, tracking error vs unrounded optimal %.4f costs %.4f"
            % (label, tracking_error, costs)
        )

    def adjust_weights_for_size_of_tracking_error(
        self, optimised_weights_as_np: np.array
    ) -> np.array:
        if self.no_prior_positions_provided:
            return optimised_weights_as_np

        prior_weights_as_np = self.weights_prior_as_np_replace_nans_with_zeros
        tracking_error_of_prior = self.tracking_error_against_passed_weights(
            prior_weights_as_np, optimised_weights_as_np
        )
        speed_control = self.speed_control
        per_contract_value_as_np = self.per_contract_value_as_np

        adj_factor = calculate_adjustment_factor(
            tracking_error_of_prior=tracking_error_of_prior, speed_control=speed_control
        )

        self.log.debug(
            "Tracking error current vs optimised %.4f vs buffer %.4f doing %.3f of adjusting trades (0 means no trade)"
            % (tracking_error_of_prior, speed_control.tracking_error_buffer, adj_factor)
        )

        if adj_factor <= 0:
            return prior_weights_as_np

        new_optimal_weights_as_np = adjust_weights_with_factor(
            optimised_weights_as_np=optimised_weights_as_np,
            adj_factor=adj_factor,
            per_contract_value_as_np=per_contract_value_as_np,
            prior_weights_as_np=prior_weights_as_np,
        )

        return new_optimal_weights_as_np

    def evaluate(self, weights: np.array) -> float:
        track_error = self.tracking_error_against_optimal(weights)
        trade_costs = self.calculate_costs(weights)
        constraint_function_value = self.constraint_function_value(weights)

        return track_error + trade_costs + constraint_function_value

    def tracking_error_against_optimal(self, weights: np.array) -> float:
        track_error = self.tracking_error_against_passed_weights(
            weights, self.weights_optimal_as_np
        )

        return track_error

    def tracking_error_against_passed_weights(
        self, weights: np.array, optimal_weights: np.array
    ) -> float:
        solution_gap = weights - optimal_weights
        track_error_var = solution_gap.dot(self.covariance_matrix_as_np).dot(
            solution_gap
        )

        if track_error_var < 0:
            ## can happen in some corner cases due to way covar estimated
            ## this effectively means we won't trade until problem solved seems reasonable
            msg = "Negative covariance when optimising!"
            self.log.critical(msg)
            raise Exception(msg)

        track_error_std = track_error_var**0.5

        return track_error_std

    def calculate_costs(self, weights: np.array) -> float:
        if self.no_prior_positions_provided:
            return 0.0
        trade_gap = weights - self.weights_prior_as_np_replace_nans_with_zeros
        costs_per_trade = self.costs_as_np
        trade_shadow_cost = self.trade_shadow_cost
        trade_costs = sum(abs(costs_per_trade * trade_gap * trade_shadow_cost))

        if np.isnan(trade_costs):
            raise Exception(
                "Trade costs are zero, most likely have a zero cost somewhere"
            )

        return trade_costs

    @property
    def trade_shadow_cost(self):
        return self.speed_control.trade_shadow_cost

    def constraint_function_value(self, weights: np.array):
        ## Function that will return a big number if constraints aren't satisfied
        if self.constraint_function == arg_not_supplied:
            return 0.0

        portfolio_weights = portfolioWeights.from_weights_and_keys(
            list_of_weights=weights, list_of_keys=self.keys_with_valid_data
        )
        constraint_function = self.constraint_function
        value = constraint_function(portfolio_weights)

        return value

    @property
    def starting_weights_as_np(self) -> np.array:
        return self.input_data.starting_weights_as_np

    @property
    def no_prior_positions_provided(self) -> bool:
        return self.previous_positions is arg_not_supplied

    @property
    def maxima_as_np(self) -> np.array:
        return self.input_data.maxima_as_np

    @property
    def minima_as_np(self) -> np.array:
        return self.input_data.minima_as_np

    @property
    def keys_with_valid_data(self) -> list:
        return self.input_data.keys_with_valid_data

    @property
    def weights_optimal_as_np(self) -> np.array:
        return self.input_data.weights_optimal_as_np

    @property
    def per_contract_value_as_np(self) -> np.array:
        return self.input_data.per_contract_value_as_np

    @property
    def weights_prior_as_np_replace_nans_with_zeros(self) -> np.array:
        return self.input_data.weights_prior_as_np_replace_nans_with_zeros

    @property
    def covariance_matrix_as_np(self) -> np.array:
        return self.input_data.covariance_matrix_as_np

    @covariance_matrix_as_np.setter
    def covariance_matrix_as_np(self, new_array: np.array) -> np.array:
        self.input_data.covariance_matrix_as_np = new_array

    @property
    def costs_as_np(self) -> np.array:
        return self.input_data.costs_as_np

    @property
    def direction_as_np(self) -> np.array:
        return self.input_data.direction_as_np

    @property
    def input_data(self):
        input_data = getattr(self, "_input_data", None)
        if input_data is None:
            input_data = dataForOptimisation(self)
            self._input_data = input_data

        return input_data
