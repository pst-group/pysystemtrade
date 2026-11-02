from collections import namedtuple

import numpy as np
import pandas as pd
from dataclasses import dataclass

from sysobjects.dict_of_futures_per_contract_prices import (
    dictFuturesContractFinalPrices,
)
from sysobjects.dict_of_named_futures_per_contract_prices import (
    price_name,
    forward_name,
    carry_name,
    contract_name_from_column_name,
)

missing_row = object()


@dataclass
class rollCalendarWithRollIndex:
    roll_calendar: None
    rolling_row_index: int = 1
    already_added_data: bool = False

    def iterate_roll(self):
        self.rolling_row_index = self.rolling_row_index + 1

    def not_end_of_calendar(self):
        return self.rolling_row_index < len(self.roll_calendar.index)

    def data_now_added(self):
        self.already_added_data = True


rollDateInfo = namedtuple(
    "rollDateInfo",
    [
        "last_roll_date",
        "next_roll_date",
        "start_of_roll_period",
        "end_of_roll_period",
        "roll_calendar_with_roll_index",
    ],
)
contractAndPriceInfo = namedtuple(
    "ccontractAndPriceInfo",
    [
        "current_contract",
        "next_contract",
        "carry_contract",
        "current_contract_str",
        "next_contract_str",
        "carry_contract_str",
        "dict_of_futures_contract_closing_prices",
    ],
)


def create_multiple_price_stack_from_raw_data(
    roll_calendar,
    dict_of_futures_contract_closing_prices: dictFuturesContractFinalPrices,
):
    """
    # NO TYPE CHECK FOR ROLL_CALENDAR AS WOULD CAUSE CIRCULAR IMPORT

    :param roll_calendar: rollCalendar
    :param dict_of_futures_closing_contract_prices: dictFuturesContractPrices with only one column, keys are date_str

    :return: pd.DataFrame with the 6 columns PRICE, CARRY, FORWARD, PRICE_CONTRACT, CARRY_CONTRACT, FORWARD_CONTRACT
    """

    all_price_data_stack = []
    roll_calendar_with_roll_index = rollCalendarWithRollIndex(roll_calendar)
    while roll_calendar_with_roll_index.not_end_of_calendar():
        all_price_data = _get_price_data_between_rolls(
            roll_calendar_with_roll_index, dict_of_futures_contract_closing_prices
        )
        if all_price_data is missing_row:
            pass
        else:
            all_price_data_stack.append(all_price_data)
            roll_calendar_with_roll_index.data_now_added()

        roll_calendar_with_roll_index.iterate_roll()

    # end of loop
    all_price_data_stack = pd.concat(all_price_data_stack, axis=0)

    return all_price_data_stack


def _get_price_data_between_rolls(
    roll_calendar_with_roll_index: rollCalendarWithRollIndex,
    dict_of_futures_contract_closing_prices: dictFuturesContractFinalPrices,
):
    # consider consolidating input args

    roll_date_info = _calc_roll_date_info(roll_calendar_with_roll_index)
    contract_date_info = _calc_contract_date_info(
        roll_date_info, dict_of_futures_contract_closing_prices
    )

    invalid = _invalid_current_contract(contract_date_info)

    if invalid:
        # missing, this is okay if we haven't started properly yet
        if not roll_calendar_with_roll_index.already_added_data:
            print(
                "Missing contracts at start of roll calendar not in price data, ignoring"
            )
            return missing_row
        else:
            raise Exception(
                "Missing contracts in middle of roll calendar %s, not in price data!"
                % str(roll_date_info.next_roll_date)
            )

    all_price_data = _calculate_price_data_from_current_next_carry_data(
        roll_date_info, contract_date_info
    )

    return all_price_data


def _calc_roll_date_info(
    roll_calendar_with_roll_index: rollCalendarWithRollIndex,
) -> rollDateInfo:
    # Between these dates is where we are populating prices
    roll_calendar = roll_calendar_with_roll_index.roll_calendar
    rolling_row_index = roll_calendar_with_roll_index.rolling_row_index

    last_roll_date = roll_calendar.index[rolling_row_index - 1]
    next_roll_date = roll_calendar.index[rolling_row_index]

    end_of_roll_period = next_roll_date
    start_of_roll_period = last_roll_date + pd.DateOffset(
        seconds=1
    )  # to avoid overlaps

    roll_date_info = rollDateInfo(
        last_roll_date,
        next_roll_date,
        start_of_roll_period,
        end_of_roll_period,
        roll_calendar_with_roll_index,
    )

    return roll_date_info


def _calc_contract_date_info(
    roll_date_info: rollDateInfo,
    dict_of_futures_contract_closing_prices: dictFuturesContractFinalPrices,
) -> contractAndPriceInfo:
    roll_calendar = roll_date_info.roll_calendar_with_roll_index.roll_calendar

    contracts_now = roll_calendar.loc[roll_date_info.next_roll_date, :]
    current_contract = contracts_now.current_contract
    next_contract = contracts_now.next_contract
    carry_contract = contracts_now.carry_contract

    current_contract_str = str(current_contract)
    next_contract_str = str(next_contract)
    carry_contract_str = str(carry_contract)

    contract_date_info = contractAndPriceInfo(
        current_contract,
        next_contract,
        carry_contract,
        current_contract_str,
        next_contract_str,
        carry_contract_str,
        dict_of_futures_contract_closing_prices,
    )

    return contract_date_info


