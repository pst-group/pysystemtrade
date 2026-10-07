# Review notes (quantum-like fork)

Review of `pst-group/pysystemtrade` `develop` at `326b5d40` (merge of release 1.8.3), on behalf of Amir Vahid (`@quantum-like`). Branch `review/fixes` is that commit plus the fixes below. `develop` on this fork was not moved.

Scope: static reading of the IB client, order/fill path, stack handler, process control, and the data/quant code that feeds production, plus the existing pytest suite. No Interactive Brokers connection was available, so nothing here was checked against a live or paper gateway.

These fixes do not change config defaults, private config conventions, or control schedules. Where a happy-path 1.8.3 paper run already used the module-level order-type singletons and same-length quantities, behaviour is unchanged. The IB fixes matter on the failure and reconstruction paths described in the table.

## Commits

| SHA | File | Category | Why | Could affect a 1.8.3 IB paper/production run? |
|---|---|---|---|---|
| `cd9efe7d` | `sysbrokers/IB/client/ib_orders_client.py` | IB orders | Limit, stop, snap and adaptive types were matched with `is`. `brokerOrderType` compares by string, so a new instance (Mongo `from_dict`, or any constructor other than the module singleton) was "unrecognised" and not built. Market already used `==`. | Yes, for a non-singleton limit/stop/snap/adaptive type. In-process `original_best` and market algos pass the singletons, so those submissions already matched. |
| `353ab02d` | `sysbrokers/IB/client/ib_orders_client.py` | IB orders | A failed `_build_ib_order` (around line 126) returned `missing_order` and then passed that sentinel to `placeOrder` / `whatIfOrder`. | Yes, on that failure path only (unknown type, or limit/stop with no price). A successful submit is unchanged. Stops an API exception from replacing the `missing_order` return the stack handler already handles. |
| `05e0511b` | `sysexecution/order_stacks/order_stack.py` | Execution | `zero_out` / `deactivate_order` (lines 346 and 370) formatted an error string with no placeholder, so a missing order raised `TypeError` instead of `missingOrder`. | Yes, only if cleanup touches an id that is already gone (rollback, crash recovery, end-of-day removal). Normal fills are unchanged. |
| `ca4a190b` | `syscontrol/run_process.py` | Process control | The unknown-status branch (line 236) called `.log` on the `process_running` token. The wait-path check just below already logs on the process logger and raises. | Only if process control returns something other than `success`, `process_running`, `process_stop`, or `process_no_run`. Today's `check_if_okay_to_start_process` does not do that. |
| `58c68a4d` | `sysobjects/rolls.py` | Data | `rollParameters.__eq__` compared `priced_rollcycle` to itself (line 234), so a different priced cycle still compared equal. | No direct effect on a running session. Matters only where roll-parameter objects are compared. |
| `3e4fd4fb` | `sysexecution/trade_qty.py` | Execution | `==` and the overfill check used `zip()`, so `tradeQuantity([1, -1]) == tradeQuantity([1])` was true and a one-leg fill passed against a spread. Completion uses `fill == trade`. | Same-length quantities (normal outright and complete spread fills) are unchanged. A shorter leg list no longer looks fully filled or within size. |
| `0ed509cd` | `sysexecution/stack_handler/spawn_children_from_instrument_orders.py` | Production logging | A reducing passive roll that stays in the current contract (line 352) logged "next contract" and printed the next id. The order already used the current contract. | No change to which contract is traded. The debug line during a passive roll now names that contract. |
| `30921bfc` | `sysdata/mongodb/mongo_IB_client_id.py` | IB client id | The tracker defined `_repr__` instead of `__repr__`, so the Mongo collection never appeared in the object's text. | No. Lock allocation is unchanged. |

## Questions for maintainers

Not changed, because I was not sure they are unintentional, or because changing them would change live behaviour.

1. `orderStackData.is_completed` returns `True` for every id, including a missing one, as soon as `allow_zero_completions` is true (`sysexecution/order_stacks/order_stack.py` line 227), before the missing-order check. `safe_stack_removal` passes that flag. Is the end-of-day sweep intentionally "treat everything as complete"?

2. `_change_order_on_stack` logs "Can't change order … as inactive" and then writes the change anyway (line 440). The method comment says it does not enforce "active". Should an inactive order be immutable, or is the warning only advisory so a late fill can still land?

3. `list_of_orders_not_yet_cancelled` treats `missingOrder` as cancelled (`sysexecution/stack_handler/cancel_and_modify.py` lines 99–102). The comment says this keeps previous behaviour. A working IB order that can no longer be matched then drops out of the uncancelled list during end-of-day removal. Is that still what you want?

4. `fillExceedsTrade` is logged as a warning and the fill is ignored (`sysexecution/stack_handler/fills.py` lines 84–89), with the note that it will hopefully go away. Is that still an IB glitch that should not page someone, even though the stack position then lags the broker until an external break fires?

