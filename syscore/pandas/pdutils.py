"""
Utilities to help with pandas
"""

import pandas as pd
import datetime

from collections import namedtuple  # noqa F401
from typing import Union, List
import numpy as np

from syscore.constants import named_object, arg_not_supplied

DEFAULT_DATE_FORMAT_FOR_CSV = "%Y-%m-%d %H:%M:%S"
EXPECTED_LENGTH_OF_DATE = 19

FALLBACK_DATE_FORMAT_FOR_CSV = "%Y-%m-%d"


def rolling_pairwise_correlation(
    x: pd.DataFrame, periods: int, min_periods: int = 3
) -> pd.Series:
    assert len(x.columns) == 2

    rolling_corr_df = x.rolling(periods, min_periods=min_periods).corr()
    return rolling_corr_df.droplevel(1)[::2].iloc[:, 1]


def is_a_series(x: Union[pd.Series, pd.DataFrame]) -> bool:
    columns = getattr(x, "columns", None)
    return columns is None


def is_a_dataframe(x: Union[pd.Series, pd.DataFrame]) -> bool:
    return not is_a_series(x)


def top_and_tail(x: pd.DataFrame, rows=5) -> pd.DataFrame:
    return pd.concat([x[:rows], x[-rows:]], axis=0)


def sum_series(list_of_series: List[pd.Series], ffill=True) -> pd.Series:
    list_of_series_as_df = pd.concat(list_of_series, axis=1)
    if ffill:
        list_of_series_as_df = list_of_series_as_df.ffill()

    sum_of_series = list_of_series_as_df.sum(axis=1)

    return sum_of_series


