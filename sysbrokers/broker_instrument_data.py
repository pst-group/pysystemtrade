from sysdata.data_blob import dataBlob
from sysdata.futures.instruments import futuresInstrumentData

from syslogging.logger import get_logger


class brokerFuturesInstrumentData(futuresInstrumentData):
    """
    Extends futuresInstrumentData to a data source for broker futures instrument data.
    Could be extended to implement a data source for a specific broker
    """

    def __init__(self, data: dataBlob, log=get_logger("brokerFuturesInstrumentData")):
        super().__init__(log=log)
        self._data = data

    def get_instrument_code_from_broker_contract_object(
        self, broker_contract_object: str
    ) -> str:
        raise NotImplementedError

    def get_list_of_instruments(self) -> list:
        raise NotImplementedError

    @property
    def data(self) -> dataBlob:
        return self._data
