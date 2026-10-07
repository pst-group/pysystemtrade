import numpy as np

from syscore.genutils import sign
from sysexecution.orders.named_order_objects import missing_order


class tradeQuantity(list):
    def __init__(self, trade_or_fill_qty):
        if trade_or_fill_qty is None:
            trade_or_fill_qty = []
        elif isinstance(trade_or_fill_qty, tradeQuantity):
            pass
        elif isinstance(trade_or_fill_qty, int):
            trade_or_fill_qty = [trade_or_fill_qty]
        elif isinstance(trade_or_fill_qty, np.int64):
            trade_or_fill_qty = [int(trade_or_fill_qty)]
        elif isinstance(trade_or_fill_qty, float):
            trade_or_fill_qty = [int(trade_or_fill_qty)]
        else:
            # must be a list
            trade_or_fill_qty = [int(trade) for trade in trade_or_fill_qty]

        super().__init__(trade_or_fill_qty)

    def zero_version(self):
        len_self = len(self)
        return tradeQuantity([0] * len_self)

    def fill_less_than_or_equal_to_desired_trade(self, proposed_fill):
        # zip() would ignore a missing leg and treat a short fill as valid
        if len(proposed_fill) != len(self):
            return False
        return all(
            [abs(x) <= abs(y) and x * y >= 0 for x, y in zip(proposed_fill, self)]
        )

    def equals_zero(self):
        return all([x == 0 for x in self])

    def sign_of_single_trade(self):
        qty = self.as_single_trade_qty_or_error()
        return sign(qty)

    def sign_equal(self, other):
        return all([sign(x) == sign(y) for x, y in zip(self, other)])

    def __eq__(self, other):
        # zip() would treat [1, -1] as equal to [1], so a spread could look filled
        if len(self) != len(other):
            return False
        return all([x == y for x, y in zip(self, other)])

    def __sub__(self, other):
        assert len(self) == len(other)
        result = [x - y for x, y in zip(self, other)]
        result = tradeQuantity(result)
        return result

    def __add__(self, other):
        assert len(self) == len(other)
        result = [x + y for x, y in zip(self, other)]
        result = tradeQuantity(result)
        return result

    def __radd__(self, other):
        ## required to make list adding work
        if other == 0:
            return self
        else:
            return self.__add__(other)

    def total_abs_qty(self):
        abs_qty_list = [abs(x) for x in self]
        return sum(abs_qty_list)

    def change_trade_size_proportionally_to_meet_abs_qty_limit(self, max_abs_qty: int):
        new_qty = change_trade_size_proportionally_to_meet_abs_qty_limit(
            self, max_abs_qty
        )
        return tradeQuantity(new_qty)

    def sort_with_idx(self, idx_list: list):
        unsorted = self
        qty_sorted = [unsorted[idx] for idx in idx_list]
        self = tradeQuantity(qty_sorted)

    def as_single_trade_qty_or_error(self) -> int:
        if len(self) > 1:
            return missing_order
        return self[0]

    def reduce_trade_size_proportionally_to_abs_limit_per_leg(self, abs_list: list):
        # for each item in _trade and abs_list, return the signed minimum of the zip
        # eg if self._trade = [2,-2] and abs_list = [1,1], return [2,-2]
        applied_list = reduce_trade_size_proportionally_to_abs_limit_per_leg(
            self, abs_list
        )

        return tradeQuantity(applied_list)

    def reduce_trade_size_proportionally_so_smallest_leg_is_max_size(
        self, max_size: int
    ):
        """
        Cut the trade down proportionally so the smallest leg is min_size
        eg self = [2], min_size = 1 -> [1]
        self = [-2,2], min_size = 1 -> [-1,1]
        self = [-2,4,-2], min_size = 1 -> [-1,2,2]
        self = [-3,4,-3], min_size = 1 -> [-3,4,-3]

        :param max_size:
        :return: tradeQuantity
        """

        new_trade_list = reduce_trade_size_proportionally_so_smallest_leg_is_max_size(
            self, max_size
        )
        return tradeQuantity(new_trade_list)

    def buy_or_sell(self) -> int:
        # sign of trade quantity
        return sign(self[0])


class listOfTradeQuantity(list):
    def total_filled_qty(self) -> tradeQuantity:
        total_filled_qty = sum(self)
        return total_filled_qty


