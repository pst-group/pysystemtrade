import datetime

import pytest

from sysexecution.trade_qty import tradeQuantity
from sysobjects.production.trade_limits import listOfTradeLimits, tradeLimit
from sysobjects.production.tradeable_object import instrumentStrategy


@pytest.mark.parametrize("used, remaining", [(0, 8), (3, 5), (8, 0), (17, 0)])
def test_remaining_capacity_is_nonnegative(used: int, remaining: int):
    limit = tradeLimit(8, instrumentStrategy("", "TEST"), trades_since_last_reset=used)

    assert limit.trade_capacity_remaining == remaining
    assert limit.what_abs_trade_is_possible(10) == remaining


@pytest.mark.parametrize("proposed", [[10], [-10], [1, -1]])
def test_lowered_limit_blocks_trades_without_resetting_usage(proposed: list):
    reset_time = datetime.datetime.now() - datetime.timedelta(hours=1)
    limit = tradeLimit(
        17,
        instrumentStrategy("", "TEST"),
        trades_since_last_reset=17,
        last_reset_time=reset_time,
    )
    limit.update_limit(8)
    quantity = tradeQuantity(proposed)
    allowance = listOfTradeLimits([limit]).what_abs_trade_is_possible(
        quantity.total_abs_qty()
    )

    assert allowance == 0
    assert quantity.change_trade_size_proportionally_to_meet_abs_qty_limit(
        allowance
    ) == [0] * len(proposed)
    assert limit.as_dict()["trades_since_last_reset"] == 17
    assert limit.as_dict()["last_reset_time"] == reset_time


def test_expired_usage_still_resets():
    reset_time = datetime.datetime.now() - datetime.timedelta(days=2)
    limit = tradeLimit(
        8,
        instrumentStrategy("", "TEST"),
        trades_since_last_reset=17,
        last_reset_time=reset_time,
    )

    assert limit.trade_capacity_remaining == 8
    assert limit.trades_since_last_reset == 0
    assert limit.as_dict()["last_reset_time"] > reset_time