5. A position that raises `missingContract` is skipped with no log (`sysbrokers/IB/ib_contract_position_data.py` lines 59–64). Instrument lookup always uses `allow_expired=False` (`sysbrokers/IB/client/ib_client.py` lines 111–114), so a non-zero position on an expired month can disappear from the broker position list. Should that be a critical break instead of a silent skip? Zero positions also use this path, so a blanket critical would be noisy.

6. Open combo orders resolve each leg `conId` with `includeExpired=False` (`ib_orders_client.py` `add_contract_legs_to_order`). One missing leg aborts the whole open-order sync. Should that lookup include expired contracts?

7. Limit changes are allowed only in status `Submitted` (`sysbrokers/IB/ib_orders.py` lines 511–517). IB often leaves a working order in `PreSubmitted` (outside RTH, or briefly after submit). `original_best` catches `orderCannotBeModified` and keeps the old limit. Was `Submitted`-only chosen because modifying `PreSubmitted` caused duplicate or rejected orders?

8. `resolve_order_type` only maps `MKT` (`sysbrokers/IB/ib_translate_broker_order_objects.py` line 527). `LMT`, stop, snap and adaptive come back as `""` and are stored as a bare string on the order built from the IB trade. Anything that then calls `.as_string()` or `==` against a `brokerOrderType` will throw. Is that object only used for fill quantities, where the type string is ignored?

9. Account value sums every currency row, and the comment in `sysproduction/data/broker.py` (`get_total_capital_value_in_base_currency`) says this assumes no double counting. IB `accountSummary` often includes both the real currency and `BASE` for `NetLiquidation`. There is no `BASE` filter. If both are present, capital is doubled, or the `BASE` FX lookup (`BASE` + base currency) throws and the capital update dies. What does a current paper account summary actually contain? I would not change this without that payload: some accounts may report only `BASE`.

10. `check_order_is_cancelled_given_control_object` treats every `DoneStates` value except `Filled` as cancelled (`ib_orders.py` lines 461–463). That includes `Inactive`. Should a rejected/inactive order follow the same path as a cancel?

11. `sysproduction/startup.py` calls `finish_all_processes()` and clears the "running" flag without looking at the stored PID. That is the right boot-time clear after a crash, and the monitor has its own PID check. If `startup` runs while `run_stack_handler` is still alive, cron can start a second handler. Is `startup` documented as "machine boot only, nothing else is up"?

12. `get_time_difference` (`sysbrokers/IB/ib_trading_hours.py` lines 129–150) is a fixed offset table and does not handle DST. An IB `timeZoneId` that is not in the table raises, and that contract's hours come back empty. Newer ids such as `America/Chicago` are not listed (`US/Central` is). Is the conservative table still intended, and should an unknown zone be logged with the raw id?

13. `calculate_cost_deflator` scales the whole history by the final sample volatility (`syscore/pandas/strategy_functions.py` lines 164–172); the comment says this is crude and does not matter. `seriesOfStdevEstimates.shocked` backfills early quantiles from later data (`sysquant/estimators/stdev_estimator.py` lines 55–64). I left both alone. Please confirm they are not inputs to the live production position run.

14. `sysbrokers/IB/client/ib_client.py` uses `datetime` and `Union` without importing them. They arrive today via `from syslogging.logger import *` (which re-exports them from `pst_logger`). Worth an explicit import before that star import is tightened. I did not change it because the import succeeds as the code stands.

15. `_build_ib_order` defaults `account_id` to `""`, then sets `ib_order.account` because `""` is not `arg_not_supplied`. `broker_submit_order` passes the account through, and the algo sets `broker_account` from config before submit, so a normal paper run is fine. Was the default meant to be `arg_not_supplied`?

16. `adjust_to_price_series` stops before the last row of the approximate calendar because that row has no following contract (`sysinit/futures/build_roll_calendars.py` `_get_local_data_for_row_number`). The multiple-price path documents a phantom row for this. I treated that as the supported calling convention, not a bug. Callers that do not append a phantom will drop the last roll.

## Test suite

`pytest` on Python 3.12.3, with the pins from `pyproject.toml` (pandas 2.1.3, numpy 1.26.4, ib_async 2.1.0):

`101 passed, 40 skipped, 3 xfailed, 11 warnings in 38.20s`

No failures. Skips are the example-system tests that are marked skip, not errors. Warnings are `pytz`/`bson` `utcfromtimestamp` deprecations and a multiprocessing fork warning in the optimisation test. Nothing in that run was caused by these commits. Black 23.11.0 reports the touched files unchanged.

## What I could not check

- Any live or paper IB Gateway session: connect, reconnect, client-id locks in Mongo, pacing, historical bars, what-if commissions, or real order status (`PreSubmitted` vs `Submitted`).
- End-of-end stack handler against Mongo (order round-trip, fill propagation, roll state, capital update).
- Whether this account's `accountSummary` includes a `BASE` row next to the trading currency.
- Whether commission reports still arrive as `UNSET_DOUBLE` before the real figure, and whether that value is briefly stored on the order.
- Private config, `control_config` schedules, and the production process timetable. Those were left exactly as in 1.8.3.
- Look-ahead questions in (13) against the YAML actually used for the live system run.
