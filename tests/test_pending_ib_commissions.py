"""Delayed IB commissions must not become permanent zero fees.

Uses native translation, fill propagation and completion with memory-only stores;
never connects to IB or Mongo. Price averaging is deliberately unchanged.
"""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ib_async import (
    IB,
    ComboLeg,
    CommissionReport,
    Contract,
    Execution,
    Fill,
    Order,
    Trade,
)

from sysbrokers.IB.ib_contracts import ibcontractWithLegs
from sysbrokers.IB.ib_translate_broker_order_objects import (
    create_broker_order_from_trade_with_contract,
    extract_fill_info,
    extract_totals_from_fill_data,
    tradeWithContract,
)
from sysexecution.order_stacks.broker_order_stack import brokerOrderStackData
from sysexecution.order_stacks.contract_order_stack import contractOrderStackData
from sysexecution.order_stacks.instrument_order_stack import instrumentOrderStackData
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.instrument_orders import instrumentOrder
from sysexecution.orders.named_order_objects import missing_order
from sysexecution.stack_handler import completed_orders, fills
from sysexecution.stack_handler.fills import stackHandlerForFills
from sysproduction.data.broker import dataBroker
from sysproduction.data.currency_data import dataCurrency


NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def make_fill(*, exec_id="test.1", month="202612", quantity=1, report=None):
    return Fill(
        Contract(secType="FUT", lastTradeDateOrContractMonth=month),
        Execution(
            execId=exec_id,
            time=NOW,
            side="BOT",
            shares=1,
            cumQty=quantity,
            price=0.7444,
            avgPrice=0.744,
        ),
        report if report is not None else CommissionReport(),
        NOW,
    )


def fee_report(amount, exec_id="test.1"):
    return CommissionReport(execId=exec_id, currency="USD", commission=amount)


def translated_totals(*ib_fills):
    return extract_totals_from_fill_data(
        extract_fill_info(SimpleNamespace(fills=list(ib_fills)))
    )


@pytest.mark.parametrize(
    "report",
    [
        CommissionReport(),
        CommissionReport(commission=2.4, currency="USD"),
        CommissionReport(execId="wrong", commission=2.4, currency="USD"),
        CommissionReport(execId="test.1", commission=2.4),
    ],
)
def test_unreceived_or_mismatched_report_is_unknown_not_zero(report):
    totals = translated_totals(make_fill(report=report))
    assert totals[4] is None
    assert totals[5] == {"202612": 1}
    assert totals[2] == {"202612": 0.744}  # No price-average change.


@pytest.mark.parametrize("amount", [0.0, 2.4, -0.2])
def test_received_zero_positive_and_rebate_reports_are_known(amount):
    totals = translated_totals(make_fill(report=fee_report(amount)))
    assert [fee.value for fee in totals[4]] == [amount]


@pytest.mark.parametrize("second_month", ["202612", "202703"])
def test_every_partial_fill_and_spread_leg_requires_its_report(second_month):
    first = make_fill(report=fee_report(2.4))
    second = make_fill(exec_id="test.2", month=second_month, quantity=2)
    assert translated_totals(first, second)[4] is None
    second.commissionReport.execId = "test.2"
    second.commissionReport.currency = "USD"
    second.commissionReport.commission = 2.5
    assert sum(f.value for f in translated_totals(first, second)[4]) == 4.9


def test_parent_bag_report_is_not_required_or_double_counted():
    leg = make_fill(report=fee_report(2.4))
    bag = Fill(Contract(secType="BAG"), Execution(), CommissionReport(), NOW)
    assert [f.value for f in translated_totals(leg, bag)[4]] == [2.4]


def memory_stack(stack_class, order):
    """Exercise native stack methods, replacing only persistence primitives."""
    stack = stack_class(log=Mock())
    records = {order.order_id: order.as_dict()}
    stack.get_order_with_id_from_stack = lambda oid: (
        type(order).from_dict(deepcopy(records[oid]))
        if oid in records
        else missing_order
    )
    stack._get_list_of_all_order_ids = lambda: list(records)
    stack._change_order_on_stack_no_checking = lambda oid, value: records.__setitem__(
        oid, value.as_dict()
    )
    return stack


