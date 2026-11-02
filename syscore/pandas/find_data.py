import datetime
from typing import Union

import pandas as pd

from syscore.constants import arg_not_supplied, none_type


def get_row_of_df_aligned_to_weights_as_dict(
    df: pd.DataFrame, relevant_date: datetime.datetime = arg_not_supplied
) -> dict:
    """
    >>> d = datetime.datetime
    >>> date_index = [d(2000,1,1),d(2000,1,2),d(2000,1,3), d(2000,1,4)]
    >>> df = pd.DataFrame(dict(a=[1, 2, 3,4], b=[4,5,6,7]), index=date_index)
    >>> get_row_of_df_aligned_to_weights_as_dict(df, d(2000,1,3))
    {'a': 3, 'b': 6}
    """

    if relevant_date is arg_not_supplied:
        data_at_date = df.iloc[-1]
    else:
        try:
            data_at_date = df.loc[relevant_date]
        except KeyError:
            raise Exception("Date %s not found in data" % str(relevant_date))

    return data_at_date.to_dict()


def get_row_of_series(
    series: pd.Series, relevant_date: datetime.datetime = arg_not_supplied
):
    """
    >>> d = datetime.datetime
    >>> date_index1 = [d(2000,1,1),d(2000,1,2),d(2000,1,3)]
    >>> s1 = pd.Series([1,2,3], index=date_index1)
    >>> get_row_of_series(s1, d(2000,1,2))
    2
    """

    if relevant_date is arg_not_supplied:
        data_at_date = series.values[-1]
    else:
        try:
            data_at_date = series.loc[relevant_date]
        except KeyError:
            raise Exception("Date %s not found in data" % str(relevant_date))

    return data_at_date.item()


def get_row_of_series_before_date(
    series: pd.Series, relevant_date: datetime.datetime = arg_not_supplied
):
    """
    >>> d = datetime.datetime
    >>> date_index1 = [d(2000,1,1),d(2000,1,2),d(2000,1,5)]
    >>> s1 = pd.Series([1,2,3], index=date_index1)
    >>> get_row_of_series_before_date(s1, d(2000,1,3))
    2
    """

    if relevant_date is arg_not_supplied:
        data_at_date = series.values[-1]
    else:
        index_point = get_max_index_before_datetime(series.index, relevant_date)
        data_at_date = series.values[index_point]

    return data_at_date.item()


def get_max_index_before_datetime(
    index: pd.core.indexes.datetimes.DatetimeIndex, date_point: datetime.datetime
) -> Union[int, none_type]:
    matching_index_size = index[index < date_point].size

    if matching_index_size == 0:
        return None
    else:
        return matching_index_size - 1
