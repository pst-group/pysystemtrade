"""
I use caching a lot

There is the caching in the base system, but that's special uses decorators etc

Here's a more general one
"""

from syscore.exceptions import missingData


class Cache(object):
    """
    >>> some_class = _testCacheClass()
    >>> some_class.square(2)
    calculating
    4
    >>> some_class.square(2)
    4
    """

    def __init__(self, parent_object):
        self._parent = parent_object
        self._store = {}

    def get(self, function_instance, *args, **kwargs):
        function_name = function_instance.__name__
        key = _get_key(function_name, args, kwargs)
        try:
            value_from_store = self._get_from_store(key)
        except missingData:
            value_from_store = self._calculate_and_store(
                key, function_instance, *args, **kwargs
            )

        return value_from_store

    def _calculate_and_store(self, key: str, function_instance, *args, **kwargs):
        value = function_instance(*args, **kwargs)
        self._put_in_store(key, value)

        return value

    def _put_in_store(self, key: str, value):
        self.store[key] = value

    def _get_from_store(self, key: str):
        try:
            value = self.store[key]
        except KeyError as e:
            raise missingData("Missing cache element %s" % key) from e
        return value

    @property
    def store(self) -> dict:
        return self._store

    @property
    def parent(self):
        return self._parent


def _get_key(function_name, tuple_of_args: tuple, dict_of_kwargs: dict) -> str:
    return "%s/%s/%s" % (str(function_name), str(tuple_of_args), str(dict_of_kwargs))


class _testCacheClass(object):
    def __init__(self):
        self.cache = Cache(self)

    def square(self, x):
        return self.cache.get(self._square, x)

    def _square(self, x):
        print("calculating")
        return x**2
