from typing import List, Dict

import pandas as pd
from sysobjects.spot_fx_prices import currencyValue
from sysproduction.data.instruments import diagInstruments
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysobjects.contracts import futuresContract
from sysdata.data_blob import dataBlob
from sysdata.config.instruments import get_list_of_untradeable_instruments_in_config

error_getting_costs = currencyValue(currency="Error", value=0)
missing_contract = "price not collected"
prices_not_collected = currencyValue(currency="No prices", value=0)
percentage_commissions = currencyValue(currency="% commission ignore", value=0)


def filter_tradeable_instruments_for_commission_report(
    data: dataBlob, instrument_list: List[str]
) -> List[str]:
    """
    Filter out trading-restricted and stale instruments from commission reporting.
    Trading-restricted instruments can't be traded so commission accuracy is not
    relevant. Stale instruments no longer exist so commission data retrieval will fail.

    This fixes erroneous "Currency doesn't match" and "One or both missing" errors
    that occurred when the system tried to get broker commission data for instruments
    with trading restrictions, regulatory blocks, or permission issues.
    """
    trading_restricted = get_list_of_untradeable_instruments_in_config(data.config)
    stale_instruments = data.config.get_element_or_default("stale_instruments", [])

    exclude_list = list(set(trading_restricted + stale_instruments))
    tradeable_instruments = [
        instrument for instrument in instrument_list if instrument not in exclude_list
    ]

    if exclude_list:
        restricted_count = len([i for i in instrument_list if i in trading_restricted])
        stale_count = len([i for i in instrument_list if i in stale_instruments])
        data.log.debug(
            "Commission report: Analyzing %d tradeable instruments "
            "(%d trading-restricted, %d stale instruments skipped)"
            % (len(tradeable_instruments), restricted_count, stale_count)
        )

    return tradeable_instruments


def df_of_configure_and_broker_block_cost_sorted_by_index(
    data: dataBlob,
) -> pd.DataFrame:
    both = df_of_configure_and_broker_block_cost_sorted_by_diff(data)
    both = both.sort_index()

    return both


def df_of_configure_and_broker_block_cost_sorted_by_diff(
    data: dataBlob,
) -> pd.DataFrame:
    list_of_instrument_codes = get_instrument_list(data)

    list_of_instrument_codes = filter_tradeable_instruments_for_commission_report(
        data, list_of_instrument_codes
    )

    configured_costs = get_current_configured_block_costs(
        data=data, list_of_instrument_codes=list_of_instrument_codes
    )
    broker_costs = get_broker_block_costs(
        data=data, list_of_instrument_codes=list_of_instrument_codes
    )

    valid_costs = {}
    missing_values = {}
    for instrument_code in list_of_instrument_codes:
        update_valid_and_missing_costs_for_instrument_code(
            instrument_code=instrument_code,
            missing_values=missing_values,
            valid_costs=valid_costs,
            broker_costs=broker_costs,
            configured_costs=configured_costs,
        )

    valid_costs_df = create_df_in_commission_report(valid_costs)
    missing_values_df = create_df_in_commission_report(missing_values)

    both = pd.concat([valid_costs_df, missing_values_df], axis=0)

    return both


def update_valid_and_missing_costs_for_instrument_code(
    instrument_code: str,
    configured_costs: Dict[str, currencyValue],
    broker_costs: dict[str, currencyValue],
    valid_costs: dict,
    missing_values: dict,
):
    configured_cost = configured_costs.get(instrument_code, error_getting_costs)
    broker_cost = broker_costs.get(instrument_code, error_getting_costs)

    if broker_cost is prices_not_collected or configured_cost is percentage_commissions:
        ## skip
        return

    if configured_cost is error_getting_costs or broker_cost is error_getting_costs:
        update_missing_values_with_currencies_and_errors(
            instrument_code=instrument_code,
            missing_values=missing_values,
            configured_cost=configured_cost,
            broker_cost=broker_cost,
            error_str="One or both missing",
        )
        return

    currency_mismatch = not configured_cost.currency == broker_cost.currency
    if currency_mismatch:
        update_missing_values_with_currencies_and_errors(
            instrument_code=instrument_code,
            missing_values=missing_values,
            configured_cost=configured_cost,
            broker_cost=broker_cost,
            error_str="Currency doesn't match",
        )
        return

    update_valid_costs(
        valid_costs=valid_costs,
        instrument_code=instrument_code,
        configured_cost=configured_cost,
        broker_cost=broker_cost,
    )