def make_handler(monkeypatch, *, quantity=1, spread=False):
    handler = object.__new__(stackHandlerForFills)
    handler._log = Mock()
    handler._data = SimpleNamespace(log=handler.log)
    dates = ["202609", "202612"] if spread else "202612"
    trade = [-1, 1] if spread else quantity
    handler._instrument_stack = memory_stack(
        instrumentOrderStackData,
        instrumentOrder(
            "test", "KRWUSD_mini", 0 if spread else quantity, order_id=1, children=[2]
        ),
    )
    handler._contract_stack = memory_stack(
        contractOrderStackData,
        contractOrder(
            "test", "KRWUSD_mini", dates, trade, order_id=2, parent=1, children=[3]
        ),
    )
    handler._broker_stack = memory_stack(
        brokerOrderStackData,
        brokerOrder("test", "KRWUSD_mini", dates, trade, order_id=3, parent=2),
    )
    positions = Mock()
    monkeypatch.setattr(fills, "updatePositions", lambda data: positions)
    archive = Mock()
    monkeypatch.setattr(completed_orders, "dataOrders", lambda data: archive)
    currency = SimpleNamespace(get_last_fx_rate_to_base=lambda ccy: 1.0)
    currency.currency_value_in_base = lambda value: dataCurrency.currency_value_in_base(
        currency, value
    )
    monkeypatch.setattr("sysproduction.data.broker.dataCurrency", lambda data: currency)
    broker = SimpleNamespace(data=handler.data)
    broker.calculate_total_commission_for_broker_order = lambda order: (
        dataBroker.calculate_total_commission_for_broker_order(broker, order)
    )
    monkeypatch.setattr(fills, "dataBroker", lambda data: broker)
    return handler, positions, archive, broker


def ib_execution(*, quantity=1):
    ib = IB()  # Disconnected: callbacks below are synthetic.
    contract = Contract(
        secType="FUT", symbol="KU", conId=1, lastTradeDateOrContractMonth="202612"
    )
    order = Order(
        orderId=11,
        clientId=7,
        permId=99,
        action="BUY",
        totalQuantity=quantity,
        orderType="MKT",
    )
    trade = Trade(contract, order)
    ib.wrapper.trades[ib.wrapper.orderKey(7, 11, 99)] = trade
    ib.wrapper.permId2Trade[99] = trade
    ib.wrapper.execDetails(
        -1,
        contract,
        Execution(
            execId="test.1",
            orderId=11,
            clientId=7,
            permId=99,
            time=NOW,
            side="BOT",
            shares=1,
            cumQty=1,
            price=0.7444,
            avgPrice=0.744,
        ),
    )
    wrapped = tradeWithContract(ibcontractWithLegs(contract), trade)

    def translated_order():
        result = create_broker_order_from_trade_with_contract(wrapped, "KRWUSD_mini")
        result.parent = 2
        return result

    return ib, translated_order


@pytest.mark.parametrize("fee", [0.0, 2.4, -0.2])
def test_delayed_report_updates_fee_without_reapplying_positions(monkeypatch, fee):
    handler, positions, archive, broker = make_handler(monkeypatch)
    ib, translated_order = ib_execution()
    broker.match_db_broker_order_to_order_from_brokers = Mock(
        side_effect=lambda stored: translated_order()
    )

    handler.apply_broker_order_fills_to_database(3, translated_order())
    stored = handler.broker_stack.get_order_with_id_from_stack(3)
    assert stored.fill == [1] and stored.commission is None and stored.active
    assert handler.contract_stack.get_order_with_id_from_stack(2).fill == [1]
    assert handler.instrument_stack.get_order_with_id_from_stack(1).fill == [1]
    positions.update_contract_position_table_with_contract_order.assert_called_once()
    positions.update_strategy_position_table_with_instrument_order.assert_called_once()
    archive.add_historic_orders_to_data.assert_not_called()

    # Unknown fees can persist through several sweeps without losing the order.
    handler.pass_fills_from_broker_to_broker_stack()
    assert handler.broker_stack.get_order_with_id_from_stack(3).active
    archive.add_historic_orders_to_data.assert_not_called()

    ib.wrapper.commissionReport(fee_report(fee))
    handler.pass_fills_from_broker_to_broker_stack()
    stored = handler.broker_stack.get_order_with_id_from_stack(3)
    assert stored.commission == fee and not stored.active
    assert broker.match_db_broker_order_to_order_from_brokers.call_count == 2
    positions.update_contract_position_table_with_contract_order.assert_called_once()
    positions.update_strategy_position_table_with_instrument_order.assert_called_once()
    archive.add_historic_orders_to_data.assert_called_once()
    assert archive.add_historic_orders_to_data.call_args.args[2][0].commission == fee

    # No new refresh or duplicate archiving once the order is inactive.
    handler.pass_fills_from_broker_to_broker_stack()
    assert broker.match_db_broker_order_to_order_from_brokers.call_count == 2


@pytest.mark.parametrize("quantity, has_fill", [(1, True), (2, True), (1, False)])
def test_explicit_cleanup_preserves_unknown_fee_and_remains_available(
    monkeypatch, quantity, has_fill
):
    handler, positions, archive, broker = make_handler(monkeypatch, quantity=quantity)
    ib, translated_order = ib_execution(quantity=quantity)
    if has_fill:
        handler.apply_broker_order_fills_to_database(3, translated_order())
    handler.handle_completed_orders(
        allow_partial_completions=True, allow_zero_completions=True
    )
    assert not handler.broker_stack.get_order_with_id_from_stack(3).active
    archive.add_historic_orders_to_data.assert_called_once()
    if has_fill:
        assert (
            archive.add_historic_orders_to_data.call_args.args[2][0].commission is None
        )
        handler.log.warning.assert_any_call(
            "Completing broker order with commission still unavailable",
            **handler.broker_stack.get_order_with_id_from_stack(3).log_attributes(),
        )


