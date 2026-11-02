from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from sysdata.production.roll_state import rollStateData
from syslogging.logger import get_logger


class csvRollStateData(rollStateData):
    """
    Get data about roll state

    """

    def __init__(self, datapath=arg_not_supplied, log=get_logger("csvRollStateData")):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            raise Exception("Datapath needs to be passed")

        self._config_file = resolve_path_and_filename_for_package(
            datapath, "roll_state.csv"
        )
        self.name = "Roll state data from %s" % self._config_file

    def __repr__(self):
        return self.name

    def write_all_instrument_data(self, instrument_data):
        instrument_data.to_csv(self._config_file, index_label="Instrument")
