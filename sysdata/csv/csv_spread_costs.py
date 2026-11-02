from syscore.fileutils import resolve_path_and_filename_for_package
from sysdata.futures.spread_costs import spreadCostData
from sysdata.csv.csv_instrument_data import INSTRUMENT_CONFIG_PATH
from syscore.constants import arg_not_supplied

from syslogging.logger import get_logger
import pandas as pd


CONFIG_FILE_NAME = "spreadcosts.csv"
INSTRUMENT_COLUMN_NAME = "Instrument"
SPREAD_COST_COLUMN_NAME = "SpreadCost"


class csvSpreadCostData(spreadCostData):
    """
    Get data about instruments from a special configuration used for initialising the system

    """

    def __init__(
        self,
        datapath=arg_not_supplied,
        log=get_logger("csvSpreadCostData"),
    ):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            datapath = INSTRUMENT_CONFIG_PATH
        config_file = resolve_path_and_filename_for_package(datapath, CONFIG_FILE_NAME)
        self._config_file = config_file

    @property
    def config_file(self):
        return self._config_file

    def delete_spread_cost(self, instrument_code: str):
        raise Exception(
            "Cannot do a partial update of spread costs .csv, have to do whole thing using write_all_instrument_spreads"
        )

    def update_spread_cost(self, instrument_code: str, spread_cost: float):
        raise Exception(
            "Cannot do a partial update of spread costs .csv, have to do whole thing using write_all_instrument_spreads"
        )

    def get_spread_cost(self, instrument_code: str) -> float:
        return self._get_spread_cost_if_series_provided(instrument_code)

    def get_spread_costs_as_series(self) -> pd.Series:
        try:
            spread_cost_data = pd.read_csv(self.config_file)
        except BaseException:
            raise Exception("Can't read file %s" % self.config_file)

        try:
            spread_cost_data.index = spread_cost_data[INSTRUMENT_COLUMN_NAME]
            spread_cost_series = spread_cost_data[SPREAD_COST_COLUMN_NAME]

        except BaseException:
            raise Exception("Badly configured file %s" % (self._config_file))

        return spread_cost_series

    def write_all_instrument_spreads(self, spread_cost_as_series: pd.Series):
        spread_cost_as_df = pd.DataFrame(spread_cost_as_series)
        spread_cost_as_df.columns = [SPREAD_COST_COLUMN_NAME]
        spread_cost_as_df.to_csv(self._config_file, index_label="Instrument")

    def get_list_of_instruments(self) -> list:
        all_data_as_series = self.get_spread_costs_as_series()
        return list(all_data_as_series.keys())
