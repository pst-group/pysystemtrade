from sysdata.base_data import baseData
from syslogging.logger import get_logger
from sysobjects.rolls import rollParameters

USE_CHILD_CLASS_ROLL_PARAMS_ERROR = (
    "You need to use a child class of rollParametersData"
)


class rollParametersMissing(Exception):
    pass


class rollParametersData(baseData):
    """
    Read and write data class to get roll data for a given instrument

    We'd inherit from this class for a specific implementation

    """

    def __init__(self, log=get_logger("futuresInstrumentData")):
        super().__init__(log=log)

    def __repr__(self):
        return "rollParametersData base class - DO NOT USE"

    def keys(self):
        return self.get_list_of_instruments()

    def __getitem__(self, instrument_code: str) -> rollParameters:
        return self.get_roll_parameters(instrument_code)

    def get_roll_parameters(self, instrument_code: str) -> rollParameters:
        if self.is_code_in_data(instrument_code):
            return self._get_roll_parameters_without_checking(instrument_code)
        else:
            raise rollParametersMissing(
                "Don't have parameters for %s" % instrument_code
            )

    def delete_roll_parameters(self, instrument_code: str, are_you_sure: bool = False):
        self.log.debug("Updating log attributes", instrument_code=instrument_code)

        if are_you_sure:
            if self.is_code_in_data(instrument_code):
                self._delete_roll_parameters_data_without_any_warning_be_careful(
                    instrument_code
                )
                self.log.info("Deleted roll parameters for %s" % instrument_code)

            else:
                # doesn't exist anyway
                self.log.warning(
                    "Tried to delete roll parameters for non existent instrument code %s"
                    % instrument_code
                )
        else:
            self.log.error(
                "You need to call delete_roll_parameters with a flag to be sure"
            )

    def add_roll_parameters(
        self,
        instrument_code: str,
        roll_parameters: rollParameters,
        ignore_duplication: bool = False,
    ):
        self.log.debug("Updating log attributes", instrument_code=instrument_code)

        if self.is_code_in_data(instrument_code):
            if ignore_duplication:
                pass
            else:
                raise self.log.warning(
                    "There is already %s in the data, you have to delete it first"
                    % instrument_code
                )

        self._add_roll_parameters_without_checking_for_existing_entry(
            instrument_code, roll_parameters
        )

        self.log.info("Added roll parameters for instrument %s" % instrument_code)

    def is_code_in_data(self, instrument_code: str) -> bool:
        if instrument_code in self.get_list_of_instruments():
            return True
        else:
            return False

    def _delete_roll_parameters_data_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError(USE_CHILD_CLASS_ROLL_PARAMS_ERROR)

    def _add_roll_parameters_without_checking_for_existing_entry(
        self, instrument_code: str, roll_parameters: rollParameters
    ):
        raise NotImplementedError(USE_CHILD_CLASS_ROLL_PARAMS_ERROR)

    def get_list_of_instruments(self) -> list:
        raise NotImplementedError(USE_CHILD_CLASS_ROLL_PARAMS_ERROR)

    def _get_roll_parameters_without_checking(
        self, instrument_code: str
    ) -> rollParameters:
        raise NotImplementedError(USE_CHILD_CLASS_ROLL_PARAMS_ERROR)
