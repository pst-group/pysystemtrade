import pandas as pd
from syslogging.logger import get_logger
from sysquant.optimisation.pre_processing import returnsPreProcessor
from sysquant.optimisation.optimise_over_time import optimiseWeightsOverTime
from sysquant.optimisation.SR_adjustment import adjust_dataframe_of_weights_for_SR_costs
from sysquant.returns import returnsForOptimisation, SINGLE_NAME


class genericOptimiser(object):
    def __init__(
        self,
        returns_pre_processor: returnsPreProcessor,
        asset_name: str = SINGLE_NAME,
        log=get_logger("optimiser"),
        **weighting_params,
    ):
        net_returns = returns_pre_processor.get_net_returns(asset_name)

        self._net_returns = net_returns
        self._weighting_params = weighting_params
        self._log = log
        self._returns_processor = returns_pre_processor
        self._asset_name = asset_name

    @property
    def net_returns(self) -> returnsForOptimisation:
        return self._net_returns

    @property
    def log(self):
        return self._log

    @property
    def apply_cost_weights(self) -> bool:
        apply_cost_weight = self.weighting_params["apply_cost_weight"]
        return apply_cost_weight

    @property
    def asset_name(self) -> str:
        return self._asset_name

    @property
    def returns_processor(self) -> returnsPreProcessor:
        return self._returns_processor

    @property
    def weighting_params(self) -> dict:
        return self._weighting_params

    def weights(self) -> pd.DataFrame:
        raw_weights = self.raw_weights()
        weights = self.weights_post_processing(raw_weights)

        ## apply cost weight
        return weights

    @property
    def fit_dates(self) -> list:
        return self.optimiser.fit_dates

    @property
    def correlation_estimator(self):
        return self.optimiser.correlation_estimator

    @property
    def mean_estimator(self):
        return self.optimiser.mean_estimator

    @property
    def stdev_estimator(self):
        return self.optimiser.stdev_estimator

    def raw_weights(self) -> pd.DataFrame:
        return self.optimiser.weights()

    @property
    def optimiser(self) -> optimiseWeightsOverTime:
        optimiser = optimiseWeightsOverTime(
            self.net_returns, log=self.log, **self.weighting_params
        )
        return optimiser

    def weights_post_processing(self, weights: pd.DataFrame) -> pd.DataFrame:
        # apply cost weights
        # cleaning is done elsewhere

        if self.apply_cost_weights:
            asset_name = self.asset_name
            costs_dict = (
                self.returns_processor.get_dict_of_unadjusted_cost_SR_for_asset_name(
                    asset_name
                )
            )
            weights = adjust_dataframe_of_weights_for_SR_costs(
                weights=weights, costs_dict=costs_dict
            )

        return weights
