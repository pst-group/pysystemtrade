import pandas as pd
import numpy as np
import datetime

from collections import namedtuple

from syscore.exceptions import missingData
from sysproduction.reporting.reporting_functions import table, header, body_text
from syscore.dateutils import ROOT_BDAYS_INYEAR, from_marker_string_to_datetime
from sysproduction.data.positions import diagPositions

from sysobjects.production.backtest_storage import interactiveBacktest
from sysobjects.production.tradeable_object import instrumentStrategy


def report_system_classic(data, backtest: interactiveBacktest) -> list:
    """

    :param strategy_name: str
    :param data: dataBlob
    :param backtest: dataBacktest object populated with a specific backtest
    :return: list of report format type objects
    """

    strategy_name = backtest.strategy_name
    timestamp = backtest.timestamp

    format_output = []
    report_header = header(
        "Strategy report for %s backtest timestamp %s produced at %s"
        % (strategy_name, timestamp, str(datetime.datetime.now()))
    )
    format_output.append(report_header)

    format_output = report_system_classic_no_header_or_footer(
        data, backtest=backtest, format_output=format_output
    )

    format_output.append(body_text("End of report for %s" % strategy_name))

    return format_output


def report_system_classic_no_header_or_footer(
    data, backtest: interactiveBacktest, format_output: list
) -> list:
    """

    :param strategy_name: str
    :param data: dataBlob
    :param backtest: dataBacktest object populated with a specific backtest
    :return: list of report format type objects
    """
    risk_scaling_str = risk_scaling_string(backtest)
    format_output.append(body_text(risk_scaling_str))

    # Cash target
    cash_target_dict = backtest.system.positionSize.get_vol_target_dict()
    cash_target_text = body_text("\nVol target calculation %s\n" % cash_target_dict)

    format_output.append(cash_target_text)

    # Vol calc
    vol_calc_df = get_stage_breakdown_over_codes(
        backtest,
        method_list=[daily_returns_vol, daily_denom_price, rawdata_daily_perc_vol],
    )
    vol_calc_df["annual % vol"] = vol_calc_df["Daily % vol"] * ROOT_BDAYS_INYEAR
    vol_calc_df_rounded = vol_calc_df.round(4)
    vol_calc_table = table("Vol calculation", vol_calc_df_rounded)
    format_output.append(vol_calc_table)

    # Subsystem position table
    subystem_positions_df = get_stage_breakdown_over_codes(
        backtest,
        method_list=[
            get_block_value,
            get_price_volatility,
            get_instrument_ccy_vol,
            get_fx_rate,
            get_instrument_value_vol,
            get_daily_cash_vol_target,
            get_vol_scalar,
            get_combined_forecast,
            get_subsystem_position,
        ],
    )
    subystem_positions_df_rounded = subystem_positions_df.round(2)
    subystem_positions_table = table(
        "Subsystem position", subystem_positions_df_rounded
    )
    format_output.append(subystem_positions_table)

    # Portfolio position table: ss position, instr weight, IDM, position
    # required
    portfolio_positions_df = get_stage_breakdown_over_codes(
        backtest,
        method_list=[
            get_subsystem_position,
            get_instrument_weights,
            get_idm,
            get_required_portfolio_position,
        ],
    )
    portfolio_positions_df_rounded = portfolio_positions_df.round(3)
    portfolio_positions_table = table(
        "Portfolio positions", portfolio_positions_df_rounded
    )

    format_output.append(portfolio_positions_table)

    # position diags
    position_diags_df = calc_position_diags(
        portfolio_positions_df, subystem_positions_df
    )

    position_diags_df_rounded = position_diags_df.round(2)
    position_diags_table = table("Position diags", position_diags_df_rounded)

    format_output.append(position_diags_table)

    # Position vs buffer table: position required, buffers, actual position
    versus_buffers_df = get_stage_breakdown_over_codes(
        backtest,
        method_list=[
            get_required_portfolio_position,
            get_lower_buffer,
            get_upper_buffer,
        ],
    )

    instrument_code_list = versus_buffers_df.index
    timestamp_positions = get_position_at_timestamp_df_for_instrument_code_list(
        backtest, data, instrument_code_list
    )
    current_positions = get_current_position_df_for_instrument_code_list(
        backtest, data, instrument_code_list
    )
    versus_buffers_and_positions_df = pd.concat(
        [versus_buffers_df, timestamp_positions, current_positions], axis=1
    )
    versus_buffers_and_positions_df_rounded = versus_buffers_and_positions_df.round(1)
    versus_buffers_and_positions_table = table(
        "Positions vs buffers", versus_buffers_and_positions_df_rounded
    )

    format_output.append(versus_buffers_and_positions_table)

    # Forecast weights
    forecast_weights_df = get_forecast_matrix_over_code(
        backtest, stage_name="combForecast", method_name="get_forecast_weights"
    )
    forecast_weights_df_as_perc = forecast_weights_df * 100
    forecast_weights_df_as_perc_rounded = forecast_weights_df_as_perc.round(1)
    forecast_weights_table = table(
        "Forecast weights", forecast_weights_df_as_perc_rounded
    )
    format_output.append(forecast_weights_table)

    unweighted_forecasts_df = get_forecast_matrix(
        backtest, stage_name="forecastScaleCap", method_name="get_capped_forecast"
    )

    # Weighted forecast
    weighted_forecasts_df = forecast_weights_df * unweighted_forecasts_df
    weighted_forecast_rounded = weighted_forecasts_df.round(1)
    weighted_forecast_table = table("Weighted forecasts", weighted_forecast_rounded)
    format_output.append(weighted_forecast_table)

    unweighted_forecasts_df_rounded = unweighted_forecasts_df.round(1)
    unweighted_forecasts_table = table(
        "Unweighted forecasts", unweighted_forecasts_df_rounded
    )
    format_output.append(unweighted_forecasts_table)

    return format_output


