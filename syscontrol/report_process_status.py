import datetime

from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

LOG_CLEARED = object()
NO_LOG_ENTRY = object()
FREQUENCY_TO_CHECK_LOG_MINUTES = 10


class reportStatus(object):
    ## Report on status when waiting and paused, ensures we don't spam the log
    def __init__(self, log=arg_not_supplied):
        if log is arg_not_supplied:
            log = get_logger("")
        self._log = log

    @property
    def log(self):
        return self._log

    def log_status(self, status: str = ""):
        we_already_logged_recently = self._have_we_logged_recently(status)

        if we_already_logged_recently:
            return None

        self._log_and_mark_timing(status)

    def clear_status(self, status: str = ""):
        have_we_never_logged_before = self._have_we_never_logged_at_all_before(status)
        if have_we_never_logged_before:
            # nothing to clear
            return None

        have_we_logged_clear_already = self._have_we_logged_clear_already(status)
        if have_we_logged_clear_already:
            return None
        self._log_clear_and_mark(status)

    def clear_all_status(self):
        self._log_store = {}

    def _have_we_logged_recently(self, status: str) -> bool:
        last_log_time = self._get_last_log_time(status)
        if last_log_time is NO_LOG_ENTRY:
            return False
        if last_log_time is LOG_CLEARED:
            return False
        time_for_another_log = self._time_for_another_log(last_log_time)
        if time_for_another_log:
            return False
        return True

    def _time_for_another_log(self, log_time):
        elapsed_minutes = self._minutes_elapsed_since_log(log_time)
        if elapsed_minutes > FREQUENCY_TO_CHECK_LOG_MINUTES:
            return True
        else:
            return False

    def _minutes_elapsed_since_log(self, log_time: datetime.datetime) -> float:
        time_now = datetime.datetime.now()
        elapsed_time = time_now - log_time
        elapsed_seconds = elapsed_time.total_seconds()
        elapsed_minutes = elapsed_seconds / 60

        return elapsed_minutes

    def _log_and_mark_timing(self, status: str):
        self.log.debug(status)
        self._mark_timing_of_log(status)

    def _mark_timing_of_log(self, status):
        self._set_last_log_time(status, datetime.datetime.now())

    def _have_we_logged_clear_already(self, status: str) -> bool:
        last_log_time = self._get_last_log_time(status)

        return last_log_time is LOG_CLEARED

    def _have_we_never_logged_at_all_before(self, status: str) -> bool:
        last_log_time = self._get_last_log_time(status)

        return last_log_time is NO_LOG_ENTRY

    def _get_all_keys_in_store(self) -> list:
        log_store = self._get_log_store()
        all_keys = list(log_store.keys())

        return all_keys

    def _log_clear_and_mark(self, status: str):
        self.log.debug("No longer- %s" % status)
        self._mark_log_of_clear(status)

    def _mark_log_of_clear(self, status):
        self._set_last_log_time(status, LOG_CLEARED)

    def _get_last_log_time(self, status: str) -> datetime.datetime:
        log_store = self._get_log_store()
        last_log_time = log_store.get(status, NO_LOG_ENTRY)

        return last_log_time

    def _set_last_log_time(self, status: str, log_time):
        log_store = self._get_log_store()
        log_store[status] = log_time

    def _get_log_store(self) -> dict:
        log_store = getattr(self, "_log_store", None)
        if log_store is None:
            log_store = self._log_store = {}
        return log_store


def _store_name(reason, condition):
    return condition + ":" + reason


def _split_name(keyname):
    return keyname.split(":")


class reportProcessStatus(reportStatus):
    def report_wait_condition(self, reason: str, condition_name: str = ""):
        status = _store_name(reason, condition_name)
        super().log_status(status)

    def clear_all_reasons_for_condition(self, condition_name: str):
        list_of_reasons = self._get_all_reasons_for_condition(condition_name)
        _ = [
            self.clear_wait_condition(reason, condition_name)
            for reason in list_of_reasons
        ]

    def clear_wait_condition(self, reason, condition_name: str = ""):
        status = _store_name(reason, condition_name)
        super().clear_status(status)

    def _get_all_reasons_for_condition(self, condition_name: str):
        paired_keys = self._get_all_paired_keys_in_store()
        reason_list = [pair[1] for pair in paired_keys if pair[0] == condition_name]

        return reason_list

    def _get_all_paired_keys_in_store(self) -> list:
        all_keys = self._get_all_keys_in_store()
        paired_keys = [_split_name(keyname) for keyname in all_keys]

        return paired_keys
