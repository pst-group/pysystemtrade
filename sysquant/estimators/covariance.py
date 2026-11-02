import numpy as np
from syscore.constants import arg_not_supplied
from sysquant.estimators.correlations import correlationEstimate
from sysquant.estimators.stdev_estimator import stdevEstimates
from sysquant.optimisation.weights import portfolioWeights
from sysquant.optimisation.shared import sigma_from_corr_and_std


class covarianceEstimate(correlationEstimate):
    def clean_correlations(self, must_haves: list = arg_not_supplied, offdiag=0.99):
        raise Exception("Can't clean covariance matrix")

    def shrink(self, prior_corr: "correlationEstimate", shrinkage_corr: float = 1.0):
        raise Exception("Can't shrink covariance matrix")

    def boring_corr_matrix(self, offdiag: float = 0.99, diag: float = 1.0):
        raise Exception("Can't have boring covariance")

    def average_corr(self) -> float:
        raise Exception("Can't do averaging with covariance")

    def assets_with_missing_data(self) -> list:
        na_row_count = self.as_pd().isna().all(axis=1)
        return [keyname for keyname in na_row_count.keys() if na_row_count[keyname]]


def covariance_from_stdev_and_correlation(
    correlation_estimate: correlationEstimate, stdev_estimate: stdevEstimates
) -> covarianceEstimate:
    all_assets = set(list(correlation_estimate.columns) + stdev_estimate.list_of_keys())
    list_of_assets_with_data = list(
        set(correlation_estimate.assets_with_data()).intersection(
            set(stdev_estimate.assets_with_data())
        )
    )
    assets_without_data = list(all_assets.difference(list_of_assets_with_data))

    aligned_stdev_list = stdev_estimate.list_in_key_order(list_of_assets_with_data)
    aligned_corr_list = correlation_estimate.subset(list_of_assets_with_data)
    sigma = sigma_from_corr_and_std(aligned_stdev_list, aligned_corr_list.values)

    cov_assets_with_data = covarianceEstimate(sigma, columns=list_of_assets_with_data)

    cov = cov_assets_with_data.add_assets_with_nan_values(assets_without_data)

    return cov


def get_annualised_risk(
    std_dev: stdevEstimates, cmatrix: correlationEstimate, weights: portfolioWeights
) -> float:
    weights_as_np = weights.as_np()
    std_dev_as_np = std_dev.as_np()
    cmatrix_as_np = cmatrix.as_np()

    std_dev_as_np, cmatrix_as_np, weights_as_np = clean_values(
        std_dev_as_np, cmatrix_as_np, weights_as_np
    )
    sigma = sigma_from_corr_and_std(std_dev_as_np, cmatrix_as_np)

    portfolio_variance = weights_as_np.dot(sigma).dot(weights_as_np.transpose())
    portfolio_std = portfolio_variance**0.5

    return portfolio_std


def clean_values(std_dev: np.array, cmatrix: np.array, weights: np.array):
    cmatrix = np.where(np.isnan(cmatrix), 1.0, cmatrix)
    weights = np.where(np.isnan(weights), 0.0, weights)
    std_dev = np.where(np.isnan(std_dev), 100.0, std_dev)

    return std_dev, cmatrix, weights
