"""Limit-price regressions without database or broker connections."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import sysexecution.algos.algo as algo_module
from syscore.exceptions import missingData
from sysexecution.algos.algo import (
    benchmarkPriceCollection,
    limit_price_from_input,
    limit_price_from_offside_price,
    limit_price_from_side_price,
)
from sysexecution.algos.algo_original_best import algoOriginalBest
from sysexecution.orders.broker_orders import limit_order_type
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.named_order_objects import missing_order


QUOTE_SOURCES = [limit_price_from_side_price, limit_price_from_offside_price]


@pytest.fixture
def make_algo(monkeypatch):
    broker = Mock()
    broker.get_min_tick_size_for_contract.return_value = 0.00005
    broker.get_broker_name.return_value = "IB"
    broker.get_broker_account.return_value = "paper-test"
    broker.get_broker_clientid.return_value = 14

    def submit(order):
        control = broker.submit_broker_order.return_value
        control.order = order
        return control

    broker.submit_broker_order.side_effect = submit
    monkeypatch.setattr(algo_module, "dataBroker", lambda data: broker)

    def make(*, spread=True, direction=-1):
        contract = ["20260900", "20261200"] if spread else "20260900"
        trade = [direction, -direction] if spread else direction
        order = contractOrder(
            "test", "AUD", contract, trade, order_id=159, parent=170, roll_order=spread
        )
        return algoOriginalBest(SimpleNamespace(log=Mock()), order), broker

    return make


@pytest.mark.parametrize("source", QUOTE_SOURCES)
@pytest.mark.parametrize("price", [0.00104, -0.00104, 0.0])
@pytest.mark.parametrize("direction", [-1, 1])
def test_spread_quote_is_not_rounded_to_an_outright_tick(
    make_algo, source, price, direction
):
    algo, broker = make_algo(direction=direction)
    prices = benchmarkPriceCollection(side_price=9.0, offside_price=10.0)
    setattr(prices, source, price)

    result = algo.set_limit_price(algo.contract_order, prices, limit_price_from=source)

    assert result == price
    broker.get_min_tick_size_for_contract.assert_not_called()


@pytest.mark.parametrize("source", QUOTE_SOURCES + [limit_price_from_input])
@pytest.mark.parametrize("direction", [-1, 1])
def test_outright_limit_rounding_is_unchanged(make_algo, source, direction):
    algo, broker = make_algo(spread=False, direction=direction)
    prices = benchmarkPriceCollection(side_price=0.66104, offside_price=0.66106)
    inputs = {
        limit_price_from_input: 0.66103,
        limit_price_from_side_price: prices.side_price,
        limit_price_from_offside_price: prices.offside_price,
    }

    result = algo.set_limit_price(
        algo.contract_order, prices, input_limit_price=0.66103, limit_price_from=source
    )

    assert result == 0.00005 * round(inputs[source] / 0.00005)
    broker.get_min_tick_size_for_contract.assert_called_once_with(
        algo.contract_order.futures_contract
    )


def test_explicit_spread_limit_still_uses_existing_rounding(make_algo):
    algo, broker = make_algo()

    result = algo.set_limit_price(
        algo.contract_order,
        benchmarkPriceCollection(),
        input_limit_price=0.00104,
        limit_price_from=limit_price_from_input,
    )

    assert result == 0.00005 * round(0.00104 / 0.00005)
    broker.get_min_tick_size_for_contract.assert_called_once()


@pytest.mark.parametrize("source", QUOTE_SOURCES)
@pytest.mark.parametrize("price", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_quote_cannot_bypass_existing_rounding_failure(
    make_algo, source, price
):
    algo, broker = make_algo()
    prices = benchmarkPriceCollection(side_price=price, offside_price=price)

    with pytest.raises((ValueError, OverflowError)):
        algo.set_limit_price(algo.contract_order, prices, limit_price_from=source)

    broker.submit_broker_order.assert_not_called()


@pytest.mark.parametrize("direction", [-1, 1])
def test_initial_broker_order_preserves_aud_spread_quote(make_algo, direction):
    algo, broker = make_algo(direction=direction)
    prices = benchmarkPriceCollection(
        side_price=0.00102, mid_price=0.00103, offside_price=0.00104
    )
    algo.get_market_data_for_order_modifies_ticker_object = Mock(return_value=prices)
    ticker = Mock()

    result = algo.get_and_submit_broker_order_for_contract_order(
        algo.contract_order,
        order_type=limit_order_type,
        limit_price_from=limit_price_from_offside_price,
        ticker_object=ticker,
    )

    submitted = broker.submit_broker_order.call_args.args[0]
    assert submitted.limit_price == 0.00104
    assert submitted.trade == [direction, -direction]
    assert submitted.contract_date == algo.contract_order.contract_date
    assert submitted.side_price == prices.side_price
    assert submitted.mid_price == prices.mid_price
    assert submitted.offside_price == prices.offside_price
    assert result is broker.submit_broker_order.return_value
    result.add_or_replace_ticker.assert_called_once_with(ticker)
    broker.get_min_tick_size_for_contract.assert_not_called()


def test_missing_quote_still_prevents_broker_submission(make_algo):
    algo, broker = make_algo()
    ticker = Mock()
    ticker.wait_for_valid_bid_and_ask_and_return_current_tick.side_effect = missingData

    result = algo.get_and_submit_broker_order_for_contract_order(
        algo.contract_order,
        order_type=limit_order_type,
        limit_price_from=limit_price_from_offside_price,
        ticker_object=ticker,
    )

    assert result is missing_order
    broker.submit_broker_order.assert_not_called()
    broker.get_min_tick_size_for_contract.assert_not_called()


@pytest.mark.parametrize("price", [0.00102, -0.00102, 0.0])
@pytest.mark.parametrize("direction", [-1, 1])
def test_spread_repricing_keeps_using_the_quoted_price(make_algo, price, direction):
    algo, broker = make_algo(direction=direction)
    control = Mock()
    control.order.order_type = limit_order_type
    control.order.log_attributes.return_value = algo.contract_order.log_attributes()
    control.broker_limit_price.return_value = price + 0.00002
    control.ticker.current_side_price = price

    result = algo.set_aggressive_limit_price(control)

    broker.modify_limit_price_given_control_object.assert_called_once_with(
        control, price
    )
    assert result is broker.modify_limit_price_given_control_object.return_value
    broker.get_min_tick_size_for_contract.assert_not_called()
