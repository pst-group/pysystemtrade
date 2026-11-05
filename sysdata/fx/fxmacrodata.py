import json
import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from syscore.constants import arg_not_supplied
from sysdata.fx.spotfx import fxPricesData
from syslogging.logger import *
from sysobjects.spot_fx_prices import DEFAULT_CURRENCY, fxPrices, get_fx_tuple_from_code


FXMACRODATA_API_BASE_URL = "https://api.fxmacrodata.com/v1"
FXMACRODATA_API_KEY_ENV_VARS = ("FXMACRODATA_API_KEY", "FXMD_API_KEY")
FXMACRODATA_DEFAULT_FX_CODES = [
    "%s%s" % (currency, DEFAULT_CURRENCY)
    for currency in (
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNH",
        "CNY",
        "DKK",
        "EUR",
        "GBP",
        "IDR",
        "ILS",
        "JPY",
        "NGN",
        "NOK",
        "NZD",
        "PEN",
        "SEK",
        "THB",
    )
]


class fxMacroDataFxPricesData(fxPricesData):
    """
    FX spot price source backed by FXMacroData.

    FXMacroData can return arbitrary currency pairs, but pysystemtrade stores
    spot FX rates against the default currency. The default code list therefore
    uses XXXUSD pairs and inherits the standard inversion and cross-rate logic
    from fxPricesData.
    """

    def __init__(
        self,
        fx_codes=arg_not_supplied,
        api_key=None,
        base_url=FXMACRODATA_API_BASE_URL,
        start_date=None,
        end_date=None,
        timeout=30,
        log=get_logger("fxMacroDataFxPricesData"),
    ):
        super().__init__(log=log)

        if fx_codes is arg_not_supplied:
            fx_codes = FXMACRODATA_DEFAULT_FX_CODES

        self._fx_codes = [str(code).upper() for code in fx_codes]
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._start_date = start_date
        self._end_date = end_date
        self._timeout = timeout

    def __repr__(self):
        return "FXMacroData FX price data"

    def get_list_of_fxcodes(self) -> list:
        return list(self._fx_codes)

    def _get_fx_prices_without_checking(self, code: str) -> fxPrices:
        currency1, currency2 = get_fx_tuple_from_code(code)
        log_attrs = {CURRENCY_CODE_LOG_LABEL: code, "method": "temp"}

        try:
            payload = self._download_fxmacrodata_payload(currency1, currency2)
        except Exception as exc:
            self.log.warning(
                "Can't get FXMacroData prices for %s: %s" % (code, str(exc)),
                **log_attrs,
            )
            return fxPrices.create_empty()

        raw_prices = self._series_from_payload(payload, code)
        if len(raw_prices) == 0:
            self.log.warning(
                "No available FXMacroData prices for %s" % code,
                **log_attrs,
            )
            return fxPrices.create_empty()

        prices = fxPrices(raw_prices)
        self.log.debug("Downloaded %d prices" % len(prices), **log_attrs)
        return prices

    def _download_fxmacrodata_payload(self, currency1: str, currency2: str) -> dict:
        query = self._query_params()
        url = "%s/forex/%s/%s" % (
            self._base_url,
            currency1.lower(),
            currency2.lower(),
        )
        if query:
            url = "%s?%s" % (url, urlencode(query))

        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise ValueError(_read_http_error(error)) from error

    def _query_params(self) -> dict:
        query = {}
        if self._start_date is not None:
            query["start_date"] = _format_date(self._start_date)
        if self._end_date is not None:
            query["end_date"] = _format_date(self._end_date)

        api_key = self._api_key or _api_key_from_environment()
        if api_key:
            query["api_key"] = api_key

        return query

    def _series_from_payload(self, payload: dict, code: str) -> pd.Series:
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError("FXMacroData response did not include a data list")

        records = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            date_value = row.get("date")
            price_value = row.get("val")
            if date_value is None or price_value is None:
                continue
            records.append((pd.Timestamp(date_value), price_value))

        if len(records) == 0:
            return pd.Series(dtype=float)

        series = pd.Series(
            data=[price for _, price in records],
            index=pd.DatetimeIndex([date for date, _ in records]),
            name=code,
        )

        return pd.to_numeric(series, errors="coerce").dropna().sort_index()

    def update_fx_prices(self, *args, **kwargs):
        raise NotImplementedError("FXMacroData is a read only source of prices")

    def add_fx_prices(self, *args, **kwargs):
        raise NotImplementedError("FXMacroData is a read only source of prices")

    def _delete_fx_prices_without_any_warning_be_careful(self, *args, **kwargs):
        raise NotImplementedError("FXMacroData is a read only source of prices")

    def _add_fx_prices_without_checking_for_existing_entry(self, *args, **kwargs):
        raise NotImplementedError("FXMacroData is a read only source of prices")


def _format_date(value) -> str:
    return pd.Timestamp(value).date().isoformat()


def _api_key_from_environment():
    for env_var in FXMACRODATA_API_KEY_ENV_VARS:
        api_key = os.getenv(env_var)
        if api_key:
            return api_key
    return None


def _read_http_error(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8").strip()
    except Exception:
        body = ""

    message = "HTTP %s" % error.code
    if body:
        message = "%s: %s" % (message, body)
    return message
