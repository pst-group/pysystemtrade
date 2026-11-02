import datetime
from typing import Union, Tuple, List

import pandas as pd

from syscore.pandas.full_merge_with_replacement import full_merge_of_existing_series
from syscore.constants import named_object


def merge_data_series_with_label_column(
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    data_column="PRICE",
    label_column="PRICE_CONTRACT",
):
    """
    For two pd.DataFrames with 2 columns, including a label column, update the data when the labels
      start consistently matching

    >>> import numpy as np
    >>> s1=pd.DataFrame(dict(PRICE=[1,2,3,np.nan], PRICE_CONTRACT = ["a", "a", "b", "b"]), index=['a1','a2','a3','a4'])
    >>> s2=pd.DataFrame(dict(PRICE=[  7,3,4], PRICE_CONTRACT = [          "b", "b", "b"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    2.0              a
    a3    3.0              b
    a4    4.0              b
    >>> s2=pd.DataFrame(dict(PRICE=[  2,5,4], PRICE_CONTRACT = [          "b", "b", "b"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    2.0              a
    a3    3.0              b
    a4    4.0              b
    >>> s2=pd.DataFrame(dict(PRICE=[  2,3,np.nan], PRICE_CONTRACT = [          "b", "b", "b"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    2.0              a
    a3    3.0              b
    a4    NaN              b
    >>> s1=pd.DataFrame(dict(PRICE=[1,np.nan,3,np.nan], PRICE_CONTRACT = ["a", "a", "b", "b"]), index=['a1','a2','a3','a4'])
    >>> s2=pd.DataFrame(dict(PRICE=[  2,     3,4], PRICE_CONTRACT = [      "a", "b", "b"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    2.0              a
    a3    3.0              b
    a4    4.0              b
    >>> s1=pd.DataFrame(dict(PRICE=[1,np.nan,np.nan], PRICE_CONTRACT = ["a", "a", "b"]), index=['a1','a2','a3'])
    >>> s2=pd.DataFrame(dict(PRICE=[  2,     3,4], PRICE_CONTRACT = [      "b", "b", "b"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    NaN              a
    a3    3.0              b
    a4    4.0              b
    >>> s2=pd.DataFrame(dict(PRICE=[  2,     3,4], PRICE_CONTRACT = [      "b", "c", "c"]), index=['a2','a3','a4'])
    >>> merge_data_series_with_label_column(s1,s2)
        PRICE PRICE_CONTRACT
    a1    1.0              a
    a2    NaN              a
    a3    NaN              b


    :param original_data: a pd.DataFrame with two columns, equal to col_names
    :param new_data: a pd.DataFrame with the same two columns

    :return: pd.DataFrame with two columns
    """

    if len(new_data) == 0:
        return original_data

    if len(original_data) == 0:
        return new_data

    current_and_merged_data = (
        _merge_data_series_with_label_column_when_old_and_new_data_provided(
            original_data=original_data,
            new_data=new_data,
            data_column=data_column,
            label_column=label_column,
        )
    )

    return current_and_merged_data


ALL_LABELS_MATCH = named_object("all labels match")
MISMATCH_ON_LAST_DAY = named_object("MISMATCH_ON_LAST_DAY")
ORIGINAL_INDEX_MATCHES_NEW = named_object("original index matches new")


def _merge_data_series_with_label_column_when_old_and_new_data_provided(
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    data_column="PRICE",
    label_column="PRICE_CONTRACT",
):
    """
    For two pd.DataFrames with 2 columns, including a label column, update the data when the labels
      start consistently matching
    """

    # From the date after this, can happily merge new and old data
    match_dates = _find_dates_when_label_changes(
        original_data, new_data, label_column=label_column
    )

    if match_dates is MISMATCH_ON_LAST_DAY:
        # No matching is possible
        return original_data
    elif match_dates is ORIGINAL_INDEX_MATCHES_NEW:
        first_date_after_series_mismatch = original_data.index[0]
        last_date_when_series_mismatch = ORIGINAL_INDEX_MATCHES_NEW
    else:
        first_date_after_series_mismatch, last_date_when_series_mismatch = match_dates

    current_and_merged_data = _merge_data_given_matching_dates(
        original_data=original_data,
        new_data=new_data,
        last_date_when_series_mismatch=last_date_when_series_mismatch,
        first_date_after_series_mismatch=first_date_after_series_mismatch,
        data_column=data_column,
        label_column=label_column,
    )

    return current_and_merged_data


