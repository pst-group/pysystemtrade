from sysdata.parquet.parquet_access import ParquetAccess
from sysdata.futures.adjusted_prices import (
    futuresAdjustedPricesData,
)
from sysobjects.adjusted_prices import futuresAdjustedPrices

from syslogging.logger import get_logger
import pandas as pd

ADJPRICE_COLLECTION = "futures_adjusted_prices"


class parquetFuturesAdjustedPricesData(futuresAdjustedPricesData):
    """
    Read and write futures adjusted price data stored as Parquet files.

    Implements the abstract 'futuresAdjustedPricesData' interface using a
    'ParquetAccess' backend. Each instrument's adjusted price series is stored
    as a separate Parquet file in the 'futures_adjusted_prices' collection.
    """

    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetFuturesAdjustedPrices"),
    ):
        super().__init__(log=log)
        self._parquet = parquet_access

    def __repr__(self):
        return "parquetFuturesAdjustedPrices"

    @property
    def parquet(self) -> ParquetAccess:
        return self._parquet

    def get_list_of_instruments(self) -> list:
        return self.parquet.get_all_identifiers_with_data_type(
            data_type=ADJPRICE_COLLECTION
        )

    def _get_adjusted_prices_without_checking(
        self, instrument_code: str
    ) -> futuresAdjustedPrices:
        raw_price_df = self.parquet.read_data_given_data_type_and_identifier(
            data_type=ADJPRICE_COLLECTION, identifier=instrument_code
        )
        return futuresAdjustedPrices(raw_price_df.squeeze())

    def _delete_adjusted_prices_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        self.parquet.delete_data_given_data_type_and_identifier(
            data_type=ADJPRICE_COLLECTION, identifier=instrument_code
        )
        self.log.debug(
            "Deleted adjusted prices for %s from %s" % (instrument_code, str(self)),
            instrument_code=instrument_code,
        )

    def _add_adjusted_prices_without_checking_for_existing_entry(
        self, instrument_code: str, adjusted_price_data: futuresAdjustedPrices
    ):
        adjusted_price_data_aspd = pd.DataFrame(adjusted_price_data)
        adjusted_price_data_aspd.columns = ["price"]
        adjusted_price_data_aspd = adjusted_price_data_aspd.astype(float)

        self.parquet.write_data_given_data_type_and_identifier(
            data_to_write=adjusted_price_data_aspd,
            data_type=ADJPRICE_COLLECTION,
            identifier=instrument_code,
        )

        self.log.debug(
            "Wrote %s lines of prices for %s to %s"
            % (len(adjusted_price_data), instrument_code, str(self)),
            instrument_code=instrument_code,
        )
