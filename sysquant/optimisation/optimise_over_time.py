import pandas as pd

from syscore.interactive.progress_bar import progressBar

from syslogging.logger import get_logger

from sysquant.fitting_dates import generate_fitting_dates, listOfFittingDates
from sysquant.optimisation.portfolio_optimiser import portfolioOptimiser
from sysquant.returns import returnsForOptimisation

from multiprocessing import Pool


class optimiseWeightsOverTime(object):
    def __init__(
        self,
        net_returns: returnsForOptimisation,
        date_method="expanding",
        rollyears=20,
        log=get_logger("optimiser"),
        **kwargs,
    ):
        # Generate time periods
        fit_dates = generate_fitting_dates(
            net_returns, date_method=date_method, rollyears=rollyears
        )
        optimiser_for_one_period = portfolioOptimiser(net_returns, log=log, **kwargs)
        self._fit_dates = fit_dates
        self._optimiser = optimiser_for_one_period
        self.n_threads = None
        if "n_threads" in kwargs:
            self.n_threads = kwargs["n_threads"]

    @property
    def fit_dates(self) -> listOfFittingDates:
        return self._fit_dates

    @property
    def correlation_estimator(self):
        return self.optimiser.correlation_estimator()

    @property
    def mean_estimator(self):
        return self.optimiser.mean_estimator()

    @property
    def stdev_estimator(self):
        return self.optimiser.stdev_estimator()

    @property
    def optimiser(self) -> portfolioOptimiser:
        return self._optimiser

    def weights(self) -> pd.DataFrame:
        fit_dates = self.fit_dates
        optimiser = self.optimiser

        progress = progressBar(len(fit_dates), "Optimising weights")

        weight_list = []

        # Now for each time period, estimate weights
        if self.n_threads is None:
            for fit_period in fit_dates:
                weight_dict = optimiser.calculate_weights_for_period(fit_period)
                weight_list.append(weight_dict)
                progress.iterate()
        else:
            with Pool(self.n_threads) as p:
                for i, weight_dict in enumerate(
                    p.imap(optimiser.calculate_weights_for_period, fit_dates), 1
                ):
                    weight_list.append(weight_dict)
                    print(i)
                    progress.iterate()

        weight_index = fit_dates.list_of_starting_periods()
        weights = pd.DataFrame(weight_list, index=weight_index)
        weights.sort_index(ascending=True, inplace=True)

        return weights
