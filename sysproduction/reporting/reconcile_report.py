"""
Monitor health of system by seeing when things last run

We can also check: when last adjusted prices were updated, when FX was last updated, when optimal position was
   last updated
"""

from syscore.constants import arg_not_supplied

from sysdata.data_blob import dataBlob

from sysproduction.reporting.api import reportingApi


def reconcile_report(data=arg_not_supplied):
    """
    Report on system status

    :param: data blob
    :return: list of formatted output items
    """
    if data is arg_not_supplied:
        data = dataBlob()

    reporting_api = reportingApi(data)
    formatted_output = []
    formatted_output.append(reporting_api.terse_header("Reconcile report"))
    list_of_func_names = [
        "body_text_position_breaks",
        "table_of_my_positions",
        "table_of_ib_positions",
        "table_of_my_recent_trades_from_db",
        "table_of_recent_ib_trades",
        "table_of_optimal_positions",
    ]

    for func_name in list_of_func_names:
        func = getattr(reporting_api, func_name)
        formatted_output.append(func())

    formatted_output.append(reporting_api.footer())

    return formatted_output


if __name__ == "__main__":
    reconcile_report()
