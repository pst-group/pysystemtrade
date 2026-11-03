import datetime

import pandas as pd
from dateutil.tz import tz

from sysbrokers.IB.client.ib_price_client import ibPriceClient

# the conversion uses no connection state, so skip __init__
client = ibPriceClient.__new__(ibPriceClient)


def _local(stamp: str) -> pd.Timestamp:
    return pd.Timestamp(stamp).tz_localize(tz.tzlocal())


def test_hourly_bar_at_local_midnight_keeps_its_time():
    converted = client._ib_timestamp_to_datetime(_local("2026-10-16 00:00"))
    assert converted == pd.Timestamp("2026-10-16 00:00")


def test_other_hourly_bars_keep_their_time():
    for stamp in ["2026-10-16 01:00", "2026-10-16 23:00"]:
        assert client._ib_timestamp_to_datetime(_local(stamp)) == pd.Timestamp(stamp)


def test_daily_bar_gets_notional_closing_time():
    converted = client._ib_timestamp_to_datetime(datetime.date(2026, 10, 16))
    assert converted == pd.Timestamp("2026-10-16 23:00")
