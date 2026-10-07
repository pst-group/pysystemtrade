from sysbrokers.IB.client.ib_client_id import ibBrokerClientIdData
from syscore.constants import arg_not_supplied
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import *

IB_CLIENT_COLLECTION = "IBClientTracker"
IB_ID_REF = "client_id"


class mongoIbBrokerClientIdData(ibBrokerClientIdData):
    """
    Read and write data class to get next used client id
    """

    def __init__(
        self,
        mongo_db=arg_not_supplied,
        idoffset=arg_not_supplied,
        log=get_logger("mongoIDTracker"),
    ):
        super().__init__(log=log, idoffset=idoffset)
        self._mongo_data = mongoDataWithSingleKey(
            IB_CLIENT_COLLECTION, IB_ID_REF, mongo_db
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "Tracking IB client IDs, mongodb %s" % (str(self.mongo_data))

    def _get_list_of_clientids(self) -> list:
        return self.mongo_data.get_list_of_keys()

    def _lock_clientid(self, next_id: int):
        self.mongo_data.add_data(next_id, {})
        self.log.debug("Locked IB client ID %d" % next_id)

    def release_clientid(self, clientid: int):
        """
        Delete a client id lock
        :param clientid:
        :return: None
        """
        self.mongo_data.delete_data_without_any_warning(clientid)
        self.log.debug("Released IB client ID %d" % clientid)
