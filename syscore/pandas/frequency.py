from typing import Union, List

import numpy as np
import pandas as pd

from syscore.dateutils import (
    Frequency,
    BUSINESS_DAY_FREQ,
    HOURLY_FREQ,
    NOTIONAL_CLOSING_TIME_AS_PD_OFFSET,
    check_time_matches_closing_time_to_second,
    BUSINESS_DAYS_IN_YEAR,
    WEEKS_IN_YEAR,
    MONTHS_IN_YEAR,
    CALENDAR_DAYS_IN_YEAR,
    HOURS_PER_DAY,
)
from syscore.pandas.pdutils import uniquets


def closing_date_rows_in_pd_object(
    pd_object: Union[pd.DataFrame, pd.Series],
    closing_time: pd.DateOffset = NOTIONAL_CLOSING_TIME_AS_PD_OFFSET,
) -> Union[pd.DataFrame, pd.Series]:
    """
    >>> import datetime
    >>> d = datetime.datetime
    >>> date_index = [d(2000,1,1,15),d(2000,1,1,23), d(2000,1,2,15)]
    >>> df = pd.DataFrame(dict(a=[1, 2, 3], b=[4 , 6, 5]), index=date_index)
    >>> closing_date_rows_in_pd_object(df)
                         a  b
    2000-01-01 23:00:00  2  6

    """
    return pd_object[
        [
            check_time_matches_closing_time_to_second(
                index_entry=index_entry, closing_time=closing_time
            )
            for index_entry in pd_object.index
        ]
    ]


def intraday_date_rows_in_pd_object(
    pd_object: Union[pd.DataFrame, pd.Series],
    closing_time: pd.DateOffset = NOTIONAL_CLOSING_TIME_AS_PD_OFFSET,
) -> Union[pd.DataFrame, pd.Series]:
    """
    >>> import datetime
    >>> d = datetime.datetime
    >>> date_index = [d(2000,1,1,15),d(2000,1,1,23), d(2000,1,2,15)]
    >>> df = pd.DataFrame(dict(a=[1, 2, 3], b=[4 , 6, 5]), index=date_index)
    >>> intraday_date_rows_in_pd_object(df)
                         a  b
    2000-01-01 15:00:00  1  4
    2000-01-02 15:00:00  3  5
    """

    return pd_object[
        [
            not check_time_matches_closing_time_to_second(
                index_entry=index_entry, closing_time=closing_time
            )
            for index_entry in pd_object.index
        ]
    ]


def get_intraday_pdf_at_frequency(
    pd_object: Union[pd.DataFrame, pd.Series],
    frequency: str = "H",
    closing_time: pd.DateOffset = NOTIONAL_CLOSING_TIME_AS_PD_OFFSET,
) -> Union[pd.Series, pd.DataFrame]:
    """
    >>> import datetime
    >>> d = datetime.datetime
    >>> date_index = [d(2000,1,1,15),d(2000,1,1,16),d(2000,1,1,23), d(2000,1,2,15)]
    >>> df = pd.DataFrame(dict(a=[1, 2, 3,4], b=[4,5,6,7]), index=date_index)
    >>> get_intraday_pdf_at_frequency(df,"2H")
                           a    b
    2000-01-01 14:00:00  1.0  4.0
    2000-01-01 16:00:00  2.0  5.0
    2000-01-02 14:00:00  4.0  7.0
    """
    intraday_only_df = intraday_date_rows_in_pd_object(
        pd_object, closing_time=closing_time
    )
    intraday_df = intraday_only_df.resample(frequency).last()
    intraday_df_clean = intraday_df.dropna()

    return intraday_df_clean


def merge_data_with_different_freq(
    list_of_data: List[Union[pd.DataFrame, pd.Series]]
) -> Union[pd.Series, pd.DataFrame]:
    """
    Where items share a timestamp, the row from the later item in list_of_data wins,
    so pass daily prices last to keep them over intraday bars at the closing time.

    >>> import datetime
    >>> d = datetime.datetime
    >>> date_index1 = [d(2000,1,1,23),d(2000,1,2,23),d(2000,1,3,23)]
    >>> date_index2 = [d(2000,1,1,15),d(2000,1,1,16),d(2000,1,2,15)]
    >>> s1 = pd.Series([3,5,6], index=date_index1)
    >>> s2 = pd.Series([1,2,4], index=date_index2)
    >>> merge_data_with_different_freq([s1,s2])
    2000-01-01 15:00:00    1
    2000-01-01 16:00:00    2
    2000-01-01 23:00:00    3
    2000-01-02 15:00:00    4
    2000-01-02 23:00:00    5
    2000-01-03 23:00:00    6
    dtype: int64
    >>> s3 = pd.Series([9], index=[d(2000,1,1,23)])
    >>> merge_data_with_different_freq([s3, s1])
    2000-01-01 23:00:00    3
    2000-01-02 23:00:00    5
    2000-01-03 23:00:00    6
    dtype: int64
    """

    filtered = [item for item in list_of_data if len(item) > 0]
    if len(filtered) == 0:
        return list_of_data[0]
    else:
        list_as_concat_pd = pd.concat(filtered, axis=0)
    # stable sort keeps input order among equal timestamps, so the later item's row is
    # last; take the whole row rather than the last non-null value in each column
    sorted_pd = list_as_concat_pd.sort_index(kind="stable")
    unique_pd = sorted_pd[~sorted_pd.index.duplicated(keep="last")]

    return unique_pd


