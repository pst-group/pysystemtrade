"""
General class for 'running' processes

We kick them all off in the crontab at a specific time (midnight is easiest), but their subsequent behaviour will
 depend on various rules, as defined in ... attribute of defaults.yaml or overridden in private_config

- is my process marked as NO OPEN in process control  (check database)
- is it too early for me to run? (defined in .yaml)
- is there a process I am waiting for to finish first?  (defined in .yaml, check database)
- is my process marked as STOP in process control (check database)

- within me, what methods do I call and how often? (defined in child objects)

- is it too late for me to run (definied in .yaml): then I should close down
- what I do when I close down? (defined in child objects)
- how do I mark myself as FINISHED for a subsequent process to know (in database)

"""
import time
import sys
from syscontrol.report_process_status import reportProcessStatus
from syscore.constants import success

from syscontrol.timer_functions import get_list_of_timer_functions, listOfTimerFunctions

from sysdata.data_blob import dataBlob

from syslogging.logger import *

from sysobjects.production.process_control import (
    process_no_run,
    process_running,
    process_stop,
    processNotRunning,
    processNotStarted,
)

from sysproduction.data.control_process import dataControlProcess, diagControlProcess


class processToRun(object):
    """
    Create, then do main_loop
    """

    def __init__(
        self,
        process_name: str,
        data: dataBlob,
        list_of_timer_names_and_functions_as_strings: list,
    ):
        self._data = data
        self._process_name = process_name
        self._list_of_timer_functions = get_list_of_timer_functions(
            data, process_name, list_of_timer_names_and_functions_as_strings
        )

        self._setup()

    @property
    def process_name(self):
        return self._process_name

    @property
    def data(self) -> dataBlob:
        return self._data

    @property
    def list_of_timer_functions(self) -> listOfTimerFunctions:
        return self._list_of_timer_functions

    def _setup(self):
        self._log = self.data.log
        data_control = dataControlProcess(self.data)
        self._data_control = data_control
        diag_process = diagControlProcess(self.data)
        self._diag_process = diag_process

        wait_reporter = reportProcessStatus(self.log)
        self._wait_reporter = wait_reporter

    @property
    def log(self):
        return self._log

    @property
    def data_control(self) -> dataControlProcess:
        return self._data_control

    @property
    def diag_process(self) -> diagControlProcess:
        return self._diag_process

    @property
    def wait_reporter(self) -> reportProcessStatus:
        return self._wait_reporter

    def run_process(self):
        try:
            _start_or_wait(self)
        except processNotStarted:
            return None

        try:
            self._run_on_start()
            self._main_loop_over_methods()
            self._finish()
        except Exception:
            config = self.data.config
            if config.get_element_or_default("log_failed_processes", False):
                self.log.critical(f"Process {self.process_name} failed!")
            raise

    def _run_on_start(self):
        self.data_control.start_process(self.process_name)

    def _main_loop_over_methods(self):
        is_running = True
        while is_running:
            time.sleep(0.5)
            list_of_timer_functions = self._list_of_timer_functions
            we_should_stop = _check_for_stop(self)
            if we_should_stop:
                return None
            wait_for_next_method_run_time(self)

            for timer_class in list_of_timer_functions:
                we_should_stop = _check_for_stop(self)
                if we_should_stop:
                    return None

                we_should_pause = check_for_pause_and_log(self)
                if we_should_pause:
                    continue

                kwargs = self._kwargs_for_method_and_process(timer_class.method_name)
                timer_class.check_and_run(**kwargs)

    def _kwargs_for_method_and_process(self, method_name: str) -> dict:
        return self.diag_process.get_configured_kwargs_for_process_name_and_method(
            process_name=self.process_name, method=method_name
        )

    def _finish(self):
        kwargs = self._kwargs_for_exit_only_method_and_process()
        self.list_of_timer_functions.run_methods_which_run_on_exit_only(**kwargs)
        self._finish_control_process()
        self.data.close()

    def _kwargs_for_exit_only_method_and_process(self) -> dict:
        return self.diag_process.get_configured_kwargs_for_process_name_and_methods_that_run_on_completion(
            self.process_name
        )

    def _finish_control_process(self):
        try:
            self.data_control.finish_process(self.process_name)
        except processNotRunning:
            self.log.warning(
                "Process %s won't finish in process control as already close: weird!"
                % self.process_name
            )
        else:
            self.log.debug("Process control %s marked close" % self.process_name)