def test_known_commission_keeps_existing_full_fill_shortcut(monkeypatch):
    handler, positions, archive, broker = make_handler(monkeypatch)
    ib, translated_order = ib_execution()
    ib.wrapper.commissionReport(fee_report(0.0))
    handler.apply_broker_order_fills_to_database(3, translated_order())
    broker.match_db_broker_order_to_order_from_brokers = Mock()
    handler.apply_broker_fill_from_broker_to_broker_database(3)
    broker.match_db_broker_order_to_order_from_brokers.assert_not_called()
    archive.add_historic_orders_to_data.assert_called_once()


@pytest.mark.parametrize("quantity", [0, -1, 2])
def test_commission_refresh_cannot_replace_recorded_fill_with_different_quantity(
    monkeypatch, quantity
):
    handler, positions, archive, broker = make_handler(monkeypatch)
    ib, translated_order = ib_execution()
    handler.apply_broker_order_fills_to_database(3, translated_order())
    before = handler.broker_stack.get_order_with_id_from_stack(3).as_dict()
    incomplete = brokerOrder(
        "test",
        "KRWUSD_mini",
        "202612",
        quantity,
        fill=[quantity],
        commission=2.4,
        filled_price=0.75,
    )
    broker.match_db_broker_order_to_order_from_brokers = Mock(return_value=incomplete)
    handler.pass_fills_from_broker_to_broker_stack()
    assert handler.broker_stack.get_order_with_id_from_stack(3).as_dict() == before
    positions.update_contract_position_table_with_contract_order.assert_called_once()
    positions.update_strategy_position_table_with_instrument_order.assert_called_once()
    archive.add_historic_orders_to_data.assert_not_called()
    handler.log.warning.assert_called_once()


def test_commission_only_refresh_preserves_recorded_price_and_time(monkeypatch):
    handler, positions, archive, broker = make_handler(monkeypatch)
    ib, translated_order = ib_execution()
    handler.apply_broker_order_fills_to_database(3, translated_order())
    before = handler.broker_stack.get_order_with_id_from_stack(3)
    ib.wrapper.commissionReport(fee_report(2.4))
    changed = translated_order()
    changed.fill_order(changed.fill, 0.75, datetime(2026, 9, 23))
    changed.leg_filled_price = [0.75]
    broker.match_db_broker_order_to_order_from_brokers = Mock(return_value=changed)
    handler.pass_fills_from_broker_to_broker_stack()
    after = handler.broker_stack.get_order_with_id_from_stack(3)
    assert after.commission == 2.4
    assert after.filled_price == before.filled_price
    assert after.leg_filled_price == before.leg_filled_price
    assert after.fill_datetime == before.fill_datetime
    assert after.fill == before.fill
    assert not after.active


def test_roll_waits_for_both_leg_reports_without_delaying_contract_positions(
    monkeypatch,
):
    handler, positions, archive, broker = make_handler(monkeypatch, spread=True)
    legs = [
        make_fill(month="202609", report=fee_report(2.46)),
        make_fill(month="202612", exec_id="test.2"),
    ]
    legs[0].execution.side = "SLD"
    for index, leg in enumerate(legs):
        leg.contract.conId = index + 1
    bag = Contract(
        secType="BAG",
        comboLegs=[
            ComboLeg(conId=1, ratio=1, action="SELL"),
            ComboLeg(conId=2, ratio=1, action="BUY"),
        ],
    )
    trade = Trade(
        bag, Order(action="BUY", totalQuantity=1, orderType="MKT"), fills=legs
    )
    wrapped = tradeWithContract(
        ibcontractWithLegs(bag, [f.contract for f in legs]), trade
    )

    def translated_order():
        result = create_broker_order_from_trade_with_contract(wrapped, "KRWUSD_mini")
        result.parent = 2
        return result

    broker.match_db_broker_order_to_order_from_brokers = Mock(
        side_effect=lambda stored: translated_order()
    )
    handler.apply_broker_order_fills_to_database(3, translated_order())
    assert handler.contract_stack.get_order_with_id_from_stack(2).fill == [-1, 1]
    assert handler.broker_stack.get_order_with_id_from_stack(3).commission is None
    assert handler.broker_stack.get_order_with_id_from_stack(3).active
    positions.update_contract_position_table_with_contract_order.assert_called_once()
    positions.update_strategy_position_table_with_instrument_order.assert_not_called()
    archive.add_historic_orders_to_data.assert_not_called()

    legs[1].commissionReport.execId = "test.2"
    legs[1].commissionReport.currency = "USD"
    legs[1].commissionReport.commission = 2.46
    handler.pass_fills_from_broker_to_broker_stack()
    assert handler.broker_stack.get_order_with_id_from_stack(3).commission == 4.92
    assert not handler.broker_stack.get_order_with_id_from_stack(3).active
    positions.update_contract_position_table_with_contract_order.assert_called_once()
    positions.update_strategy_position_table_with_instrument_order.assert_not_called()
    archive.add_historic_orders_to_data.assert_called_once()
