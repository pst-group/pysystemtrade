from syscore.constants import arg_not_supplied
from sysdata.production.locks import lockData, lock_on
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

LOCK_STATUS_COLLECTION = "locks"
LOCK_DICT_KEY = "lock"


class mongoLockData(lockData):
    """
    Read and write data class to get lock data


    """

    def __init__(self, mongo_db=arg_not_supplied, log=get_logger("mongoLockData")):
        super().__init__(log=log)
        self._mongo_data = mongoDataWithSingleKey(
            LOCK_STATUS_COLLECTION, "instrument_code", mongo_db=mongo_db
        )

    def __repr__(self):
        return "mongoLockData %s" % str(self.mongo_data)

    @property
    def mongo_data(self):
        return self._mongo_data

    def _get_lock_for_instrument_no_checking(self, instrument_code: str) -> str:
        result = self.mongo_data.get_result_dict_for_key(instrument_code)

        lock = result[LOCK_DICT_KEY]

        return lock

    def add_lock_for_instrument(self, instrument_code: str):
        self.mongo_data.add_data(instrument_code, {LOCK_DICT_KEY: lock_on})

    def remove_lock_for_instrument(self, instrument_code):
        self.mongo_data.delete_data_without_any_warning(instrument_code)

    def get_list_of_locked_instruments(self):
        all_instruments = self.mongo_data.get_list_of_keys()
        all_instruments_with_locks = [
            instrument_code
            for instrument_code in all_instruments
            if self.is_instrument_locked(instrument_code)
        ]

        return all_instruments_with_locks
