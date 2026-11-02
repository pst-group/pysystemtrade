from copy import copy

import numpy as np
import pandas as pd

from syscore.constants import success, failure
from sysdata.data_blob import dataBlob
from sysobjects.adjusted_prices import futuresAdjustedPrices
from sysobjects.contracts import futuresContract
from sysobjects.dict_of_named_futures_per_contract_prices import (
    price_column_names,
    forward_name,
    carry_name,
    price_name,
    contract_column_names,
)
from sysobjects.instruments import futuresInstrument
from sysobjects.multiple_prices import futuresMultiplePrices, singleRowMultiplePrices

from sysproduction.data.contracts import dataContracts
from sysproduction.data.positions import diagPositions
from sysproduction.data.prices import diagPrices, updatePrices
from sysproduction.data.volumes import diagVolumes


def get_roll_data_for_instrument(instrument_code, data):
    """
    Get roll data for an individual instrument

    :param instrument_code: str
    :param data: dataBlob
    :return:
    """
    c_data = dataContracts(data)
    contract_priced = c_data.get_priced_contract_id(instrument_code)
    contract_fwd = c_data.get_forward_contract_id(instrument_code)

    relative_volumes = relative_volume_in_forward_contract_and_price(
        data, instrument_code
    )
    relative_volume_fwd = relative_volumes[1]

    contract_volume_fwd = volume_contracts_in_forward_contract(data, instrument_code)

    # length to expiries / length to suggested roll

    price_expiry_days = c_data.days_until_price_expiry(instrument_code)
    carry_expiry_days = c_data.days_until_carry_expiry(instrument_code)
    when_to_roll_days = c_data.days_until_roll(instrument_code)

    # roll status
    diag_positions = diagPositions(data)
    roll_status = diag_positions.get_name_of_roll_state(instrument_code)

    # Positions
    position_priced = diag_positions.get_position_for_contract(
        futuresContract(instrument_code, contract_priced)
    )

    results_dict_code = dict(
        status=roll_status,
        roll_expiry=when_to_roll_days,
        price_expiry=price_expiry_days,
        carry_expiry=carry_expiry_days,
        contract_priced=contract_priced,
        contract_fwd=contract_fwd,
        position_priced=position_priced,
        relative_volume_fwd=relative_volume_fwd,
        contract_volume_fwd=contract_volume_fwd,
    )

    return results_dict_code


def relative_volume_in_forward_contract_versus_price(
    data: dataBlob, instrument_code: str
) -> float:
    volumes = relative_volume_in_forward_contract_and_price(data, instrument_code)
    required_volume = volumes[1]
    if np.isnan(required_volume):
        required_volume = 0

    return required_volume


def relative_volume_in_forward_contract_and_price(
    data: dataBlob, instrument_code: str
) -> list:
    c_data = dataContracts(data)
    forward_contract_id = c_data.get_forward_contract_id(instrument_code)
    current_contract = c_data.get_priced_contract_id(instrument_code)
    v_data = diagVolumes(data)
    ## normalises so first contract as volume of 1
    volumes = v_data.get_normalised_smoothed_volumes_of_contract_list(
        instrument_code, [current_contract, forward_contract_id]
    )

    return volumes


def volume_contracts_in_forward_contract(data: dataBlob, instrument_code: str) -> float:
    c_data = dataContracts(data)
    forward_contract_id = c_data.get_forward_contract_id(instrument_code)
    v_data = diagVolumes(data)
    volume = v_data.get_smoothed_volume_for_contract(
        instrument_code, forward_contract_id
    )

    if np.isnan(volume):
        volume = 0

    return volume


