"""
Created on 27 Nov 2015

@author: rob
"""

import unittest as ut

import numpy as np

from syscore.pandas.pdutils import pd_readcsv
from sysquant.estimators.vol import robust_vol_calc
from syscore.fileutils import resolve_path_and_filename_for_package


def get_data(path):
    """
    returns: DataFrame or Series if 1 col
    """
    df = pd_readcsv(resolve_path_and_filename_for_package(path), date_format="%Y-%m-%d")
    if len(df.columns) == 1:
        return df[df.columns[0]]
    return df


class Test(ut.TestCase):
    @ut.SkipTest
    def test_robust_vol_calc(self):
        prices = get_data("syscore.tests.pricetestdata.csv")
        returns = prices.diff()
        vol = robust_vol_calc(returns, days=35)

        self.assertAlmostEqual(vol.iloc[-1], 0.41905275480464305)

        vol = robust_vol_calc(returns, days=100)
        self.assertAlmostEqual(vol.iloc[-1], 0.43906619578902956)

    def test_robust_vol_calc_min_period(self):
        prices = get_data("syscore.tests.pricetestdata_min_period.csv")

        returns = prices.diff()
        vol = robust_vol_calc(returns, min_periods=9)
        self.assertAlmostEqual(vol.iloc[-1], 0.45829858614978286)
        vol = robust_vol_calc(returns, min_periods=10)
        self.assertTrue(np.isnan(vol.iloc[-1]))

    def test_robust_vol_calc_min_value(self):
        prices = get_data("syscore.tests.pricetestdata_zero_vol.csv")
        returns = prices.diff()
        vol = robust_vol_calc(returns, vol_abs_min=0.01)
        self.assertEqual(vol.iloc[-1], 0.01)

    @ut.SkipTest
    def test_robust_vol_calc_floor(self):
        prices = get_data("syscore.tests.pricetestdata_vol_floor.csv")
        returns = prices.diff()

        vol = robust_vol_calc(returns)
        self.assertAlmostEqual(vol.iloc[-1], 0.54492982003602064)

        vol = robust_vol_calc(returns, vol_floor=False)
        self.assertAlmostEqual(vol.iloc[-1], 0.42134038479240132)

        vol = robust_vol_calc(returns, floor_min_quant=0.5)
        self.assertAlmostEqual(vol.iloc[-1], 1.6582199589924964)

        vol = robust_vol_calc(returns, floor_min_periods=500)
        self.assertAlmostEqual(vol.iloc[-1], 0.42134038479240132)

        vol = robust_vol_calc(returns, floor_days=10, floor_min_periods=5)
        self.assertAlmostEqual(vol.iloc[-1], 0.42134038479240132)


"""
    def test_calc_ewmac_forecast(self):
        prices=pd_readcsv_frompackage("syscore", "pricetestdata.csv", ["tests"])
        fcast=calc_ewmac_forecast(prices, 2, 8)
        self.assertAlmostEqual(fcast.iloc[-1][0],-0.58728633970596145)
        fcast=calc_ewmac_forecast(prices, 100, 500)
        self.assertAlmostEqual(fcast.iloc[-1][0],20.914172249098829)
        self.assertEqual(fcast.shape, (528,1))
"""

if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.test_robust_vol_calc']
    ut.main()
