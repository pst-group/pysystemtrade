import pandas as pd
from sysdata.production.optimal_positions import optimalPositionData
from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger
from sysobjects.production.tradeable_object import instrumentStrategy

DATE_INDEX_NAME = "DATETIME"


class csvOptimalPositionData(optimalPositionData):
    """

    Class for contract_positions write to / read from csv
    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvOptimalPositionData")
    ):
        super().__init__(log=log)

        if datapath is None:
            raise Exception("Need to provide datapath")

        self._datapath = datapath

    def __repr__(self):
        return "csvOptimalPositionData accessing %s" % self._datapath

    def write_optimal_position_as_df_for_instrument_strategy_without_checking(
        self,
        instrument_strategy: instrumentStrategy,
        optimal_positions_as_df: pd.DataFrame,
    ):
        filename = self._filename_given_instrument_strategy(instrument_strategy)
        optimal_positions_as_df.to_csv(filename, index_label=DATE_INDEX_NAME)

    def _filename_given_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ):
        return resolve_path_and_filename_for_package(
            self._datapath,
            "%s_%s.csv"
            % (instrument_strategy.strategy_name, instrument_strategy.instrument_code),
        )
