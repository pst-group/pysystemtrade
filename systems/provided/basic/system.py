"""
Minimum viable system

Note: This has no trading rules

"""

from syscore.constants import arg_not_supplied

from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysdata.config.configdata import Config

from systems.forecasting import Rules
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from systems.forecast_scale_cap import ForecastScaleCap
from systems.rawdata import RawData
from systems.positionsizing import PositionSizing
from systems.portfolio import Portfolios
from systems.accounts.accounts_stage import Account


def basic_futures_system(
    data,
    config=arg_not_supplied,
    trading_rules=arg_not_supplied,
):
    if config is arg_not_supplied:
        config = Config()

    rules = Rules(trading_rules)

    system = System(
        [
            Account(),
            Portfolios(),
            PositionSizing(),
            RawData(),
            ForecastCombine(),
            ForecastScaleCap(),
            rules,
        ],
        data,
        config,
    )

    return system


def basic_csv_futures_system(
    data=arg_not_supplied,
    config=arg_not_supplied,
    trading_rules=arg_not_supplied,
):
    if data is arg_not_supplied:
        data = csvFuturesSimData()

    system = basic_futures_system(data, config=config, trading_rules=trading_rules)
    return system


def basic_db_futures_system(
    data=arg_not_supplied,
    config=arg_not_supplied,
    trading_rules=arg_not_supplied,
):
    if data is arg_not_supplied:
        data = dbFuturesSimData()

    system = basic_futures_system(data, config=config, trading_rules=trading_rules)
    return system
