"""
Get data from mongo and arctic used for futures trading

"""

from syscore.constants import arg_not_supplied

from sysdata.parquet.parquet_adjusted_prices import parquetFuturesAdjustedPricesData
from sysdata.parquet.parquet_multiple_prices import parquetFuturesMultiplePricesData
from sysdata.parquet.parquet_spotfx_prices import parquetFxPricesData

"""
from sysdata.arctic.arctic_adjusted_prices import arcticFuturesAdjustedPricesData
from sysdata.arctic.arctic_multiple_prices import arcticFuturesMultiplePricesData
from sysdata.arctic.arctic_spotfx_prices import arcticFxPricesData
"""

from sysdata.csv.csv_instrument_data import csvFuturesInstrumentData
from sysdata.csv.csv_roll_parameters import csvRollParametersData
from sysdata.mongodb.mongo_spread_costs import mongoSpreadCostData
from sysdata.data_blob import dataBlob
from sysdata.sim.futures_sim_data_with_data_blob import genericBlobUsingFuturesSimData

from syslogging.logger import get_logger


class dbFuturesSimData(genericBlobUsingFuturesSimData):
    def __init__(
        self,
        data: dataBlob = arg_not_supplied,
        csv_data_paths=arg_not_supplied,
        log=get_logger("dbFuturesSimData"),
    ):
        if data is arg_not_supplied:
            data = dataBlob(
                log=log,
                csv_data_paths=csv_data_paths,
                class_list=[
                    get_class_for_data_type(FUTURES_ADJUSTED_PRICE_DATA),
                    get_class_for_data_type(FUTURES_MULTIPLE_PRICE_DATA),
                    get_class_for_data_type(FX_DATA),
                    get_class_for_data_type(FUTURES_INSTRUMENT_DATA),
                    get_class_for_data_type(ROLL_PARAMETERS_DATA),
                    get_class_for_data_type(STORED_SPREAD_DATA),
                ],
            )

        super().__init__(data=data)

    def __repr__(self):
        return "dbFuturesSimData object with %d instruments" % len(
            self.get_instrument_list()
        )


FUTURES_MULTIPLE_PRICE_DATA = "futures_multiple_price_data"
FUTURES_ADJUSTED_PRICE_DATA = "futures_adjusted_price_data"
CAPITAL_DATA = "capital_data"
FX_DATA = "fx_data"
ROLL_PARAMETERS_DATA = "roll_parameters_data"
FUTURES_INSTRUMENT_DATA = "futures_instrument_data"
STORED_SPREAD_DATA = "stored_spread_data"


def get_class_for_data_type(data_type: str):
    return use_sim_classes[data_type]


use_sim_classes = {
    FX_DATA: parquetFxPricesData,
    ROLL_PARAMETERS_DATA: csvRollParametersData,
    FUTURES_INSTRUMENT_DATA: csvFuturesInstrumentData,
    FUTURES_MULTIPLE_PRICE_DATA: parquetFuturesMultiplePricesData,
    FUTURES_ADJUSTED_PRICE_DATA: parquetFuturesAdjustedPricesData,
    STORED_SPREAD_DATA: mongoSpreadCostData,
}


if __name__ == "__main__":
    import doctest

    doctest.testmod()