def get_forecast_matrix(
    data_backtest, stage_name="combForecast", method_name="get_capped_forecast"
):
    instrument_codes = data_backtest.system.get_instrument_list()
    trading_rules = data_backtest.system.rules.trading_rules()
    trading_rule_names = list(trading_rules.keys())

    datetime_cutoff = from_marker_string_to_datetime(data_backtest.timestamp)

    value_dict = {}
    for rule_name in trading_rule_names:
        value_dict[rule_name] = []
        for instrument_code in instrument_codes:
            stage = getattr(data_backtest.system, stage_name)
            method = getattr(stage, method_name)
            value = (
                method(instrument_code, rule_name).ffill()[:datetime_cutoff].iloc[-1]
            )
            value_dict[rule_name].append(value)

    value_df = pd.DataFrame(value_dict, index=instrument_codes)

    return value_df


def get_forecast_matrix_over_code(
    data_backtest, stage_name="combForecast", method_name="get_forecast_weights"
):
    instrument_codes = data_backtest.system.get_instrument_list()
    trading_rules = data_backtest.system.rules.trading_rules()
    trading_rule_names = list(trading_rules.keys())

    datetime_cutoff = from_marker_string_to_datetime(data_backtest.timestamp)

    value_dict = {}
    for instrument_code in instrument_codes:
        stage = getattr(data_backtest.system, stage_name)
        method = getattr(stage, method_name)
        values = method(instrument_code).ffill()[:datetime_cutoff]

        if not values.empty:
            value_row = values.iloc[-1]
            values_by_rule = [
                value_row.get(rule_name, np.nan) for rule_name in trading_rule_names
            ]
        else:
            values_by_rule = [np.nan] * len(trading_rule_names)

        value_dict[instrument_code] = values_by_rule

    value_df = pd.DataFrame(value_dict, index=trading_rule_names)
    value_df = value_df.transpose()

    return value_df


# ss position, instr weight, IDM, position required

configForMethod = namedtuple(
    "ConfigForMethod",
    [
        "stage_name",
        "method_name",
        "name",
        "global_bool",
        "requires_code_bool",
        "col_selector",
        "scalar_bool",
    ],
)

daily_returns_vol = configForMethod(
    "rawdata", "daily_returns_volatility", "Daily return vol", False, True, None, False
)