def _find_dates_when_label_changes(
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    label_column="PRICE_CONTRACT",
) -> Union[named_object, Tuple[datetime.datetime, datetime.datetime]]:
    """
    For two pd.DataFrames with 2 columns, including a label column, find the date after which the labelling
     is consistent across columns

    >>> import numpy as np
    >>> s1=pd.DataFrame(dict(PRICE=[1,2,3,np.nan], PRICE_CONTRACT = ["a", "a", "b", "b"]), index=['a1','a2','a3','a4'])
    >>> s2=pd.DataFrame(dict(PRICE=[  2,3,4], PRICE_CONTRACT = [          "b", "b", "b"]), index=['a2','a3','a4'])
    >>> _find_dates_when_label_changes(s1, s2)
    ('a3', 'a2')
    >>> s2=pd.DataFrame(dict(PRICE=[  2,3,4], PRICE_CONTRACT = [          "a", "b", "b"]), index=['a2','a3','a4'])
    >>> _find_dates_when_label_changes(s1, s2)
    ('a2', 'a1')
    >>> s2=pd.DataFrame(dict(PRICE=[  2,3,4], PRICE_CONTRACT = [          "c", "c", "c"]), index=['a2','a3','a4'])
    >>> _find_dates_when_label_changes(s1, s2)
    MISMATCH_ON_LAST_DAY
    >>> _find_dates_when_label_changes(s1, s1)
    original index matches new
    >>> s2=pd.DataFrame(dict(PRICE=[1, 2,3,4], PRICE_CONTRACT = ["a","c", "c", "c"]), index=['a1','a2','a3','a4'])
    >>> _find_dates_when_label_changes(s1, s2)
    MISMATCH_ON_LAST_DAY

    """

    joint_labels = pd.concat(
        [original_data[label_column], new_data[label_column]], axis=1
    )
    joint_labels.columns = ["current", "new"]
    joint_labels = joint_labels.sort_index()

    new_data_start = new_data.index[0]

    existing_labels_in_new_period = joint_labels["current"][new_data_start:].ffill()
    new_labels_in_new_period = joint_labels["new"][new_data_start:].ffill()

    match_dates = _find_dates_when_labels_change_given_label_data(
        original_data=original_data,
        new_data=new_data,
        existing_labels_in_new_period=existing_labels_in_new_period,
        new_labels_in_new_period=new_labels_in_new_period,
    )

    return match_dates


def _find_dates_when_labels_change_given_label_data(
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    existing_labels_in_new_period: pd.Series,
    new_labels_in_new_period: pd.Series,
) -> Union[named_object, Tuple[datetime.datetime, datetime.datetime]]:
    # Find the last date when the labels didn't match, and the first date
    # after that
    match_dates = _find_dates_when_series_starts_matching(
        existing_labels_in_new_period, new_labels_in_new_period
    )

    if match_dates is MISMATCH_ON_LAST_DAY:
        # Can't use any of new data
        return MISMATCH_ON_LAST_DAY

    elif match_dates is ALL_LABELS_MATCH:
        match_dates_for_matching_labels = (
            _match_dates_when_entire_series_of_labels_matches(
                original_data=original_data, new_data=new_data
            )
        )
        return match_dates_for_matching_labels
    else:
        return match_dates


