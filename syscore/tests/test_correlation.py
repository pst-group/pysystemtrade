"""
Created on 20 Jan 2016



@author: rob
"""

import unittest
import numpy as np
from systems.tests.testdata import (
    get_test_object_futures_with_rules_and_capping_estimate,
)
from systems.basesystem import System


class Test(unittest.TestCase):
    def setUp(self):
        (
            accounts,
            fcs,
            rules,
            rawdata,
            data,
            config,
        ) = get_test_object_futures_with_rules_and_capping_estimate()
        system = System(
            [accounts, rawdata, rules, fcs, ForecastCombineEstimated()], data, config
        )
        setattr(self, "system", system)

    def tearDown(self):
        self.system.delete_all_items(delete_protected=True)

    @unittest.SkipTest
    def testDefaults(self):
        instrument_code = "EDOLLAR"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[0][0][1], 0.99, places=5)
        print(ans.columns)

        instrument_code = "US10"
        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.11686990, places=5)
        print(ans.columns)

        instrument_code = "BUND"
        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.9014138496, places=5)
        print(ans.columns)

    @unittest.SkipTest
    def testPooling(self):
        self.system.config.forecast_correlation_estimate["pool_instruments"] = "False"

        instrument_code = "EDOLLAR"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.080792737, places=5)
        print(ans.columns)

        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.1614655717, places=5)
        print(ans.columns)

    @unittest.SkipTest
    def testFrequency(self):
        self.system.config.forecast_correlation_estimate["frequency"] = "D"
        self.system.config.forecast_correlation_estimate["floor_at_zero"] = False
        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.012915602974, places=5)

    @unittest.SkipTest
    def testDatemethod(self):
        self.system.config.forecast_correlation_estimate["date_method"] = "rolling"
        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.1152719945526076, places=5)

    @unittest.SkipTest
    def testExponent(self):
        self.system.config.forecast_correlation_estimate["using_exponent"] = "False"
        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        print(ans)
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.127147, places=5)

    @unittest.SkipTest
    def testExponentLookback(self):
        self.system.config.forecast_correlation_estimate["ew_lookback"] = 50
        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[-1][0][1], 0.0764327959, places=5)

    @unittest.SkipTest
    def testminperiods(self):
        self.system.config.forecast_correlation_estimate["pool_instruments"] = "False"
        self.system.config.forecast_correlation_estimate["min_periods"] = 500
        instrument_code = "US10"

        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertAlmostEqual(ans.corr_list[9][0][1], 0.99, places=5)
        self.assertAlmostEqual(ans.corr_list[10][0][1], 0.10745399, places=5)

    @unittest.SkipTest
    def testnotcleaning(self):
        self.system.config.forecast_correlation_estimate["cleaning"] = "False"
        self.system.config.forecast_correlation_estimate["pool_instruments"] = "False"
        self.system.config.forecast_correlation_estimate["min_periods"] = 5000

        instrument_code = "US10"
        ans = self.system.combForecast.get_forecast_correlation_matrices(
            instrument_code
        )
        self.assertTrue(np.isnan(ans.corr_list[0][0][0]))
        self.assertTrue(np.isnan(ans.corr_list[1][0][0]))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
