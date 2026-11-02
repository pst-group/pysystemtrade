## Merge series together
import datetime

import pandas as pd

from enum import Enum
from typing import Union

from syscore.dateutils import SECONDS_PER_DAY
from syscore.constants import named_object, arg_not_supplied
from syscore.pandas.pdutils import is_a_series

VERY_BIG_NUMBER = 99999999.0


def merge_newer_data(
    old_data: Union[pd.Series, pd.DataFrame],
    new_data: Union[pd.Series, pd.DataFrame],
    check_for_spike: bool = True,
    max_spike: float = VERY_BIG_NUMBER,
    column_to_check_for_spike: str = arg_not_supplied,
):
    """
    Merge new data, with old data. Any new data that is older than the newest old data will be ignored
    If check_for_spike will return data_error if price moves too much on join point (checking column_to_check)

    """
    merged_data_with_status = merge_newer_data_no_checks(old_data, new_data)

    # check for spike
    if check_for_spike:
        merged_data_with_status = spike_check_merged_data(
            merged_data_with_status,
            column_to_check_for_spike=column_to_check_for_spike,
            max_spike=max_spike,
        )
        if merged_data_with_status.spike_present:
            return SPIKE_IN_DATA

    merged_data = merged_data_with_status.merged_data

    return merged_data


class mergeStatus(Enum):
    ONLY_OLD = 1
    ONLY_NEW = 2
    MERGED = 3


OLD_DATA_ONLY = mergeStatus.ONLY_OLD
NEW_DATA_ONLY = mergeStatus.ONLY_NEW
MERGED_DATA = mergeStatus.MERGED

NO_SPIKE = named_object("No spike in data")
SPIKE_IN_DATA = named_object("Spike in data")
NO_MERGE_DATE = named_object("No data")


class mergeError(Exception):
    pass


class mergingDataWithStatus(object):
    def __init__(
        self,
        status: mergeStatus,
        date_of_merge_join: Union[datetime.datetime, named_object],
        merged_data: Union[pd.DataFrame, pd.Series],
    ):
        self._status = status
        self._date_of_merge_join = date_of_merge_join
        self._merged_data = merged_data

    @classmethod
    def only_old_data(cls, old_data):
        return mergingDataWithStatus(
            status=OLD_DATA_ONLY, date_of_merge_join=NO_MERGE_DATE, merged_data=old_data
        )

    @classmethod
    def only_new_data(cls, new_data):
        return mergingDataWithStatus(
            status=NEW_DATA_ONLY, date_of_merge_join=NO_MERGE_DATE, merged_data=new_data
        )

    @property
    def spike_present(self) -> bool:
        spike_date = self.spike_date
        if spike_date is NO_SPIKE:
            return False
        else:
            return True

    @property
    def spike_date(self) -> Union[datetime.datetime, named_object]:
        spike_date = getattr(self, "_spike_date", NO_SPIKE)
        return spike_date

    @spike_date.setter
    def spike_date(self, spike_date: datetime.datetime):
        self._spike_date = spike_date

    @property
    def status(self) -> mergeStatus:
        return self._status

    @property
    def date_of_merge_join(self) -> Union[datetime.datetime, named_object]:
        return self._date_of_merge_join

    @property
    def merged_data(self):
        return self._merged_data


def merge_newer_data_no_checks(
    old_data: Union[pd.Series, pd.DataFrame], new_data: Union[pd.Series, pd.DataFrame]
) -> mergingDataWithStatus:
    """
    Merge new data, with old data. Any new data that is older than the newest old data will be ignored

    Also returns status and possibly date of merge

    """

    if len(new_data.index) == 0:
        return mergingDataWithStatus.only_old_data(old_data)
    if len(old_data.index) == 0:
        return mergingDataWithStatus.only_new_data(new_data)

    merged_data_with_status = _merge_newer_data_no_checks_if_both_old_and_new(
        old_data, new_data
    )

    return merged_data_with_status


def _merge_newer_data_no_checks_if_both_old_and_new(
    old_data: Union[pd.Series, pd.DataFrame], new_data: Union[pd.Series, pd.DataFrame]
) -> mergingDataWithStatus:
    last_date_in_old_data = old_data.index[-1]
    new_data.sort_index()
    actually_new_data = new_data[new_data.index > last_date_in_old_data]

    if len(actually_new_data) == 0:
        # No additional data
        return mergingDataWithStatus.only_old_data(old_data)

    first_date_in_new_data = actually_new_data.index[0]

    merged_data = pd.concat([old_data, actually_new_data], axis=0)
    merged_data = merged_data.sort_index()

    # remove duplicates (shouldn't be any, but...)
    merged_data = merged_data[~merged_data.index.duplicated(keep="first")]

    return mergingDataWithStatus(
        status=MERGED_DATA,
        date_of_merge_join=first_date_in_new_data,
        merged_data=merged_data,
    )


def spike_check_merged_data(
    merged_data_with_status: mergingDataWithStatus,
    column_to_check_for_spike: str = arg_not_supplied,
    max_spike: float = VERY_BIG_NUMBER,
) -> mergingDataWithStatus:
    merge_status = merged_data_with_status.status
    merged_data = merged_data_with_status.merged_data

    if merge_status is OLD_DATA_ONLY:
        # No checking, just old data
        return merged_data_with_status

    if merge_status is NEW_DATA_ONLY:
        # check everything as there is no old data
        first_date_in_new_data = NO_MERGE_DATE
    else:
        first_date_in_new_data = merged_data_with_status.date_of_merge_join

    spike_date = _find_first_spike_in_data(
        merged_data,
        first_date_in_new_data,
        column_to_check_for_spike=column_to_check_for_spike,
        max_spike=max_spike,
    )

    merged_data_with_status.spike_date = spike_date

    return merged_data_with_status