### STARTUP CODE


def _start_or_wait(process_to_run: processToRun):
    waiting = True
    while waiting:
        okay_to_start = _is_okay_to_start(process_to_run)
        if okay_to_start:
            return

        okay_to_wait = _is_okay_to_wait_before_starting(process_to_run)
        if not okay_to_wait:
            raise processNotStarted

        time.sleep(60)


def _is_okay_to_start(process_to_run: processToRun) -> bool:
    """
    - is my process marked as NO OPEN in process control  (check database): WAIT
    - is it too early for me to run? (defined in .yaml): WAIT
    - is there a process I am waiting for to finish first?  (defined in .yaml, check database): WAIT
    - is my process marked as STOP in process control (check database): DO NOT OPEN

    :return:
    """
    process_status_okay = _check_if_process_status_is_okay_to_run(process_to_run)
    time_to_run = _is_it_time_to_run(process_to_run)
    previous_process_finished = _has_previous_process_finished(process_to_run)

    if process_status_okay and time_to_run and previous_process_finished:
        return True
    else:
        return False


NOT_STARTING_CONDITION = "Not starting process"


def _check_if_process_status_is_okay_to_run(process_to_run: processToRun) -> bool:
    data_control = process_to_run.data_control
    process_name = process_to_run.process_name
    okay_to_run = data_control.check_if_okay_to_start_process(process_name)

    wait_reporter = process_to_run.wait_reporter
    if okay_to_run is process_running:
        # already running
        wait_reporter.report_wait_condition(
            "because already running", NOT_STARTING_CONDITION
        )
        return False

    elif okay_to_run is process_stop:
        wait_reporter.report_wait_condition(
            "because process STOP status", NOT_STARTING_CONDITION
        )
        return False

    elif okay_to_run is process_no_run:
        wait_reporter.report_wait_condition(
            "because process NO RUN status", NOT_STARTING_CONDITION
        )
        return False

    elif okay_to_run is success:
        wait_reporter.clear_all_reasons_for_condition(NOT_STARTING_CONDITION)
        return True

    else:
        error_msg = "Process control returned unknown object %s!" % str(okay_to_run)
        process_to_run.log.critical(error_msg)
        raise Exception(error_msg)


def _is_it_time_to_run(process_to_run: processToRun) -> bool:
    diag_process = process_to_run.diag_process
    process_name = process_to_run.process_name
    time_to_run = diag_process.is_it_time_to_run(process_name)

    TIME_TO_RUN_REASON = "because Not yet time to run"
    wait_reporter = process_to_run.wait_reporter

    if time_to_run:
        wait_reporter.clear_wait_condition(TIME_TO_RUN_REASON, NOT_STARTING_CONDITION)
    else:
        wait_reporter.report_wait_condition(TIME_TO_RUN_REASON, NOT_STARTING_CONDITION)

    return time_to_run


def _has_previous_process_finished(process_to_run: processToRun) -> bool:
    diag_process = process_to_run.diag_process
    process_name = process_to_run.process_name

    other_process_finished = diag_process.has_previous_process_finished_in_last_day(
        process_name
    )
    PREVIOUS_PROCESS_REASON = "because Previous process still running"
    wait_reporter = process_to_run.wait_reporter

    if other_process_finished:
        wait_reporter.clear_wait_condition(
            PREVIOUS_PROCESS_REASON, NOT_STARTING_CONDITION
        )
    else:
        wait_reporter.report_wait_condition(
            PREVIOUS_PROCESS_REASON, NOT_STARTING_CONDITION
        )

    return other_process_finished