def uniquets(x: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
    """
    Makes x unique
    """
    x = x.groupby(level=0).last()
    return x


def get_column_names_in_df_with_at_least_one_value(df: pd.DataFrame) -> List[str]:
    """

    >>> df = pd.DataFrame(dict(a=[1,2], b=[np.nan, 3], c=[np.nan, np.nan]), index=pd.date_range(datetime.datetime(2000,1,1),periods=2))
    >>> get_column_names_in_df_with_at_least_one_value(df)
    ['a', 'b']
    """
    list_of_must_have = get_index_of_columns_in_df_with_at_least_one_value(df)
    columns = list(df.columns)
    must_have_columns = [
        col for idx, col in enumerate(columns) if list_of_must_have[idx]
    ]
    return must_have_columns


def get_index_of_columns_in_df_with_at_least_one_value(df: pd.DataFrame) -> List[bool]:
    """
    Returns the bool for columns of slice_data for which we have at least one non nan value

    >>> df = pd.DataFrame(dict(a=[1,2], b=[np.nan, 3], c=[np.nan, np.nan]), index=pd.date_range(datetime.datetime(2000,1,1),periods=2))
    >>> get_index_of_columns_in_df_with_at_least_one_value(df)
    [True, True, False]
    """

    return (~df.isna().all()).tolist()


def pd_readcsv(
    filename: str,
    date_index_name: str = "DATETIME",
    date_format: str = DEFAULT_DATE_FORMAT_FOR_CSV,
    fallback_date_format: str = FALLBACK_DATE_FORMAT_FOR_CSV,
    input_column_mapping: Union[dict, named_object] = arg_not_supplied,
    skiprows: int = 0,
    skipfooter: int = 0,
) -> pd.DataFrame:
    """
    Reads a pandas data frame, with time index labelled
    package_name(/path1/path2.., filename

    :param filename: Filename with extension
    :param date_index_name: Column name of date index
    :param date_format: usual stfrtime format
    :param input_column_mapping: If supplied remaps column names in .csv file
    :param skiprows, skipfooter: passed to pd.read_csv

    :returns: pd.DataFrame

    """

    df = pd.read_csv(filename, skiprows=skiprows, skipfooter=skipfooter)

    ## Add time index as index
    try:
        df = add_datetime_index(
            df=df, date_index_name=date_index_name, date_format=date_format
        )
    except:
        df = add_datetime_index(
            df=df, date_index_name=date_index_name, date_format=fallback_date_format
        )

    if input_column_mapping is not arg_not_supplied:
        df = remap_columns_in_pd(df, input_column_mapping)

    return df


def add_datetime_index(
    df: pd.DataFrame,
    date_index_name: str,
    date_format: str = DEFAULT_DATE_FORMAT_FOR_CSV,
    expected_length_of_date: int = EXPECTED_LENGTH_OF_DATE,
) -> pd.DataFrame:
    date_index = df[date_index_name]
    date_index = date_index.astype(str)

    def left(x: str, n):
        return x[:n]

    date_index = date_index.apply(left, n=expected_length_of_date)
    df.index = pd.to_datetime(date_index, format=date_format).values
    del df[date_index_name]
    df.index.name = None

    return df


def remap_columns_in_pd(df: pd.DataFrame, input_column_mapping: dict) -> pd.DataFrame:
    """
    Returns the bool for columns of slice_data for which we have at least one non nan value

    >>> df = pd.DataFrame(dict(a=[1,2], b=[np.nan, 3]), index=pd.date_range(datetime.datetime(2000,1,1),periods=2))
    >>> remap_columns_in_pd(df, dict(b='a', a='b'))
                b    a
    2000-01-01  1  NaN
    2000-01-02  2  3.0
    """

    new_df = pd.DataFrame(index=df.index)
    for new_col_name, old_col_name in input_column_mapping.items():
        new_df[new_col_name] = df[old_col_name]

    return new_df


def from_dict_of_values_to_df(
    data_dict: dict, ts_index: pd.Index, columns: List[str] = arg_not_supplied
) -> pd.DataFrame:
    """
    Turn a set of fixed values into a pd.DataFrame that spans the long index

    >>> from_dict_of_values_to_df({'a':2, 'b':1}, ts_index = pd.date_range(datetime.datetime(2000,1,1),periods=4))
                a  b
    2000-01-01  2  1
    2000-01-02  2  1
    2000-01-03  2  1
    2000-01-04  2  1
    >>> from_dict_of_values_to_df({'a':2, 'b':1}, columns = ['b', 'a'],ts_index = pd.date_range(datetime.datetime(2000,1,1),periods=4))
                b  a
    2000-01-01  1  2
    2000-01-02  1  2
    2000-01-03  1  2
    2000-01-04  1  2

    """

    if columns is not arg_not_supplied:
        data_dict = {keyname: data_dict[keyname] for keyname in columns}

    pd_dataframe = pd.DataFrame(data_dict, ts_index)

    return pd_dataframe


def from_scalar_values_to_ts(scalar_value: float, ts_index: pd.Index) -> pd.Series:
    """
    Turn a scalar value into a pd.Series that spans the long index
    >>> from_scalar_values_to_ts(4, ts_index = pd.date_range(datetime.datetime(2000,1,1),periods=4))
    2000-01-01    4
    2000-01-02    4
    2000-01-03    4
    2000-01-04    4
    Freq: D, dtype: int64
    """

    pd_series = pd.Series(scalar_value, index=ts_index)

    return pd_series


def create_arbitrary_pdseries(
    data_list: list, date_start=datetime.datetime(1980, 1, 1), freq: str = "B"
) -> pd.Series:
    """
    Return a pandas Series with an arbitrary date index

    >>> create_arbitrary_pdseries([1,2,3])
    1980-01-01    1
    1980-01-02    2
    1980-01-03    3
    Freq: B, dtype: int64
    >>> create_arbitrary_pdseries([1,2,3], date_start = datetime.datetime(2000,1,1), freq="W")
    2000-01-02    1
    2000-01-09    2
    2000-01-16    3
    Freq: W-SUN, dtype: int64
    """

    date_index = pd.date_range(start=date_start, periods=len(data_list), freq=freq)
    pdseries = pd.Series(data_list, index=date_index)

    return pdseries


def dataframe_pad(
    starting_df: pd.DataFrame,
    target_column_list: List[str],
    pad_with_value: float = 0.0,
) -> pd.DataFrame:
    """
    Takes a dataframe and adds extra columns if necessary so we end up with columns named column_list

    >>> df = pd.DataFrame(dict(a=[1, 2, 3], b=[4 , 6, 5]), index=pd.date_range(datetime.datetime(2000,1,1),periods=3))
    >>> dataframe_pad(df, ['a','b','c'], pad_with_value=4.0)
                a  b    c
    2000-01-01  1  4  4.0
    2000-01-02  2  6  4.0
    2000-01-03  3  5  4.0
    >>> dataframe_pad(df, ['a','c'])
                a    c
    2000-01-01  1  0.0
    2000-01-02  2  0.0
    2000-01-03  3  0.0
    """

    def _pad_column(column_name: str, starting_df: pd.DataFrame, pad_with_value: float):
        if column_name in starting_df.columns:
            return starting_df[column_name]
        else:
            return pd.Series(
                np.full(starting_df.shape[0], pad_with_value), starting_df.index
            )

    new_data = [
        _pad_column(column_name, starting_df, pad_with_value)
        for column_name in target_column_list
    ]

    new_df = pd.concat(new_data, axis=1)
    new_df.columns = target_column_list

    return new_df


def check_df_equals(x, y):
    try:
        pd.testing.assert_frame_equal(x, y)
        return True
    except AssertionError:
        return False


def check_ts_equals(x, y):
    try:
        pd.testing.assert_series_equal(x, y, check_names=False)
        return True
    except AssertionError:
        return False


def make_df_from_list_of_named_tuple(
    tuple_class,
    list_of_tuples: list,
    make_index: bool = True,
    field_name_for_index: str = arg_not_supplied,
):
    """
    Turn a list of named tuples into a dataframe
    The first element in the tuple will become the index

    >>> T = namedtuple('T', 'name value_a value_b')
    >>> t1 = T('X', 3,1)
    >>> t2 = T('Y',1,2)
    >>> t3 = T('Z', 4, 3)
    >>> make_df_from_list_of_named_tuple(T, [t1, t2, t3])  # doctest: +SKIP
          value_a  value_b
    ...
    X           3        1
    Y           1        2
    Z           4        3
    """
    elements = tuple_class._fields
    dict_of_elements = {}
    for element_name in elements:
        this_element_values = [
            getattr(list_entry, element_name) for list_entry in list_of_tuples
        ]
        dict_of_elements[element_name] = this_element_values

    pdf = pd.DataFrame(dict_of_elements)

    if make_index:
        if field_name_for_index is arg_not_supplied:
            field_name_for_index = elements[0]
        pdf_index = list(pdf[field_name_for_index])
        pdf = pdf.drop(labels=field_name_for_index, axis=1)
        pdf.index = pdf_index

    return pdf


def sort_df_ignoring_missing(df: pd.DataFrame, column: List[str]) -> pd.DataFrame:
    # sorts df by column, with rows with missing data coming at the end
    # Pandas treats NaN, NaT, and None as missing
    return df.sort_values(column, na_position="last")


def apply_with_min_periods(
    xcol: pd.Series, my_func=np.nanmean, min_periods: int = 0
) -> float:
    not_nan = sum(~np.isnan(xcol))

    if not_nan >= min_periods:
        return my_func(xcol)
    else:
        return np.nan


### unused but might be useful
def from_series_to_matching_df_frame(
    pd_series: pd.Series, pd_df_to_match: pd.DataFrame, method="ffill"
) -> pd.DataFrame:
    list_of_columns = list(pd_df_to_match.columns)
    new_df = from_series_to_df_with_column_names(pd_series, list_of_columns)
    new_df = new_df.reindex(pd_df_to_match.index, method=method)

    return new_df


def from_series_to_df_with_column_names(
    pd_series: pd.Series, list_of_columns: list
) -> pd.DataFrame:
    new_df = pd.concat([pd_series] * len(list_of_columns), axis=1)
    new_df.columns = list_of_columns

    return new_df


def print_full(x):
    """
    Prints out a pd dataframe with no truncation, then sets display options back to
    their defaults
    :param x:
    :type x:
    """
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 2000)
    pd.set_option("display.max_colwidth", None)
    print(x)
    pd.reset_option("display.max_rows")
    pd.reset_option("display.max_columns")
    pd.reset_option("display.width")
    pd.reset_option("display.float_format")
    pd.reset_option("display.max_colwidth")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
