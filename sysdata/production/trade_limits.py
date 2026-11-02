"""
We want to limit the number of trades we expect to do in a given period (usually a day, but could be longer if
  eg going on holiday)

Limits per contract don't make sense, but it makes sense to limit (a) the number of times a given instrument
   within a strategy can be traded and (b) the number of times an instrument can be traded, period.
"""

from dataclasses import dataclass

from syscore.exceptions import missingData
from sysdata.base_data import baseData
from syslogging.logger import get_logger
from sysobjects.production.trade_limits import tradeLimit, listOfTradeLimits

from sysobjects.production.tradeable_object import instrumentStrategy


@dataclass
class instrumentStrategyKeyAndDays:
    instrument_strategy_key: str
    period_days: int

    @classmethod
    def from_trade_limit(instrumentStrategyKeyAndDays, trade_limit: tradeLimit):
        return instrumentStrategyKeyAndDays(
            trade_limit.instrument_strategy.key, trade_limit.period_days
        )


class listOfInstrumentStrategyKeyAndDays(list):
    def for_given_instrument_strategy(self, instrument_strategy: instrumentStrategy):
        instrument_strategy_key = instrument_strategy.key
        results = [
            item
            for item in self
            if item.instrument_strategy_key == instrument_strategy_key
        ]

        return listOfInstrumentStrategyKeyAndDays(results)


class tradeLimitData(baseData):
    def __init__(self, log=get_logger("Overrides")):
        super().__init__(log=log)

    def no_limit(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ) -> tradeLimit:
        return tradeLimit(
            999999,
            instrument_strategy,
            period_days=period_days,
        )

    def what_trade_is_possible_for_instrument(
        self, instrument_code: str, proposed_trade: int
    ) -> int:
        combined_list = self.get_trade_limits_for_instrument(instrument_code)
        possible_trade = combined_list.what_trade_is_possible(proposed_trade)

        return possible_trade

    def what_trade_is_possible_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy, proposed_trade: int
    ) -> int:
        combined_list = self._get_list_of_all_relevant_trade_limits(instrument_strategy)
        possible_trade = combined_list.what_trade_is_possible(proposed_trade)

        return possible_trade

    def add_trade(self, instrument_strategy: instrumentStrategy, trade: int):
        combined_list = self._get_list_of_all_relevant_trade_limits(instrument_strategy)
        combined_list.add_trade(trade)
        self._update_list_of_trade_limits(combined_list)

    def remove_trade(self, instrument_strategy: instrumentStrategy, trade: int):
        combined_list = self._get_list_of_all_relevant_trade_limits(instrument_strategy)
        combined_list.remove_trade(trade)
        self._update_list_of_trade_limits(combined_list)

    def _get_list_of_all_relevant_trade_limits(
        self, instrument_strategy: instrumentStrategy
    ) -> listOfTradeLimits:
        instrument_trade_limits = self.get_trade_limits_for_instrument(
            instrument_strategy.instrument_code
        )
        strategy_instrument_trade_limits = (
            self.get_trade_limits_for_instrument_strategy(instrument_strategy)
        )

        combined_list = listOfTradeLimits(
            instrument_trade_limits + strategy_instrument_trade_limits
        )

        return combined_list

    def get_trade_limits_for_instrument(
        self, instrument_code: str
    ) -> listOfTradeLimits:
        instrument_strategy = instrument_strategy_for_instrument_only(instrument_code)

        return listOfTradeLimits(
            self.get_trade_limits_for_instrument_strategy(instrument_strategy)
        )

    def get_trade_limits_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> listOfTradeLimits:
        all_keys = self._get_all_limit_keys()
        relevant_keys = all_keys.for_given_instrument_strategy(instrument_strategy)
        trade_limits = [
            self._get_trade_limit_object_from_isd_key(isd_key)
            for isd_key in relevant_keys
        ]

        return listOfTradeLimits(trade_limits)

    def _update_list_of_trade_limits(self, list_of_trade_limits: list):
        result = [
            self._update_trade_limit_object(trade_limit_object)
            for trade_limit_object in list_of_trade_limits
        ]

        return result

    def update_instrument_limit_with_new_limit(
        self, instrument_code: str, period_days: int, new_limit: int
    ):
        """
        self.update_instrument_strategy_limit_with_new_limit(
            "", instrument_code, period_days, new_limit
        )
        """
        instrument_strategy = instrument_strategy_for_instrument_only(instrument_code)
        self.update_instrument_strategy_limit_with_new_limit(
            instrument_strategy, period_days, new_limit
        )

    def update_instrument_strategy_limit_with_new_limit(
        self, instrument_strategy: instrumentStrategy, period_days: int, new_limit: int
    ):
        trade_limit = self._get_trade_limit_object(instrument_strategy, period_days)
        trade_limit.update_limit(new_limit)
        self._update_trade_limit_object(trade_limit)

    def reset_all_limits(self):
        all_limits = self.get_all_limits()
        for limit in all_limits:
            self.reset_instrument_strategy_limit(
                instrument_strategy=limit.instrument_strategy,
                period_days=limit.period_days,
            )

    def reset_instrument_limit(self, instrument_code: str, period_days: int):
        instrument_strategy = instrument_strategy_for_instrument_only(instrument_code)
        self.reset_instrument_strategy_limit(instrument_strategy, period_days)

    def reset_strategy_limit_all_instruments(
        self, strategy_name: str, period_days: int
    ):
        pass

    def reset_instrument_strategy_limit(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ):
        trade_limit = self._get_trade_limit_object(instrument_strategy, period_days)

        trade_limit.reset()
        self._update_trade_limit_object(trade_limit)

    def get_all_limits(self) -> list:
        all_keys = self._get_all_limit_keys()
        all_limits = [
            self._get_trade_limit_object_from_isd_key(key) for key in all_keys
        ]

        return listOfTradeLimits(all_limits)

    def _get_trade_limit_object_from_isd_key(
        self, isd_key: instrumentStrategyKeyAndDays
    ) -> tradeLimit:
        instrument_strategy = instrumentStrategy.from_key(
            isd_key.instrument_strategy_key
        )
        period_days = isd_key.period_days

        return self._get_trade_limit_object(instrument_strategy, period_days)

    def _get_trade_limit_object(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ) -> tradeLimit:
        try:
            trade_limit_as_dict = self._get_trade_limit_as_dict_or_missing_data(
                instrument_strategy, period_days
            )
        except missingData:
            return self.no_limit(instrument_strategy, period_days)

        trade_limit_object = tradeLimit.from_dict(trade_limit_as_dict)

        return trade_limit_object

    def _update_trade_limit_object(self, trade_limit_object):
        trade_limit_as_dict = trade_limit_object.as_dict()
        self._update_trade_limit_as_dict(trade_limit_as_dict)

    def _get_trade_limit_as_dict_or_missing_data(
        self, instrument_strategy: instrumentStrategy, period_days: int
    ) -> dict:
        raise NotImplementedError

    def _update_trade_limit_as_dict(self, trade_limit_object: dict):
        raise NotImplementedError

    def _get_all_limit_keys(self) -> listOfInstrumentStrategyKeyAndDays:
        raise NotImplementedError


def instrument_strategy_for_instrument_only(instrument_code) -> instrumentStrategy:
    return instrumentStrategy(strategy_name="", instrument_code=instrument_code)