daily_denom_price = configForMethod(
    "rawdata", "daily_denominator_price", "Price", False, True, None, False
)

rawdata_daily_perc_vol = configForMethod(
    "rawdata",
    "get_daily_percentage_volatility",
    "Daily % vol",
    False,
    True,
    None,
    False,
)

get_combined_forecast = configForMethod(
    "positionSize",
    "get_combined_forecast",
    "Combined forecast",
    False,
    True,
    None,
    False,
)

get_block_value = configForMethod(
    "positionSize", "get_block_value", "Block_Value", False, True, None, False
)

get_price_volatility = configForMethod(
    "positionSize",
    "get_price_volatility",
    "Daily price % vol",
    False,
    True,
    None,
    False,
)

get_fx_rate = configForMethod(
    "positionSize", "get_fx_rate", "FX", False, True, None, False
)

get_instrument_ccy_vol = configForMethod(
    "positionSize", "get_instrument_currency_vol", "ICV", False, True, None, False
)

get_instrument_value_vol = configForMethod(
    "positionSize", "get_instrument_value_vol", "IVV", False, True, None, False
)

get_daily_cash_vol_target = configForMethod(
    "positionSize",
    "get_daily_cash_vol_target",
    "Daily Cash Vol Tgt",
    False,
    False,
    None,
    True,
)

get_vol_scalar = configForMethod(
    "positionSize",
    "get_average_position_at_subsystem_level",
    "Vol Scalar",
    False,
    True,
    None,
    False,
)

get_subsystem_position = configForMethod(
    "positionSize",
    "get_subsystem_position",
    "subsystem_position",
    False,
    True,
    None,
    False,
)

get_instrument_weights = configForMethod(
    "portfolio", "get_instrument_weights", "instr weight", False, False, None, False
)

get_idm = configForMethod(
    "portfolio",
    "get_instrument_diversification_multiplier",
    "IDM",
    True,
    False,
    None,
    False,
)

get_required_portfolio_position = configForMethod(
    "portfolio", "get_notional_position", "Notional position", False, True, None, False
)

get_lower_buffer = configForMethod(
    "portfolio",
    "get_actual_buffers_for_position",
    "Lower buffer",
    False,
    True,
    "bot_pos",
    False,
)

get_upper_buffer = configForMethod(
    "portfolio",
    "get_actual_buffers_for_position",
    "Upper buffer",
    False,
    True,
    "top_pos",
    False,
)


def get_stage_breakdown_over_codes(backtest: interactiveBacktest, method_list: list):
    value_dict = {}
    for config_for_method in method_list:
        value_dict[config_for_method.name] = (
            get_list_of_values_by_instrument_for_config(backtest, config_for_method)
        )

    instrument_codes = backtest.system.get_instrument_list()
    value_df = pd.DataFrame(value_dict, index=instrument_codes)

    return value_df


def get_list_of_values_by_instrument_for_config(backtest, config_for_method):
    instrument_codes = backtest.system.get_instrument_list()
    datetime_cutoff = from_marker_string_to_datetime(backtest.timestamp)

    stage = getattr(backtest.system, config_for_method.stage_name)
    method = getattr(stage, config_for_method.method_name)

    if config_for_method.global_bool:
        # Same value regardless of instrument
        value = method().ffill()[:datetime_cutoff].iloc[-1]
        if config_for_method.col_selector is not None:
            value = value[config_for_method.col_selector]
        value_list = [value] * len(instrument_codes)

        return value_list

    if config_for_method.requires_code_bool:
        # call for each code
        if config_for_method.col_selector is not None:
            value_list = [
                method(instrument_code)
                .ffill()[:datetime_cutoff]
                .iloc[-1][config_for_method.col_selector]
                for instrument_code in instrument_codes
            ]
        else:
            value_list = [
                method(instrument_code).ffill()[:datetime_cutoff].iloc[-1]
                for instrument_code in instrument_codes
            ]

        return value_list

    if config_for_method.scalar_bool:
        value = method()
        value_list = [value] * len(instrument_codes)

        return value_list

    # get dataframe

    value_row = method().ffill()[:datetime_cutoff].iloc[-1]
    value_list = [
        value_row.get(instrument_code, np.nan) for instrument_code in instrument_codes
    ]

    return value_list


