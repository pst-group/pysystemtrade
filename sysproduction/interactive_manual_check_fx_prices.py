"""
Update spot FX prices using interactive brokers data, dump into mongodb

Allow manual checking resolution of spikes

"""

from syscore.constants import success

from sysdata.tools.manual_price_checker import manual_price_checker
from sysobjects.spot_fx_prices import fxPrices

from sysdata.data_blob import dataBlob
from sysproduction.data.currency_data import dataCurrency, get_valid_fx_code_from_user
from sysproduction.data.broker import dataBroker


def interactive_manual_check_fx_prices():
    """
    Update FX prices stored in Arctic (Mongo) with interactive brokers prices (usually going back about a year)

    :return: Nothing
    """

    with dataBlob(log_name="Interactive-Manual-Check-FX-prices") as data:
        do_another = True
        while do_another:
            EXIT_STR = "Finished - EXIT"
            fx_code = get_valid_fx_code_from_user(
                data, allow_none=True, none_str=EXIT_STR
            )
            if fx_code is EXIT_STR:
                do_another = False  ## belt. Also braces.
            else:
                data.log.debug(
                    "Updating log attributes",
                    method="clear",
                    currency_code=fx_code,
                )
                check_fx_ok_for_broker(data, fx_code)
                update_manual_check_fx_prices_for_code(fx_code, data)

    return success


def check_fx_ok_for_broker(data: dataBlob, fx_code: str):
    data_broker = dataBroker(data)
    list_of_codes_all = (
        data_broker.get_list_of_fxcodes()
    )  # codes must be in .csv file /sysbrokers/IB/ibConfigSpotFx.csv

    if fx_code not in list_of_codes_all:
        print(
            "\n\n%s is not an FX code (valid codes: %s) \n\n"
            % (fx_code, list_of_codes_all)
        )
        raise Exception()


def update_manual_check_fx_prices_for_code(fx_code: str, data: dataBlob):
    db_currency_data = dataCurrency(data)
    data_broker = dataBroker(data)

    new_fx_prices = data_broker.get_fx_prices(fx_code)  # returns fxPrices object
    if len(new_fx_prices) == 0:
        data.log.warning("No FX prices found for %s" % fx_code)

    old_fx_prices = db_currency_data.get_fx_prices(fx_code)

    # Will break manual price checking code if not equal
    old_fx_prices.name = new_fx_prices.name = ""

    print("\n\nManually checking prices for %s\n\n" % fx_code)
    new_prices_checked = manual_price_checker(
        old_fx_prices, new_fx_prices, type_new_data=fxPrices.from_data_frame
    )

    db_currency_data.update_fx_prices_and_return_rows_added(
        fx_code, new_prices_checked, check_for_spike=False
    )

    return success


if __name__ == "__main__":
    interactive_manual_check_fx_prices()
