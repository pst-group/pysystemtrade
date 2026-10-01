import json

import pandas as pd

from sysdata.fx import fxmacrodata
from sysdata.fx.fxmacrodata import fxMacroDataFxPricesData


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload.encode("utf-8")


def test_fxmacrodata_downloads_prices(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["accept"] = request.headers["Accept"]
        captured["timeout"] = timeout
        return FakeResponse(
            json.dumps(
                {
                    "data": [
                        {"date": "2024-01-03", "val": 1.0920},
                        {"date": "2024-01-01", "val": "1.1038"},
                    ]
                }
            )
        )

    monkeypatch.setattr(fxmacrodata, "urlopen", fake_urlopen)

    data = fxMacroDataFxPricesData(
        fx_codes=["EURUSD"],
        api_key="test-key",
        start_date="2024-01-01",
        end_date="2024-01-31",
        timeout=12,
    )
    actual = data.get_fx_prices("EURUSD")

    expected = pd.Series(
        [1.1038, 1.092],
        index=pd.to_datetime(["2024-01-01", "2024-01-03"]),
    )
    pd.testing.assert_series_equal(
        actual, expected, check_names=False, check_series_type=False
    )
    assert captured == {
        "url": "https://api.fxmacrodata.com/v1/forex/eur/usd?start_date=2024-01-01&end_date=2024-01-31&api_key=test-key",
        "accept": "application/json",
        "timeout": 12,
    }


def test_fxmacrodata_uses_environment_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse(json.dumps({"data": [{"date": "2024-01-01", "val": 1.1}]}))

    monkeypatch.setattr(fxmacrodata, "urlopen", fake_urlopen)
    monkeypatch.setenv("FXMACRODATA_API_KEY", "env-key")
    monkeypatch.delenv("FXMD_API_KEY", raising=False)

    data = fxMacroDataFxPricesData(fx_codes=["GBPUSD"])
    data.get_fx_prices("GBPUSD")

    assert captured["url"].endswith("/forex/gbp/usd?api_key=env-key")


def test_fxmacrodata_inherits_usd_inversion(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(json.dumps({"data": [{"date": "2024-01-01", "val": 1.25}]}))

    monkeypatch.setattr(fxmacrodata, "urlopen", fake_urlopen)

    data = fxMacroDataFxPricesData(fx_codes=["EURUSD"])
    actual = data.get_fx_prices("USDEUR")

    expected = pd.Series([0.8], index=pd.to_datetime(["2024-01-01"]))
    pd.testing.assert_series_equal(actual, expected, check_names=False)
