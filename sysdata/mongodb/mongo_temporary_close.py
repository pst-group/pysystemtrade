from syscore.constants import arg_not_supplied

from sysdata.production.temporary_close import temporaryCloseData
from sysobjects.production.position_limits import positionLimitForInstrument
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

TEMPORARY_CLOSE_COLLECTION = "temporary_close_collection"
KEY = "instrument_code"
POSITION_LIMIT_FIELD = "position_limit"


class mongoTemporaryCloseData(temporaryCloseData):
    def __init__(
        self, mongo_db=arg_not_supplied, log=get_logger("mongotemporaryCloseData")
    ):
        super().__init__(log=log)
        self._mongo_data = mongoDataWithSingleKey(
            TEMPORARY_CLOSE_COLLECTION, "instrument_code", mongo_db=mongo_db
        )

    def __repr__(self):
        return "mongoTemporaryCloseDataData %s" % str(self.mongo_data)

    @property
    def mongo_data(self):
        return self._mongo_data

    def get_list_of_instruments(self):
        return self.mongo_data.get_list_of_keys()

    def get_stored_position_limit_for_instrument(
        self, instrument_code: str
    ) -> positionLimitForInstrument:
        result_dict = self.mongo_data.get_result_dict_for_key(instrument_code)

        return positionLimitForInstrument(
            instrument_code, result_dict[POSITION_LIMIT_FIELD]
        )

    def _add_stored_position_limit_without_checking(
        self, position_limit_for_instrument: positionLimitForInstrument
    ):
        data_dict = {POSITION_LIMIT_FIELD: position_limit_for_instrument.position_limit}
        instrument_code = position_limit_for_instrument.key
        self.mongo_data.add_data(instrument_code, data_dict, allow_overwrite=True)

    def does_instrument_have_position_limit_stored(self, instrument_code) -> bool:
        list_of_keys = self.get_list_of_instruments()
        return instrument_code in list_of_keys

    def _delete_stored_position_limit_without_checking(self, instrument_code: str):
        self.mongo_data.delete_data_without_any_warning(instrument_code)
