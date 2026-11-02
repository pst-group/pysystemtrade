from copy import copy

from syscore.objects import resolve_function
from syscore.genutils import str2Bool

from syslogging.logger import get_logger

from sysquant.fitting_dates import fitDates
from sysquant.estimators.correlations import correlationEstimate
from sysquant.estimators.stdev_estimator import stdevEstimates
from sysquant.estimators.mean_estimator import meanEstimates
from sysquant.estimators.generic_estimator import genericEstimator

from sysquant.optimisation.optimisers.call_optimiser import optimiser_for_method
from sysquant.optimisation.weights import (
    portfolioWeights,
    one_over_n_weights_given_data,
    estimatesWithPortfolioWeights,
)
from sysquant.estimators.estimates import Estimates
from sysquant.optimisation.cleaning import clean_weights, get_must_have_dict_from_data

from sysquant.returns import returnsForOptimisation


class portfolioOptimiser:
    def __init__(
        self,
        net_returns: returnsForOptimisation,
        log=get_logger("optimiser"),
        method="handcraft",
        **weighting_args,
    ):
        self._net_returns = net_returns
        self._log = log
        self._weighting_args = weighting_args
        self._method = method

    @property
    def net_returns(self) -> returnsForOptimisation:
        return self._net_returns

    @property
    def frequency(self) -> str:
        return self.net_returns.frequency

    @property
    def length_adjustment(self) -> int:
        return self.net_returns.pooled_length

    @property
    def method(self) -> str:
        return self._method

    @property
    def weighting_args(self) -> dict:
        return self._weighting_args

    @property
    def cleaning(self) -> bool:
        return str2Bool(self.weighting_args["cleaning"])

    def calculate_weights_for_period(self, fit_period: fitDates) -> portfolioWeights:
        if fit_period.no_data:
            return one_over_n_weights_given_data(self.net_returns)

        weights = self.calculate_weights_given_data(fit_period)

        if self.cleaning:
            weights = self.clean_weights_for_period(weights, fit_period=fit_period)

        return weights

    def clean_weights_for_period(
        self, weights: portfolioWeights, fit_period: fitDates
    ) -> portfolioWeights:
        if fit_period.no_data:
            return weights

        data_subset = self.net_returns[fit_period.fit_start : fit_period.fit_end]
        must_haves = get_must_have_dict_from_data(data_subset)

        cleaned_weights = clean_weights(weights=weights, must_haves=must_haves)

        return cleaned_weights

    def calculate_weights_given_data(self, fit_period: fitDates) -> portfolioWeights:
        estimates_and_portfolio_weights = (
            self.get_weights_and_returned_estimates_for_period(fit_period)
        )
        portfolio_weights = estimates_and_portfolio_weights.weights

        return portfolio_weights

    def get_weights_and_returned_estimates_for_period(
        self, fit_period: fitDates
    ) -> estimatesWithPortfolioWeights:
        method = self.method
        weighting_args = self._weighting_args

        estimates = self.get_estimators_for_period(fit_period)
        estimates = copy(estimates)

        estimates_and_portfolio_weights = optimiser_for_method(
            method, estimates=estimates, **weighting_args
        )

        return estimates_and_portfolio_weights

    def get_estimators_for_period(self, fit_period: fitDates) -> Estimates:
        correlation = self.calculate_correlation_matrix_for_period(fit_period)
        mean = self.calculate_mean_for_period(fit_period)
        stdev = self.calculate_stdev_for_period(fit_period)
        data_length = self.data_length_for_period(fit_period)
        frequency = self.frequency

        estimates = Estimates(
            correlation=correlation,
            mean=mean,
            stdev=stdev,
            data_length=data_length,
            frequency=frequency,
        )

        return estimates

    def data_length_for_period(self, fit_period: fitDates) -> int:
        if fit_period.no_data:
            return 0

        return len(self.net_returns[fit_period.fit_start : fit_period.fit_end].index)

    def calculate_correlation_matrix_for_period(
        self, fit_period: fitDates
    ) -> correlationEstimate:
        estimator = self.correlation_estimator()
        estimate = estimator.calculate_estimate_for_period(fit_period)

        return estimate

    def calculate_stdev_for_period(self, fit_period: fitDates) -> stdevEstimates:
        estimator = self.stdev_estimator()
        estimate = estimator.calculate_estimate_for_period(fit_period)

        return estimate

    def calculate_mean_for_period(self, fit_period: fitDates) -> meanEstimates:
        estimator = self.mean_estimator()
        estimate = estimator.calculate_estimate_for_period(fit_period)

        return estimate

    def correlation_estimator(self):
        estimator = self._generic_estimator("correlation_estimate")

        return estimator

    def mean_estimator(self):
        estimator = self._generic_estimator("mean_estimate")

        return estimator

    def stdev_estimator(self):
        estimator = self._generic_estimator("vol_estimate")

        return estimator

    def _generic_estimator(
        self, param_entry: str = "mean_estimate"
    ) -> genericEstimator:
        store_as_name = "_" + param_entry
        estimator = getattr(self, store_as_name, None)
        if estimator is None:
            estimator = self._get_estimator(param_entry)
            setattr(self, store_as_name, estimator)

        return estimator

    def _get_estimator(self, param_entry="mean_estimate") -> genericEstimator:
        params = copy(self.weighting_args[param_entry])
        func_name = params.pop("func")
        function_object = resolve_function(func_name)

        data = self.net_returns
        params["length_adjustment"] = self.length_adjustment
        params["frequency"] = self.frequency

        estimator = function_object(data, **params)

        return estimator
