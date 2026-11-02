import datetime
from syscore.constants import arg_not_supplied

from sysdata.config.configdata import Config
from sysdata.data_blob import dataBlob
from sysobjects.production.optimal_positions import (
    optimalPositionWithReference,
)
from sysobjects.production.tradeable_object import instrumentStrategy

from sysproduction.data.sim_data import get_sim_data_object_for_production
from sysproduction.strategy_code.run_system_classic import (
    runSystemClassic,
)
from sysproduction.data.contracts import dataContracts
from sysproduction.data.optimal_positions import dataOptimalPositions

from syslogging.logger import get_logger

from systems.basesystem import System


class runSystemCarryTrendDynamic(runSystemClassic):
    # DO NOT CHANGE THE NAME OF THIS FUNCTION; IT IS HARDCODED INTO CONFIGURATION FILES
    # BECAUSE IT IS ALSO USED TO LOAD BACKTESTS
    def system_method(
        self,
        notional_trading_capital: float = arg_not_supplied,
        base_currency: str = arg_not_supplied,
    ) -> System:
        data = self.data
        backtest_config_filename = self.backtest_config_filename

        system = dynamic_system(
            data,
            backtest_config_filename,
            log=data.log,
            notional_trading_capital=notional_trading_capital,
            base_currency=base_currency,
        )

        return system

    @property
    def function_to_call_on_update(self):
        return updated_optimal_positions_for_dynamic_system


def dynamic_system(
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


from systems.forecasting import Rules
from systems.basesystem import System
from systems.forecast_combine import ForecastCombine
from systems.forecast_scale_cap import ForecastScaleCap
from systems.rawdata import RawData
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
            RawData(),
            ForecastCombine(),
            ForecastScaleCap(),
            Rules(),
        ],
        data,
        config,
    )

    return system


def updated_optimal_positions_for_dynamic_system(
    data: dataBlob, strategy_name: str, system: System
):
    log = data.log

    data_optimal_positions = dataOptimalPositions(data)

    instruments_in_system = system.get_instrument_list()

    # Instruments with existing optimal positions
    # If not included in the system, they need to be assigned a weight of zero
    instruments_with_positions = data_optimal_positions.get_list_of_instruments_for_strategy_with_optimal_position(
        strategy_name, raw_positions=True
    )

    list_of_instruments = set(instruments_in_system).union(instruments_with_positions)

    for instrument_code in list_of_instruments:
        position_entry = construct_optimal_position_entry(
            data=data,
            system=system,
            instrument_code=instrument_code,
        )
        instrument_strategy = instrumentStrategy(
            instrument_code=instrument_code, strategy_name=strategy_name
        )
        data_optimal_positions.update_optimal_position_for_instrument_strategy(
            instrument_strategy=instrument_strategy,
            raw_positions=True,
            position_entry=position_entry,
        )

        log.debug("New Optimal position %s %s" % (str(position_entry), instrument_code))


def construct_optimal_position_entry(
    data: dataBlob, system: System, instrument_code: str
) -> optimalPositionWithReference:
    log = data.log
    diag_contracts = dataContracts(data)

    if instrument_code in system.get_instrument_list():
        optimal_position = get_optimal_position_from_system(system, instrument_code)
    else:
        optimal_position = 0.0

    try:
        reference_price = system.rawdata.get_daily_prices(instrument_code).iloc[-1]
        reference_date = system.rawdata.get_daily_prices(instrument_code).index[-1]
        reference_contract = diag_contracts.get_priced_contract_id(instrument_code)
    except Exception:
        log.warning(f"{instrument_code} has optimal position, but no price data")
        reference_price = 0.0
        reference_date = datetime.datetime.now()
        reference_contract = reference_date.strftime("%Y%m00")

    position_entry = optimalPositionWithReference(
        date=datetime.datetime.now(),
        optimal_position=optimal_position,
        reference_price=reference_price,
        reference_contract=reference_contract,
        reference_date=reference_date,
    )

    return position_entry


def get_optimal_position_from_system(system: System, instrument_code: str) -> float:
    optimal_position = system.portfolio.get_notional_position(instrument_code)

    return float(optimal_position.iloc[-1])