def change_trade_size_proportionally_to_meet_abs_qty_limit(
    trade_list: tradeQuantity, max_abs_qty: int
) -> list:
    """

    :param trade_list: tradeQuantity
    :param max_abs_qty: int
    :return: list of ints


    """
    original_qty = trade_list
    current_abs_qty = trade_list.total_abs_qty()
    if current_abs_qty == 0:
        return original_qty
    if max_abs_qty == 0:
        return [0] * len(original_qty)
    max_abs_qty = float(max_abs_qty)
    ratio = max_abs_qty / current_abs_qty
    if ratio >= 1.0:
        return original_qty

    new_qty = [abs(int(np.floor(ratio * qty))) for qty in trade_list]
    new_qty_adjusted = reduce_trade_size_proportionally_to_abs_limit_per_leg(
        original_qty, new_qty
    )

    return new_qty_adjusted


def reduce_trade_size_proportionally_to_abs_limit_per_leg(
    trade_list_qty: list, abs_list: list
) -> list:
    """

    :param trade_list_qty:
    :param abs_list:
    :return: list


    """
    # for each item in _trade and abs_list, return the signed minimum of the zip
    # eg if self._trade = [2,-2] and abs_list = [1,1], return [2,-2]

    assert all([x >= 0 for x in abs_list])
    assert len(trade_list_qty) == len(abs_list)

    abs_trade_list = [abs(x) for x in trade_list_qty]
    smallest_abs_leg = min(abs_trade_list)
    if smallest_abs_leg == 0:
        # can't do this
        return [0 for x in trade_list_qty]

    abs_size_ratio_list = [
        min([x, y]) / float(x) for x, y in zip(abs_trade_list, abs_list)
    ]
    min_abs_size_ratio = min(abs_size_ratio_list)
    new_smallest_leg = np.floor(smallest_abs_leg * min_abs_size_ratio)
    ratio_applied = new_smallest_leg / smallest_abs_leg
    trade_list_with_ratio_as_float = [x * ratio_applied for x in trade_list_qty]
    trade_list_with_ratio_as_int = [int(x) for x in trade_list_with_ratio_as_float]
    diff = [
        abs(x - y)
        for x, y in zip(trade_list_with_ratio_as_float, trade_list_with_ratio_as_int)
    ]
    largediff = any([x > 0.0001 for x in diff])
    if largediff:
        trade_list_with_ratio_as_int = [0] * len(trade_list_qty)

    return trade_list_with_ratio_as_int


def reduce_trade_size_proportionally_so_smallest_leg_is_max_size(
    trade_list_qty: list, max_size: int
):
    """
    Cut the trade down proportionally so the smallest leg is min_size

    :param max_size:
    :return: tradeQuantity


    """

    if max_size == 0:
        return [0] * len(trade_list_qty)

    assert max_size > 0

    abs_trade_list = [abs(x) for x in trade_list_qty]
    smallest_abs_leg = min(abs_trade_list)

    if smallest_abs_leg == 0:
        return trade_list_qty

    new_smallest_leg = max_size
    ratio_applied = new_smallest_leg / smallest_abs_leg
    if ratio_applied >= 1.0:
        return trade_list_qty

    trade_list_with_ratio_as_float = [x * ratio_applied for x in trade_list_qty]
    trade_list_with_ratio_as_int = [int(x) for x in trade_list_with_ratio_as_float]
    diff = [
        abs(x - y)
        for x, y in zip(trade_list_with_ratio_as_float, trade_list_with_ratio_as_int)
    ]
    largediff = any([x > 0.0001 for x in diff])
    if largediff:
        return trade_list_qty

    return trade_list_with_ratio_as_int


def calculate_most_conservative_qty_from_list_of_qty_with_limits_applied(
    position: int, list_of_trade_qty: listOfTradeQuantity
) -> tradeQuantity:
    # only works with single legs
    trade_qty_list_as_single_legs = [
        trade_qty.as_single_trade_qty_or_error() for trade_qty in list_of_trade_qty
    ]

    if position >= 0:
        most_conservative_trade = min(trade_qty_list_as_single_legs)
    else:
        most_conservative_trade = max(trade_qty_list_as_single_legs)

    new_trade_qty = tradeQuantity(most_conservative_trade)

    return new_trade_qty
