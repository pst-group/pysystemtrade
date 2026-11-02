"""
Get FX prices from arctic and write to csv

WARNING WILL OVERWRITE EXISTING!
"""

from sysproduction.data.currency_data import fxPricesData
from sysdata.csv.csv_spot_fx import csvFxPricesData


db_fx_prices_data = fxPricesData()

if __name__ == "__main__":
    input("Will overwrite existing data are you sure?! CTL-C to abort")
    csv_fx_prices = csvFxPricesData()

    list_of_ccy_codes = csv_fx_prices.get_list_of_fxcodes()

    for currency_code in list_of_ccy_codes:
        fx_prices = db_fx_prices_data.get_fx_prices(currency_code)
        print(fx_prices)

        csv_fx_prices.add_fx_prices(currency_code, fx_prices, ignore_duplication=True)