def sumup_business_days_over_pd_series_without_double_counting_of_closing_data(
    pd_series: pd.Series,
    closing_time: pd.DateOffset = NOTIONAL_CLOSING_TIME_AS_PD_OFFSET,
) -> pd.Series:
    """
    Used for volume data - adds up a series over a day to get a daily total

    Uses closing values when available, otherwise sums up intraday values

    >>> import datetime
    >>> d = datetime.datetime
    >>> date_index1 = [d(2000,2,1,15),d(2000,2,1,16), d(2000,2,1,23), ]
    >>> s1 = pd.Series([10,5,17], index=date_index1)
    >>> sumup_business_days_over_pd_series_without_double_counting_of_closing_data(s1)
    2000-02-01    17
    Freq: B, Name: 0, dtype: int64
    >>> date_index1 = [d(2000,2,1,15),d(2000,2,1,16), d(2000,2,2,23) ]
    >>> s1 = pd.Series([10,5,2], index=date_index1)
    >>> sumup_business_days_over_pd_series_without_double_counting_of_closing_data(s1)
    2000-02-01    15.0
    2000-02-02     2.0
    Freq: B, Name: 0, dtype: float64
    """
    intraday_data = intraday_date_rows_in_pd_object(
        pd_series, closing_time=closing_time
    )
    if len(intraday_data) == 0:
        return pd_series

    intraday_data_summed = intraday_data.resample("1B").sum()
    intraday_data_summed.name = "intraday"

    closing_data = closing_date_rows_in_pd_object(pd_series)
    closing_data_summed = closing_data.resample("1B").sum()

    both_sets_of_data = pd.concat([intraday_data_summed, closing_data_summed], axis=1)
    both_sets_of_data[both_sets_of_data == 0] = np.nan
    joint_data = both_sets_of_data.ffill(axis=1)
    joint_data = joint_data.iloc[:, 1]

    return joint_data


def resample_prices_to_business_day_index(x):
    return x.resample("1B").last()


def how_many_times_a_year_is_pd_frequency(frequency: str) -> float:
    DICT_OF_FREQ = {
        "B": BUSINESS_DAYS_IN_YEAR,
        "W": WEEKS_IN_YEAR,
        "M": MONTHS_IN_YEAR,
        "D": CALENDAR_DAYS_IN_YEAR,
    }

    try:
        times_a_year = DICT_OF_FREQ[frequency]
    except KeyError as e:
        raise Exception(
            "Frequency %s is no good I only know about %s"
            % (frequency, str(list(DICT_OF_FREQ.keys())))
        ) from e

    return float(times_a_year)


def interpolate_data_during_day(
    data_series: pd.Series, resample_freq="600S"
) -> pd.Series:
    set_of_data_by_day = [
        group[1] for group in data_series.groupby(data_series.index.date)
    ]
    interpolate_data_by_day = [
        interpolate_for_a_single_day(
            data_series_for_a_single_day, resample_freq=resample_freq
        )
        for data_series_for_a_single_day in set_of_data_by_day
    ]

    interpolated_data_as_single_series = pd.concat(interpolate_data_by_day, axis=0)

    return interpolated_data_as_single_series


def interpolate_for_a_single_day(
    data_series_for_single_day: pd.Series, resample_freq="600S"
) -> pd.Series:
    if len(data_series_for_single_day) < 2:
        return data_series_for_single_day

    resampled_data = data_series_for_single_day.resample(resample_freq).interpolate()

    return resampled_data


def reindex_last_monthly_include_first_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df_monthly_index = list(df.resample("1M").last().index)  ## last day in month
    df_first_date_in_index = df.index[0]
    df_monthly_index = [df_first_date_in_index] + df_monthly_index
    df_reindex = df.reindex(df_monthly_index).ffill()

    return df_reindex


def infer_frequency(df_or_ts: Union[pd.DataFrame, pd.Series]) -> Frequency:
    inferred = pd.infer_freq(df_or_ts.index)
    if inferred is None:
        return infer_frequency_approx(df_or_ts)
    if inferred == "B":
        return BUSINESS_DAY_FREQ
    if inferred == "H":
        return HOURLY_FREQ
    raise Exception("Frequency of time series unknown")


UPPER_BOUND_HOUR_FRACTION_OF_A_DAY = 1.0 / 2.0
LOWER_BOUND_HOUR_FRACTION_OF_A_DAY = 1.0 / HOURS_PER_DAY
BUSINESS_CALENDAR_FRACTION = CALENDAR_DAYS_IN_YEAR / BUSINESS_DAYS_IN_YEAR


def infer_frequency_approx(df_or_ts: Union[pd.DataFrame, pd.Series]) -> Frequency:
    avg_time_delta_in_days = average_time_delta_for_time_series(df_or_ts)

    if _probably_daily_freq(avg_time_delta_in_days):
        return BUSINESS_DAY_FREQ

    if _probably_hourly_freq(avg_time_delta_in_days):
        return HOURLY_FREQ

    raise Exception("Can't work out approximate frequency")


def _probably_daily_freq(avg_time_delta_in_days: float) -> bool:
    return round(avg_time_delta_in_days, 1) == BUSINESS_CALENDAR_FRACTION


def _probably_hourly_freq(avg_time_delta_in_days: float) -> bool:
    return (avg_time_delta_in_days < UPPER_BOUND_HOUR_FRACTION_OF_A_DAY) & (
        avg_time_delta_in_days >= LOWER_BOUND_HOUR_FRACTION_OF_A_DAY
    )


def average_time_delta_for_time_series(
    df_or_ts: Union[pd.DataFrame, pd.Series]
) -> float:
    avg_time_delta = abs(np.diff(df_or_ts.index)).mean()
    avg_time_delta_in_days = avg_time_delta / np.timedelta64(1, "D")

    return avg_time_delta_in_days
