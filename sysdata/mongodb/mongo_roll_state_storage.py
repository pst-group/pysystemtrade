from sysdata.production.roll_state import rollStateData
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

ROLL_STATUS_COLLECTION = "futures_roll_status"
ROLL_KEY = "instrument_code"
ROLL_STATE_KEY = "roll_state"


class mongoRollStateData(rollStateData):
    """
    Read and write data class to get roll state data


    """

    def __init__(self, mongo_db=None, log=get_logger("mongoRollStateData")):
        super().__init__(log=log)

        self._mongo_data = mongoDataWithSingleKey(
            ROLL_STATUS_COLLECTION, ROLL_KEY, mongo_db=mongo_db
        )

    def __repr__(self):
        return "Data connection for futures roll state, mongodb %s" % str(
            self.mongo_data
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def get_list_of_instruments(self) -> list:
        codes = self.mongo_data.get_list_of_keys()

        return codes

    def _get_roll_state_as_str_no_default(self, instrument_code: str):
        result_dict = self.mongo_data.get_result_dict_for_key(instrument_code)

        roll_status = result_dict[ROLL_STATE_KEY]

        return roll_status

    def _set_roll_state_as_str_without_checking(
        self, instrument_code: str, new_roll_state_as_str: str
    ):
        data_dict = {ROLL_STATE_KEY: new_roll_state_as_str}
        self.mongo_data.add_data(instrument_code, data_dict, allow_overwrite=True)
