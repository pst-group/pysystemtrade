import pandas as pd

from syscore.genutils import flatten_list
from syscore.pandas.pdutils import dataframe_pad


class listOfDataFrames(list):
    def ffill(self):
        ffill_data = [item.ffill() for item in self]
        return listOfDataFrames(ffill_data)

    def resample(self, frequency: str):
        data_resampled = [data_item.resample(frequency).last() for data_item in self]

        return listOfDataFrames(data_resampled)

    def resample_sum(self, frequency: str):
        data_resampled = [data_item.resample(frequency).sum() for data_item in self]

        return listOfDataFrames(data_resampled)

    def stacked_df_with_added_time_from_list(self) -> pd.DataFrame:
        data_as_df = stacked_df_with_added_time_from_list(self)

        return data_as_df

    def aligned(self):
        list_of_df_reindexed = self.reindex_to_common_index()
        list_of_df_common = list_of_df_reindexed.reindex_to_common_columns()

        return list_of_df_common

    def reindex_to_common_index(self):
        common_index = self.common_index()
        reindexed_data = self.reindex(common_index)

        return reindexed_data

    def reindex(self, new_index: list):
        data_reindexed = [data_item.reindex(new_index) for data_item in self]
        return listOfDataFrames(data_reindexed)

    def common_index(self):
        all_indices = [data_item.index for data_item in self]
        all_indices_flattened = flatten_list(all_indices)
        common_unique_index = list(set(all_indices_flattened))
        common_unique_index.sort()

        return common_unique_index

    def reindex_to_common_columns(self, padwith: float = 0.0):
        common_columns = self.common_columns()
        data_reindexed = [
            dataframe_pad(data_item, common_columns, pad_with_value=padwith)
            for data_item in self
        ]
        return listOfDataFrames(data_reindexed)

    def common_columns(self) -> list:
        all_columns = [data_item.columns for data_item in self]
        all_columns_flattened = flatten_list(all_columns)
        common_unique_columns = list(set(all_columns_flattened))
        common_unique_columns.sort()

        return common_unique_columns

    def fill_and_multipy(self) -> pd.DataFrame:
        list_of_df_common = self.aligned()
        list_of_df_common = list_of_df_common.ffill()
        result = list_of_df_common[0]
        for other in list_of_df_common[1:]:
            result = result * other

        return result


def stacked_df_with_added_time_from_list(data: listOfDataFrames) -> pd.DataFrame:
    """
    Create a single data frame from list of data frames

    Useful for fitting or calculating forecast correlations eg across instruments

    To preserve a unique time signature we add on 1..2..3... micro seconds to successive elements of the list

    WARNING: SO THIS METHOD WON'T WORK WITH HIGH FREQUENCY DATA!

    THIS WILL ALSO DESTROY ANY AUTOCORRELATION PROPERTIES

    >>> import datetime
    >>> d1 = pd.DataFrame(dict(a=[1,2]), index=pd.date_range(datetime.datetime(2000,1,1),periods=2))
    >>> d2 = pd.DataFrame(dict(a=[5,6,7]), index=pd.date_range(datetime.datetime(2000,1,1),periods=3))
    >>> list_of_df = listOfDataFrames([d1, d2])
    >>> stacked_df_with_added_time_from_list(list_of_df)
                                a
    2000-01-01 00:00:00.000000  1
    2000-01-01 00:00:00.000001  5
    2000-01-02 00:00:00.000000  2
    2000-01-02 00:00:00.000001  6
    2000-01-03 00:00:00.000001  7
    """

    # ensure all are properly aligned
    # note we don't check that all the columns match here
    aligned_data = data.reindex_to_common_columns()

    # add on an offset
    for offset_value, data_item in enumerate(aligned_data):
        data_item.index = data_item.index.shift(offset_value, freq="us")

    # pooled
    # stack everything up
    stacked_data = pd.concat(aligned_data, axis=0)
    stacked_data = stacked_data.sort_index()

    return stacked_data
