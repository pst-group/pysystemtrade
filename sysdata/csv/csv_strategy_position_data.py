import pandas as pd
from sysdata.production.historic_strategy_positions import strategyPositionData
from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger
from sysobjects.production.tradeable_object import instrumentStrategy

DATE_INDEX_NAME = "DATETIME"


class csvStrategyPositionData(strategyPositionData):
    """

    Class for contract_positions write to / read from csv
    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvStrategyPositionData")
    ):
        super().__init__(log=log)

        if datapath is None:
            raise Exception("Need to provide datapath")

        self._datapath = datapath

    def __repr__(self):
        return "csvStrategyPositionData accessing %s" % self._datapath

    def _write_updated_position_series_for_instrument_strategy_object(
        self, instrument_strategy: instrumentStrategy, updated_series: pd.Series
    ):
        position_df = pd.DataFrame(updated_series)
        filename = self._filename_given_instrument_strategy(instrument_strategy)
        position_df.to_csv(filename, index_label=DATE_INDEX_NAME)

    def _filename_given_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ):
        return resolve_path_and_filename_for_package(
            self._datapath,
            "%s_%s.csv"
            % (instrument_strategy.strategy_name, instrument_strategy.instrument_code),
        )
