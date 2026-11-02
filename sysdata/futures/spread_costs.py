## Expected slippage eg half bid-ask spread
## Used to be in instrument config, now separate
import pandas as pd
from sysdata.base_data import baseData
from syslogging.logger import get_logger


class spreadCostData(baseData):
    def __init__(self, log=get_logger("SpreadCosts")):
        super().__init__(log=log)

    def delete_spread_cost(self, instrument_code: str):
        raise NotImplementedError

    def update_spread_cost(self, instrument_code: str, spread_cost: float):
        raise NotImplementedError

    def get_list_of_instruments(self) -> list:
        raise NotImplementedError

    def get_spread_cost(self, instrument_code: str) -> float:
        raise NotImplementedError

    def get_spread_costs_as_series(self) -> pd.Series:
        raise NotImplementedError

    def _get_spread_cost_if_series_provided(self, instrument_code: str) -> float:
        all_data = self.get_spread_costs_as_series()
        costs = all_data.get(instrument_code, 0)
        return costs

    def _get_spread_costs_as_series_if_individual_spreads_provided(self) -> pd.Series:
        all_instruments = self.get_list_of_instruments()
        spread_costs_as_series = pd.Series(
            [
                self.get_spread_cost(instrument_code)
                for instrument_code in all_instruments
            ],
            index=all_instruments,
        )
        return spread_costs_as_series
