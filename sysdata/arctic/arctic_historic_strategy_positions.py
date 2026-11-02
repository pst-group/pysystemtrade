import pandas as pd

from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)
from sysdata.arctic.arctic_connection import arcticData
from sysdata.production.historic_strategy_positions import strategyPositionData
from syscore.exceptions import missingData

from syslogging.logger import get_logger

STRATEGY_POSITION_COLLECTION = "strategy_positions"


class arcticStrategyPositionData(strategyPositionData):
    def __init__(self, mongo_db=None, log=get_logger("arcticStrategyPositionData")):
        super().__init__(log=log)

        self._arctic = arcticData(STRATEGY_POSITION_COLLECTION, mongo_db=mongo_db)

    def __repr__(self):
        return repr(self._arctic)

    @property
    def arctic(self):
        return self._arctic

    def get_list_of_instrument_strategies(self) -> listOfInstrumentStrategies:
        list_of_keys = self.arctic.get_keynames()
        list_of_instrument_strategies = [
            instrumentStrategy.from_key(key) for key in list_of_keys
        ]

        return listOfInstrumentStrategies(list_of_instrument_strategies)

    def _write_updated_position_series_for_instrument_strategy_object(
        self, instrument_strategy: instrumentStrategy, updated_series: pd.Series
    ):
        ident = instrument_strategy.key
        updated_data_as_df = pd.DataFrame(updated_series)
        updated_data_as_df.columns = ["position"]

        self.arctic.write(ident=ident, data=updated_data_as_df)

    def _delete_position_series_for_instrument_strategy_object_without_checking(
        self, instrument_strategy: instrumentStrategy
    ):
        ident = instrument_strategy.key
        self.arctic.delete(ident)

    def get_position_as_series_for_instrument_strategy_object(
        self, instrument_strategy: instrumentStrategy
    ) -> pd.Series:
        keyname = instrument_strategy.key
        try:
            pd_df = self.arctic.read(keyname)
        except:
            raise missingData

        return pd_df.iloc[:, 0]
