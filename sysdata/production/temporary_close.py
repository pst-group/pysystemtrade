from sysdata.base_data import baseData
from syslogging.logger import get_logger

from sysobjects.production.position_limits import positionLimitForInstrument


class temporaryCloseData(baseData):
    """
    Temporary close is a way of temporarily setting position limits to
     zero

    We use this table to store the old position limits

    """

    def __init__(self, log=get_logger("temporaryCloseData")):
        super().__init__(log=log)

    def add_stored_position_limit(
        self, position_limit_for_instrument: positionLimitForInstrument
    ):
        if self.does_instrument_have_position_limit_stored(
            position_limit_for_instrument.key
        ):
            raise Exception(
                "Need to clear_stored_position_limit before adding a new one for %s"
                % position_limit_for_instrument.key
            )

        self._add_stored_position_limit_without_checking(position_limit_for_instrument)

    def get_stored_position_limit_for_instrument(
        self, instrument_code: str
    ) -> positionLimitForInstrument:
        raise NotImplementedError("Need to use inheriting class")

    def clear_stored_position_limit_for_instrument(self, instrument_code: str):
        if self.does_instrument_have_position_limit_stored(instrument_code):
            self._delete_stored_position_limit_without_checking(instrument_code)

    def _add_stored_position_limit_without_checking(
        self, position_limit_for_instrument: positionLimitForInstrument
    ):
        raise NotImplementedError("Need to use inheriting class")

    def does_instrument_have_position_limit_stored(self, instrument_code) -> bool:
        raise NotImplementedError("Need to use inheriting class")

    def _delete_stored_position_limit_without_checking(self, instrument_code: str):
        raise NotImplementedError("Need to use inheriting class")