def _is_okay_to_wait_before_starting(process_to_run: processToRun):
    """
    - I have run out of time
    - is my process marked as STOP in process control (check database): DO NOT OPEN
    - am I running on the correct machine (defined in .yaml): DO NOT OPEN

    :return: bool: True if okay to wait, False if have to stop waiting
    """

    # check to see if process should have stopped already
    should_have_stopped = _check_for_stop(process_to_run)

    if should_have_stopped:
        # not okay to wait, should have stopped
        return False

    # check to see if process control status means we can't wait
    okay_to_wait = _check_if_okay_to_wait_before_starting_process(process_to_run)

    return okay_to_wait


def _check_if_okay_to_wait_before_starting_process(
    process_to_run: processToRun,
) -> bool:
    data_control = process_to_run.data_control
    process_name = process_to_run.process_name

    okay_to_run = data_control.check_if_okay_to_start_process(process_name)

    log = process_to_run.log
    if okay_to_run is process_running:
        log.warning(
            "Can't start process %s at all since already running" % process_name
        )
        return False

    elif okay_to_run is process_stop:
        log.warning(
            "Can't start process %s at all since STOPPED by control" % process_name
        )
        return False

    elif okay_to_run is process_no_run:
        # wait in case process changes
        return True

    elif okay_to_run is success:
        # will 'wait' but on next iteration will run
        return True
    else:
        error_msg = "Process control returned unknown object %s!" % str(okay_to_run)
        log.critical(error_msg)
        raise Exception(error_msg)


## WAIT CODE


def wait_for_next_method_run_time(process_to_run: processToRun):
    list_of_timer_functions = process_to_run.list_of_timer_functions
    seconds_to_next_run = list_of_timer_functions.seconds_until_next_method_runs()
    if seconds_to_next_run > 10.0:
        sleep_time = min(seconds_to_next_run, 60)
        msg = (
            "Sleeping for %d seconds as %d seconds until next method ready to run (will react to STOP or PAUSE at that point)"
            % (sleep_time, seconds_to_next_run)
        )
        process_to_run.log.debug(msg)
        sys.stdout.flush()
        time.sleep(sleep_time)


## PAUSE CODE


def check_for_pause_and_log(process_to_run: processToRun) -> bool:
    data_control = process_to_run.data_control
    should_pause = data_control.check_if_should_pause_process(
        process_to_run.process_name
    )

    wait_reporter = process_to_run.wait_reporter
    condition = "Paused running methods"
    reason = "because process status is PAUSE"
    if should_pause:
        wait_reporter.report_wait_condition(reason, condition)
    else:
        # clear that we've logged in case we pause again
        wait_reporter.clear_wait_condition(reason, condition)

    return should_pause


## FINISH CODE
def _check_for_stop(process_to_run: processToRun) -> bool:
    """
    - is my process marked as STOP in process control (check database)

    - is it too late for me to run (definied in .yaml): then I should close down
    :return: bool
    """

    process_requires_stop = _check_for_stop_control_process(process_to_run)
    all_methods_finished = _check_if_all_methods_finished(process_to_run)
    time_to_stop = _check_for_finish_time(process_to_run)

    log = process_to_run.log

    if process_requires_stop:
        log.debug("Process control marked as STOP")

    if all_methods_finished:
        log.debug("Finished doing all executions of provided methods")

    if time_to_stop:
        log.debug("Passed finish time of process")

    if process_requires_stop or all_methods_finished or time_to_stop:
        return True
    else:
        return False


def _check_for_stop_control_process(process_to_run: processToRun) -> bool:
    data_control = process_to_run.data_control
    process_name = process_to_run.process_name

    check_for_stop = data_control.check_if_process_status_stopped(process_name)

    return check_for_stop


def _check_if_all_methods_finished(process_to_run: processToRun) -> bool:
    list_of_timer_functions = process_to_run.list_of_timer_functions
    check_for_all_methods_finished = list_of_timer_functions.check_all_finished()

    return check_for_all_methods_finished


def _check_for_finish_time(process_to_run: processToRun) -> bool:
    diag_process = process_to_run.diag_process
    process_name = process_to_run.process_name

    return diag_process.is_it_time_to_stop(process_name)
