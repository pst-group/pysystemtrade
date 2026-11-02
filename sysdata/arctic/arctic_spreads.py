from sysdata.futures.spreads import spreadsForInstrumentData
from sysobjects.spreads import spreadsForInstrument
from sysdata.arctic.arctic_connection import arcticData
from syslogging.logger import get_logger
import pandas as pd

SPREAD_COLLECTION = "spreads"
SPREAD_COLUMN_NAME = "spread"


class arcticSpreadsForInstrumentData(spreadsForInstrumentData):
    def __init__(self, mongo_db=None, log=get_logger("arcticSpreadsForInstrument")):
        super().__init__(log=log)

        self._arctic = arcticData(SPREAD_COLLECTION, mongo_db=mongo_db)

    def __repr__(self):
        return repr(self._arctic)

    @property
    def arctic(self):
        return self._arctic

    def get_list_of_instruments(self) -> list:
        return self.arctic.get_keynames()

    def _get_spreads_without_checking(
        self, instrument_code: str
    ) -> spreadsForInstrument:
        data = self.arctic.read(instrument_code)

        spreads = spreadsForInstrument(data[SPREAD_COLUMN_NAME])

        return spreads

    def _delete_spreads_without_any_warning_be_careful(self, instrument_code: str):
        self.arctic.delete(instrument_code)
        self.log.debug(
            "Deleted spreads for %s from %s" % (instrument_code, str(self)),
            instrument_code=instrument_code,
        )

    def _add_spreads_without_checking_for_existing_entry(
        self, instrument_code: str, spreads: spreadsForInstrument
    ):
        spreads_as_pd = pd.DataFrame(spreads)
        spreads_as_pd.columns = [SPREAD_COLUMN_NAME]
        spreads_as_pd = spreads_as_pd.astype(float)
        self.arctic.write(instrument_code, spreads_as_pd)
        self.log.debug(
            "Wrote %s lines of spreads for %s to %s"
            % (len(spreads_as_pd), instrument_code, str(self)),
            instrument_code=instrument_code,
        )