class rollingAdjustedAndMultiplePrices(object):
    def __init__(
        self, data: dataBlob, instrument_code: str, allow_forward_fill: bool = False
    ):
        self.data = data
        self.instrument_code = instrument_code
        self.allow_forward_fill = allow_forward_fill

    def compare_old_and_new_prices(self):
        # We want user input before we do anything
        compare_old_and_new_prices(
            [
                self.current_multiple_prices,
                self.updated_multiple_prices,
                self.current_adjusted_prices,
                self.new_adjusted_prices,
            ],
            [
                "Current multiple prices",
                "New multiple prices",
                "Current adjusted prices",
                "New adjusted prices",
            ],
        )
        print("")

    @property
    def current_multiple_prices(self):
        current_multiple_prices = getattr(self, "_current_multiple_prices", None)
        if current_multiple_prices is None:
            diag_prices = diagPrices(self.data)
            current_multiple_prices = self._current_multiple_prices = (
                diag_prices.get_multiple_prices(self.instrument_code)
            )

        return current_multiple_prices

    @property
    def current_adjusted_prices(self):
        current_adjusted_prices = getattr(self, "_current_adjusted_prices", None)
        if current_adjusted_prices is None:
            diag_prices = diagPrices(self.data)
            current_adjusted_prices = self._current_adjusted_prices = (
                diag_prices.get_adjusted_prices(self.instrument_code)
            )

        return current_adjusted_prices

    @property
    def updated_multiple_prices(self):
        updated_multiple_prices = getattr(self, "_updated_multiple_prices", None)
        if updated_multiple_prices is None:
            updated_multiple_prices = self._updated_multiple_prices = (
                update_multiple_prices_on_roll(
                    self.data,
                    self.current_multiple_prices,
                    self.instrument_code,
                    allow_forward_fill=self.allow_forward_fill,
                )
            )

        return updated_multiple_prices

    @property
    def new_adjusted_prices(self):
        new_adjusted_prices = getattr(self, "_new_adjusted_prices", None)
        if new_adjusted_prices is None:
            new_adjusted_prices = self._new_adjusted_prices = (
                futuresAdjustedPrices.stitch_multiple_prices(
                    self.updated_multiple_prices
                )
            )

        return new_adjusted_prices

    def write_new_rolled_data(self):
        # Apparently good let's try and write rolled data
        price_updater = updatePrices(self.data)
        price_updater.add_multiple_prices(
            self.instrument_code, self.updated_multiple_prices, ignore_duplication=True
        )
        price_updater.add_adjusted_prices(
            self.instrument_code, self.new_adjusted_prices, ignore_duplication=True
        )

    def rollback(self):
        rollback_adjustment(
            self.data,
            self.instrument_code,
            self.current_adjusted_prices,
            self.current_multiple_prices,
        )


def compare_old_and_new_prices(price_list, price_list_names):
    for df_prices, df_name in zip(price_list, price_list_names):
        print(df_name)
        print("")
        print(df_prices.tail(6))
        print("")


