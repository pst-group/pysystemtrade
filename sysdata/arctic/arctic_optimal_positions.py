"""
Read and write data from mongodb for individual futures contracts

"""

from syscore.exceptions import missingData
from sysdata.arctic.arctic_connection import arcticData
from sysdata.production.optimal_positions import optimalPositionData
from syslogging.logger import get_logger

from sysobjects.production.tradeable_object import (
    instrumentStrategy,
    listOfInstrumentStrategies,
)

import pandas as pd

OPTIMAL_POSITION_COLLECTION = "optimal_positions"


class arcticOptimalPositionData(optimalPositionData):
    def __init__(self, mongo_db=None, log=get_logger("arcticOptimalPositionData")):
        super().__init__(log=log)

        self._arctic_connection = arcticData(
            OPTIMAL_POSITION_COLLECTION, mongo_db=mongo_db
        )

    def __repr__(self):
        return repr(self._arctic_connection)

    @property
    def arctic_connection(self):
        return self._arctic_connection

    def get_list_of_instrument_strategies_with_optimal_position(
        self,
    ) -> listOfInstrumentStrategies:
        raw_list_of_instrument_strategies = self.arctic_connection.get_keynames()
        list_of_instrument_strategies = [
            instrumentStrategy.from_key(key)
            for key in raw_list_of_instrument_strategies
        ]

        return listOfInstrumentStrategies(list_of_instrument_strategies)

    def get_optimal_position_as_df_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> pd.DataFrame:
        try:
            ident = instrument_strategy.key
            df_result = self.arctic_connection.read(ident)
        except:
            raise missingData

        return df_result

    def write_optimal_position_as_df_for_instrument_strategy_without_checking(
        self,
        instrument_strategy: instrumentStrategy,
        optimal_positions_as_df: pd.DataFrame,
    ):
        ident = instrument_strategy.key
        self.arctic_connection.write(ident, optimal_positions_as_df)
