"""
Read and write data from mongodb for 'multiple prices'

"""

import pandas as pd
from sysdata.parquet.parquet_access import ParquetAccess
from sysdata.futures.multiple_prices import (
    futuresMultiplePricesData,
)
from sysobjects.multiple_prices import futuresMultiplePrices
from sysobjects.dict_of_named_futures_per_contract_prices import (
    list_of_price_column_names,
    contract_name_from_column_name,
)
from syslogging.logger import get_logger

MULTIPLE_COLLECTION = "futures_multiple_prices"


class parquetFuturesMultiplePricesData(futuresMultiplePricesData):
    """
    Class to read / write multiple futures price data to and from arctic
    """

    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetFuturesMultiplePricesData"),
    ):
        super().__init__(log=log)
        self._parquet = parquet_access

    def __repr__(self):
        return "parquetFuturesMultiplePricesData"

    @property
    def parquet(self):
        return self._parquet

    def get_list_of_instruments(self) -> list:
        return self.parquet.get_all_identifiers_with_data_type(
            data_type=MULTIPLE_COLLECTION
        )

    def _get_multiple_prices_without_checking(
        self, instrument_code: str
    ) -> futuresMultiplePrices:
        data = self.parquet.read_data_given_data_type_and_identifier(
            data_type=MULTIPLE_COLLECTION, identifier=instrument_code
        )

        return futuresMultiplePrices(data)

    def _delete_multiple_prices_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        self.parquet.delete_data_given_data_type_and_identifier(
            data_type=MULTIPLE_COLLECTION, identifier=instrument_code
        )
        self.log.debug(
            "Deleted multiple prices for %s from %s" % (instrument_code, str(self))
        )

    def _add_multiple_prices_without_checking_for_existing_entry(
        self, instrument_code: str, multiple_price_data_object: futuresMultiplePrices
    ):
        multiple_price_data_aspd = pd.DataFrame(multiple_price_data_object)
        multiple_price_data_aspd = _change_contracts_to_str(multiple_price_data_aspd)

        self.parquet.write_data_given_data_type_and_identifier(
            data_type=MULTIPLE_COLLECTION,
            identifier=instrument_code,
            data_to_write=multiple_price_data_aspd,
        )
        self.log.debug(
            "Wrote %s lines of prices for %s to %s"
            % (len(multiple_price_data_aspd), instrument_code, str(self)),
            instrument_code=instrument_code,
        )


def _change_contracts_to_str(multiple_price_data_aspd):
    for price_column in list_of_price_column_names:
        multiple_price_data_aspd[price_column] = multiple_price_data_aspd[
            price_column
        ].astype(float)

        contract_column = contract_name_from_column_name(price_column)
        multiple_price_data_aspd[contract_column] = multiple_price_data_aspd[
            contract_column
        ].astype(str)

    return multiple_price_data_aspd
