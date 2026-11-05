from typing import List
import datetime

from syscore.genutils import sign
from syscore.constants import arg_not_supplied

from sysobjects.production.tradeable_object import instrumentStrategy


class tradeLimit(object):
    def __init__(
        self,
        trade_limit: int,
        instrument_strategy: instrumentStrategy,
        period_days: int = 1,
        trades_since_last_reset: int = 0,
        last_reset_time: datetime.datetime = arg_not_supplied,
    ):
        self._trade_limit = int(trade_limit)
        self._period_days = period_days
        self._timedelta = datetime.timedelta(days=period_days)
        self._trades_since_last_reset = trades_since_last_reset
        self._instrument_strategy = instrument_strategy

        if last_reset_time is arg_not_supplied:
            last_reset_time = datetime.datetime.now()
        self._last_reset_time = last_reset_time

    def __repr__(self):
        return (
            "Trade limit for %s of %d over %d days, %d trades since last reset %s"
            % (
                str(self.instrument_strategy),
                self._trade_limit,
                self.period_days,
                self.trades_since_last_reset,
                str(self._last_reset_time),
            )
        )

    def as_dict(self) -> dict:
        instrument_strategy_key = self.instrument_strategy.key
        result_dict = dict(
            trade_limit=self.trade_limit,
            period_days=self.period_days,
            trades_since_last_reset=self.trades_since_last_reset,
            last_reset_time=self._last_reset_time,
            instrument_strategy_key=instrument_strategy_key,
        )

        return result_dict

    @classmethod
    def from_dict(tradeLimit, trade_limit_dict):
        ## new style
        instrument_strategy_key = trade_limit_dict.pop("instrument_strategy_key")
        instrument_strategy = instrumentStrategy.from_key(instrument_strategy_key)
        trade_limit_dict["instrument_strategy"] = instrument_strategy

        return tradeLimit(**trade_limit_dict)

    def what_abs_trade_is_possible(self, abs_proposed_trade: int) -> int:
        # Returns proposed_trade, or a fraction thereof
        # Sign is NOT preserved

        spare_capacity = self.trade_capacity_remaining
        if abs_proposed_trade <= spare_capacity:
            abs_possible_trade = abs_proposed_trade
        else:
            abs_possible_trade = spare_capacity

        return abs_possible_trade

    @property
    def instrument_strategy(self) -> instrumentStrategy:
        return self._instrument_strategy

    @property
    def instrument_code(self) -> str:
        return self.instrument_strategy.instrument_code

    @property
    def strategy_name(self) -> str:
        return self.instrument_strategy.strategy_name

    @property
    def trade_capacity_remaining(self) -> int:
        trades_since_last_reset = self.trades_since_last_reset
        limit = self.trade_limit
        spare_capacity = max(0, limit - trades_since_last_reset)

        return spare_capacity

    @property
    def trade_limit(self) -> int:
        return self._trade_limit

    @property
    def period_days(self) -> int:
        return self._period_days

    def update_limit(self, new_limit: int):
        assert new_limit >= 0
        self._trade_limit = int(new_limit)

    @property
    def trades_since_last_reset(self) -> int:
        self._reset_if_reset_due()

        return self._trades_since_last_reset

    @property
    def time_since_last_reset(self):
        now_time = datetime.datetime.now()
        last_reset = self._last_reset_time
        diff = now_time - last_reset

        return diff

    def _reset_if_reset_due(self):
        if self._is_reset_due():
            self.reset()

    def _is_reset_due(self) -> bool:
        reset_period = self._timedelta
        diff = self.time_since_last_reset
        if diff > reset_period:
            return True
        else:
            return False

    def add_trade(self, trade_to_add: int):
        abs_trade_to_add = int(abs(trade_to_add))
        self._trades_since_last_reset = self._trades_since_last_reset + abs_trade_to_add

    def remove_trade(self, trade_to_remove: int):
        abs_trade_to_remove = int(abs(trade_to_remove))
        self._trades_since_last_reset = max(
            self._trades_since_last_reset - abs_trade_to_remove, 0
        )

    def reset(self):
        self._trades_since_last_reset = 0
        self._last_reset_time = datetime.datetime.now()


class listOfTradeLimits(list):
    def __init__(self, list_of_trade_limits: List[tradeLimit]):
        super().__init__(list_of_trade_limits)

    def filter_to_remove_list_of_instruments(
        self, list_of_instruments_to_remove: list
    ) -> "listOfTradeLimits":
        new_list = [
            trade_limit
            for trade_limit in self
            if trade_limit.instrument_code not in list_of_instruments_to_remove
        ]
        return listOfTradeLimits(new_list)

    def filter_to_remove_list_of_strategy_names(
        self, list_of_strategy_names_to_remove: list
    ) -> "listOfTradeLimits":
        new_list = [
            trade_limit
            for trade_limit in self
            if trade_limit.strategy_name not in list_of_strategy_names_to_remove
        ]
        return listOfTradeLimits(new_list)

    def what_trade_is_possible(self, proposed_trade: int):
        abs_proposed_trade = abs(proposed_trade)
        possible_abs_trade = self.what_abs_trade_is_possible(abs_proposed_trade)
        # convert to same sign as proposed
        possible_trade = possible_abs_trade * sign(proposed_trade)

        return possible_trade

    def what_abs_trade_is_possible(self, abs_proposed_trade: int):
        # returns a list of abs_possible_trades
        list_of_abs_possible_trades = [
            trade_limit.what_abs_trade_is_possible(abs_proposed_trade)
            for trade_limit in self
        ]
        if len(list_of_abs_possible_trades) == 0:
            return abs_proposed_trade

        # get the smallest
        possible_abs_trade = min(list_of_abs_possible_trades)

        return possible_abs_trade

    def add_trade(self, trade_to_add: int):
        __ = [trade_limit.add_trade(trade_to_add) for trade_limit in self]

    def remove_trade(self, trade_to_remove: int):
        __ = [trade_limit.remove_trade(trade_to_remove) for trade_limit in self]

    def reset_all(self):
        __ = [trade_limit.reset() for trade_limit in self]
