from syscore.constants import arg_not_supplied

from syslogging.logger import get_logger

from sysbrokers.IB.ib_connection_defaults import ib_defaults
from sysdata.production.broker_client_id import brokerClientIdData


class ibBrokerClientIdData(brokerClientIdData):
    """
    Read and write data class to get next used client id
    """

    def __init__(
        self,
        idoffset=arg_not_supplied,
        log=get_logger("brokerClientIdTracker"),
    ):
        if idoffset is arg_not_supplied:
            _notused_ipaddress, _notused_port, idoffset = ib_defaults()

        super().__init__(log=log, idoffset=idoffset)

    def __repr__(self):
        return "Tracking IB client IDs"