def _find_first_spike_in_data(
    merged_data: Union[pd.Series, pd.DataFrame],
    date_of_merge_join: Union[datetime.datetime, named_object] = NO_MERGE_DATE,
    column_to_check_for_spike: str = arg_not_supplied,
    max_spike: float = VERY_BIG_NUMBER,
):
    """
    Checks to see if any data after last_date_in_old_data has spikes
    """
    data_to_check = _get_data_to_check(
        merged_data, column_to_check_for_spike=column_to_check_for_spike
    )
    change_in_vol_normalised_units = _calculate_change_in_vol_normalised_units(
        data_to_check
    )
    relevant_change_in_vol_normalised_units = (
        _get_relevant_period_in_vol_normalised_units_to_check(
            change_in_vol_normalised_units=change_in_vol_normalised_units,
            date_of_merge_join=date_of_merge_join,
        )
    )

    first_spike = _check_for_spikes_in_change_in_vol_normalised_units(
        relevant_change_in_vol_normalised_units=relevant_change_in_vol_normalised_units,
        max_spike=max_spike,
    )

    return first_spike


def _get_data_to_check(
    merged_data: Union[pd.Series, pd.DataFrame],
    column_to_check_for_spike: str = arg_not_supplied,
) -> Union[pd.Series, pd.DataFrame]:
    if is_a_series(merged_data):
        # already a series
        data_to_check = merged_data
    else:
        column_list = merged_data.columns
        if column_to_check_for_spike is arg_not_supplied:
            ## arbitrarily use first column
            column_to_check_for_spike = column_list[0]

        data_to_check = merged_data[column_to_check_for_spike]

    return data_to_check


def _calculate_change_in_vol_normalised_units(data_to_check: pd.Series) -> pd.Series:
    # Calculate the average change per day
    change_per_day = _calculate_change_in_daily_units(data_to_check)

    # absolute is what matters
    absolute_change_per_day = change_per_day.abs()

    # hard to know what span to use here as could be daily, intraday or a
    #     mixture...
    average_absolute_change = absolute_change_per_day.ewm(span=500).mean()

    change_in_vol_normalised_units = absolute_change_per_day / average_absolute_change

    return change_in_vol_normalised_units


def _calculate_change_in_daily_units(data_to_check: pd.Series) -> pd.Series:
    """
    Calculate the average change in daily units asssuming brownian motion
     for example, a change of 0.5 over half a day would be equal to a change of 0.5/sqrt(0.5) = 0.7 over a day
      a change of 2.0 over 5 days, would be equal to a change of 2/sqrt(5) = 0.89 a day
    >>> data_to_check1 = pd.Series([1,1,2], pd.date_range(datetime.datetime(2000,1,1), periods=3))
    >>> data_to_check2 = pd.Series([4,1,8], pd.date_range(datetime.datetime(2000,1,6), periods=3, freq="h"))
    >>> data_to_check = pd.concat([data_to_check1, data_to_check2], axis=0)
    >>> _calculate_change_in_daily_units(data_to_check)
    2000-01-02 00:00:00     0.000000
    2000-01-03 00:00:00     1.000000
    2000-01-06 00:00:00     1.154701
    2000-01-06 01:00:00   -14.696938
    2000-01-06 02:00:00    34.292856
    dtype: float64
    """
    data_diff = data_to_check.diff()[1:]
    index_diff = data_to_check.index[1:] - data_to_check.index[:-1]
    index_diff_days = [diff.total_seconds() / SECONDS_PER_DAY for diff in index_diff]

    change_in_daily_units_as_list = [
        diff / (diff_days**0.5)
        for diff, diff_days in zip(data_diff.values, index_diff_days)
    ]

    change_in_daily_units = pd.Series(
        change_in_daily_units_as_list, index=data_to_check.index[1:]
    )

    return change_in_daily_units


def _get_relevant_period_in_vol_normalised_units_to_check(
    change_in_vol_normalised_units: pd.Series,
    date_of_merge_join: Union[datetime.datetime, named_object] = NO_MERGE_DATE,
):
    if date_of_merge_join is NO_MERGE_DATE:
        # No merged data so we check it all
        relevant_change_in_vol_normalised_units = change_in_vol_normalised_units
    else:
        # just check more recent data
        relevant_change_in_vol_normalised_units = change_in_vol_normalised_units[
            date_of_merge_join:
        ]

    return relevant_change_in_vol_normalised_units


def _check_for_spikes_in_change_in_vol_normalised_units(
    relevant_change_in_vol_normalised_units: pd.Series,
    max_spike: float = VERY_BIG_NUMBER,
) -> Union[datetime.datetime, named_object]:
    if any(relevant_change_in_vol_normalised_units > max_spike):
        first_spike = relevant_change_in_vol_normalised_units.index[
            relevant_change_in_vol_normalised_units > max_spike
        ][0]
    else:
        first_spike = NO_SPIKE

    return first_spike
