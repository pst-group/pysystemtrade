"""

Optimal positions describe what a particular trading strategy would like to do, conditional (or not) on prices and
  current positions

The exact implementation of this depends on the strategy.
A basic class is an optimal position with buffers around it.
A mean reversion style class would include price buffers

"""

import pandas as pd
from syscore.exceptions import missingData
from sysdata.base_data import baseData
from sysobjects.production.optimal_positions import (
    baseOptimalPosition,
    from_df_row_to_optimal_position,
    add_optimal_position_entry_row_to_positions_as_df,
    instrumentStrategyAndOptimalPosition,
    listOfOptimalPositionsAcrossInstrumentStrategies,
)

from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)


class optimalPositionData(baseData):
    """
    Store and retrieve the optimal positions assigned to a particular strategy

    We store the type of list in the data
    """

    def __repr__(self):
        return "optimalPositionData object"

    def get_list_of_optimal_positions_for_strategy(
        self, strategy_name: str
    ) -> listOfOptimalPositionsAcrossInstrumentStrategies:
        list_of_instrument_strategies = (
            self.get_list_of_instrument_strategies_for_strategy_with_optimal_position(
                strategy_name
            )
        )

        list_of_instrument_strategies_with_positions = (
            self.get_list_of_optimal_positions_given_list_of_instrument_strategies(
                list_of_instrument_strategies
            )
        )

        return list_of_instrument_strategies_with_positions

    def get_list_of_optimal_positions(
        self,
    ) -> listOfOptimalPositionsAcrossInstrumentStrategies:
        list_of_instrument_strategies = (
            self.get_list_of_instrument_strategies_with_optimal_position()
        )

        list_of_optimal_positions_and_instrument_strategies = (
            self.get_list_of_optimal_positions_given_list_of_instrument_strategies(
                list_of_instrument_strategies
            )
        )

        return list_of_optimal_positions_and_instrument_strategies

    def get_list_of_optimal_positions_given_list_of_instrument_strategies(
        self, list_of_instrument_strategies: listOfInstrumentStrategies
    ) -> listOfOptimalPositionsAcrossInstrumentStrategies:
        list_of_optimal_positions_and_instrument_strategies = [
            self.get_instrument_strategy_and_optimal_position(instrument_strategy)
            for instrument_strategy in list_of_instrument_strategies
        ]

        list_of_optimal_positions_and_instrument_strategies = (
            listOfOptimalPositionsAcrossInstrumentStrategies(
                list_of_optimal_positions_and_instrument_strategies
            )
        )

        return list_of_optimal_positions_and_instrument_strategies

    def get_instrument_strategy_and_optimal_position(
        self, instrument_strategy: instrumentStrategy
    ) -> instrumentStrategyAndOptimalPosition:
        optimal_position = self.get_current_optimal_position_for_instrument_strategy(
            instrument_strategy
        )
        instrument_strategy_and_optimal_position = instrumentStrategyAndOptimalPosition(
            instrument_strategy, optimal_position
        )

        return instrument_strategy_and_optimal_position

    def get_list_of_instruments_for_strategy_with_optimal_position(
        self, strategy_name: str
    ) -> list:
        list_of_instrument_strategies = (
            self.get_list_of_instrument_strategies_with_optimal_position()
        )

        list_of_instruments = (
            list_of_instrument_strategies.get_list_of_instruments_for_strategy(
                strategy_name
            )
        )

        return list_of_instruments

    def list_of_strategies_with_optimal_position(self) -> list:
        list_of_instrument_strategies = (
            self.get_list_of_instrument_strategies_with_optimal_position()
        )

        list_of_strategies = list_of_instrument_strategies.get_list_of_strategies()

        return list_of_strategies

    def get_list_of_instrument_strategies_for_strategy_with_optimal_position(
        self, strategy_name: str
    ) -> listOfInstrumentStrategies:
        list_of_instrument_strategies = (
            self.get_list_of_instrument_strategies_with_optimal_position()
        )
        list_of_instrument_strategies_for_strategy = list_of_instrument_strategies.get_list_of_instrument_strategies_for_strategy(
            strategy_name
        )

        return list_of_instrument_strategies_for_strategy

    def get_current_optimal_position_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> baseOptimalPosition:
        existing_optimal_positions_as_df = (
            self.get_optimal_position_as_df_for_instrument_strategy(instrument_strategy)
        )

        final_position_row = existing_optimal_positions_as_df.iloc[-1, :]
        optimal_position = from_df_row_to_optimal_position(final_position_row)

        return optimal_position

    def update_optimal_position_for_instrument_strategy(
        self,
        instrument_strategy: instrumentStrategy,
        position_entry: baseOptimalPosition,
    ):
        try:
            existing_optimal_positions_as_df = (
                self.get_optimal_position_as_df_for_instrument_strategy(
                    instrument_strategy
                )
            )
            updated_optimal_positions_as_df = (
                add_optimal_position_entry_row_to_positions_as_df(
                    existing_optimal_positions_as_df, position_entry
                )
            )

        except missingData:
            #### Starting from scracth
            updated_optimal_positions_as_df = position_entry.as_df_row()

        self.write_optimal_position_as_df_for_instrument_strategy_without_checking(
            instrument_strategy=instrument_strategy,
            optimal_positions_as_df=updated_optimal_positions_as_df,
        )

    def get_list_of_instrument_strategies_with_optimal_position(
        self,
    ) -> listOfInstrumentStrategies:
        raise NotImplementedError

    def get_optimal_position_as_df_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> pd.DataFrame:
        raise NotImplementedError

    def write_optimal_position_as_df_for_instrument_strategy_without_checking(
        self,
        instrument_strategy: instrumentStrategy,
        optimal_positions_as_df: pd.DataFrame,
    ) -> pd.DataFrame:
        raise NotImplementedError
