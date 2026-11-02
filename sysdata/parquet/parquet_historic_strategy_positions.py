import pandas as pd

from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)
from sysdata.parquet.parquet_access import ParquetAccess
from sysdata.production.historic_strategy_positions import strategyPositionData
from syscore.exceptions import missingData

from syslogging.logger import get_logger

STRATEGY_POSITION_COLLECTION = "strategy_positions"


class parquetStrategyPositionData(strategyPositionData):
    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetStrategyPositionData"),
    ):
        super().__init__(log=log)

        self._parquet = parquet_access

    def __repr__(self):
        return "parquetStrategyPositionData"

    @property
    def parquet(self):
        return self._parquet

    def get_list_of_instrument_strategies(self) -> listOfInstrumentStrategies:
        list_of_keys = self.parquet.get_all_identifiers_with_data_type(
            data_type=STRATEGY_POSITION_COLLECTION
        )
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

        self.parquet.write_data_given_data_type_and_identifier(
            data_to_write=updated_data_as_df,
            identifier=ident,
            data_type=STRATEGY_POSITION_COLLECTION,
        )

    def _delete_position_series_for_instrument_strategy_object_without_checking(
        self, instrument_strategy: instrumentStrategy
    ):
        ident = instrument_strategy.key
        self.parquet.delete_data_given_data_type_and_identifier(
            data_type=STRATEGY_POSITION_COLLECTION, identifier=ident
        )

    def get_position_as_series_for_instrument_strategy_object(
        self, instrument_strategy: instrumentStrategy
    ) -> pd.Series:
        keyname = instrument_strategy.key
        try:
            pd_df = self.parquet.read_data_given_data_type_and_identifier(
                data_type=STRATEGY_POSITION_COLLECTION, identifier=keyname
            )
        except:
            raise missingData

        return pd_df.iloc[:, 0]
