from syscore.constants import arg_not_supplied

from sysdata.data_blob import dataBlob

from sysproduction.data.sim_data import get_sim_data_object_for_production
from sysproduction.strategy_code.run_dynamic_optimised_system import (
    runSystemCarryTrendDynamic,
)

from syslogging.logger import get_logger

from systems.basesystem import System


class runMySystemCarryTrendDynamic(runSystemCarryTrendDynamic):
    # DO NOT CHANGE THE NAME OF THIS FUNCTION; IT IS HARDCODED INTO CONFIGURATION FILES
    # BECAUSE IT IS ALSO USED TO LOAD BACKTESTS
    def system_method(
        self, notional_trading_capital: float = None, base_currency: str = None
    ) -> System:
        data = self.data
        backtest_config_filename = self.backtest_config_filename

        system = production_carry_trend_dynamic_system(
            data,
            backtest_config_filename,
            log=data.log,
            notional_trading_capital=notional_trading_capital,
            base_currency=base_currency,
        )

        return system


def production_carry_trend_dynamic_system(
    data: dataBlob,
    config_filename: str,
    log=get_logger("futures_system"),
    notional_trading_capital: float = arg_not_supplied,
    base_currency: str = arg_not_supplied,
) -> System:
    sim_data = get_sim_data_object_for_production(data)
    config = Config(config_filename)

    # Overwrite capital and base currency
    if notional_trading_capital is not arg_not_supplied:
        config.notional_trading_capital = notional_trading_capital

    if base_currency is not arg_not_supplied:
        config.base_currency = base_currency

    system = futures_system(data=sim_data, config=config)
    system._log = log

    return system


from sysdata.config.configdata import Config

from systems.forecasting import Rules
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from private.systems.arch.carrytrend.forecastScaleCap import volAttenForecastScaleCap
from private.systems.arch.carrytrend import myFuturesRawData
from systems.positionsizing import PositionSizing
from systems.portfolio import Portfolios
from systems.provided.dynamic_small_system_optimise.optimised_positions_stage import (
    optimisedPositions,
)
from systems.risk import Risk
from systems.provided.dynamic_small_system_optimise.accounts_stage import (
    accountForOptimisedStage,
)


def futures_system(data, config):
    system = System(
        [
            Risk(),
            accountForOptimisedStage(),
            optimisedPositions(),
            Portfolios(),
            PositionSizing(),
            myFuturesRawData(),
            ForecastCombine(),
            volAttenForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )

    return system