def update_multiple_prices_on_roll(
    data: dataBlob,
    current_multiple_prices: futuresMultiplePrices,
    instrument_code: str,
    allow_forward_fill: bool = False,
) -> futuresMultiplePrices:
    """
    Roll multiple prices

    Adds rows to multiple prices

    First row: (optionally) Inferred price and forward prices
    If there is no (old) forward contract price, one needs to be inferred
    If there is no (old) price contract price, one needs to be inferred

    Time index = Last time index + 1 second

    Second row:
    Time index:  Last time index + 1 second

    PRICE = last price of the forward contract
    PRICE_CONTRACT = previous forward contract

    FORWARD_CONTRACT = the new forward contract
    FORWARD_PRICE = the new forward price, this can be Nan; it will get filled in

    CARRY_CONTRACT = the new carry contract
    CARRY_PRICE = the new carry price: if possible infer from price, this can be Nan

    :param data: dataBlob
    :param current_multiple_prices: futuresMultiplePrices
    :return: new futuresMultiplePrices
    """

    new_multiple_prices = futuresMultiplePrices(copy(current_multiple_prices))

    if allow_forward_fill:
        new_multiple_prices = futuresMultiplePrices(new_multiple_prices.ffill())

    # If the last row is all Nans, we can't do this
    new_multiple_prices = new_multiple_prices.sort_index()
    new_multiple_prices = new_multiple_prices.drop_trailing_nan()

    price_column = price_column_names["PRICE"]
    fwd_column = price_column_names["FORWARD"]

    current_contract_dict = new_multiple_prices.current_contract_dict()
    old_forward_contract = current_contract_dict.forward

    old_priced_contract_last_price, price_inferred = get_or_infer_latest_price(
        new_multiple_prices, price_col=price_column
    )

    old_forward_contract_last_price, forward_inferred = get_or_infer_latest_price(
        new_multiple_prices, price_col=fwd_column
    )

    diag_contracts = dataContracts(data)

    instrument_object = futuresInstrument(instrument_code)
    # Old forward contract -> New price contract
    new_price_contract_date_object = (
        diag_contracts.get_contract_date_object_with_roll_parameters(
            instrument_code, old_forward_contract
        )
    )
    new_forward_contract_date = new_price_contract_date_object.next_held_contract()
    new_carry_contract_date = new_price_contract_date_object.carry_contract()

    new_price_contract_object = futuresContract(
        instrument_object, new_price_contract_date_object.contract_date
    )
    new_forward_contract_object = futuresContract(
        instrument_object, new_forward_contract_date.contract_date
    )
    new_carry_contract_object = futuresContract(
        instrument_object, new_carry_contract_date.contract_date
    )

    new_price_price = old_forward_contract_last_price
    new_forward_price = get_final_matched_price_from_contract_object(
        data, new_forward_contract_object, new_multiple_prices
    )
    new_carry_price = get_final_matched_price_from_contract_object(
        data, new_carry_contract_object, new_multiple_prices
    )

    new_price_contractid = new_price_contract_object.date_str
    new_forward_contractid = new_forward_contract_object.date_str
    new_carry_contractid = new_carry_contract_object.date_str

    # If any prices had to be inferred, then add row with both current priced and forward prices
    # Otherwise adjusted prices will break
    if price_inferred or forward_inferred:
        new_single_row = singleRowMultiplePrices(
            price=old_priced_contract_last_price,
            forward=old_forward_contract_last_price,
        )
        new_multiple_prices = new_multiple_prices.add_one_row_with_time_delta(
            new_single_row
        )
    # SOME KIND OF WARNING HERE...?

    # Now we add a row with the new rolled contracts
    newer_single_row = singleRowMultiplePrices(
        price=new_price_price,
        forward=new_forward_price,
        carry=new_carry_price,
        price_contract=new_price_contractid,
        forward_contract=new_forward_contractid,
        carry_contract=new_carry_contractid,
    )
    newer_multiple_prices = new_multiple_prices.add_one_row_with_time_delta(
        newer_single_row
    )

    return newer_multiple_prices


def get_final_matched_price_from_contract_object(
    data, contract_object, new_multiple_prices
):
    diag_prices = diagPrices(data)
    price_series = diag_prices.get_merged_prices_for_contract_object(
        contract_object
    ).return_final_prices()

    price_series_reindexed = price_series.reindex(new_multiple_prices.index)

    final_price = price_series_reindexed.values[-1]

    return final_price


preferred_columns = dict(
    PRICE=[forward_name, carry_name],
    FORWARD=[price_name, carry_name],
    CARRY=[price_name, forward_name],
)


def get_or_infer_latest_price(new_multiple_prices, price_col: str = "PRICE"):
    """
    Get the last price in a given column

    If one can't be found, infer (There will always be a price in some column)

    :param new_multiple_prices: futuresMultiplePrices
    :param price_col: one of 'PRICE','CARRY','FORWARD'
    :return: tuple: float, bool. Bool is true if the price is inferred, otherwise False
    """

    last_price = new_multiple_prices[price_col].values[-1]
    if not np.isnan(last_price):
        ## not inferred
        return last_price, False

    # try and infer from another column
    which_columns_preference = preferred_columns[price_col]

    for col_to_use in which_columns_preference:
        inferred_price = infer_latest_price(new_multiple_prices, price_col, col_to_use)
        if not np.isnan(inferred_price):
            # do in order of preference so if we find one we stop
            print(
                "Price for contract %s of %f inferred from contract %s"
                % (price_col, inferred_price, col_to_use)
            )
            return inferred_price, True

    raise Exception("Couldn't infer price of %s column - can't roll" % price_col)


