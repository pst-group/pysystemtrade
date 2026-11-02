from syscore.constants import arg_not_supplied
from sysdata.base_data import baseData
from syslogging.logger import get_logger


class brokerClientIdData(baseData):
    """
    Read and write data class to get next used client id
    """

    def __init__(
        self,
        idoffset: int = 0,
        log=get_logger("brokerClientIdTracker"),
    ):
        super().__init__(log=log)

        self._idoffset = idoffset

    @property
    def idoffset(self) -> int:
        return self._idoffset

    def __repr__(self):
        return "Tracking broker client IDs"

    def return_valid_client_id(self, clientid_to_try: int = arg_not_supplied) -> int:
        """
        If clientid_to_try is None, return the next free ID
        If clientid_to_try is being used, return the next free ID, otherwise allow that to be used
        :param clientid_to_try: int or None
        :return: int
        """
        if clientid_to_try is arg_not_supplied:
            clientid_to_use = self._get_and_lock_next_clientid()
            return clientid_to_use

        if self._is_clientid_used(clientid_to_try):
            # being used, get another one
            # this will also lock it
            clientid_to_use = self._get_and_lock_next_clientid()
            return clientid_to_use

        self._lock_clientid(clientid_to_try)  # lock

        return clientid_to_try

    def _is_clientid_used(self, clientid: int) -> bool:
        """
        Checks if a client id is in use
        :param clientid: int
        :return: bool
        """
        current_ids = self._get_list_of_clientids()
        if clientid in current_ids:
            return True
        else:
            return False

    def _get_and_lock_next_clientid(self) -> int:
        """
        Returns a client id which will be locked so no other use can use it
        The clientid in question is the lowest available unused value
        :return: clientid
        """

        current_list_of_ids = self._get_list_of_clientids()
        next_id = get_next_id_from_current_list(
            current_list_of_ids, id_offset=self.idoffset
        )

        # lock
        self._lock_clientid(next_id)

        return next_id

    def _get_list_of_clientids(self) -> list:
        raise NotImplementedError("Need to implement in child class")

    def _lock_clientid(self, next_id):
        raise NotImplementedError("Need to implement in child class")

    def clear_all_clientids(self):
        """
        Clear all the client ids
        Should be done on machine startup
        :return:
        """
        client_id_list = self._get_list_of_clientids()
        self.log.warning(
            "Clearing all broker client IDs: if anything still running will probably break!"
        )
        for client_id in client_id_list:
            self.release_clientid(client_id)

    def release_clientid(self, clientid: int):
        """
        Delete a client id lock
        :param clientid:
        :return: None
        """

        raise NotImplementedError("Need to implement in child class")


def get_next_id_from_current_list(current_list_of_ids: list, id_offset: int = 0) -> int:
    if len(current_list_of_ids) == 0:
        # no IDS in use
        return id_offset

    full_set_of_available_ids = set(range(id_offset, max(current_list_of_ids) + 1))

    next_id = get_next_id_from_current_list_and_full_set(
        current_list_of_ids, full_set_of_available_ids
    )

    return next_id


def get_next_id_from_current_list_and_full_set(
    current_list_of_ids: list, full_set_of_available_ids: set
) -> int:
    unused_values = full_set_of_available_ids - set(current_list_of_ids)
    if len(unused_values) == 0:
        # no gaps, return the higest number plus 1
        return max(current_list_of_ids) + 1
    else:
        # there is a gap, use the lowest numbered one
        return min(unused_values)
