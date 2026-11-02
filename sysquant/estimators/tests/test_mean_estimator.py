"""
Created on 17 May 2026

@author: javierdejesusda
"""

import datetime
import unittest

import numpy as np
import pandas as pd

from sysquant.estimators.mean_estimator import exponentialMeans, meanEstimates
from sysquant.fitting_dates import fitDates


class Test(unittest.TestCase):
    def test_estimate_before_any_data_returns_empty_mean(self):
        index = pd.date_range(datetime.datetime(2020, 1, 1), periods=50, freq="W")
        data = pd.DataFrame({"a": np.arange(50.0), "b": np.arange(50.0)}, index=index)

        estimator = exponentialMeans(data)

        before_data = datetime.datetime(2019, 1, 1)
        fit_period = fitDates(before_data, before_data, before_data, before_data)

        estimate = estimator.get_estimate_for_fitperiod_with_data(fit_period)

        self.assertIsInstance(estimate, meanEstimates)
        self.assertEqual(estimate.list_of_keys(), ["a", "b"])
        self.assertTrue(np.isnan(estimate["a"]))
        self.assertTrue(np.isnan(estimate["b"]))


if __name__ == "__main__":
    unittest.main()
