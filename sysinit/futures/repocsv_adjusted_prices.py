"""
Copy from csv repo files to arctic for adjusted prices
"""

from syscore.constants import arg_not_supplied

from sysproduction.data.prices import diagPrices

from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData

if __name__ == "__main__":
    diag_prices = diagPrices()

    input("Will overwrite existing prices are you sure?! CTL-C to abort")
    db_adjusted_prices = diag_prices.db_futures_adjusted_prices_data

    ## MODIFY PATH TO USE SOMETHING OTHER THAN DEFAULT
    csv_adj_datapath = arg_not_supplied
    csv_adjusted_prices = csvFuturesAdjustedPricesData(csv_adj_datapath)

    instrument_code = input("Instrument code? <return for ALL instruments> ")
    if instrument_code == "":
        instrument_list = csv_adjusted_prices.get_list_of_instruments()
    else:
        instrument_list = [instrument_code]

    for instrument_code in instrument_list:
        print(instrument_code)

        adjusted_prices = csv_adjusted_prices.get_adjusted_prices(instrument_code)

        print(adjusted_prices)

        db_adjusted_prices.add_adjusted_prices(
            instrument_code, adjusted_prices, ignore_duplication=True
        )
