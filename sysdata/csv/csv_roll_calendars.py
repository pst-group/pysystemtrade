from sysobjects.roll_calendars import rollCalendar
from sysdata.futures.roll_calendars import rollCalendarData
from syscore.fileutils import (
    resolve_path_and_filename_for_package,
    files_with_extension_in_pathname,
)
from syscore.pandas.pdutils import pd_readcsv
from syscore.constants import arg_not_supplied
from syslogging.logger import get_logger

CSV_ROLL_CALENDAR_DIRECTORY = "data.futures.roll_calendars_csv"
DATE_INDEX_NAME = "DATE_TIME"

# NOTE: can't change calendars here - do we need init?
# common with all other csv objects?


class csvRollCalendarData(rollCalendarData):
    """

    Class for roll calendars write / to from csv
    """

    def __init__(
        self, datapath=arg_not_supplied, log=get_logger("csvRollCalendarData")
    ):
        super().__init__(log=log)

        if datapath is arg_not_supplied:
            datapath = CSV_ROLL_CALENDAR_DIRECTORY

        self._datapath = datapath

    def __repr__(self):
        return "csvRollCalendarData accessing %s" % self.datapath

    @property
    def datapath(self):
        return self._datapath

    def get_list_of_instruments(self) -> list:
        return files_with_extension_in_pathname(self.datapath, ".csv")

    def _get_roll_calendar_without_checking(self, instrument_code: str) -> rollCalendar:
        filename = self._filename_given_instrument_code(instrument_code)
        try:
            roll_calendar = pd_readcsv(filename, date_index_name=DATE_INDEX_NAME)
        except OSError:
            self.log.warning("Can't find roll calendar file %s" % filename)
            return rollCalendar.create_empty()

        roll_calendar = rollCalendar(roll_calendar)

        return roll_calendar

    def _delete_roll_calendar_data_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError(
            "You can't delete a roll calendar stored as a csv - Add to overwrite existing or delete file manually"
        )

    def _add_roll_calendar_without_checking_for_existing_entry(
        self, instrument_code: str, roll_calendar: rollCalendar
    ):
        filename = self._filename_given_instrument_code(instrument_code)
        roll_calendar.to_csv(filename, index_label=DATE_INDEX_NAME)
        self.log.debug("Wrote calendar for %s to %s" % (instrument_code, str(filename)))

    def _filename_given_instrument_code(self, instrument_code: str):
        return resolve_path_and_filename_for_package(
            self.datapath, "%s.csv" % (instrument_code)
        )
