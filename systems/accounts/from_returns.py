"""
Functions to do calculations just from percentage returns
"""

import pandas as pd
from systems.accounts.curves.account_curve import accountCurve

from syscore.constants import arg_not_supplied
from systems.accounts.pandl_calculators.pandl_cash_costs import (
    pandlCalculationWithCashCostsAndFills,
)


def account_curve_from_returns(
    returns: pd.Series,
    costs: pd.Series = arg_not_supplied,
    capital: pd.Series = arg_not_supplied,
):
    returns = returns.dropna()
    if costs is arg_not_supplied:
        costs = pd.Series(0.0, index=returns.index)

    pandl_calculator = pandlCalculationWithCashCostsAndFillsFromReturns(
        price=returns.cumsum(),
        positions=pd.Series(1.0, index=returns.index),
        capital=capital,
        raw_costs=costs,  # ignore warning, not used
        rolls_per_year=0,
        vol_normalise_currency_costs=False,
    )

    account_curve = accountCurve(pandl_calculator)

    return account_curve


class pandlCalculationWithCashCostsAndFillsFromReturns(
    pandlCalculationWithCashCostsAndFills
):
    def costs_pandl_in_points(self) -> pd.Series:
        return self._raw_costs  # ignore warning