def _invalid_current_contract(contract_date_info: contractAndPriceInfo) -> bool:
    dict_of_futures_contract_closing_prices = (
        contract_date_info.dict_of_futures_contract_closing_prices
    )
    contract_keys = dict_of_futures_contract_closing_prices.keys()

    if contract_date_info.current_contract_str not in contract_keys:
        return True
    else:
        return False


def _calculate_price_data_from_current_next_carry_data(
    roll_date_info: rollDateInfo, contract_date_info: contractAndPriceInfo
):
    set_of_price_data = _get_current_next_carry_data(roll_date_info, contract_date_info)

    all_price_data = _build_all_price_data(set_of_price_data, contract_date_info)

    return all_price_data


def _get_current_next_carry_data(
    roll_date_info: rollDateInfo, contract_date_info: contractAndPriceInfo
):
    dict_of_futures_contract_closing_prices = (
        contract_date_info.dict_of_futures_contract_closing_prices
    )
    current_contract_data = dict_of_futures_contract_closing_prices[
        contract_date_info.current_contract_str
    ]
    last_date_in_data = current_contract_data.index[-1]
    start_of_period = roll_date_info.start_of_roll_period
    end_of_period = min([roll_date_info.end_of_roll_period, last_date_in_data])

    current_contract_data = current_contract_data.sort_index()
    current_price_data = current_contract_data[start_of_period:end_of_period]

    carry_price_data = _get_carry_price_data(
        contract_date_info, current_price_data, roll_date_info
    )

    next_price_data = _get_next_price_data(
        contract_date_info, current_price_data, roll_date_info
    )

    return current_price_data, next_price_data, carry_price_data


def _get_next_price_data(
    contract_date_info: contractAndPriceInfo,
    current_price_data: pd.Series,
    roll_date_info: rollDateInfo,
):
    dict_of_futures_contract_closing_prices = (
        contract_date_info.dict_of_futures_contract_closing_prices
    )
    contract_keys = dict_of_futures_contract_closing_prices.keys()
    next_contract_str = contract_date_info.next_contract_str

    if next_contract_str not in contract_keys:
        if _last_row_in_roll_calendar(roll_date_info):
            # Last entry, this is fine
            print(
                "Next contract %s missing in last row of roll calendar - this is okay"
                % next_contract_str
            )
            next_price_data = pd.Series(np.nan, current_price_data.index)
            next_price_data.iloc[:] = np.nan
        else:
            raise Exception(
                "Missing contract %s in middle of roll calendar on %s"
                % (next_contract_str, str(roll_date_info.next_roll_date))
            )
    else:
        next_price_data_for_contract = dict_of_futures_contract_closing_prices[
            next_contract_str
        ]

        next_price_data_for_contract = next_price_data_for_contract.sort_index()

        next_price_data = next_price_data_for_contract[
            roll_date_info.start_of_roll_period : roll_date_info.end_of_roll_period
        ]

    return next_price_data


def _get_carry_price_data(
    contract_date_info: contractAndPriceInfo,
    current_price_data: pd.Series,
    roll_date_info: rollDateInfo,
):
    dict_of_futures_contract_closing_prices = (
        contract_date_info.dict_of_futures_contract_closing_prices
    )
    contract_keys = dict_of_futures_contract_closing_prices.keys()
    carry_contract_str = contract_date_info.carry_contract_str

    if carry_contract_str not in contract_keys:
        if _last_row_in_roll_calendar(roll_date_info):
            # Last entry, this is fine
            print(
                "Carry contract %s missing in last row of roll calendar - this is okay"
                % carry_contract_str
            )
            carry_price_data = pd.Series(np.nan, current_price_data.index)
            carry_price_data.iloc[:] = np.nan
        else:
            raise Exception(
                "Missing contract %s in middle of roll calendar on %s"
                % (carry_contract_str, str(roll_date_info.next_roll_date))
            )
    else:
        carry_price_data_for_contract = dict_of_futures_contract_closing_prices[
            carry_contract_str
        ]
        carry_price_data_for_contract = carry_price_data_for_contract.sort_index()
        carry_price_data = carry_price_data_for_contract[
            roll_date_info.start_of_roll_period : roll_date_info.end_of_roll_period
        ]

    return carry_price_data


def _last_row_in_roll_calendar(roll_date_info: rollDateInfo):
    roll_calendar_with_roll_index = roll_date_info.roll_calendar_with_roll_index
    if (
        roll_calendar_with_roll_index.rolling_row_index
        == len(roll_calendar_with_roll_index.roll_calendar.index) - 1
    ):
        return True
    else:
        return False


def _build_all_price_data(set_of_price_data, contract_date_info):
    current_price_data, next_price_data, carry_price_data = set_of_price_data
    all_price_data = pd.concat(
        [current_price_data, next_price_data, carry_price_data], axis=1
    )
    all_price_data.columns = [
        price_name,
        forward_name,
        carry_name,
    ]

    all_price_data[contract_name_from_column_name(price_name)] = (
        contract_date_info.current_contract
    )
    all_price_data[contract_name_from_column_name(forward_name)] = (
        contract_date_info.next_contract
    )
    all_price_data[contract_name_from_column_name(carry_name)] = (
        contract_date_info.carry_contract
    )

    return all_price_data
