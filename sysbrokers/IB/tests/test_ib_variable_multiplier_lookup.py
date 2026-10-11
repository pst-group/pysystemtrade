"""A blank IBMultiplier in ib_config_futures.csv marks a product whose IB
multiplier varies by delivery month: GAS_NL (TTF, the hours in the month:
720/743/744/745/672/696) and GAS_UK (NBP, 1000 therms x the days in the month:
30000/31000 as listed by IB; February by the same rule). A single pinned value makes IB reject every month
with a different multiplier ("No security definition has been found").

Three things must hold for such a row, and each is pinned here:

- the lookup pattern sent to reqContractDetails carries no multiplier, so IB
  matches the month on symbol, exchange and currency alone;
- the reverse lookup from a broker contract (a fill or position, which carries
  the month's real multiplier) still finds the instrument;
- logging the config does not crash on the missing value.
"""

import pandas as pd
import pytest

from sysbrokers.IB.config.ib_instrument_config import (
    IBconfig,
    IBInstrumentIdentity,
    _get_instrument_object_from_valid_config,
    get_instrument_code_from_broker_instrument_identity,
    read_ib_config_from_file,
)
from sysbrokers.IB.ib_instruments import NOT_REQUIRED_FOR_IB, ib_futures_instrument


def _config() -> IBconfig:
    return IBconfig(
        pd.DataFrame(
            [
                ["GAS_NL", "TFM", "ENDEX", "EUR", float("nan"), 1, False],
                ["GAS_UK", "NGF", "IPE", "GBP", float("nan"), 1, False],
                ["SP500_micro", "MES", "CME", "USD", 5.0, 1, False],
            ],
            columns=[
                "Instrument",
                "IBSymbol",
                "IBExchange",
                "IBCurrency",
                "IBMultiplier",
                "priceMagnifier",
                "IgnoreWeekly",
            ],
        )
    )


def _identity(code, multiplier, exchange="ENDEX"):
    return IBInstrumentIdentity(
        ib_code=code,
        ib_multiplier=multiplier,
        ib_exchange=exchange,
        ib_valid_exchange=exchange,
    )


def test_blank_multiplier_is_left_off_the_lookup_pattern():
    instrument = _get_instrument_object_from_valid_config("GAS_NL", _config())
    assert instrument.ib_data.ibMultiplier is NOT_REQUIRED_FOR_IB

    pattern = ib_futures_instrument(instrument)

    assert pattern.symbol == "TFM"
    assert pattern.exchange == "ENDEX"
    assert pattern.currency == "EUR"
    assert pattern.multiplier == ""


@pytest.mark.parametrize("instrument_code", ["GAS_NL", "GAS_UK"])
def test_shipped_config_sends_no_multiplier_for_variable_products(instrument_code):
    instrument = _get_instrument_object_from_valid_config(
        instrument_code, read_ib_config_from_file()
    )
    assert ib_futures_instrument(instrument).multiplier == ""


def test_numeric_multiplier_is_still_sent():
    instrument = _get_instrument_object_from_valid_config("SP500_micro", _config())
    assert ib_futures_instrument(instrument).multiplier == "5"


@pytest.mark.parametrize("hours", [720.0, 743.0, 744.0, 745.0, 672.0, 696.0])
def test_reverse_lookup_matches_any_month_for_a_blank_row(hours):
    code = get_instrument_code_from_broker_instrument_identity(
        _config(), _identity("TFM", hours)
    )
    assert code == "GAS_NL"


@pytest.mark.parametrize("therms", [28000.0, 29000.0, 30000.0, 31000.0])
def test_reverse_lookup_matches_any_month_for_uk_gas(therms):
    code = get_instrument_code_from_broker_instrument_identity(
        _config(), _identity("NGF", therms, exchange="IPE")
    )
    assert code == "GAS_UK"


def test_reverse_lookup_still_requires_the_multiplier_for_a_numeric_row():
    with pytest.raises(Exception, match="not found in configuration file"):
        get_instrument_code_from_broker_instrument_identity(
            _config(), _identity("MES", 50.0, exchange="CME")
        )


def test_config_with_blank_multiplier_can_be_logged():
    ib_data = _get_instrument_object_from_valid_config("GAS_NL", _config()).ib_data

    assert ib_data.effective_multiplier is NOT_REQUIRED_FOR_IB
    assert "effective_multiplier=''" in repr(ib_data)
    assert ib_data.as_dict()["effective_multiplier"] == NOT_REQUIRED_FOR_IB


def test_numeric_effective_multiplier_format_is_unchanged():
    ib_data = _get_instrument_object_from_valid_config("SP500_micro", _config()).ib_data
    assert "effective_multiplier='5.00'" in repr(ib_data)


def test_blank_row_next_to_a_numeric_row_fails_closed():
    config = _config()
    config.loc[len(config)] = ["GAS_NL_720", "TFM", "ENDEX", "EUR", 720.0, 1, False]

    with pytest.raises(Exception, match="appears more than once"):
        get_instrument_code_from_broker_instrument_identity(
            config, _identity("TFM", 720.0)
        )
