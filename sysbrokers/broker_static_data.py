from sysdata.base_data import baseData
from sysdata.data_blob import dataBlob
from syslogging.logger import get_logger


class brokerStaticData(baseData):
    def __init__(self, data: dataBlob, log=get_logger("brokerStaticData")):
        super().__init__(log=log)
        self._data = data

    def get_broker_clientid(self) -> int:
        raise NotImplementedError

    def get_broker_account(self) -> str:
        raise NotImplementedError

    def get_broker_name(self) -> str:
        raise NotImplementedError

    @property
    def data(self) -> dataBlob:
        return self._data
