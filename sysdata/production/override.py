"""
An override is something that affects our normal trading behaviour
"""

from syslogging.logger import get_logger
from sysobjects.production.override import Override, DEFAULT_OVERRIDE
from sysobjects.production.tradeable_object import instrumentStrategy
from sysdata.base_data import baseData


strategy_overrides = "strategies"
instrument_overrides = "instruments"
strategy_instruments_overrides = "strategies_instruments"


class overrideData(baseData):
    def __init__(self, log=get_logger("Overrides")):
        super().__init__(log=log)

    def default_override(self):
        return DEFAULT_OVERRIDE

    def get_cumulative_override_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> Override:
        strategy_override = self._get_override_for_strategy(
            instrument_strategy.strategy_name
        )
        instrument_override = self.get_override_for_instrument(
            instrument_strategy.instrument_code
        )
        strategy_instrument_override = self._get_override_for_instrument_strategy(
            instrument_strategy
        )
        cumulative_override = (
            strategy_override * instrument_override * strategy_instrument_override
        )
        return cumulative_override

    def _get_override_for_strategy(self, strategy_name: str) -> Override:
        return self._get_override_object_for_type_and_key(
            strategy_overrides, strategy_name
        )

    def _get_override_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> Override:
        key = _key_from_instrument_strategy(instrument_strategy)
        return self._get_override_object_for_type_and_key(
            strategy_instruments_overrides, key
        )

    def get_override_for_instrument(self, instrument_code: str) -> Override:
        return self._get_override_object_for_type_and_key(
            instrument_overrides, instrument_code
        )

    def update_override_for_strategy(self, strategy_name: str, new_override: Override):
        self._update_override(strategy_overrides, strategy_name, new_override)

    def update_override_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy, new_override: Override
    ):
        key = _key_from_instrument_strategy(instrument_strategy)
        self._update_override(strategy_instruments_overrides, key, new_override)

    def update_override_for_instrument(
        self, instrument_code: str, new_override: Override
    ):
        self._update_override(instrument_overrides, instrument_code, new_override)

    def get_dict_of_all_overrides(self) -> dict:
        strategy_dict = self._get_dict_of_strategies_with_overrides()
        strategy_instrument_dict = (
            self._get_dict_of_strategy_instrument_with_overrides()
        )
        instrument_dict = self._get_dict_of_instruments_with_overrides()

        all_overrides = {**strategy_dict, **strategy_instrument_dict, **instrument_dict}

        return all_overrides

    def delete_all_overrides(self, are_you_sure=False):
        if are_you_sure:
            self._delete_all_overrides_without_checking()

    def _get_dict_of_strategies_with_overrides(self) -> dict:
        return self._get_dict_of_items_with_overrides_for_type(strategy_overrides)

    def _get_dict_of_strategy_instrument_with_overrides(self) -> dict:
        return self._get_dict_of_items_with_overrides_for_type(
            strategy_instruments_overrides
        )

    def _get_dict_of_instruments_with_overrides(self) -> dict:
        return self._get_dict_of_items_with_overrides_for_type(instrument_overrides)

    def _delete_all_overrides_without_checking(self):
        raise NotImplementedError

    def _update_override(
        self, override_type: str, key: str, new_override_object: Override
    ):
        raise NotImplementedError

    def _get_override_object_for_type_and_key(
        self, override_type: str, key: str
    ) -> Override:
        raise NotImplementedError

    def _get_dict_of_items_with_overrides_for_type(self, override_type: str) -> dict:
        raise NotImplementedError


def _key_from_instrument_strategy(instrument_strategy: instrumentStrategy):
    return instrument_strategy.strategy_name + "/" + instrument_strategy.instrument_code
