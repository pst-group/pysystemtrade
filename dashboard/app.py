from flask import Flask, g, render_template, request
from werkzeug.local import LocalProxy

from syscore.genutils import str2Bool

from syscontrol.list_running_pids import describe_trading_server_login_data

from sysdata.config.control_config import get_control_config

from sysdata.data_blob import dataBlob

from sysobjects.production.roll_state import (
    RollState,
)


from sysproduction.reporting.api import reportingApi

from sysproduction.data.broker import dataBroker
from sysproduction.data.control_process import dataControlProcess
from sysproduction.data.capital import dataCapital
from sysproduction.interactive_update_roll_status import (
    modify_roll_state,
    setup_roll_data_with_state_reporting,
)
from sysproduction.reporting.data.rolls import rollingAdjustedAndMultiplePrices

import asyncio
import json
import pandas as pd

app = Flask(__name__)


def get_data():
    if not hasattr(g, "data"):
        g.data = dataBlob(log_name="dashboard")
    return g.data


data = LocalProxy(get_data)


def get_reporting_api():
    return reportingApi(data, calendar_days_back=1)


reporting_api = LocalProxy(get_reporting_api)


@app.teardown_appcontext
def cleanup_data(exception):
    if hasattr(g, "data"):
        g.data.close()
        del g.data


