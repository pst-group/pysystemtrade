from syscore.exceptions import missingData
from sysdata.parquet.parquet_access import ParquetAccess
from sysdata.production.optimal_positions import optimalPositionData
from syslogging.logger import get_logger

from sysobjects.production.tradeable_object import (
    instrumentStrategy,
    listOfInstrumentStrategies,
)

import pandas as pd

OPTIMAL_POSITION_COLLECTION = "optimal_positions"


class parquetOptimalPositionData(optimalPositionData):
    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetOptimalPositionData"),
    ):
        super().__init__(log=log)
        self._parquet = parquet_access

    def __repr__(self):
        return "parquetOptimalPositionData"

    @property
    def parquet(self):
        return self._parquet

    def get_list_of_instrument_strategies_with_optimal_position(
        self,
    ) -> listOfInstrumentStrategies:
        raw_list_of_instrument_strategies = (
            self.parquet.get_all_identifiers_with_data_type(
                data_type=OPTIMAL_POSITION_COLLECTION
            )
        )
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
            df_result = self.parquet.read_data_given_data_type_and_identifier(
                data_type=OPTIMAL_POSITION_COLLECTION, identifier=ident
            )
        except:
            raise missingData

        return df_result

    def write_optimal_position_as_df_for_instrument_strategy_without_checking(
        self,
        instrument_strategy: instrumentStrategy,
        optimal_positions_as_df: pd.DataFrame,
    ):
        ident = instrument_strategy.key
        self.parquet.write_data_given_data_type_and_identifier(
            data_type=OPTIMAL_POSITION_COLLECTION,
            identifier=ident,
            data_to_write=optimal_positions_as_df,
        )
