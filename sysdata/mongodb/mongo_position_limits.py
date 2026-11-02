from sysdata.mongodb.mongo_generic import mongoDataWithMultipleKeys
from sysdata.production.position_limits import positionLimitData
from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)
from syslogging.logger import get_logger

POSITION_LIMIT_STATUS_COLLECTION = "position_limit_status"

MARKER_KEY = "marker"

MARKER_STRATEGY_INSTRUMENT = "strategy_instrument"
MARKER_INSTRUMENT = "instrument"

INSTRUMENT_KEY = "instrument_code"
STRATEGY_KEY = "strategy_name"
POSITION_LIMIT_KEY = "position_limit"


class mongoPositionLimitData(positionLimitData):
    """
    Read and write data class to get override state data


    """

    def __init__(self, mongo_db=None, log=get_logger("mongoPositionLimitData")):
        super().__init__(log=log)

        self._mongo_data = mongoDataWithMultipleKeys(
            POSITION_LIMIT_STATUS_COLLECTION, mongo_db=mongo_db
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "Data connection for position limit data, mongodb %s"

    def get_all_instruments_with_limits(self) -> list:
        dict_of_keys = {MARKER_KEY: MARKER_INSTRUMENT}
        list_of_dicts = self.mongo_data.get_list_of_result_dicts_for_dict_keys(
            dict_of_keys
        )
        list_of_instruments = [db_entry[INSTRUMENT_KEY] for db_entry in list_of_dicts]

        return list_of_instruments

    def get_all_instrument_strategies_with_limits(self) -> listOfInstrumentStrategies:
        dict_of_keys = {MARKER_KEY: MARKER_STRATEGY_INSTRUMENT}
        list_of_dicts = self.mongo_data.get_list_of_result_dicts_for_dict_keys(
            dict_of_keys
        )

        list_of_instrument_strategies = [
            instrumentStrategy(
                strategy_name=db_entry[STRATEGY_KEY],
                instrument_code=db_entry[INSTRUMENT_KEY],
            )
            for db_entry in list_of_dicts
        ]

        list_of_instrument_strategies = listOfInstrumentStrategies(
            list_of_instrument_strategies
        )

        return list_of_instrument_strategies

    def delete_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ):
        dict_of_keys = {
            MARKER_KEY: MARKER_STRATEGY_INSTRUMENT,
            STRATEGY_KEY: instrument_strategy.strategy_name,
            INSTRUMENT_KEY: instrument_strategy.instrument_code,
        }

        self.mongo_data.delete_data_without_any_warning(dict_of_keys)

    def delete_position_limit_for_instrument(self, instrument_code: str):
        dict_of_keys = {MARKER_KEY: MARKER_INSTRUMENT, INSTRUMENT_KEY: instrument_code}

        self.mongo_data.delete_data_without_any_warning(dict_of_keys)

    def _get_abs_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> int:
        dict_of_keys = {
            MARKER_KEY: MARKER_STRATEGY_INSTRUMENT,
            STRATEGY_KEY: instrument_strategy.strategy_name,
            INSTRUMENT_KEY: instrument_strategy.instrument_code,
        }
        find_object_dict = self.mongo_data.get_result_dict_for_dict_keys(dict_of_keys)
        position_limit = find_object_dict[POSITION_LIMIT_KEY]

        return position_limit

    def _get_abs_position_limit_for_instrument(
        self,
        instrument_code: str,
    ) -> int:
        dict_of_keys = {MARKER_KEY: MARKER_INSTRUMENT, INSTRUMENT_KEY: instrument_code}

        find_object_dict = self.mongo_data.get_result_dict_for_dict_keys(dict_of_keys)
        position_limit = find_object_dict[POSITION_LIMIT_KEY]

        return position_limit

    def set_position_limit_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy, new_position_limit: int
    ):
        dict_of_keys = {
            MARKER_KEY: MARKER_STRATEGY_INSTRUMENT,
            STRATEGY_KEY: instrument_strategy.strategy_name,
            INSTRUMENT_KEY: instrument_strategy.instrument_code,
        }
        data_dict = {POSITION_LIMIT_KEY: new_position_limit}

        self.mongo_data.add_data(dict_of_keys, data_dict, allow_overwrite=True)

    def set_position_limit_for_instrument(
        self, instrument_code: str, new_position_limit: int
    ):
        dict_of_keys = {MARKER_KEY: MARKER_INSTRUMENT, INSTRUMENT_KEY: instrument_code}
        data_dict = {POSITION_LIMIT_KEY: new_position_limit}

        self.mongo_data.add_data(dict_of_keys, data_dict, allow_overwrite=True)
