"""
Update spot FX prices using interactive brokers data, dump into mongodb
"""

from syscore.constants import success, failure
from syscore.pandas.merge_data_keeping_past_data import SPIKE_IN_DATA
from sysdata.data_blob import dataBlob
from sysproduction.data.currency_data import dataCurrency
from sysproduction.data.broker import dataBroker
from syslogdiag.email_via_db_interface import send_production_mail_msg


def update_fx_prices():
    """
    Update FX prices stored in Arctic (Mongo) with interactive brokers prices (usually going back about a year)

    :return: Nothing
    """

    ## Called as standalone
    with dataBlob(log_name="Update-FX-Prices") as data:
        update_fx_prices_object = updateFxPrices(data)
        update_fx_prices_object.update_fx_prices()

    return success


class updateFxPrices(object):
    ## Called by run_daily_price_updates
    def __init__(self, data: dataBlob):
        self.data = data

    def update_fx_prices(self):
        data = self.data
        update_fx_prices_with_data(data)


def update_fx_prices_with_data(data: dataBlob):
    broker_fx_source = dataBroker(data)
    list_of_codes_all = (
        broker_fx_source.get_list_of_fxcodes()
    )  # codes must be in .csv file /sysbrokers/IB/ibConfigSpotFx.csv
    data.log.debug("FX Codes: %s" % str(list_of_codes_all))

    for fx_code in list_of_codes_all:
        data.log.debug(
            "Updating log attributes",
            method="clear",
            currency_code=fx_code,
        )
        update_fx_prices_for_code(fx_code, data)


def update_fx_prices_for_code(fx_code: str, data: dataBlob):
    broker_fx_data = dataBroker(data)
    db_fx_data = dataCurrency(data)

    new_fx_prices = broker_fx_data.get_fx_prices(fx_code)  # returns fxPrices object
    rows_added = db_fx_data.update_fx_prices_and_return_rows_added(
        fx_code, new_fx_prices, check_for_spike=True
    )

    if rows_added is SPIKE_IN_DATA:
        report_fx_data_spike(data, fx_code)
        return failure

    return success


def report_fx_data_spike(data: dataBlob, fx_code: str):
    msg = (
        "Spike found in prices for %s: need to manually check by running interactive_manual_check_fx_prices"
        % str(fx_code)
    )
    data.log.warning(msg)
    try:
        send_production_mail_msg(data, msg, "FX Price Spike %s" % str(fx_code))
    except BaseException:
        data.log.warning("Couldn't send email about price spike")


if __name__ == "__main__":
    update_fx_prices()
