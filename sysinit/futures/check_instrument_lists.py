"""
This little utility allows you to keep up with your various sets of instruments, basically designed for those that add a
big load of instruments in one go as is my wont

"""

import pandas as pd
from syscore.interactive.progress_bar import progressBar
from sysproduction.data.prices import diagPrices
from sysproduction.data.instruments import diagInstruments
from systems.provided.rob_system.run_system import (
    futures_system,
)  ## replace with your own

diag_prices = diagPrices()

all_instruments_with_prices = diag_prices.get_list_of_instruments_with_contract_prices()
all_instruments_with_prices.sort()

## check for high correlations, likely to be repeats


def check_for_high_correlations():
    checked = []
    all_dups = []
    returns = dict()
    p = progressBar((len(all_instruments_with_prices) ** 2) / 2)
    for instrument1 in all_instruments_with_prices:
        if instrument1 not in returns.keys():
            returns[instrument1] = weekly_perc_returns_last_year(instrument1)
        for instrument2 in all_instruments_with_prices:
            if instrument1 == instrument2:
                continue
            if (instrument2, instrument1) in checked:
                continue
            checked.append((instrument1, instrument2))
            if instrument2 not in returns.keys():
                returns[instrument2] = weekly_perc_returns_last_year(instrument2)

            ret1 = returns[instrument1]
            ret2 = returns[instrument2]
            both = pd.concat([ret1, ret2], axis=1)
            both.columns = ["1", "2"]
            both = both.dropna()
            corr = both.corr()["1"]["2"]
            if corr > 0.9:
                all_dups.append(
                    "Possible duplicates %s %s corr %.3f"
                    % (instrument1, instrument2, corr)
                )
                print(all_dups)

            p.iterate()

    return all_dups


def weekly_perc_returns_last_year(instrument_code):
    weekly_prices = (
        diag_prices.get_adjusted_prices(instrument_code).resample("1W").ffill()
    )
    weekly_prices_last_year = weekly_prices[-52:]
    return (weekly_prices_last_year / weekly_prices_last_year.shift(1)) - 1


def check_for_zero_commission():
    diag_instruments = diagInstruments()
    zero_warnings = []

    for instrument_code in all_instruments_with_prices:
        commission = diag_instruments.get_cost_object(
            instrument_code
        ).value_of_block_commission
        if commission == 0:
            zero_warnings.append(instrument_code)

    return zero_warnings


def print_missing_and_no_trade_markets():
    system = futures_system()
    all_instruments = system.data.get_instrument_list()
    duplicates = system.get_list_of_duplicate_instruments_to_remove()
    ignored = system.get_list_of_ignored_instruments_to_remove()
    all_instruments_without_duplicates = [
        instrument_code
        for instrument_code in all_instruments
        if instrument_code not in duplicates and instrument_code not in ignored
    ]

    configured_in_system = list(
        system.config.instrument_weights.keys()
    )  ## not all will be traded

    missing = [
        instrument_code
        for instrument_code in all_instruments_without_duplicates
        if instrument_code not in configured_in_system
    ]
    missing.sort()

    print("Missing: %s" % missing)
    print("No trade: %s" % system.get_list_of_markets_with_trading_restrictions())
