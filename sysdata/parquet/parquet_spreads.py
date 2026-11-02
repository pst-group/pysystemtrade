from sysdata.parquet.parquet_access import ParquetAccess

from sysdata.futures.spreads import spreadsForInstrumentData
from sysobjects.spreads import spreadsForInstrument
from syslogging.logger import get_logger
import pandas as pd

SPREAD_COLLECTION = "spreads"
SPREAD_COLUMN_NAME = "spread"


class parquetSpreadsForInstrumentData(spreadsForInstrumentData):
    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetSpreadsForInstrument"),
    ):
        super().__init__(log=log)

        self._parquet = parquet_access

    def __repr__(self):
        return "parquetSpreadsForInstrument"

    @property
    def parquet(self):
        return self._parquet

    def get_list_of_instruments(self) -> list:
        return self.parquet.get_all_identifiers_with_data_type(
            data_type=SPREAD_COLLECTION
        )

    def _get_spreads_without_checking(
        self, instrument_code: str
    ) -> spreadsForInstrument:
        data = self.parquet.read_data_given_data_type_and_identifier(
            data_type=SPREAD_COLLECTION, identifier=instrument_code
        )

        spreads = spreadsForInstrument(data[SPREAD_COLUMN_NAME])

        return spreads

    def _delete_spreads_without_any_warning_be_careful(self, instrument_code: str):
        self.parquet.delete_data_given_data_type_and_identifier(
            data_type=SPREAD_COLLECTION, identifier=instrument_code
        )
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
        self.parquet.write_data_given_data_type_and_identifier(
            data_type=SPREAD_COLLECTION,
            data_to_write=spreads_as_pd,
            identifier=instrument_code,
        )
        self.log.debug(
            "Wrote %s lines of spreads for %s to %s"
            % (len(spreads_as_pd), instrument_code, str(self)),
            instrument_code=instrument_code,
        )
