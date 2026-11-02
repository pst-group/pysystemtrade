import pandas as pd
import numpy as np

from syscore.exceptions import missingData
from sysdata.futures.spread_costs import spreadCostData
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

SPREAD_COST_COLLECTION = "spread_costs"
INSTRUMENT_KEY = "instrument_code"


class mongoSpreadCostData(spreadCostData):
    """
    Read and write data class to get spread costs


    """

    def __init__(self, mongo_db=None, log=get_logger("mongoSpreadCostData")):
        super().__init__(log=log)
        self._mongo_data = mongoDataWithSingleKey(
            SPREAD_COST_COLLECTION, mongo_db=mongo_db, key_name=INSTRUMENT_KEY
        )

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "Data connection for spread cost data, mongodb %s" % (
            str(self.mongo_data)
        )

    def delete_spread_cost(self, instrument_code: str):
        self.mongo_data.delete_data_without_any_warning(instrument_code)

    def get_list_of_instruments(self) -> list:
        return self.mongo_data.get_list_of_keys()

    def get_spread_costs_as_series(self) -> pd.Series:
        return self._get_spread_costs_as_series_if_individual_spreads_provided()

    def get_spread_cost(self, instrument_code: str) -> float:
        ## override base method for speed
        try:
            result_dict = self.mongo_data.get_result_dict_for_key_without_key_value(
                instrument_code
            )
        except missingData:
            self.log.warning(
                "No spread cost in database for %s, using 0" % instrument_code
            )
            return 0.0

        spread_cost = _cost_value_from_dict(result_dict)
        if np.isnan(spread_cost):
            self.log.warning("No valid spread cost for %s, using 0" % instrument_code)
            return 0.0

        return spread_cost

    def update_spread_cost(self, instrument_code: str, spread_cost: float):
        data_dict = _dict_from_spread_cost(spread_cost)

        self.mongo_data.add_data(
            instrument_code,
            data_dict=data_dict,
            allow_overwrite=True,
            clean_ints=False,
        )


SPREAD_COST_KEY = "cost_price_units"


def _cost_value_from_dict(result_dict) -> float:
    return result_dict[SPREAD_COST_KEY]


def _dict_from_spread_cost(spread_cost: float) -> dict:
    return {SPREAD_COST_KEY: spread_cost}