def _find_dates_when_series_starts_matching(
    series1: pd.Series, series2: pd.Series
) -> Union[named_object, Tuple[datetime.datetime, datetime.datetime]]:
    """
    Find the last index value when series1 and series 2 didn't match, and the next index after that

    series must be matched for index and same length

    >>> idx=pd.date_range(datetime.datetime(2000,1,1), periods=4)
    >>> s1=pd.Series(["a", "b", "b", "b"], index=idx)
    >>> s2=pd.Series(["c", "b", "b", "b"], index=idx)
    >>> _find_dates_when_series_starts_matching(s1, s2)
    (Timestamp('2000-01-02 00:00:00'), Timestamp('2000-01-01 00:00:00'))
    >>> s2=pd.Series(["a", "a", "b", "b"], index=idx)
    >>> _find_dates_when_series_starts_matching(s1, s2)
    (Timestamp('2000-01-03 00:00:00'), Timestamp('2000-01-02 00:00:00'))
    >>> s2=pd.Series(["a", "b", "a", "b"], index=idx)
    >>> _find_dates_when_series_starts_matching(s1, s2)
    (Timestamp('2000-01-04 00:00:00'), Timestamp('2000-01-03 00:00:00'))
    >>> s2=pd.Series(["a", "b", "b", "b"], index=idx)
    >>> _find_dates_when_series_starts_matching(s1, s2)
    all labels match
    >>> s2=pd.Series(["a", "b", "b", "c"], index=idx)
    >>> _find_dates_when_series_starts_matching(s1, s2)
    MISMATCH_ON_LAST_DAY

    """

    # Data is same length, and timestamp matched, so equality of values is
    # sufficient
    period_equal = [x == y for x, y in zip(series1.values, series2.values)]

    if all(period_equal):
        return ALL_LABELS_MATCH

    if not period_equal[-1]:
        return MISMATCH_ON_LAST_DAY

    match_dates = _match_dates_for_labels_when_not_equal_or_mismatch(
        series1=series1, period_equal=period_equal
    )

    return match_dates


def _match_dates_for_labels_when_not_equal_or_mismatch(
    series1: pd.Series, period_equal: List[bool]
) -> Tuple[datetime.datetime, datetime.datetime]:
    # Want last False value
    period_equal.reverse()
    first_false_in_reversed_list = period_equal.index(False)

    last_true_before_first_false_in_reversed_list = first_false_in_reversed_list - 1

    reversed_time_index = series1.index[::-1]
    last_true_before_first_false_in_reversed_list_date = reversed_time_index[
        last_true_before_first_false_in_reversed_list
    ]
    first_false_in_reversed_list_date = reversed_time_index[
        first_false_in_reversed_list
    ]

    first_date_after_series_mismatch = (
        last_true_before_first_false_in_reversed_list_date
    )
    last_date_when_series_mismatch = first_false_in_reversed_list_date

    return first_date_after_series_mismatch, last_date_when_series_mismatch


def _match_dates_when_entire_series_of_labels_matches(
    original_data: pd.DataFrame, new_data: pd.DataFrame
) -> Union[named_object, Tuple[datetime.datetime, datetime.datetime]]:
    # Can use entire series becuase all match
    if new_data.index[0] == original_data.index[0]:
        # They are same size, so have to use whole of original data
        return ORIGINAL_INDEX_MATCHES_NEW

    # All the new data matches
    new_data_start = new_data.index[0]
    first_date_after_series_mismatch = new_data_start
    last_date_when_series_mismatch = original_data.index[
        original_data.index < new_data_start
    ][-1]

    return first_date_after_series_mismatch, last_date_when_series_mismatch