def infer_latest_price(new_multiple_prices, price_col: str, col_to_use: str):
    """
    Infer the last price in price_col from col_to_use

    :param new_multiple_prices:
    :param price_col: str, must be column in new_multiple_prices
    :param col_to_use: str, must be column in new_multiple_prices
    :return: float or np.nan if no price found
    """

    last_price_to_infer_from = new_multiple_prices[col_to_use].values[-1]

    if np.isnan(last_price_to_infer_from):
        # Can't infer
        return np.nan

    # Can infer, but need last valid time these were matched
    # Need to match up, ensuring that there is no contract switch
    price_col_contract_col = contract_column_names[price_col]
    col_to_use_contract_col = contract_column_names[col_to_use]

    df_of_col_and_col_to_use = new_multiple_prices[
        [price_col, price_col_contract_col, col_to_use, col_to_use_contract_col]
    ]
    df_of_col_and_col_to_use.columns = [
        "Price_to_find",
        "Contract_of_to_find",
        "Price_infer_from",
        "Contract_infer_from",
    ]

    try:
        # Ensure we only have price data back to the last roll
        matched_price_data = last_price_data_with_matched_contracts(
            df_of_col_and_col_to_use
        )
        inferred_price = infer_price_from_matched_price_data(matched_price_data)
    except BaseException:
        return np.nan

    return inferred_price


def last_price_data_with_matched_contracts(df_of_col_and_col_to_use):
    """
    Track back in a Df, removing the early period before a roll

    :param df_of_col_and_col_to_use: DataFrame with ['Price_to_find', 'Contract_of_to_find', 'Price_infer_from', 'Contract_infer_from']
    :return: DataFrame with ['Price_to_find', 'Price_infer_from']
    """

    final_contract_of_to_infer_from = (
        df_of_col_and_col_to_use.Contract_infer_from.values[-1]
    )
    final_contract_of_to_find = df_of_col_and_col_to_use.Contract_of_to_find.values[-1]

    matched_df_dict = pd.DataFrame(columns=["Price_to_find", "Price_infer_from"])

    # We will do this backwards, but then sort the final DF so in right order
    length_data = len(df_of_col_and_col_to_use)
    for data_row_idx in range(length_data - 1, 0, -1):
        relevant_row_of_data = df_of_col_and_col_to_use.iloc[data_row_idx]
        current_contract_to_infer_from = relevant_row_of_data.Contract_infer_from
        current_contract_to_find = relevant_row_of_data.Contract_of_to_find

        if (
            current_contract_to_find == final_contract_of_to_find
            and current_contract_to_infer_from == final_contract_of_to_infer_from
        ):
            row_to_copy = df_of_col_and_col_to_use[
                ["Price_to_find", "Price_infer_from"]
            ].iloc[[data_row_idx]]

            if matched_df_dict.empty:
                matched_df_dict = row_to_copy
            else:
                matched_df_dict = pd.concat([matched_df_dict, row_to_copy])
        else:
            # We're full
            break

    if len(matched_df_dict) == 0:
        raise Exception("Empty matched price series!")

    matched_df_dict = matched_df_dict.sort_index()

    return matched_df_dict


def infer_price_from_matched_price_data(matched_price_data):
    """
    Infer the final price of one contract from the price of another contract

    :param matched_price_data: df with two price columns: Price_to_find, Price_infer_from
    :return: float
    """
    final_price_to_infer_from = matched_price_data.Price_infer_from.values[-1]
    matched_price_data_no_nan = matched_price_data.dropna()

    if len(matched_price_data_no_nan) == 0:
        print("Can't find any non NA when implying price")
        return np.nan

    offset = (
        matched_price_data_no_nan["Price_to_find"]
        - matched_price_data_no_nan["Price_infer_from"]
    )
    # Might be noisy. Okay this might be a mixture of daily or weekly, or
    # intraday data, but live with it
    smoothed_offset = offset.rolling(5, min_periods=1).median().values[-1]

    inferred_price = final_price_to_infer_from + smoothed_offset

    return inferred_price


def rollback_adjustment(
    data: dataBlob,
    instrument_code: str,
    current_adjusted_prices: futuresAdjustedPrices,
    current_multiple_prices: futuresMultiplePrices,
):
    price_updater = updatePrices(data)

    try:
        price_updater.add_adjusted_prices(
            instrument_code, current_adjusted_prices, ignore_duplication=True
        )
        price_updater.add_multiple_prices(
            instrument_code, current_multiple_prices, ignore_duplication=True
        )
    except Exception as e:
        data.log.warning(
            "***** ROLLBACK FAILED! %s!You may need to rebuild your data! Check before trading!! *****"
            % e
        )
        return failure

    return success
