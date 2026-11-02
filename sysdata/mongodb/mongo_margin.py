import pandas as pd
from syscore.dateutils import long_to_datetime, datetime_to_long
from syscore.exceptions import missingData
from syscore.constants import arg_not_supplied
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey

from sysdata.production.margin import marginData, seriesOfMargin
from syslogging.logger import get_logger

MARGIN_COLLECTION = "margin"
STRATEGY_REF = "strategy_name"


class mongoMarginData(marginData):
    """
    Read and write data class to get next used client id
    """

    def __init__(
        self,
        mongo_db=arg_not_supplied,
        log=get_logger("mongoMarginData"),
    ):
        self._mongo_data = mongoDataWithSingleKey(
            MARGIN_COLLECTION, STRATEGY_REF, mongo_db
        )
        self._log = log

    @property
    def log(self):
        return self._log

    @property
    def mongo_data(self):
        return self._mongo_data

    def _repr__(self):
        return "Margin data, mongodb %s" % (str(self.mongo_data))

    def get_series_of_strategy_margin(self, strategy_name: str) -> seriesOfMargin:
        data_dict = self._get_data_dict_for_strategy_margin(strategy_name)
        series_of_margin = from_dict_of_entries_to_margin_series(data_dict)

        return series_of_margin

    def _get_data_dict_for_strategy_margin(self, strategy_name: str) -> dict:
        try:
            data_dict = self.mongo_data.get_result_dict_for_key_without_key_value(
                strategy_name
            )
        except missingData:
            return dict()

        return data_dict

    def _write_series_of_strategy_margin(
        self, strategy_name: str, series_of_margin: seriesOfMargin
    ):
        data_dict = from_series_of_margin_to_dict_of_entries(series_of_margin)
        self.mongo_data.add_data(strategy_name, data_dict, allow_overwrite=True)

    def _get_list_of_strategies_with_margin_including_total(self) -> list:
        return self.mongo_data.get_list_of_keys()


def from_dict_of_entries_to_margin_series(dict_of_entries: dict) -> seriesOfMargin:
    list_of_keys = dict_of_entries.keys()
    list_of_keys_as_datetime = [
        long_to_datetime(int(key_entry)) for key_entry in list_of_keys
    ]
    list_of_values = list(dict_of_entries.values())

    pd_series = pd.Series(
        list_of_values, index=list_of_keys_as_datetime, dtype="float64"
    )
    pd_series = pd_series.sort_index()

    return seriesOfMargin(pd_series)


def from_series_of_margin_to_dict_of_entries(series_of_margin: seriesOfMargin) -> dict:
    series_of_dates = list(series_of_margin.index)
    list_of_keys = [str(datetime_to_long(date_entry)) for date_entry in series_of_dates]
    list_of_values = list(series_of_margin.values)

    data_dict = dict([(key, value) for key, value in zip(list_of_keys, list_of_values)])

    return data_dict
