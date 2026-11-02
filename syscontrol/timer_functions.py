import numpy as np
import datetime

from syscontrol.report_process_status import reportStatus
from syscontrol.timer_parameters import timerClassParameters
from sysdata.data_blob import dataBlob
from sysproduction.data.control_process import diagControlProcess, dataControlProcess
from syslogging.logger import get_logger

## Don't change this without also changing the config
INFINITE_EXECUTIONS = -1

## Used to indicate not yet run
A_LONG_LONG_TIME_AGO = datetime.datetime(1980, 1, 1)


class timerClassWithFunction(object):
    def __init__(
        self,
        function_to_execute,
        data: dataBlob,
        parameters: timerClassParameters,
        log=get_logger(""),
    ):
        self._function = function_to_execute  # class.method to run
        self._data = data
        self._parameters = parameters

        self._log = log
        self._report_status = reportStatus(log)

        self._actual_executions = 0

        self._log_on_startup()

    def _log_on_startup(self):
        log = self.log
        method_name = self.method_name
        if self.run_on_completion_only:
            log.debug("%s will run once only on process completion" % method_name)
            return None

        max_executions = self.max_executions

        if max_executions == INFINITE_EXECUTIONS:
            exec_string = "until process ends"
        else:
            exec_string = "at most %d times" % max_executions

        log.debug(
            "%s will run every %d minutes %s with heartbeats every %d minutes"
            % (
                method_name,
                self.frequency_minutes,
                exec_string,
                self.minutes_between_heartbeats,
            )
        )

    @property
    def data(self):
        return self._data

    @property
    def parameters(self) -> timerClassParameters:
        return self._parameters

    @property
    def process_name(self):
        return self.parameters.process_name

    @property
    def log(self):
        return self._log

    @property
    def frequency_minutes(self) -> int:
        return self.parameters.frequency_minutes

    @property
    def method_name(self) -> str:
        return self.parameters.method_name

    @property
    def minutes_between_heartbeats(self) -> int:
        return self.parameters.minutes_between_heartbeats

    @property
    def run_on_completion_only(self) -> bool:
        return self.parameters.run_on_completion_only

    @property
    def max_executions(self) -> int:
        return self.parameters.max_executions

    @property
    def actual_executions(self) -> int:
        return self._actual_executions

    @property
    def reached_maximum_executions(self) -> bool:
        return self.actual_executions >= self.max_executions

    @property
    def report_status(self) -> reportStatus:
        return self._report_status

    def log_msg(self, msg: str):
        self.log.debug(msg, type=self.process_name)

    def check_and_run(self, last_run: bool = False, **kwargs):
        """

        :return: None
        """
        self.log_heartbeat_if_required()
        okay_to_run = self.check_if_okay_to_run(last_run=last_run)
        if not okay_to_run:
            return None

        self.setup_about_to_run_method()
        self.run_function(**kwargs)
        self.finished_running_method()

    def check_if_okay_to_run(self, last_run=False) -> bool:
        if self.run_on_completion_only:
            okay_to_run = self.check_if_okay_to_run_if_runs_at_end_only(last_run)
            return okay_to_run

        # normal
        okay_to_run = self.check_if_okay_to_run_normal_run(last_run)
        return okay_to_run

    def check_if_okay_to_run_if_runs_at_end_only(self, last_run: bool = False) -> bool:
        if last_run:
            self.log_msg(
                "Running %s as this is the final run for process %s"
                % (self.method_name, self.process_name)
            )

            return True

        # not the last run, don't run yet
        # use report status to avoid spamming

        self.report_status.log_status(
            "Not running %s as only runs when process %s ends"
            % (self.method_name, self.process_name)
        )
        return False

    def check_if_okay_to_run_normal_run(self, last_run: bool = False) -> bool:
        if last_run:
            # don't run a normal process on last run
            return False

        # okay not a last run, so check if timer elapsed enough and we
        # haven't done too many

        okay_to_run = self.check_if_okay_to_run_normal_run_if_not_last_run()

        return okay_to_run

    def check_if_okay_to_run_normal_run_if_not_last_run(self) -> bool:
        exceeded_max = self.completed_max_runs()
        if exceeded_max:
            return False

        enough_time_has_passed = (
            self.check_if_enough_time_has_passed_and_report_status()
        )

        if enough_time_has_passed:
            return True
        else:
            return False

    def check_if_enough_time_has_passed_and_report_status(self) -> bool:
        enough_time_has_passed = self.check_if_enough_time_has_elapsed_since_last_run()
        enough_time_has_passed_status = (
            "Not enough time has passed since last run of %s in %s"
            % (self.method_name, self.process_name)
        )
        if not enough_time_has_passed:
            self.report_status.log_status(enough_time_has_passed_status)
        else:
            self.report_status.clear_status(enough_time_has_passed_status)

        return enough_time_has_passed

    def check_if_enough_time_has_elapsed_since_last_run(self) -> bool:
        minutes_until_next_run = self.minutes_until_next_run()
        if np.isnan(minutes_until_next_run):
            ## completed the run
            return False

        if minutes_until_next_run == 0:
            return True
        else:
            return False

    def minutes_until_next_run(self) -> float:
        if self.completed_max_runs():
            return np.nan

        time_since_run = self.minutes_since_last_run()
        minutes_between_runs = self.frequency_minutes

        remaining_minutes = max(minutes_between_runs - time_since_run, 0)

        return remaining_minutes

    def log_heartbeat_if_required(self):
        time_since_heartbeat = self.minutes_since_last_heartbeat()
        if time_since_heartbeat > self.minutes_between_heartbeats:
            self.log_heartbeat()

    def log_heartbeat(self):
        if self.max_executions is INFINITE_EXECUTIONS:
            exec_string = "unlimited"
        else:
            exec_string = str(self.max_executions)

        if self.run_on_completion_only:
            log_msg = "%s will run on completion" % self.method_name
        else:
            log_msg = "%s still alive, done %d of %s executions every %d minutes" % (
                self.method_name,
                self.actual_executions,
                exec_string,
                self.frequency_minutes,
            )

        self.log_msg(log_msg)

        self._last_heartbeat = datetime.datetime.now()

    def minutes_since_last_run(self) -> float:
        when_last_run = self.when_last_run()
        time_now = datetime.datetime.now()
        delta = time_now - when_last_run
        delta_minutes = delta.total_seconds() / 60.0

        return delta_minutes

    def when_last_run(self) -> datetime.datetime:
        when_last_run = getattr(self, "_last_run", A_LONG_LONG_TIME_AGO)

        return when_last_run

    def minutes_since_last_heartbeat(self) -> float:
        when_last_beat = self.when_last_heartbeat()
        time_now = datetime.datetime.now()
        delta = time_now - when_last_beat
        delta_minutes = delta.total_seconds() / 60.0

        return delta_minutes

    def when_last_heartbeat(self):
        when_last_heartbeat = getattr(self, "_last_heartbeat", A_LONG_LONG_TIME_AGO)
        return when_last_heartbeat

    def completed_max_runs(self):
        if self.run_on_completion_only:
            # doesn't apply
            return True

        if self.max_executions == INFINITE_EXECUTIONS:
            # unlimited
            return False

        if self.reached_maximum_executions:
            return True

        return False

    def setup_about_to_run_method(self):
        self.increment_executions()
        self.set_time_of_last_run()
        self.store_in_db_run_start_method()

    def increment_executions(self):
        self._actual_executions = self._actual_executions + 1

    def set_time_of_last_run(self):
        self._last_run = datetime.datetime.now()

    def store_in_db_run_start_method(self):
        data_process = dataControlProcess(self.data)
        data_process.log_start_run_for_method(self.process_name, self.method_name)

    def run_function(self, **kwargs):
        # Functions can't take args or kwargs or return anything; pure method
        self._function(**kwargs)

    def finished_running_method(self):
        self.store_in_db_log_run_end_method()
        self.log_msg_when_completed_last_run()

    def store_in_db_log_run_end_method(self):
        data_process = dataControlProcess(self.data)
        data_process.log_end_run_for_method(self.process_name, self.method_name)

    def log_msg_when_completed_last_run(self):
        if self.completed_max_runs():
            self.log_msg(
                "%s executed %d times so done" % (self.method_name, self.max_executions)
            )


