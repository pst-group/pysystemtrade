from sysbrokers.IB.config.ib_instrument_config import (
    IBconfig,
    read_ib_config_from_file,
    get_instrument_object_from_config,
    IB_FUTURES_CONFIG_FILE,
    get_instrument_list_from_ib_config,
)
from sysbrokers.IB.ib_instruments import (
    futuresInstrumentWithIBConfigData,
)
from sysbrokers.IB.ib_contracts import ibContract
from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.client.ib_client import ibClient
from sysbrokers.broker_instrument_data import brokerFuturesInstrumentData
from syscore.exceptions import missingFile

from sysdata.data_blob import dataBlob

from syslogging.logger import get_logger


class ibFuturesInstrumentData(brokerFuturesInstrumentData):
    def __init__(
        self,
        ibconnection: connectionIB,
        data: dataBlob,
        log=get_logger("ibFuturesInstrumentData"),
    ):
        super().__init__(log=log, data=data)
        self._ibconnection = ibconnection

    def __repr__(self):
        return "IB Futures per contract data %s" % str(self.ibconnection)

    def get_instrument_code_from_broker_contract_object(
        self, broker_contract_object: ibContract
    ) -> str:
        instrument_code = (
            self.ib_client.get_instrument_code_from_broker_contract_object(
                broker_contract_object
            )
        )

        return instrument_code

    def _get_instrument_data_without_checking(self, instrument_code: str):
        return self.get_futures_instrument_object_with_IB_data(instrument_code)

    def get_futures_instrument_object_with_IB_data(
        self, instrument_code: str
    ) -> futuresInstrumentWithIBConfigData:
        config = self.ib_config
        instrument_object = get_instrument_object_from_config(
            instrument_code, log=self.log, config=config
        )

        return instrument_object

    def get_list_of_instruments(self) -> list:
        """
        Get instruments that have price data
        Pulls these in from a config file

        :return: list of str
        """

        try:
            config = self.ib_config
        except missingFile:
            self.log.warning(
                "Can't get list of instruments because IB config file missing"
            )
            return []

        instrument_list = get_instrument_list_from_ib_config(config)

        return instrument_list

    # Configuration read in and cache
    @property
    def ib_config(self) -> IBconfig:
        config = getattr(self, "_config", None)
        if config is None:
            config = self._get_and_set_ib_config_from_file()

        return config

    @property
    def ib_client(self) -> ibClient:
        client = getattr(self, "_ib_client", None)
        if client is None:
            client = self._ib_client = ibClient(
                ibconnection=self.ibconnection, log=self.log
            )

        return client

    @property
    def ibconnection(self) -> connectionIB:
        return self._ibconnection

    def _get_and_set_ib_config_from_file(self) -> IBconfig:
        config_data = read_ib_config_from_file(log=self.log)

        return config_data

    def _delete_instrument_data_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError(
            "IB instrument config is read only - manually edit .csv file %s"
            % IB_FUTURES_CONFIG_FILE
        )

    def _add_instrument_data_without_checking_for_existing_entry(
        self, instrument_object
    ):
        raise NotImplementedError(
            "IB instrument config is read only - manually edit .csv file %s"
            % IB_FUTURES_CONFIG_FILE
        )
