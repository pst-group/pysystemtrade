from sysdata.production.capital import capitalData
from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

DATE_INDEX_NAME = "DATETIME"

## ONLY USED FOR BACKUPS


class csvCapitalData(capitalData):
    def __init__(self, datapath=arg_not_supplied, log=get_logger("csvCapitalData")):
        super().__init__(log=log)

        if datapath is None:
            raise Exception("Need to provide datapath")

        self._datapath = datapath

    def write_backup_df_of_all_capital(self, capital_data):
        filename = resolve_path_and_filename_for_package(
            self._datapath, "%s.csv" % ("capital_data")
        )
        capital_data.to_csv(filename, index_label=DATE_INDEX_NAME)
