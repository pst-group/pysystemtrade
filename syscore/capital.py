"""
WARNING DO NOT REFACTOR NAMES OR LOCATION OF THIS CODE AS IT IS USED IN .YAML FILES, eg

capital_multiplier:
   func: syscore.capital.fixed_capital

Functions to calculate capital multiplier

ALl return Tx1 pd.Series, where a value of 1 is the original capital

See https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html for more details

"""

from copy import copy
import pandas as pd
import numpy as np
from systems.basesystem import System


def fixed_capital(system: System, **ignored_args) -> pd.Series:
    multiplier = copy(system.accounts.portfolio().percent)
    multiplier[:] = 1.0

    return multiplier


def full_compounding(system: System, **ignored_args) -> pd.Series:
    pandl = system.accounts.portfolio().percent
    multiplier = 1.0 + (pandl / 100.0)
    multiplier = multiplier.cumprod().ffill()

    return multiplier


def half_compounding(system: System, **ignored_args) -> pd.Series:
    ## remove any nans
    pandl = system.accounts.portfolio().percent.curve().ffill().diff()
    multiplier = 1.0
    multiplier_list = []
    for daily_return in pandl:
        actual_return = multiplier * daily_return / 100.0
        multiplier = multiplier * (1.0 + actual_return)
        multiplier = np.nanmin([multiplier, 1.0])
        multiplier_list.append(multiplier)

    multiplier = pd.Series(multiplier_list, index=pandl.index).ffill()

    return multiplier
