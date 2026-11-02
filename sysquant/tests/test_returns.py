"""
Regression tests for the sign convention used when applying SR (Sharpe Ratio)
costs to gross returns.

See GitHub issue #1644: `_adjust_df_column_for_SR_costs` was flipping the
sign of an already-negative `daily_SR_cost`, so applying trading costs made
net returns *higher* than gross returns instead of lower.
"""

import datetime
import unittest

import numpy as np
import pandas as pd

from sysquant.returns import (
    _adjust_df_column_for_SR_costs,
    _adjust_df_for_SR_costs,
    dictOfSR,
)
from syscore.dateutils import ROOT_BDAYS_INYEAR


class Test(unittest.TestCase):
    def setUp(self):
        # Deterministic, non-degenerate gross return series (need std > 0)
        np.random.seed(42)
        index = pd.bdate_range(datetime.datetime(2020, 1, 1), periods=250)
        values = np.random.normal(loc=0.0, scale=2.5, size=len(index))
        self.gross_returns = pd.DataFrame({"instrument_a": values}, index=index)

    def test_negative_SR_cost_reduces_every_days_return(self):
        # A cost curve's daily mean is inherently negative (it is a drag on
        # P&L), so its annualised SR is negative too - this is the sign
        # convention produced upstream by
        # sysquant.returns._get_annual_SR_for_returns_for_optimisation(type="costs").
        dict_of_SR_costs = dictOfSR({"instrument_a": -0.5})

        net_returns = _adjust_df_column_for_SR_costs(
            self.gross_returns, dict_of_SR_costs, "instrument_a"
        )

        gross_column = self.gross_returns["instrument_a"]

        # Costs must drag the whole return series down, not up: every day's
        # net return should be strictly lower than the matching gross return.
        self.assertTrue((net_returns < gross_column).all())

        # And the aggregate effect should also show net performance below
        # gross performance.
        self.assertLess(net_returns.mean(), gross_column.mean())

    def test_negative_SR_cost_matches_analytic_expectation(self):
        # The per-day cost drag applied is a constant:
        #   (annual_SR_cost / ROOT_BDAYS_INYEAR) * daily_gross_return_std
        # and, since annual_SR_cost is already signed negative, this
        # constant must itself be negative (not positive).
        annual_SR_cost = -0.5
        dict_of_SR_costs = dictOfSR({"instrument_a": annual_SR_cost})

        net_returns = _adjust_df_column_for_SR_costs(
            self.gross_returns, dict_of_SR_costs, "instrument_a"
        )

        gross_column = self.gross_returns["instrument_a"]
        daily_gross_return_std = gross_column.std()
        expected_daily_cost = (
            annual_SR_cost / ROOT_BDAYS_INYEAR
        ) * daily_gross_return_std

        self.assertLess(expected_daily_cost, 0.0)

        expected_net_returns = gross_column + expected_daily_cost
        pd.testing.assert_series_equal(
            net_returns, expected_net_returns, check_names=False
        )

    def test_zero_SR_cost_leaves_returns_unchanged(self):
        dict_of_SR_costs = dictOfSR({"instrument_a": 0.0})

        net_returns = _adjust_df_column_for_SR_costs(
            self.gross_returns, dict_of_SR_costs, "instrument_a"
        )

        pd.testing.assert_series_equal(
            net_returns, self.gross_returns["instrument_a"], check_names=False
        )

    def test_adjust_df_for_SR_costs_reduces_returns_across_all_columns(self):
        index = self.gross_returns.index
        np.random.seed(7)
        gross_returns = pd.DataFrame(
            {
                "instrument_a": self.gross_returns["instrument_a"].values,
                "instrument_b": np.random.normal(loc=0.0, scale=1.2, size=len(index)),
            },
            index=index,
        )
        dict_of_SR_costs = dictOfSR({"instrument_a": -0.5, "instrument_b": -0.2})

        net_returns_df = _adjust_df_for_SR_costs(gross_returns, dict_of_SR_costs)

        for column_name in gross_returns.columns:
            self.assertTrue(
                (net_returns_df[column_name] < gross_returns[column_name]).all()
            )


if __name__ == "__main__":
    unittest.main()
