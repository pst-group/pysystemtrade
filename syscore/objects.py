"""
Do fun things with objects and classes
"""

from typing import List
import importlib

LIST_OF_RESERVED_METHOD_NAMES = ["log", "name", "parent", "description", "data"]


def get_methods(a_stage_object) -> list:
    """
    Get methods from a stage object
    """
    dir_list = dir(a_stage_object)

    # remove private "_"
    dir_list = [method_name for method_name in dir_list if method_name[0] != "_"]

    # remove special
    dir_list = [
        method_name
        for method_name in dir_list
        if method_name not in LIST_OF_RESERVED_METHOD_NAMES
    ]

    return dir_list


def resolve_function(func_or_func_name):
    """
    if func_or_func_name is a callable function, then return the function

    If it is a string containing '.' then it is a function in a module, return the function

    :param func_or_func_name: Name of a function including package.module, or a callable function
    >>> resolve_function(str)
    <class 'str'>

    >>> resolve_function("sysquant.estimators.vol.robust_vol_calc").__name__
    'robust_vol_calc'

    """

    if hasattr(func_or_func_name, "__call__"):
        # it's a function, just return it so can be used
        # doesn't work for all functions, but we only care about callable ones
        return func_or_func_name

    if not isinstance(func_or_func_name, str):
        raise Exception(
            "Called resolve_function with non string or callable object %s"
            % str(func_or_func_name)
        )

    if "." in func_or_func_name:
        # it's another module, have to get it
        mod_name, func_name = func_or_func_name.rsplit(".", 1)
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name, None)

    else:
        raise Exception(
            "Need full module file name string: %s isn't good enough"
            % func_or_func_name
        )

    return func


def resolve_data_method(some_object, data_string: str):
    """
    eg if data_string="data1.data2.method" then returns the method some_object.data1.data2.method

    :param some_object: The object with a method
    :param data_string: method or attribute within object

    :returns: method in some_object

    >>> from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
    >>>
    >>> data=csvFuturesSimData()
    >>> resolve_data_method(data, "daily_prices")
    <bound method simData.daily_prices of csvFuturesSimData object with 208 instruments>

    """

    list_to_parse = data_string.rsplit(".")

    return _recursively_get_attr_within_list(some_object, list_to_parse)


def _recursively_get_attr_within_list(an_object, list_to_parse: List[str]):
    if len(list_to_parse) == 0:
        return an_object

    next_attr = list_to_parse.pop(0)
    sub_object = getattr(an_object, next_attr)

    return _recursively_get_attr_within_list(sub_object, list_to_parse)


def hasallattr(some_object, attrlist: List[str]):
    """
    Check something has all the attributes you need

    :returns: bool

    >>> from sysdata.sim.sim_data import simData
    >>> data=simData()
    >>> setattr(data, "one", 1)
    >>> setattr(data, "two", 2)
    >>> hasallattr(data, ["one", "two"])
    True
    >>> hasallattr(data, ["one", "two","three"])
    False
    """
    return all([hasattr(some_object, attrname) for attrname in attrlist])


def get_class_name(class_object) -> str:
    return class_object.__name__
