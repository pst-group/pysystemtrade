from syscore.exceptions import missingData
from sysdata.base_data import baseData
from syslogging.logger import get_logger
from sysobjects.production.roll_state import (
    RollState,
    default_state,
    name_of_roll_state,
)


class rollStateData(baseData):
    """
    Store and retrieve the roll state of a particular instrument
    """

    def __init__(self, log=get_logger("rollStateData")):
        super().__init__(log=log)

    def get_name_of_roll_state(self, instrument_code: str) -> str:
        state = self.get_roll_state(instrument_code)
        state_name = name_of_roll_state(state)
        return state_name

    def get_roll_state(self, instrument_code: str) -> RollState:
        try:
            state_as_str = self._get_roll_state_as_str_no_default(instrument_code)
        except missingData:
            state = default_state
            self.set_roll_state(instrument_code, state)
        else:
            state = RollState[state_as_str]

        return state

    def set_roll_state(self, instrument_code: str, new_roll_state: RollState):
        new_roll_state_as_str = name_of_roll_state(new_roll_state)
        self._set_roll_state_as_str_without_checking(
            instrument_code, new_roll_state_as_str
        )

    def get_list_of_instruments(self) -> list:
        raise NotImplementedError

    def _set_roll_state_as_str_without_checking(
        self, instrument_code: str, new_roll_state_as_str: str
    ):
        raise NotImplementedError("Need to use inheriting class")

    def _get_roll_state_as_str_no_default(self, instrument_code: str) -> str:
        raise NotImplementedError("Need to use inheriting class")
