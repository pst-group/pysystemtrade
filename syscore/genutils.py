"""
Utilities I can't put anywhere else...
"""

from typing import Union
import datetime
import functools
import math

import numpy as np

from collections import namedtuple
from math import copysign, gcd
from typing import Union, List

Changes = namedtuple("Changes", ["new", "existing", "removing"])


def new_removing_existing(original_list: list, new_list: list) -> Changes:
    """
    >>> new_removing_existing([1,2],[3,4])
    Changes(new=[3, 4], existing=[], removing=[1, 2])
    >>> new_removing_existing([1,2,3],[3,4])
    Changes(new=[4], existing=[3], removing=[1, 2])
    >>> new_removing_existing([1,2,3],[1,2])
    Changes(new=[], existing=[1, 2], removing=[3])
    >>> new_removing_existing([1],[1,2])
    Changes(new=[2], existing=[1], removing=[])
    """
    existing = list_intersection(original_list, new_list)
    new = list_difference(new_list, original_list)
    removing = list_difference(original_list, new_list)

    return Changes(new=new, existing=existing, removing=removing)


def list_intersection(x: list, y: list) -> list:
    """
    >>> list_intersection([2,1], [1])
    [1]
    >>> list_intersection([2,1], [3])
    []
    """
    return list(set(x).intersection(set(y)))


def list_difference(x: list, y: list) -> list:
    """
    >>> list_difference([2,1], [1])
    [2]
    >>> list_difference([2,1], [3])
    [1, 2]
    >>> list_difference([3], [1, 2])
    [3]
    >>> list_difference([2,1], [1,2])
    []
    """
    return list(set(x).difference(set(y)))


def list_union(x: list, y: list) -> list:
    """
    >>> list_union([1,2], [1])
    [1, 2]
    >>> list_union([2,1], [3])
    [1, 2, 3]
    """
    return list(set(x).union(set(y)))


def get_unique_list(somelist: list) -> list:
    return list(set(somelist))


def get_unique_list_slow(somelist):
    uniquelist = []

    for somevalue in somelist:
        if somevalue not in uniquelist:
            uniquelist.append(somevalue)

    return uniquelist


def round_significant_figures(x: float, figures: int = 3) -> float:
    """
    >>> round_significant_figures(0.0234, 2)
    0.023
    """
    if x == 0:
        return 0.0

    return round(x, figures - int(math.floor(math.log10(abs(x)))) - 1)


def flatten_list(some_list: list) -> list:
    """
    >>> flatten_list([[1],[2,3]])
    [1, 2, 3]
    """
    flattened = [item for sublist in some_list for item in sublist]

    return flattened


def str2Bool(x: str) -> bool:
    if isinstance(x, bool):
        return x
    if x.lower() in ("t", "true"):
        return True
    if x.lower() in ("f", "false"):
        return False
    raise Exception("%s can't be resolved as a bool" % x)


def str_of_int(x: int) -> str:
    """
    Returns the string of int of x, handling nan's or whatever

    >>> str_of_int(34)
    '34'

    >>> str_of_int(34.0)
    '34'

    >>> import numpy as np
    >>> str_of_int(np.nan)
    ''

    """
    if isinstance(x, int):
        return str(x)
    try:
        return str(int(x))
    except BaseException:
        return ""


def same_sign(x, y):
    return sign(x) == sign(y)


def sign(x: Union[int, float]) -> float:
    """
    >>> sign(3)
    1.0

    >>> sign(3.0)
    1.0

    >>> sign(-3)
    -1.0

    >>> sign(0)
    1.0


    """
    return copysign(1, x)


def return_another_value_if_nan(x, return_value=None):
    """
    If x is np.nan return return_value
    else return x

    :param x: np.nan or other
    :return: x or return_value

    >>> return_another_value_if_nan(np.nan)

    >>> return_another_value_if_nan(np.nan, -1)
    -1

    >>> return_another_value_if_nan("thing")
    'thing'

    >>> return_another_value_if_nan(42)
    42

    """

    try:
        if np.isnan(x):
            return return_value
        else:
            pass
            # Not a nan will return x
    except BaseException:
        # Not something that can be compared to a nan
        pass

    # Either wrong type, or not a nan
    return x


