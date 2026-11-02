from syscore.exceptions import missingData
from sysdata.production.trade_limits import (
    tradeLimitData,
    listOfInstrumentStrategyKeyAndDays,
    instrumentStrategyKeyAndDays,
)
from sysobjects.production.tradeable_object import instrumentStrategy
from sysdata.mongodb.mongo_generic import mongoDataWithMultipleKeys
from syslogging.logger import get_logger

LIMIT_STATUS_COLLECTION = "limit_status"

LEGACY_STRATEGY_KEY = "strategy_name"
LEGACY_INSTRUMENT_KEY = "instrument_code"

PERIOD_KEY = "period_days"
INSTRUMENT_STRATEGY_KEY = "instrument_strategy_key"


class mongoTradeLimitData(tradeLimitData):
    """
    Read and write data class to get override state data


    """

    def __init__(self, mongo_db=None, log=get_logger("mongoTradeLimitData")):
        super().__init__(log=log)
        self._mongo_data = mongoDataWithMultipleKeys(
            LIMIT_STATUS_COLLECTION, mongo_db=mongo_db
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "Data connection for trade limit data, mongodb %s" % (
            str(self.mongo_data)
        )

    def _get_trade_limit_as_dict_or_missing_data(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ) -> dict:
        instrument_strategy_key = instrument_strategy.key
        dict_of_keys = {
            INSTRUMENT_STRATEGY_KEY: instrument_strategy_key,
            PERIOD_KEY: period_days,
        }

        try:
            result_dict = self.mongo_data.get_result_dict_for_dict_keys(dict_of_keys)
        except missingData:
            result_dict = self._get_old_style_trade_limit_as_dict_or_missing_data(
                instrument_strategy, period_days
            )
        return result_dict

    def _get_old_style_trade_limit_as_dict_or_missing_data(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ) -> dict:
        dict_of_keys = {
            LEGACY_INSTRUMENT_KEY: instrument_strategy.instrument_code,
            LEGACY_STRATEGY_KEY: instrument_strategy.strategy_name,
            PERIOD_KEY: period_days,
        }

        result_dict = self.mongo_data.get_result_dict_for_dict_keys(dict_of_keys)
        result_dict = _from_trade_limit_dict_to_required_dict(result_dict)

        return result_dict

    def _update_trade_limit_as_dict(self, trade_limit_dict: dict):
        instrument_strategy_key = trade_limit_dict.pop("instrument_strategy_key")
        period_days = trade_limit_dict.pop("period_days")

        dict_of_keys = {
            INSTRUMENT_STRATEGY_KEY: instrument_strategy_key,
            PERIOD_KEY: period_days,
        }

        # we do this to avoid blended records old and new
        self._delete_old_style_data(instrument_strategy_key, period_days)
        self.mongo_data.add_data(dict_of_keys, trade_limit_dict, allow_overwrite=True)

    def _delete_old_style_data(self, instrument_strategy_key: str, period_days: int):
        instrument_strategy = instrumentStrategy.from_key(instrument_strategy_key)
        dict_of_keys = {
            LEGACY_STRATEGY_KEY: instrument_strategy.strategy_name,
            LEGACY_INSTRUMENT_KEY: instrument_strategy.instrument_code,
            PERIOD_KEY: period_days,
        }
        self.mongo_data.delete_data_without_any_warning(dict_of_keys)

    def _get_all_limit_keys(self) -> listOfInstrumentStrategyKeyAndDays:
        list_of_result_dicts = self.mongo_data.get_list_of_all_dicts()

        list_of_results = [
            _from_result_dict_to_isd(result_dict)
            for result_dict in list_of_result_dicts
        ]
        list_of_results = listOfInstrumentStrategyKeyAndDays(list_of_results)

        return list_of_results


def _from_result_dict_to_isd(result_dict: dict) -> instrumentStrategyKeyAndDays:
    if INSTRUMENT_STRATEGY_KEY in result_dict.keys():
        ## NEW STYLE
        instrument_strategy_key = result_dict[INSTRUMENT_STRATEGY_KEY]
    else:
        ## LEGACY
        instrument_strategy = instrumentStrategy(
            strategy_name=result_dict[LEGACY_STRATEGY_KEY],
            instrument_code=result_dict[LEGACY_INSTRUMENT_KEY],
        )
        instrument_strategy_key = instrument_strategy.key

    return instrumentStrategyKeyAndDays(
        instrument_strategy_key, result_dict[PERIOD_KEY]
    )


def _from_trade_limit_dict_to_required_dict(trade_limit_dict: dict) -> dict:
    if INSTRUMENT_STRATEGY_KEY in trade_limit_dict.keys():
        ## NEW STYLE
        return trade_limit_dict

    ## OLD STYLE
    instrument_strategy = instrumentStrategy(
        instrument_code=trade_limit_dict.pop(LEGACY_INSTRUMENT_KEY),
        strategy_name=trade_limit_dict.pop(LEGACY_STRATEGY_KEY),
    )
    trade_limit_dict[INSTRUMENT_STRATEGY_KEY] = instrument_strategy.key

    return trade_limit_dict
