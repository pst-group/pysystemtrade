"""
We want to limit the size of position we can take, both for a given strategy and across strategies

When we want to trade (create an instrument / strategy order) we check that the new net position
  for that instrument (for the strategy, and across all strategies) doesn't exceed any limits


"""

from syscore.exceptions import missingData
from sysdata.base_data import baseData
from syslogging.logger import get_logger

from sysobjects.production.position_limits import (
    positionLimitForInstrument,
    positionLimitForStrategyInstrument,
)
from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)


class positionLimitData(baseData):
    def __init__(self, log=get_logger("Overrides")):
        super().__init__(log=log)

    def get_position_limit_object_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> positionLimitForStrategyInstrument:
        try:
            position_limit = self._get_abs_position_limit_for_instrument_strategy(
                instrument_strategy
            )
        except missingData:
            position_limit_object = positionLimitForStrategyInstrument.no_limit(
                instrument_strategy
            )
        else:
            position_limit_object = positionLimitForStrategyInstrument(
                instrument_strategy, position_limit
            )

        return position_limit_object

    def get_position_limit_object_for_instrument(
        self, instrument_code: str
    ) -> positionLimitForInstrument:
        try:
            position_limit = self._get_abs_position_limit_for_instrument(
                instrument_code
            )
        except missingData:
            position_limit_object = positionLimitForInstrument.no_limit(instrument_code)
        else:
            position_limit_object = positionLimitForInstrument(
                instrument_code, position_limit
            )

        return position_limit_object

    def _get_abs_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> int:
        # return missing_data if no limit found

        raise NotImplementedError

    def _get_abs_position_limit_for_instrument(
        self,
        instrument_code: str,
    ) -> int:
        # return missing_data if no limit found

        raise NotImplementedError

    def get_all_instruments_with_limits(self) -> list:
        raise NotImplementedError

    def get_all_instrument_strategies_with_limits(self) -> listOfInstrumentStrategies:
        raise NotImplementedError

    def set_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy, new_position_limit: int
    ):
        raise NotImplementedError

    def set_position_limit_for_instrument(
        self, instrument_code: str, new_position_limit: int
    ):
        raise NotImplementedError

    def delete_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ):
        raise NotImplementedError

    def delete_position_limit_for_instrument(self, instrument_code: str):
        raise NotImplementedError
