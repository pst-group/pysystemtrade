from sysobjects.production.process_control import controlProcess
from sysdata.production.process_control_data import controlProcessData
from syscore.constants import arg_not_supplied

from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

PROCESS_CONTROL_COLLECTION = "process_control"
PROCESS_CONTROL_KEY = "process_name"


class mongoControlProcessData(controlProcessData):
    """
    Read and write data class to get process control data


    """

    def __init__(
        self, mongo_db=arg_not_supplied, log=get_logger("mongoControlProcessData")
    ):
        super().__init__(log=log)

        self._mongo_data = mongoDataWithSingleKey(
            PROCESS_CONTROL_COLLECTION, PROCESS_CONTROL_KEY, mongo_db=mongo_db
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "Data connection for process control, mongodb %s" % str(self.mongo_data)

    def get_list_of_process_names(self):
        return self.mongo_data.get_list_of_keys()

    def _get_control_for_process_name_without_default(self, process_name):
        result_dict = self.mongo_data.get_result_dict_for_key_without_key_value(
            process_name
        )

        control_object = controlProcess.from_dict(result_dict)

        return control_object

    def _modify_existing_control_for_process_name(
        self, process_name, new_control_object
    ):
        self.mongo_data.add_data(
            process_name, new_control_object.as_dict(), allow_overwrite=True
        )

    def _add_control_for_process_name(self, process_name, new_control_object):
        self.mongo_data.add_data(
            process_name, new_control_object.as_dict(), allow_overwrite=False
        )

    def delete_control_for_process_name(self, process_name):
        self.mongo_data.delete_data_without_any_warning(process_name)
