from copy import copy
from syscore.objects import resolve_function
from sysdata.data_blob import dataBlob
from syslogging import STRATEGY_NAME_LOG_LABEL
from sysproduction.data.control_process import get_strategy_class_object_config


class strategyRunner:
    ## needs to have method per strategy
    def __init__(
        self, data: dataBlob, strategy_name: str, process_name: str, function_name: str
    ):
        self.data = data
        self._strategy_name = strategy_name
        self._function_name = function_name
        self._process_name = process_name

        self._strategy_method = get_strategy_method(
            self.data, self._strategy_name, self._process_name, self._function_name
        )

    @property
    def strategy_name(self):
        return self._strategy_name

    @property
    def function_name(self):
        return self._function_name

    @property
    def process_name(self):
        return self._process_name

    @property
    def strategy_method(self):
        return self._strategy_method

    def run_strategy_method(self):
        method = self.strategy_method
        # no arguments. no return. no explanations
        method()


def get_strategy_method(
    data: dataBlob, strategy_name: str, process_name: str, function_name: str
):
    strategy_class_instance = get_strategy_class_instance(
        data=data, strategy_name=strategy_name, process_name=process_name
    )
    method = getattr(strategy_class_instance, function_name)

    return method


def get_strategy_class_instance(data: dataBlob, strategy_name: str, process_name: str):
    # useful for debugging

    strategy_class_object, other_args = get_class_object_and_other_arguments(
        data=data, strategy_name=strategy_name, process_name=process_name
    )

    strategy_data = dataBlob(log_name=process_name)
    strategy_data.log.debug(
        "Updating log attributes", **{STRATEGY_NAME_LOG_LABEL: strategy_name}
    )

    strategy_class_instance = strategy_class_object(
        strategy_data, strategy_name, **other_args
    )

    return strategy_class_instance


def get_class_object_and_other_arguments(
    data: dataBlob, strategy_name: str, process_name: str
):
    original_config_this_process = get_strategy_class_object_config(
        data, process_name, strategy_name
    )
    config_this_process = copy(original_config_this_process)
    strategy_class_object = resolve_function(config_this_process.pop("object"))

    # following are used by run process but not by us
    _ = config_this_process.pop("max_executions", None)
    _ = config_this_process.pop("frequency", None)

    other_args = config_this_process

    return strategy_class_object, other_args