def are_dicts_equal(d1: dict, d2: dict) -> bool:
    """
    >>> are_dicts_equal({1: 'a', 2: 'b'}, {2: 'b', 1: 'a'})
    True
    >>> are_dicts_equal({1: 'a', 2: 'b'}, {3: 'b', 1: 'a'})
    False
    >>> are_dicts_equal({1: 'a', 2: 'b'}, {2: 'c', 1: 'a'})
    False
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    if len(intersect_keys) != len(d1_keys):
        return False
    same_values = set(o for o in intersect_keys if d1[o] == d2[o])
    if len(same_values) != len(d1_keys):
        return False
    return True


class quickTimer(object):
    def __init__(self, seconds: Union[float, int] = 60):
        self._time_started = datetime.datetime.now()
        self._time_limit = seconds

    @property
    def unfinished(self) -> bool:
        return not self.finished

    @property
    def finished(self) -> bool:
        time_now = datetime.datetime.now()
        elapsed = time_now - self.time_started
        is_it_finished = elapsed.seconds > self.time_limit

        return is_it_finished

    @property
    def time_started(self) -> datetime.datetime:
        return self._time_started

    @property
    def time_limit(self) -> int:
        return self._time_limit


# avoids encoding problems with mongo
EMPTY_STRING = ""


def if_empty_string_return_object(x, object):
    if x == EMPTY_STRING:
        return object
    else:
        return x


def if_object_matches_return_empty_string(x, object_to_match):
    if x is object_to_match:
        return EMPTY_STRING
    else:
        return x


"""
    
    NAMED TUPLES AND OBJECTS

"""


def transfer_object_attributes(named_tuple_object, original_object):
    kwargs = dict(
        [
            (field_name, getattr(original_object, field_name))
            for field_name in named_tuple_object._fields
        ]
    )
    new_object = named_tuple_object(**kwargs)

    return new_object


"""

    COMMON FACTORS

"""


def highest_common_factor_for_list(list_of_ints: List[int]) -> int:
    """

    >>> highest_common_factor_for_list([2,3,4])
    1
    >>> highest_common_factor_for_list([2,6,4])
    2
    """
    return functools.reduce(gcd, list_of_ints)


def divide_list_of_ints_by_highest_common_factor(list_of_ints: List[int]) -> list:
    """

    >>> divide_list_of_ints_by_highest_common_factor([1,2])
    [1, 2]
    >>> divide_list_of_ints_by_highest_common_factor([2,4])
    [1, 2]
    >>> divide_list_of_ints_by_highest_common_factor([1,2,3])
    [1, 2, 3]
    >>> divide_list_of_ints_by_highest_common_factor([1])
    [1]
    """

    gcd_value = highest_common_factor_for_list(list_of_ints)
    new_list = [int(float(x) / gcd_value) for x in list_of_ints]
    return new_list


def list_of_ints_with_highest_common_factor_positive_first(
    list_of_ints: List[int],
) -> list:
    """
    Used to identify the unique version of a spread or fly contract

    :param list_of_ints:
    :return: list

    >>> list_of_ints_with_highest_common_factor_positive_first([1])
    [1]
    >>> list_of_ints_with_highest_common_factor_positive_first([-1])
    [1]
    >>> list_of_ints_with_highest_common_factor_positive_first([1,-1])
    [1, -1]
    >>> list_of_ints_with_highest_common_factor_positive_first([-1,1])
    [1, -1]
    >>> list_of_ints_with_highest_common_factor_positive_first([-1,2])
    [1, -2]
    >>> list_of_ints_with_highest_common_factor_positive_first([-2,2])
    [1, -1]
    >>> list_of_ints_with_highest_common_factor_positive_first([2,-2])
    [1, -1]
    >>> list_of_ints_with_highest_common_factor_positive_first([2,-4,2])
    [1, -2, 1]
    >>> list_of_ints_with_highest_common_factor_positive_first([-2,4,-2])
    [1, -2, 1]

    """
    new_list = divide_list_of_ints_by_highest_common_factor(list_of_ints)
    multiply_sign = sign(new_list[0])
    new_list = [int(x * multiply_sign) for x in new_list]
    return new_list


def np_convert(val):
    """
    Converts the passed numpy value to a native python type

    >>> val = np.int64(1)
    >>> type(val)
    <class 'numpy.int64'>
    >>> type(np_convert(val))
    <class 'int'>
    """
    return val.item() if isinstance(val, np.generic) else val


def intersection_intervals(intervals: list) -> list:
    """
    >>> intersection_intervals([[1,5], [2,3]])
    [2, 3]
    >>> intersection_intervals([[1,5], [2,6]])
    [2, 5]
    >>> intersection_intervals([[1,5], [1,5]])
    [1, 5]
    >>> intersection_intervals([[3,7], [2,6]])
    [3, 6]
    >>> intersection_intervals([[1,5], [7,9]])
    []
    """
    start, end = intervals.pop()
    while intervals:
        start_temp, end_temp = intervals.pop()
        start = max(start, start_temp)
        end = min(end, end_temp)

    if end < start:
        return []
    return [start, end]


if __name__ == "__main__":
    import doctest

    doctest.testmod()