def get_current_position_df_for_instrument_code_list(
    data_backtest, data, instrument_code_list
):
    position_list = [
        get_current_position_for_instrument_code(data_backtest, data, instrument_code)
        for instrument_code in instrument_code_list
    ]
    position_df = pd.DataFrame(
        position_list, index=instrument_code_list, columns=["Current position"]
    )
    return position_df


def get_position_at_timestamp_df_for_instrument_code_list(
    data_backtest, data, instrument_code_list
):
    position_list = [
        get_position_for_instrument_code_at_timestamp(
            data_backtest, data, instrument_code
        )
        for instrument_code in instrument_code_list
    ]
    position_df = pd.DataFrame(
        position_list, index=instrument_code_list, columns=["Position at timestamp"]
    )
    return position_df


def get_position_for_instrument_code_at_timestamp(data_backtest, data, instrument_code):
    diag_positions = diagPositions(data)

    strategy_name = data_backtest.strategy_name
    instrument_strategy = instrumentStrategy(
        strategy_name=strategy_name, instrument_code=instrument_code
    )

    try:
        positions_over_time = (
            diag_positions.get_position_series_for_instrument_strategy(
                instrument_strategy
            )
        )
    except missingData:
        return np.nan

    datetime_cutoff = from_marker_string_to_datetime(data_backtest.timestamp)
    positions_over_time_ffill = positions_over_time.ffill()
    positions_before_cutoff = positions_over_time_ffill[:datetime_cutoff]

    if len(positions_before_cutoff) == 0:
        return np.nan
    final_position = positions_before_cutoff.iloc[-1]

    return final_position


def get_current_position_for_instrument_code(data_backtest, data, instrument_code):
    diag_positions = diagPositions(data)
    strategy_name = data_backtest.strategy_name
    instrument_strategy = instrumentStrategy(
        strategy_name=strategy_name, instrument_code=instrument_code
    )

    current_position = diag_positions.get_current_position_for_instrument_strategy(
        instrument_strategy
    )

    return current_position


def calc_position_diags(portfolio_positions_df, subystem_positions_df):
    idm = portfolio_positions_df.IDM
    instr_weight = portfolio_positions_df["instr weight"]
    vol_scalar = subystem_positions_df["Vol Scalar"]

    average_position = idm * instr_weight * vol_scalar

    return average_position


def risk_scaling_string(backtest) -> str:
    backtest_system_portfolio_stage = backtest.system.portfolio
    normal_risk_final = (
        backtest_system_portfolio_stage.get_portfolio_risk_for_original_positions().iloc[
            -1
        ]
        * 100.0
    )
    shocked_vol_risk_final = (
        backtest_system_portfolio_stage.get_portfolio_risk_for_original_positions_with_shocked_vol().iloc[
            -1
        ]
        * 100.0
    )
    sum_abs_risk_final = (
        backtest_system_portfolio_stage.get_sum_annualised_risk_for_original_positions().iloc[
            -1
        ]
        * 100.0
    )
    leverage_final = (
        backtest_system_portfolio_stage.get_leverage_for_original_position().iloc[-1]
    )
    percentage_vol_target = backtest_system_portfolio_stage.get_percentage_vol_target()
    try:
        risk_scalar = backtest_system_portfolio_stage.get_risk_scalar()
    except missingData:
        risk_scalar_final = 1.0
    else:
        risk_scalar_final = risk_scalar.iloc[-1]
    risk_overlay_config = (
        backtest_system_portfolio_stage.config.get_element_or_arg_not_supplied(
            "risk_overlay"
        )
    )

    scaling_str = (
        "Risk overlay \n Config %s \n Percentage vol target %.1f \n Normal risk %.1f Shocked risk %.1f \n Sum abs risk %.1f Leverage %.2f \n Risk scalar %.2f"
        % (
            str(risk_overlay_config),
            percentage_vol_target,
            normal_risk_final,
            shocked_vol_risk_final,
            sum_abs_risk_final,
            leverage_final,
            risk_scalar_final,
        )
    )

    return scaling_str