def _merge_data_given_matching_dates(
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    first_date_after_series_mismatch: datetime.datetime,
    last_date_when_series_mismatch: Union[named_object, datetime.datetime],
    data_column="PRICE",
    label_column="PRICE_CONTRACT",
):
    # Concat the two price series together, fill to the left
    # This will replace any NA values in existing prices with new ones

    original_data_series_before_mismatch = original_data[data_column][
        original_data.index >= first_date_after_series_mismatch
    ]
    new_data_series_after_mismatch = new_data[data_column][
        new_data.index >= first_date_after_series_mismatch
    ]

    merged_data_series = full_merge_of_existing_series(
        old_series=original_data_series_before_mismatch,
        new_series=new_data_series_after_mismatch,
        keep_older=True,
    )

    current_and_merged_data = _stitch_merged_and_existing_data(
        merged_data_series=merged_data_series,
        original_data=original_data,
        new_data=new_data,
        first_date_after_series_mismatch=first_date_after_series_mismatch,
        last_date_when_series_mismatch=last_date_when_series_mismatch,
        data_column=data_column,
        label_column=label_column,
    )

    return current_and_merged_data


def _stitch_merged_and_existing_data(
    merged_data_series: pd.Series,
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    first_date_after_series_mismatch: datetime.datetime,
    last_date_when_series_mismatch: Union[named_object, datetime.datetime],
    data_column="PRICE",
    label_column="PRICE_CONTRACT",
) -> pd.DataFrame:
    labelled_merged_data = _get_labelled_merged_data(
        merged_data_series=merged_data_series,
        original_data=original_data,
        new_data=new_data,
        first_date_after_series_mismatch=first_date_after_series_mismatch,
        last_date_when_series_mismatch=last_date_when_series_mismatch,
        data_column=data_column,
        label_column=label_column,
    )

    # indices match exactly, so use new merged data
    if last_date_when_series_mismatch is ORIGINAL_INDEX_MATCHES_NEW:
        current_and_merged_data = labelled_merged_data
    else:
        ## Will stitch together, so ignore older original data
        original_data_to_use = original_data[:last_date_when_series_mismatch]

        # Merged data is the old data, and then the new data, stitched together
        current_and_merged_data = pd.concat(
            [original_data_to_use, labelled_merged_data], axis=0
        )

    return current_and_merged_data


def _get_labelled_merged_data(
    merged_data_series: pd.Series,
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    first_date_after_series_mismatch: datetime.datetime,
    last_date_when_series_mismatch: Union[named_object, datetime.datetime],
    data_column="PRICE",
    label_column="PRICE_CONTRACT",
) -> pd.DataFrame:
    labels_in_merged_data = _get_merged_label_data(
        merged_data_series=merged_data_series,
        original_data=original_data,
        new_data=new_data,
        first_date_after_series_mismatch=first_date_after_series_mismatch,
        last_date_when_series_mismatch=last_date_when_series_mismatch,
        label_column=label_column,
    )
    labelled_merged_data = pd.concat(
        [labels_in_merged_data, merged_data_series], axis=1
    )
    labelled_merged_data.columns = [label_column, data_column]

    return labelled_merged_data


def _get_merged_label_data(
    merged_data_series: pd.Series,
    original_data: pd.DataFrame,
    new_data: pd.DataFrame,
    first_date_after_series_mismatch: datetime.datetime,
    last_date_when_series_mismatch: Union[named_object, datetime.datetime],
    label_column="PRICE_CONTRACT",
) -> pd.Series:
    label_series_in_new_data = new_data[last_date_when_series_mismatch:][label_column]
    label_series_in_old_data = original_data[:first_date_after_series_mismatch][
        label_column
    ]
    labels_in_merged_data_original_index = pd.concat(
        [label_series_in_old_data, label_series_in_new_data], axis=0
    )
    labels_in_merged_data_original_index_without_duplicates = (
        labels_in_merged_data_original_index.loc[
            ~labels_in_merged_data_original_index.index.duplicated(keep="first")
        ]
    )
    labels_in_merged_data = (
        labels_in_merged_data_original_index_without_duplicates.reindex(
            merged_data_series.index
        )
    )

    return labels_in_merged_data