class listOfTimerFunctions(list):
    def check_all_finished(self) -> bool:
        if len(self) == 0:
            return True

        finished = [timer_class.completed_max_runs() for timer_class in self]
        all_finished = all(finished)

        return all_finished

    def run_methods_which_run_on_exit_only(self, **kwargs):
        for timer_class in self:
            timer_class.check_and_run(last_run=True, **kwargs)

    def seconds_until_next_method_runs(self) -> float:
        minutes_remaining = [
            timer_object.minutes_until_next_run() for timer_object in self
        ]
        min_minutes = np.nanmin(minutes_remaining)
        min_seconds = min_minutes * 60.0

        return min_seconds


def get_list_of_timer_functions(
    data: dataBlob,
    process_name: str,
    list_of_timer_names_and_functions_as_strings: list,
) -> listOfTimerFunctions:
    list_of_timer_functions_as_list = [
        _get_timer_class(data, process_name, entry)
        for entry in list_of_timer_names_and_functions_as_strings
    ]

    list_of_timer_functions = listOfTimerFunctions(list_of_timer_functions_as_list)

    return list_of_timer_functions


def _get_timer_class(
    data: dataBlob, process_name: str, entry
) -> timerClassWithFunction:
    method_name, object = entry

    function_object = getattr(object, method_name)

    diag_process = diagControlProcess(data)
    timer_parameters = diag_process.get_method_timer_parameters(
        process_name, method_name
    )

    # we use this rather than data.log as it will be marked up with the correct type
    log = object.data.log

    timer_class = timerClassWithFunction(
        function_object, data=data, log=log, parameters=timer_parameters
    )

    return timer_class
