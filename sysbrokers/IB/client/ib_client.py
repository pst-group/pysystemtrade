import datetime

from typing import List, Union
from ib_async import IB, ContractDetails as ibContractDetails

from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.ib_contracts import ibContract
from sysbrokers.IB.config.ib_instrument_config import (
    IBconfig,
    read_ib_config_from_file,
    get_instrument_code_from_broker_instrument_identity,
    IBInstrumentIdentity,
)

from syscore.constants import arg_not_supplied
from syscore.cache import Cache
from syscore.exceptions import missingContract

from syslogging.logger import get_logger


# IB state that pacing violations only occur for bar sizes of less than 1 minute
# See footnote at bottom of
# https://interactivebrokers.github.io/tws-api/historical_limitations.html#pacing_violations
PACING_INTERVAL_SECONDS = 0.5


STALE_SECONDS_ALLOWED_ACCOUNT_SUMMARY = 600


class ibClient(object):
    """
    Client specific to interactive brokers

    We inherit from this to do interesting stuff, so this base class just offers error handling and get time

    """

    def __init__(self, ibconnection: connectionIB, log=get_logger("ibClient")):
        # means our first call won't be throttled for pacing
        self.last_historic_price_calltime = (
            datetime.datetime.now()
            - datetime.timedelta(seconds=PACING_INTERVAL_SECONDS)
        )

        self._ib_connnection = ibconnection
        self._log = log
        self._cache = Cache(self)

    @property
    def cache(self) -> Cache:
        return self._cache

    @property
    def ib_connection(self) -> connectionIB:
        return self._ib_connnection

    @property
    def ib(self) -> IB:
        return self.ib_connection.ib

    @property
    def client_id(self) -> int:
        return self.ib.client.clientId

    @property
    def log(self):
        return self._log

    def refresh(self):
        self.ib.sleep(0.00001)

    def get_instrument_code_from_broker_contract_object(
        self, broker_contract_object: ibContract
    ) -> str:
        broker_identity = self.broker_identity_for_contract(broker_contract_object)
        instrument_code = self.get_instrument_code_from_broker_identity_for_contract(
            broker_identity
        )

        return instrument_code

    def get_instrument_code_from_broker_identity_for_contract(
        self, ib_instrument_identity: IBInstrumentIdentity, config=arg_not_supplied
    ) -> str:
        if config is arg_not_supplied:
            config = self.ib_config

        instrument_code = get_instrument_code_from_broker_instrument_identity(
            ib_instrument_identity=ib_instrument_identity,
            log=self.log,
            config=config,
        )
        return instrument_code

    @property
    def ib_config(self) -> IBconfig:
        config = getattr(self, "_config", None)
        if config is None:
            config = self._get_and_set_ib_config_from_file()

        return config

    def _get_and_set_ib_config_from_file(self) -> IBconfig:
        config_data = read_ib_config_from_file(log=self.log)

        return config_data

    def broker_identity_for_contract(
        self,
        ib_contract_pattern: ibContract,
    ) -> IBInstrumentIdentity:
        contract_details = self.get_contract_details(
            ib_contract_pattern=ib_contract_pattern,
            allow_expired=False,
            allow_multiple_contracts=False,
        )

        return IBInstrumentIdentity(
            ib_code=str(contract_details.contract.symbol),
            ib_multiplier=float(contract_details.contract.multiplier),
            ib_exchange=str(contract_details.contract.exchange),
            ib_valid_exchange=str(contract_details.validExchanges),
        )

    def get_contract_details(
        self,
        ib_contract_pattern: ibContract,
        allow_expired: bool = False,
        allow_multiple_contracts: bool = False,
    ) -> Union[ibContractDetails, List[ibContractDetails]]:
        contract_details = self._get_contract_details(
            ib_contract_pattern, allow_expired=allow_expired
        )

        if len(contract_details) == 0:
            raise missingContract

        if allow_multiple_contracts:
            return contract_details

        elif len(contract_details) > 1:
            self.log.critical(
                "Multiple contracts and only expected one - returning the first"
            )

        return contract_details[0]

    def _get_contract_details(
        self, ib_contract_pattern: ibContract, allow_expired: bool = False
    ) -> List[ibContractDetails]:
        ## in case of caching
        ib_contract_pattern.includeExpired = allow_expired

        return self.ib.reqContractDetails(ib_contract_pattern)
