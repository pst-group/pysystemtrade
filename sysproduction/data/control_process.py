import datetime

from syscore.dateutils import SECONDS_PER_HOUR
from syscore.exceptions import missingData
from syscore.genutils import str2Bool
from syscore.constants import named_object
from syscontrol.timer_parameters import timerClassParameters

from sysdata.config.control_config import get_control_config
from sysdata.data_blob import dataBlob
from sysdata.production.process_control_data import controlProcessData


from sysproduction.data.generic_production_data import productionDataLayerGeneric
from sysproduction.data.production_data_objects import (
    get_class_for_data_type,
    PROCESS_CONTROL_DATA,
)

DEFAULT_METHOD_FREQUENCY = 60
DEFAULT_MAX_EXECUTIONS = 1
DEFAULT_START_TIME_STRING = "00:01"
DEFAULT_STOP_TIME_STRING = "23:50"
NAME_OF_TRADING_PROCESS = "run_stack_handler"
LABEL_FOR_ARGS_METHOD_ON_COMPLETION = "_methods_on_completion"


class dataControlProcess(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_object(get_class_for_data_type(PROCESS_CONTROL_DATA))

        return data

    @property
    def db_control_process_data(self) -> controlProcessData:
        return self.data.db_control_process

    def delete_control_for_process_name(self, process_name: str):
        self.db_control_process_data.delete_control_for_process_name(process_name)

    def get_dict_of_control_processes(self):
        return self.db_control_process_data.get_dict_of_control_processes()

    def check_if_okay_to_start_process(self, process_name: str) -> named_object:
        """

        :param process_name: str
        :return:  success, or if not okay: process_no_run, process_stop, process_running
        """

        is_it_okay = self.db_control_process_data.check_if_okay_to_start_process(
            process_name
        )

        return is_it_okay

    def start_process(self, process_name: str) -> named_object:
        """

        :param process_name: str
        :return:  success, or if not okay: process_no_run, process_stop, process_running
        """
        result = self.db_control_process_data.start_process(process_name)

        return result

    def check_if_should_pause_process(self, process_name: str) -> bool:
        result = self.db_control_process_data.check_if_should_pause_process(
            process_name
        )

        return result

    def finish_process(self, process_name: str):
        """

        :param process_name: str
        """

        self.db_control_process_data.finish_process(process_name)

    def finish_all_processes(self) -> list:
        list_of_status = self.db_control_process_data.finish_all_processes()
        return list_of_status

    def check_if_pid_running_and_if_not_finish_all_processes(self) -> list:
        list_of_status = self.db_control_process_data.check_if_pid_running_and_if_not_finish_all_processes()

        return list_of_status

    def check_if_process_status_stopped(self, process_name: str) -> bool:
        """

        :param process_name: str
        :return: bool
        """
        has_it_stopped = self.db_control_process_data.check_if_process_status_stopped(
            process_name
        )
        return has_it_stopped

    def change_status_to_stop(self, process_name: str):
        self.db_control_process_data.change_status_to_stop(process_name)

    def change_status_to_go(self, process_name: str):
        self.db_control_process_data.change_status_to_go(process_name)

    def change_status_to_no_run(self, process_name: str):
        self.db_control_process_data.change_status_to_no_run(process_name)

    def change_status_to_pause(self, process_name: str):
        self.db_control_process_data.change_status_to_pause(process_name)

    def has_process_finished_in_last_day(self, process_name: str) -> bool:
        has_it_finished_in_last_day = (
            self.db_control_process_data.has_process_finished_in_last_day(process_name)
        )
        return has_it_finished_in_last_day

    def log_start_run_for_method(self, process_name: str, method_name: str):
        self.db_control_process_data.log_start_run_for_method(process_name, method_name)

    def log_end_run_for_method(self, process_name: str, method_name: str):
        self.db_control_process_data.log_end_run_for_method(process_name, method_name)


class diagControlProcess(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_object(get_class_for_data_type(PROCESS_CONTROL_DATA))

        return data

    @property
    def db_control_process_data(self) -> controlProcessData:
        return self.data.db_control_process

    def get_config_dict(self, process_name: str) -> dict:
        previous_process = self.previous_process_name(process_name)
        start_time = self.get_start_time(process_name)
        end_time = self.get_stop_time(process_name)

        result_dict = dict(
            previous_process=previous_process, start_time=start_time, end_time=end_time
        )

        return result_dict

    def get_process_status_dict(self, process_name: str) -> dict:
        time_to_stop = self.is_it_time_to_stop(process_name)
        time_to_start = self.is_it_time_to_run(process_name)
        prev_process = self.has_previous_process_finished_in_last_day(process_name)

        result_dict = dict(
            time_to_start=time_to_start,
            time_to_stop=time_to_stop,
            prev_process=prev_process,
        )

        return result_dict

    def has_previous_process_finished_in_last_day(self, process_name: str) -> bool:
        previous_process = self.previous_process_name(process_name)
        if previous_process is None or previous_process == "":
            ## no previous process, so return True
            return True
        control_process = dataControlProcess(self.data)
        result = control_process.has_process_finished_in_last_day(previous_process)

        return result

    def is_it_time_to_run(self, process_name: str) -> bool:
        start_time = self.get_start_time(process_name)
        stop_time = self.get_stop_time(process_name)
        now_time = datetime.datetime.now().time()

        if now_time >= start_time and now_time < stop_time:
            return True
        else:
            return False

    def is_it_time_to_stop(self, process_name: str) -> bool:
        stop_time = self.get_stop_time(process_name)
        now_time = datetime.datetime.now().time()

        if now_time > stop_time:
            return True
        else:
            return False

    def get_method_timer_parameters(
        self, process_name: str, method_name: str
    ) -> timerClassParameters:
        run_on_completion_only = self.does_method_run_on_completion_only(
            process_name, method_name
        )

        frequency_minutes = self.frequency_for_process_and_method(
            process_name, method_name
        )
        max_executions = self.max_executions_for_process_and_method(
            process_name, method_name
        )

        timer_parameters = timerClassParameters(
            method_name=method_name,
            process_name=process_name,
            frequency_minutes=frequency_minutes,
            max_executions=max_executions,
            run_on_completion_only=run_on_completion_only,
        )

        return timer_parameters

    def does_method_run_on_completion_only(
        self, process_name: str, method_name: str
    ) -> bool:
        this_method_dict = self.get_method_configuration_for_process_name(
            process_name, method_name
        )
        run_on_completion_only = this_method_dict.get("run_on_completion_only", False)
        run_on_completion_only = str2Bool(run_on_completion_only)

        return run_on_completion_only

    def frequency_for_process_and_method(
        self, process_name: str, method_name: str
    ) -> int:
        this_method_dict = self.get_method_configuration_for_process_name(
            process_name, method_name
        )

        frequency = this_method_dict.get("frequency", DEFAULT_METHOD_FREQUENCY)

        return frequency

    def max_executions_for_process_and_method(
        self, process_name: str, method_name: str
    ) -> int:
        this_method_dict = self.get_method_configuration_for_process_name(
            process_name, method_name
        )
        max_executions = this_method_dict.get("max_executions", DEFAULT_MAX_EXECUTIONS)

        return max_executions

    def get_method_configuration_for_process_name(
        self, process_name: str, method_name: str
    ) -> dict:
        all_method_dict = self.get_all_method_dict_for_process_name(process_name)
        this_method_dict = all_method_dict.get(method_name, {})

        return this_method_dict

    def get_list_of_methods_for_process_name(self, process_name: str) -> list:
        all_method_dict = self.get_all_method_dict_for_process_name(process_name)

        return list(all_method_dict.keys())

    def get_all_method_dict_for_process_name(self, process_name: str) -> dict:
        all_method_dict = self._get_configuration_item_for_process_name(
            process_name, "methods", default={}, use_config_default=False
        )

        return all_method_dict

    def previous_process_name(self, process_name: str) -> str:
        """

        :param process_name:
        :return: str or None
        """
        return self._get_configuration_item_for_process_name(
            process_name, "previous_process", default=None, use_config_default=False
        )

    def get_start_time(self, process_name: str) -> datetime.time:
        """
        Return time object, or 00:01 if none available
        :param process_name:
        :return:
        """
        result = self._get_configuration_item_for_process_name(
            process_name,
            "start_time",
            default=DEFAULT_START_TIME_STRING,
            use_config_default=True,
        )

        result = datetime.datetime.strptime(result, "%H:%M").time()

        return result

    def how_long_in_hours_before_trading_process_finishes(self) -> float:
        now_datetime = datetime.datetime.now()

        now_date = now_datetime.date()
        stop_time = self.get_stop_time_of_trading_process()
        stop_datetime = datetime.datetime.combine(now_date, stop_time)

        diff = stop_datetime - now_datetime
        time_seconds = max(0, diff.total_seconds())
        time_hours = time_seconds / SECONDS_PER_HOUR

        return time_hours

    def get_stop_time_of_trading_process(self) -> datetime.time:
        return self.get_stop_time(NAME_OF_TRADING_PROCESS)

    def get_stop_time(self, process_name: str):
        """
        Return time object, or 00:01 if none available
        :param process_name:
        :return:
        """
        result = self._get_configuration_item_for_process_name(
            process_name,
            "stop_time",
            default=DEFAULT_STOP_TIME_STRING,
            use_config_default=True,
        )

        result = datetime.datetime.strptime(result, "%H:%M").time()

        return result

    def _get_configuration_item_for_process_name(
        self,
        process_name: str,
        item_name: str,
        default=None,
        use_config_default: bool = False,
    ):
        process_config_for_item = self.get_process_configuration_for_item_name(
            item_name
        )
        config_item = process_config_for_item.get(process_name, default)
        if use_config_default and config_item is default:
            config_item = process_config_for_item.get("default", default)

        return config_item

    def get_process_configuration_for_item_name(self, item_name: str) -> dict:
        config = getattr(self, "_process_config_%s" % item_name, {})
        if config == {}:
            try:
                config = self.get_key_value_from_control_config(
                    "process_configuration_%s" % item_name
                )
            except missingData:
                return {}
            setattr(self, "_process_config_%s" % item_name, config)

        return config

    def when_method_last_started(
        self, process_name: str, method_name: str
    ) -> datetime.datetime:
        result = self.db_control_process_data.when_method_last_started(
            process_name, method_name
        )
        return result

    def when_method_last_ended(
        self, process_name: str, method_name: str
    ) -> datetime.datetime:
        result = self.db_control_process_data.when_method_last_ended(
            process_name, method_name
        )
        return result

    def method_currently_running(self, process_name: str, method_name: str) -> bool:
        result = self.db_control_process_data.method_currently_running(
            process_name, method_name
        )
        return result

    def get_control_for_process_name(self, process_name: str):
        result = self.db_control_process_data.get_control_for_process_name(process_name)

        return result

    def get_list_of_process_names(self) -> list:
        result = self.db_control_process_data.get_list_of_process_names()
        return result

    def get_configured_kwargs_for_process_name_and_methods_that_run_on_completion(
        self, process_name: str
    ) -> dict:
        return self.get_configured_kwargs_for_process_name_and_method(
            process_name=process_name, method=LABEL_FOR_ARGS_METHOD_ON_COMPLETION
        )

    def get_configured_kwargs_for_process_name_and_method(
        self, process_name: str, method: str
    ) -> dict:
        configured_kwargs_for_process_name = (
            self.get_configured_kwargs_for_process_name(process_name)
        )
        configured_kwargs_for_process_name_and_method = (
            configured_kwargs_for_process_name.get(method, {})
        )

        return configured_kwargs_for_process_name_and_method

    def get_configured_kwargs_for_process_name(self, process_name: str) -> dict:
        configured_kwargs = self.configured_kwargs()
        configured_kwargs_for_process_name = configured_kwargs.get(process_name, {})

        return configured_kwargs_for_process_name

    def configured_kwargs(self) -> dict:
        try:
            kwargs = self.get_key_value_from_control_config("arguments")
        except missingData:
            return {}
        return kwargs

    def get_key_value_from_control_config(self, item_name: str):
        config = self.get_control_config()
        item = config.get_element(item_name)

        return item

    ## Cache to avoid multiple reads of a yaml file
    def get_control_config(self):
        return self.cache.get(self._get_control_config)

    def _get_control_config(self):
        return get_control_config()


def get_list_of_strategies_for_process(data: dataBlob, process_name: str) -> list:
    diag_config = diagControlProcess(data)
    list_of_strategies = diag_config.get_list_of_methods_for_process_name(process_name)

    return list_of_strategies


def get_strategy_class_object_config(
    data: dataBlob, process_name: str, strategy_name: str
) -> dict:
    """
    returns dict with
          object: sysproduction.strategy_code.run_system_classic.runSystemClassic
      function: run_system_classic
      backtest_config_filename: systems.provided.futures_chapter15.futures_config.yaml

    """
    diag_config = diagControlProcess(data)
    config_this_process = diag_config.get_method_configuration_for_process_name(
        process_name, strategy_name
    )

    return config_this_process
