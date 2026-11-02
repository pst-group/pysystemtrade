from syscore.constants import arg_not_supplied
from syscore.fileutils import resolve_path_and_filename_for_package
from sysdata.futures.rolls_parameters import rollParametersData
from sysobjects.rolls import rollParameters
from syslogging.logger import get_logger

import pandas as pd

ROLLS_DATAPATH = "data.futures.csvconfig"
ROLLS_CONFIG_FILE = "rollconfig.csv"


class allRollParameters(pd.DataFrame):
    @classmethod
    def read_from_file(allRollParameters, filename):
        try:
            roll_data = pd.read_csv(filename)
        except BaseException:
            raise Exception("Can't read file %s" % filename)

        try:
            roll_data.index = roll_data.Instrument
            roll_data.drop(labels="Instrument", axis=1, inplace=True)

        except BaseException:
            raise Exception("Badly configured file %s" % (filename))

        return allRollParameters(roll_data)

    def get_list_of_instruments(self) -> list:
        return list(self.index)

    def get_roll_parameters_for_instrument(
        self, instrument_code: str
    ) -> rollParameters:
        config_for_this_instrument = self.loc[instrument_code]
        roll_parameters_object = rollParameters(
            hold_rollcycle=config_for_this_instrument.HoldRollCycle,
            roll_offset_day=config_for_this_instrument.RollOffsetDays,
            carry_offset=config_for_this_instrument.CarryOffset,
            priced_rollcycle=config_for_this_instrument.PricedRollCycle,
            approx_expiry_offset=config_for_this_instrument.ExpiryOffset,
        )

        return roll_parameters_object

    def update_roll_parameters_for_instrument(
        self, instrument_code: str, roll_parameters: rollParameters
    ):
        self.at[instrument_code, "HoldRollCycle"] = roll_parameters.hold_rollcycle
        self.at[instrument_code, "RollOffsetDays"] = roll_parameters.roll_offset_day
        self.at[instrument_code, "CarryOffset"] = roll_parameters.carry_offset
        self.at[instrument_code, "PricedRollCycle"] = roll_parameters.priced_rollcycle
        self.at[instrument_code, "ExpiryOffset"] = roll_parameters.approx_expiry_offset

    def write_to_file(self, filename: str):
        self.to_csv(filename, index_label="Instrument")


class csvRollParametersData(rollParametersData):
    """
    Get data about instruments from a special configuration used for initialising the system

    """

    def __init__(
        self, log=get_logger("csvRollParametersData"), datapath=arg_not_supplied
    ):
        super().__init__(log=log)
        if datapath is arg_not_supplied:
            datapath = ROLLS_DATAPATH
        config_file = resolve_path_and_filename_for_package(datapath, ROLLS_CONFIG_FILE)

        self._config_file = config_file

    def __repr__(self):
        return "Roll data for initialising system config"

    def get_list_of_instruments(self) -> list:
        all_roll_parameters = self.get_roll_parameters_all_instruments()
        return all_roll_parameters.get_list_of_instruments()

    def _get_roll_parameters_without_checking(
        self, instrument_code: str
    ) -> rollParameters:
        all_parameters = self.get_roll_parameters_all_instruments()
        return all_parameters.get_roll_parameters_for_instrument(instrument_code)

    def _delete_roll_parameters_data_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError("csv is read only")

    def _add_roll_parameters_without_checking_for_existing_entry(
        self, instrument_code: str, roll_parameters: rollParameters
    ):
        ## We don't normally allow this, but a special case as we safe modify
        all_parameters = self.get_roll_parameters_all_instruments()
        all_parameters.update_roll_parameters_for_instrument(
            instrument_code, roll_parameters
        )
        all_parameters.write_to_file(self.config_file)

        self.log.warning(
            "*** WRITTEN NEW ROLL PARAMETERS TO %s - copy to /data/futures/csvconfig/rollconfig.csv NOW ***"
            % self.config_file
        )

    def write_all_roll_parameters_data(self, roll_parameters_df: pd.DataFrame):
        all_roll_parameters = allRollParameters(roll_parameters_df)
        all_roll_parameters.write_to_file(self.config_file)

    def get_roll_parameters_all_instruments(self) -> allRollParameters:
        return allRollParameters.read_from_file(self.config_file)

    @property
    def config_file(self):
        return self._config_file