def update_missing_values_with_currencies_and_errors(
    missing_values: dict,
    configured_cost: currencyValue,
    broker_cost: currencyValue,
    instrument_code: str,
    error_str: str,
):
    missing_values[instrument_code] = [
        configured_cost.currency,
        broker_cost.currency,
        error_str,
    ]


def update_valid_costs(
    valid_costs: dict,
    configured_cost: currencyValue,
    broker_cost: currencyValue,
    instrument_code: str,
):
    configured_cost_instrument = configured_cost.value
    broker_cost_instrument = broker_cost.value
    diff = broker_cost_instrument - configured_cost_instrument
    valid_costs[instrument_code] = [
        configured_cost_instrument,
        broker_cost_instrument,
        diff,
    ]


def create_df_in_commission_report(some_dict: dict):
    if not some_dict:
        return pd.DataFrame(columns=[CONFIGURED_COLUMN, BROKER_COLUMN, DIFF_COLUMN])

    some_df = pd.DataFrame(some_dict)
    some_df = some_df.transpose()
    some_df.columns = [CONFIGURED_COLUMN, BROKER_COLUMN, DIFF_COLUMN]
    some_df = some_df.sort_values(DIFF_COLUMN, ascending=False)

    return some_df


CONFIGURED_COLUMN = "configured"
BROKER_COLUMN = "broker"
DIFF_COLUMN = "diff"


def get_instrument_list(data: dataBlob) -> list:
    db = dataBroker(data)
    list_of_instruments = db.broker_futures_contract_price_data.get_list_of_instrument_codes_with_merged_price_data()

    return list_of_instruments


def get_current_configured_block_costs(
    data: dataBlob, list_of_instrument_codes: List[str]
) -> Dict[str, currencyValue]:
    block_costs_from_config = {}
    for instrument_code in list_of_instrument_codes:
        block_costs_from_config[instrument_code] = (
            get_configured_block_cost_for_instrument(
                data=data, instrument_code=instrument_code
            )
        )

    return block_costs_from_config


def get_configured_block_cost_for_instrument(
    data: dataBlob, instrument_code: str
) -> currencyValue:
    diag_instruments = diagInstruments(data)
    if diag_instruments.has_percentage_commission(instrument_code):
        return percentage_commissions
    try:
        costs = diag_instruments.get_block_commission_for_instrument_as_currency_value(
            instrument_code
        )
    except:
        costs = error_getting_costs

    return costs


def get_broker_block_costs(
    data: dataBlob, list_of_instrument_codes: List[str]
) -> Dict[str, currencyValue]:
    priced_contracts = get_series_of_priced_contracts(
        data=data, list_of_instrument_codes=list_of_instrument_codes
    )
    block_costs_from_broker = get_costs_given_priced_contracts(
        data=data, priced_contracts=priced_contracts
    )
    return block_costs_from_broker


def get_series_of_priced_contracts(
    data: dataBlob, list_of_instrument_codes: List[str]
) -> pd.Series:
    dc = dataContracts(data)
    list_of_priced_contracts = {}
    for instrument_code in list_of_instrument_codes:
        try:
            contract_id = dc.get_priced_contract_id(instrument_code)
            contract = futuresContract(instrument_code, contract_id)
        except:
            contract = missing_contract

        list_of_priced_contracts[instrument_code] = contract

    return pd.Series(list_of_priced_contracts)


def get_costs_given_priced_contracts(
    data: dataBlob, priced_contracts: pd.Series
) -> Dict[str, currencyValue]:
    block_costs_from_broker = {}
    for instrument_code, contract in priced_contracts.items():
        block_costs_from_broker[instrument_code] = get_block_cost_for_single_contract(
            data=data, contract=contract
        )

    return block_costs_from_broker


def get_block_cost_for_single_contract(data: dataBlob, contract: futuresContract):
    db = dataBroker(data)
    if contract is missing_contract:
        return prices_not_collected
    try:
        return db.get_commission_for_contract_in_currency_value(contract)
    except:
        return error_getting_costs
