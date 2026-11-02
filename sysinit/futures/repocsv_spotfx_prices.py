"""
Get FX prices from csv repo files and write to arctic

WARNING WILL OVERWRITE EXISTING!
"""

from sysdata.csv.csv_spot_fx import csvFxPricesData
from sysproduction.data.currency_data import dataCurrency


if __name__ == "__main__":
    input("Will overwrite existing prices are you sure?! CTL-C to abort")
    dataCurrency = dataCurrency()

    csv_fx_prices = csvFxPricesData()
    db_fx_price_data = dataCurrency.db_fx_prices_data

    currency_code = input("Currency code? <return for ALL currencies> ")
    if currency_code == "":
        list_of_ccy_codes = csv_fx_prices.get_list_of_fxcodes()
    else:
        list_of_ccy_codes = [currency_code]

    for currency_code in list_of_ccy_codes:
        fx_prices = csv_fx_prices.get_fx_prices(currency_code)
        print(fx_prices)

        db_fx_price_data.add_fx_prices(
            code=currency_code, fx_price_data=fx_prices, ignore_duplication=True
        )