def dict_of_df_to_dict(d, orient):
    return {
        k: json.loads(v.to_json(orient=orient, date_format="iso"))
        if isinstance(v, pd.DataFrame)
        else v
        for k, v in d.items()
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/capital")
def capital():
    capital_data = dataCapital(data)
    capital_series = capital_data.get_series_of_all_global_capital()
    now = capital_series.iloc[-1]["Actual"]
    yesterday = capital_series.last("1D").iloc[0]["Actual"]
    return {"now": now, "yesterday": yesterday}


@app.route("/costs")
def costs():
    costs = {
        "table_of_SR_costs": reporting_api.table_of_sr_costs().Body,
        "slippage": reporting_api.table_of_slippage_comparison().Body,
    }
    costs = dict_of_df_to_dict(costs, orient="index")
    return costs


@app.route("/forex")
def forex():
    asyncio.set_event_loop(asyncio.new_event_loop())
    data_broker = dataBroker(data)
    return data_broker.broker_fx_balances()


@app.route("/liquidity")
def liquidity():
    liquidity_data = reporting_api.liquidity_data().to_dict(orient="index")
    return liquidity_data


@app.route("/pandl")
def pandl():
    pandl_data = {}
    pandl_data["pandl_for_instruments_across_strategies"] = (
        reporting_api.table_pandl_for_instruments_across_strategies().Body.to_dict(
            orient="records"
        )
    )
    pandl_data["strategies"] = (
        reporting_api.table_strategy_pandl_and_residual().Body.to_dict(orient="records")
    )
    pandl_data["sector_pandl"] = reporting_api.table_sector_pandl().Body.to_dict(
        orient="records"
    )

    return pandl_data


@app.route("/processes")
def processes():
    asyncio.set_event_loop(asyncio.new_event_loop())

    data_control = dataControlProcess(data)
    data_control.check_if_pid_running_and_if_not_finish_all_processes()

    retval = {
        "config": reporting_api.table_of_control_config_list_for_all_processes().Body,
        "control": reporting_api.table_of_control_status_list_for_all_processes().Body,
        "process": reporting_api.table_of_process_status_list_for_all_processes().Body,
        # "method_data": reporting_api.table_of_control_data_list_for_all_methods().Body,
        "price": reporting_api.table_of_last_price_updates().Body.reset_index(
            drop=False
        ),
    }
    retval = dict_of_df_to_dict(retval, orient="index")

    allprocess = {}
    for k in retval["config"].keys():
        allprocess[k] = {
            **retval["config"].get(k, {}),
            **retval["control"].get(k, {}),
            **retval["process"].get(k, {}),
        }
    retval["process"] = allprocess
    retval.pop("control")
    retval["config"] = {
        "monitor": describe_trading_server_login_data(),
        "mongo": f"{data.mongo_db.host}:{data.mongo_db.port} - {data.mongo_db.database_name}",
        "ib": f"{data.ib_conn._ib_connection_config['ipaddress']}:{data.ib_conn._ib_connection_config['port']}",
    }

    return retval


@app.route("/reconcile")
def reconcile():
    retval = {"gateway_ok": True}
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
        retval["optimal"] = reporting_api.table_of_optimal_positions().Body
        retval["ib"] = reporting_api.table_of_ib_positions().Body
        retval["my"] = reporting_api.table_of_my_positions().Body
        # retval["trades_from_db"]= reporting_api.table_of_my_recent_trades_from_db().Body
        # retval["trades_from_ib"]= reporting_api.table_of_recent_ib_trades().Body

        # Reindex the position dataframes
        retval["ib"].set_index(
            ["instrument_code", "contract_date"], inplace=True, drop=False
        )
        retval["my"].set_index(
            ["instrument_code", "contract_date"], inplace=True, drop=False
        )
    except:
        # IB gateway connection failed
        retval["gateway_ok"] = False
    if "optimal" in retval["optimal"].columns:
        # Force the underlying class to do the optimal position calc for us
        retval["optimal"]["optimal"] = retval["optimal"]["optimal"].astype(str)
    retval = dict_of_df_to_dict(retval, orient="index")
    return retval


@app.route("/rolls")
def rolls():
    rolls = reporting_api.table_of_roll_data().Body
    report = json.loads(rolls.to_json(orient="index"))

    for instrument in rolls.index:
        allowable = setup_roll_data_with_state_reporting(data, instrument)
        report[instrument]["allowable"] = allowable.allowable_roll_states_as_list_of_str

    return report


@app.route("/rolls", methods=["POST"])
def rolls_post():
    instrument = request.form["instrument"]
    new_state = RollState[request.form["state"]]

    if new_state == RollState.Roll_Adjusted and request.form["confirmed"] != "true":
        # Send back the adjusted prices for checking
        number_to_return = 6
        rolling = rollingAdjustedAndMultiplePrices(data, instrument)
        # We need to convert values to strings because there are
        # sometimes NaNs which are not valid json
        current_multiple = {
            str(k): {kk: str(vv) for kk, vv in v.items()}
            for k, v in rolling.current_multiple_prices.tail(number_to_return)
            .to_dict(orient="index")
            .items()
        }
        # There can sometimes be more than one new value, so get 5 more to be sure
        new_multiple = {
            str(k): {kk: str(vv) for kk, vv in v.items()}
            for k, v in rolling.updated_multiple_prices.tail(number_to_return + 5)
            .to_dict(orient="index")
            .items()
        }
        current_adjusted = {
            str(k): round(v, 2)
            for k, v in rolling.current_adjusted_prices.tail(number_to_return)
            .to_dict()
            .items()
        }
        new_adjusted = {
            str(k): round(v, 2)
            for k, v in rolling.new_adjusted_prices.tail(number_to_return + 5)
            .to_dict()
            .items()
        }
        single = {
            k: {"current": current_adjusted[k], "new": new_adjusted[k]}
            for k in current_adjusted.keys()
        }
        multiple = {
            k: {"current": current_multiple[k], "new": new_multiple[k]}
            for k in current_adjusted.keys()
        }
        new_date = list(new_adjusted.keys())[-1]
        single[new_date] = {"new": new_adjusted[new_date]}
        multiple[new_date] = {"new": new_multiple[new_date]}
        prices = {"single": single, "multiple": multiple}
        return prices

    roll_data = setup_roll_data_with_state_reporting(data, instrument)
    modify_roll_state(
        data, instrument, roll_data.original_roll_status, new_state, False
    )
    roll_data = setup_roll_data_with_state_reporting(data, instrument)
    return {
        "new_state": request.form["state"],
        "allowable": roll_data.allowable_roll_states_as_list_of_str,
    }


@app.route("/risk")
def risk():
    risk_data = {
        "correlations": reporting_api.table_of_correlations().Body,
        "strategy_risk": reporting_api.table_of_strategy_risk().Body,
        "instrument_risk": reporting_api.table_of_instrument_risk().Body,
    }
    risk_data = dict_of_df_to_dict(risk_data, "index")
    return risk_data


@app.route("/trades")
def trades():
    return_data = {}

    # Sometimes there are not things in the body so ignore them if not
    try:
        return_data["overview"] = reporting_api.table_of_orders_overview().Body
    except:
        pass
    try:
        return_data["delays"] = reporting_api.table_of_order_delays().Body
    except:
        pass
    try:
        return_data["raw_slippage"] = reporting_api.table_of_raw_slippage().Body
    except:
        pass
    try:
        return_data["vol_slippage"] = reporting_api.table_of_vol_slippage().Body
    except:
        pass
    try:
        return_data["cash_slippage"] = reporting_api.table_of_cash_slippage().Body
    except:
        pass

    return_data = dict_of_df_to_dict(return_data, orient="index")
    return return_data


@app.route("/strategy")
def strategy():
    return {}


def visible_on_lan() -> bool:
    config = get_control_config()
    visible = config.get_element_or_default("dashboard_visible_on_lan", False)

    visible = str2Bool(visible)

    return visible


if __name__ == "__main__":
    visible = visible_on_lan()
    if visible:
        data = dataBlob()
        data.log.warning(
            "Starting dashboard with web page visible to all - security implications!!!!"
        )
        app.run(
            threaded=True,
            use_debugger=False,
            use_reloader=False,
            passthrough_errors=True,
            host="0.0.0.0",
        )

    else:
        app.run(
            threaded=True,
            use_debugger=False,
            use_reloader=False,
            passthrough_errors=True,
        )
