import datetime

from sysdata.data_blob import dataBlob

from syscore.constants import arg_not_supplied
from sysproduction.reporting.reporting_functions import body_text
from sysproduction.reporting.api import reportingApi

REPORT_TEXT = body_text(
    "Commissions report, columns are commissions from configuration, broker, and ratio:\n"
)


def commissions_report(
    data: dataBlob = arg_not_supplied,
):
    if data is arg_not_supplied:
        data = dataBlob()

    reporting_api = reportingApi(
        data,
        start_date=datetime.datetime.now(),  ## not required for this report
    )

    formatted_output = []

    formatted_output.append(reporting_api.std_header("Commission report"))
    formatted_output.append(REPORT_TEXT)
    formatted_output.append(reporting_api.table_of_commissions())
    formatted_output.append(reporting_api.footer())

    return formatted_output


if __name__ == "__main__":
    commissions_report()
