"""Preserve execution-price precision only with complete cumulative coverage.

All inputs are disconnected ib_async objects. No IB or database is contacted.
Commission reports are already present, so these tests do not depend on the
separate pending-commission fix.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from ib_async import CommissionReport, Contract, Execution, Fill, Order, Trade
from ib_async.util import UNSET_DOUBLE

from sysbrokers.IB.ib_contracts import ibcontractWithLegs
from sysbrokers.IB.ib_translate_broker_order_objects import (
    create_broker_order_from_trade_with_contract,
    extract_fill_info,
    extract_totals_from_fill_data,
    tradeWithContract,
)


NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def make_fill(
    *,
    execution_id="test.1.01",
    shares=1,
    cumulative=1,
    price=0.7444,
    average=0.744,
    side="BOT",
    seconds=0,
    contract=None,
    commission=1.25,
):
    if contract is None:
        contract = Contract(
            secType="FUT",
            conId=1001,
            symbol="KU",
            lastTradeDateOrContractMonth="202610",
        )
    stamp = NOW + timedelta(seconds=seconds)
    return Fill(
        contract,
        Execution(
            execId=execution_id,
            time=stamp,
            side=side,
            shares=shares,
            cumQty=cumulative,
            price=price,
            avgPrice=average,
            orderId=41,
            clientId=7,
            permId=99,
        ),
        CommissionReport(execId=execution_id, commission=commission, currency="USD"),
        stamp,
    )


def totals(*fills):
    return extract_totals_from_fill_data(
        extract_fill_info(SimpleNamespace(fills=list(fills)))
    )


def assert_metadata_unchanged(result, fills, *, month="202610"):
    """Price selection must not change existing final-fill metadata or fees."""
    final = sorted(fills, key=lambda fill: fill.execution.cumQty)[-1]
    assert result[0] == final.execution.clientId
    assert result[1] == final.execution.orderId
    assert result[3] == datetime.fromtimestamp(final.execution.time.timestamp())
    sign = 1 if final.execution.side == "BOT" else -1
    assert result[5] == {month: sign * final.execution.cumQty}
    assert [(fee.currency, fee.value) for fee in result[4]] == [
        (fill.commissionReport.currency, fill.commissionReport.commission)
        for fill in fills
    ]


@pytest.mark.parametrize("price,average", [(0.7444, 0.744), (0.7424, 0.742)])
@pytest.mark.parametrize("side", ["BOT", "SLD"])
def test_krw_single_execution_preserves_observed_precision(price, average, side):
    fill = make_fill(price=price, average=average, side=side)
    raw = tradeWithContract(
        ibcontractWithLegs(fill.contract),
        Trade(
            fill.contract,
            Order(
                action="BUY" if side == "BOT" else "SELL",
                totalQuantity=1,
                orderType="MKT",
                orderId=41,
                clientId=7,
                permId=99,
            ),
            fills=[fill],
        ),
    )
    result = create_broker_order_from_trade_with_contract(raw, "KRWUSD_mini")
    assert result.filled_price == price
    assert result.leg_filled_price == [price]
    assert result.fill == ([1] if side == "BOT" else [-1])
    assert result.fill_datetime == datetime.fromtimestamp(NOW.timestamp())
    assert [(fee.currency, fee.value) for fee in result.commission] == [("USD", 1.25)]


@pytest.mark.parametrize("price", [0.0, -0.7444])
def test_zero_and_negative_execution_prices_are_valid(price):
    fill = make_fill(price=price, average=123.0)
    result = totals(fill)
    assert result[2] == {"202610": price}
    assert_metadata_unchanged(result, [fill])


@pytest.mark.parametrize("side", ["BOT", "SLD"])
@pytest.mark.parametrize("reverse", [False, True])
def test_unequal_partial_fills_are_weighted_by_shares_not_cumulative_quantity(
    side, reverse
):
    fills = [
        make_fill(price=10.02, average=10.0, side=side),
        make_fill(
            execution_id="test.2.01",
            shares=2,
            cumulative=3,
            price=20.06,
            average=16.67,
            side=side,
            seconds=5,
            commission=2.5,
        ),
    ]
    if reverse:
        fills.reverse()
    before = deepcopy(fills)
    result = totals(*fills)
    assert result[2]["202610"] == pytest.approx((10.02 + 2 * 20.06) / 3)
    assert_metadata_unchanged(result, fills)
    assert fills == before


def test_partial_order_uses_complete_execution_coverage_so_far():
    fill = make_fill(shares=2, cumulative=2)
    trade = Trade(
        fill.contract,
        Order(action="BUY", totalQuantity=5, orderType="MKT"),
        fills=[fill],
    )
    result = create_broker_order_from_trade_with_contract(
        tradeWithContract(ibcontractWithLegs(fill.contract), trade), "KRWUSD_mini"
    )
    assert result.trade == [5]
    assert result.fill == [2]
    assert result.filled_price == 0.7444
    assert result.leg_filled_price == [0.7444]


def test_finite_weighted_price_does_not_overflow_intermediate_notional():
    fills = [
        make_fill(shares=2, cumulative=2, price=1e308, average=9e307),
        make_fill(
            execution_id="test.2.01",
            shares=3,
            cumulative=5,
            price=8e307,
            average=9e307,
            seconds=1,
        ),
    ]
    result = totals(*fills)
    assert result[2]["202610"] == pytest.approx(8.8e307)
    assert_metadata_unchanged(result, fills)


@pytest.mark.parametrize(
    "coverage",
    ["missing_prefix", "missing_middle", "overlap", "duplicate_endpoint"],
)
def test_incomplete_or_overlapping_coverage_keeps_final_broker_average(coverage):
    first = make_fill(price=0.7001, average=0.7)
    final = make_fill(
        execution_id="test.3.01",
        cumulative=3,
        price=0.8002,
        average=0.766,
        seconds=2,
    )
    if coverage == "missing_prefix":
        fills = [final]
    elif coverage == "missing_middle":
        fills = [first, final]
    elif coverage == "overlap":
        first.execution.shares = first.execution.cumQty = 2
        final.execution.shares = 2
        fills = [first, final]
    else:
        # Total shares still equals final cumQty. A sum-only check would accept
        # this duplicate first interval as if the missing middle fill existed.
        duplicate = make_fill(execution_id="test.2.01", price=0.9003, seconds=1)
        fills = [first, duplicate, final]
    result = totals(*fills)
    assert result[2] == {"202610": 0.766}
    assert_metadata_unchanged(result, fills)


def test_repeated_execution_id_cannot_create_apparently_complete_coverage():
    fills = [
        make_fill(execution_id="same", price=0.7001),
        make_fill(execution_id="same", cumulative=2, price=0.8002, seconds=1),
        make_fill(
            execution_id="test.3.01",
            cumulative=3,
            price=0.9003,
            average=0.799,
            seconds=2,
        ),
    ]
    result = totals(*fills)
    assert result[2] == {"202610": 0.799}
    assert_metadata_unchanged(result, fills)


@pytest.mark.parametrize("shares", [0, -1, float("nan"), float("inf")])
def test_invalid_execution_quantity_keeps_existing_average(shares):
    fill = make_fill(shares=shares)
    result = totals(fill)
    assert result[2] == {"202610": 0.744}
    assert_metadata_unchanged(result, [fill])


@pytest.mark.parametrize(
    "price", [float("nan"), float("inf"), -float("inf"), None, UNSET_DOUBLE]
)
def test_invalid_execution_price_keeps_existing_average(price):
    fill = make_fill(price=price)
    result = totals(fill)
    assert result[2] == {"202610": 0.744}
    assert_metadata_unchanged(result, [fill])


def test_pending_execution_price_revision_keeps_existing_average():
    fill = make_fill()
    fill.execution.pendingPriceRevision = True
    result = totals(fill)
    assert result[2] == {"202610": 0.744}
    assert_metadata_unchanged(result, [fill])


def test_execution_correction_versions_are_not_counted_as_independent_fills():
    fills = [
        make_fill(execution_id="0000f0e5.6aa7261b.01.01", price=0.7001),
        make_fill(
            execution_id="0000f0e5.6aa7261b.01.02",
            cumulative=2,
            price=0.8002,
            average=0.755,
            seconds=1,
        ),
    ]
    result = totals(*fills)
    assert result[2] == {"202610": 0.755}
    assert_metadata_unchanged(result, fills)


@pytest.mark.parametrize("field,value", [("orderId", 42), ("clientId", 8)])
def test_different_order_identity_cannot_complete_execution_coverage(field, value):
    fills = [
        make_fill(price=0.7001),
        make_fill(
            execution_id="test.2.01",
            cumulative=2,
            price=0.8002,
            average=0.755,
            seconds=1,
        ),
    ]
    setattr(fills[0].execution, field, value)
    result = totals(*fills)
    assert result[2] == {"202610": 0.755}
    assert_metadata_unchanged(result, fills)


def test_execution_without_identity_keeps_existing_average():
    result = totals(make_fill(execution_id=""))
    assert result[2] == {"202610": 0.744}
    assert result[5] == {"202610": 1}


def test_mixed_execution_sides_do_not_produce_a_new_average():
    fills = [
        make_fill(side="BOT", price=0.7001),
        make_fill(
            execution_id="test.2.01",
            cumulative=2,
            side="SLD",
            price=0.8002,
            average=0.755,
            seconds=1,
        ),
    ]
    result = totals(*fills)
    assert result[2] == {"202610": 0.755}
    assert_metadata_unchanged(result, fills)


@pytest.mark.parametrize("incomplete_second_leg", [False, True])
def test_spread_legs_choose_prices_independently_and_ignore_parent_bag(
    incomplete_second_leg,
):
    first = make_fill(side="SLD")
    second = make_fill(
        execution_id="test.2.01",
        contract=Contract(
            secType="FUT", conId=1002, lastTradeDateOrContractMonth="202611"
        ),
        cumulative=2 if incomplete_second_leg else 1,
        price=0.7524,
        average=0.752,
        commission=2.5,
        seconds=1,
    )
    bag = make_fill(
        execution_id="bag",
        contract=Contract(secType="BAG"),
        price=999,
        average=999,
        commission=999,
    )
    result = totals(second, bag, first)
    assert result[2] == {
        "202610": 0.7444,
        "202611": 0.752 if incomplete_second_leg else 0.7524,
    }
    assert result[5] == {
        "202610": -1,
        "202611": 2 if incomplete_second_leg else 1,
    }
    assert [fee.value for fee in result[4]] == [1.25, 2.5]
    assert result[3] == datetime.fromtimestamp(NOW.timestamp())
