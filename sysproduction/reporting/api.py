import datetime

import pandas as pd

from syscore.cache import Cache
from syscore.dateutils import (
    SECONDS_PER_DAY,
    calculate_start_and_end_dates,
    get_date_from_period_and_end_date,
)
from syscore.constants import arg_not_supplied
from sysobjects.production.roll_state import ALL_ROLL_INSTRUMENTS
from syscore.pandas.pdutils import top_and_tail
from sysdata.data_blob import dataBlob
from sysproduction.data.prices import diagPrices
from sysproduction.data.positions import annonate_df_index_with_positions_held
from sysproduction.reporting.formatting import (
    nice_format_instrument_risk_table,
    nice_format_liquidity_table,
    nice_format_slippage_table,
    nice_format_roll_table,
    nice_format_min_capital_table,
    make_account_curve_plot,
)
from sysproduction.reporting.reporting_functions import (
    header,
    table,
    PdfOutputWithTempFileName,
    figure,
    body_text,
)
from sysproduction.reporting.data.costs import (
    get_table_of_SR_costs,
    get_combined_df_of_costs,
    adjust_df_costs_show_ticks,
)
from sysproduction.reporting.data.pricechanges import marketMovers
from sysproduction.reporting.data.trades import (
    get_recent_broker_orders,
    create_raw_slippage_df,
    create_cash_slippage_df,
    create_vol_norm_slippage_df,
    get_stats_for_slippage_groups,
    create_delay_df,
    get_recent_trades_from_db_as_terse_df,
    get_broker_trades_as_terse_df,
)
from sysproduction.reporting.data.duplicate_remove_markets import (
    get_list_of_duplicate_market_tables,
    text_suggest_changes_to_duplicate_markets,
    get_remove_market_data,
    RemoveMarketData,
    generate_duplicate_pairs,
)
from sysproduction.reporting.data.pandl import (
    get_total_capital_pandl,
    pandlCalculateAndStore,
    get_daily_perc_pandl,
)
from sysproduction.reporting.data.positions import (
    get_optimal_positions,
    get_my_positions,
    get_broker_positions,
    get_position_breaks,
)
from sysproduction.reporting.data.risk import (
    get_correlation_matrix_all_instruments,
    cluster_correlation_matrix,
    get_instrument_risk_table,
    portfolioRisks,
    get_portfolio_risk_across_strategies,
    get_margin_usage,
    minimum_capital_table,
    get_correlation_matrix_for_instruments,
)
from sysproduction.reporting.data.rolls import (
    get_roll_data_for_instrument,
)
from sysproduction.reporting.data.status import (
    get_all_overrides_as_df,
    get_overrides_in_db_as_df,
    get_trade_limits_as_df,
    get_process_status_list_for_all_processes_as_df,
    get_control_config_list_for_all_processes_as_df,
    get_control_status_list_for_all_processes_as_df,
    get_control_data_list_for_all_methods_as_df,
    get_last_price_updates_as_df,
    get_last_optimal_position_updates_as_df,
    get_list_of_position_locks,
    get_position_limits_as_df,
)
from sysproduction.reporting.data.volume import get_liquidity_data_df
from sysproduction.reporting.data.commissions import (
    df_of_configure_and_broker_block_cost_sorted_by_diff,
)

REPORT_DATETIME_FORMAT = "%d/%m/%Y %H:%M"


class reportingApi(object):
    def __init__(
        self,
        data: dataBlob,
        calendar_days_back: int = arg_not_supplied,
        end_date: datetime.datetime = arg_not_supplied,
        start_date: datetime.datetime = arg_not_supplied,
        start_period: str = arg_not_supplied,
        end_period: str = arg_not_supplied,
        min_correlation: float = arg_not_supplied,
    ):
        self._data = data
        self._calendar_days_back = calendar_days_back
        self._passed_start_date = start_date
        self._passed_end_date = end_date
        self._end_period = end_period
        self._start_period = start_period
        self._min_correlation = min_correlation
        self._cache = Cache(self)

    def std_header(self, report_name: str):
        start_date = self.start_date
        end_date = self.end_date
        std_header = header(
            "%s produced on %s from %s to %s"
            % (
                report_name,
                datetime.datetime.now().strftime(REPORT_DATETIME_FORMAT),
                start_date.strftime(REPORT_DATETIME_FORMAT),
                end_date.strftime(REPORT_DATETIME_FORMAT),
            )
        )

        return std_header

    def terse_header(self, report_name: str):
        terse_header = header(
            "%s produced on %s"
            % (report_name, datetime.datetime.now().strftime(REPORT_DATETIME_FORMAT))
        )

        return terse_header

    def footer(self):
        return header("END OF REPORT")

    ## PANDL ACCOUNT CURVE
    def figure_of_account_curve_using_dates(self) -> figure:
        pdf_output = PdfOutputWithTempFileName(self.data)
        daily_pandl = self.daily_perc_pandl
        make_account_curve_plot(
            daily_pandl,
            start_of_title="Total p&l",
            start_date=self.start_date,
            end_date=self.end_date,
        )
        figure_object = pdf_output.save_chart_close_and_return_figure()

        return figure_object

    def figure_of_account_curves_given_period(self, period: str) -> figure:
        pdf_output = PdfOutputWithTempFileName(self.data)
        daily_pandl = self.daily_perc_pandl
        start_date = get_date_from_period_and_end_date(period)

        make_account_curve_plot(
            daily_pandl, start_of_title="Total p&l", start_date=start_date
        )

        figure_object = pdf_output.save_chart_close_and_return_figure()

        return figure_object

    @property
    def daily_perc_pandl(self) -> pd.Series:
        return self.cache.get(self._get_daily_perc_pandl)

    def _get_daily_perc_pandl(self) -> pd.Series:
        return get_daily_perc_pandl(self.data)

    ## MARKET MOVES
    def table_of_market_moves_using_dates(
        self, sortby: str, truncate: bool = True
    ) -> table:
        # sort by one of ['name', 'change', 'vol_adjusted']
        raw_df = self.market_moves_for_dates()
        sorted_df = raw_df.sort_values(sortby)
        rounded_df = sorted_df.round(2)

        if truncate:
            rounded_df = top_and_tail(rounded_df, rows=6)

        return table(
            "Market moves between %s and %s, sort by %s"
            % (str(self.start_date), str(self.end_date), sortby),
            rounded_df,
        )

    def table_of_market_moves_given_period(
        self, period: str, sortby: str, truncate: bool = True
    ) -> table:
        # sort by one of ['name', 'change', 'vol_adjusted']
        # period eg ['1B', '7D', '1M', '3M', '6M', 'YTD', '12M']
        raw_df = self.market_moves_for_period(period)
        sorted_df = raw_df.sort_values(sortby)
        rounded_df = sorted_df.round(2)

        if truncate:
            rounded_df = top_and_tail(rounded_df, rows=6)

        return table(
            "Market moves for period %s, sort by %s (%s/%s)"
            % (period, sortby, period, sortby),
            rounded_df,
        )

    def market_moves_for_period(self, period: str) -> pd.DataFrame:
        market_moves = self.get_market_moves_object()
        return market_moves.get_market_moves_for_period(period)

    def market_moves_for_dates(self) -> pd.DataFrame:
        market_moves = self.get_market_moves_object()
        return market_moves.get_market_moves_for_dates(self.start_date, self.end_date)

    def get_market_moves_object(self) -> marketMovers:
        key = "_market_moves"
        try:
            stored_market_moves = getattr(self, key)
        except AttributeError:
            stored_market_moves = marketMovers(self.data)
            setattr(self, key, stored_market_moves)

        return stored_market_moves

    ## MARKETS TO REMOVE
    def body_text_all_recommended_bad_markets_clean_slate(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(
            remove_market_data.str_all_recommended_bad_markets_clean_slate_in_yaml_form
        )

    def body_text_all_recommended_bad_markets(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(
            remove_market_data.str_all_recommended_bad_markets_in_yaml_form
        )

    def body_text_existing_markets_remove(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_existing_markets_to_remove)

    def body_text_removed_markets_addback(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_removed_markets_addback)

    def body_text_expensive_markets(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_expensive_markets)

    def body_text_markets_without_enough_volume_risk(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_markets_without_enough_volume_risk)

    def body_text_markets_without_enough_volume_contracts(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_markets_without_enough_volume_contracts)

    def body_text_too_safe_markets(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_too_safe_markets)

    def body_text_explain_safety(self) -> body_text:
        remove_market_data = self.remove_market_data()

        return body_text(remove_market_data.str_explain_safety)

    def remove_market_data(self) -> RemoveMarketData:
        try:
            remove_market_data = getattr(self, "_remove_market_data")
        except AttributeError:
            remove_market_data = self._get_remove_market_data()
            setattr(self, "_remove_market_data", remove_market_data)

        return remove_market_data

    def _get_remove_market_data(self) -> RemoveMarketData:
        return get_remove_market_data(self.data)

    ## DUPLICATE MARKETS
    def body_text_suggest_changes_to_duplicate_markets(self) -> body_text:
        list_of_duplicate_markets = self.list_of_duplicate_market_tables()
        output_text = text_suggest_changes_to_duplicate_markets(
            list_of_duplicate_markets
        )
        output_body_text = body_text(output_text)

        return output_body_text

    def list_of_duplicate_market_tables(self) -> list:
        try:
            list_of_duplicate_market_tables = getattr(
                self, "_list_of_duplicate_market_tables"
            )
        except AttributeError:
            list_of_duplicate_market_tables = (
                self._get_list_of_duplicate_market_tables()
            )
        setattr(
            self, "_list_of_duplicate_market_tables", list_of_duplicate_market_tables
        )

        return list_of_duplicate_market_tables

    def _get_list_of_duplicate_market_tables(self) -> list:
        return get_list_of_duplicate_market_tables(self.data)

    def get_correlations_for_configured_duplicates(self) -> table:
        pairs = generate_duplicate_pairs(self.data)
        corr_data = get_correlation_matrix_for_instruments(
            self.data, self._get_configured_duplicates_list(pairs)
        )
        corr_data = cluster_correlation_matrix(corr_data)
        corr_data = corr_data.as_pd().round(2)

        rows = []
        for inc, exc in pairs:
            try:
                corr_value = corr_data.loc[inc, exc]
            except KeyError:
                corr_value = float("nan")
            rows.append(dict(included=inc, excluded=exc, correlation=corr_value))

        configured_correlations = pd.DataFrame(rows)
        configured_correlations = configured_correlations[
            configured_correlations.correlation < self._min_correlation
        ].sort_values("correlation", ascending=False)
        table_corr = table(
            "Potenially uncorrelated configured duplicates", configured_correlations
        )

        return table_corr

    def get_potential_unconfigured_duplicates(self) -> table:
        diag_prices = diagPrices(self.data)
        pairs = generate_duplicate_pairs(self.data)

        all_instruments = diag_prices.get_list_of_instruments_in_multiple_prices()
        unconfigured = [
            item
            for item in all_instruments
            if item not in self._get_configured_duplicates_list(pairs)
        ]

        corr_data = get_correlation_matrix_for_instruments(self.data, unconfigured)
        corr_data = cluster_correlation_matrix(corr_data)
        corr_data = corr_data.as_pd().round(2)

        instruments = corr_data.index.tolist()
        rows = []
        for i, inst1 in enumerate(instruments):
            for inst2 in instruments[i + 1 :]:
                corr_value = corr_data.loc[inst1, inst2]
                if corr_value >= self._min_correlation:
                    rows.append(dict(first=inst1, second=inst2, correlation=corr_value))

        potential_duplicates = pd.DataFrame(rows).sort_values(
            "correlation", ascending=False
        )
        table_corr = table("Potentially unconfigured duplicates", potential_duplicates)

        return table_corr

    def _get_configured_duplicates_list(self, pairs_list):
        configured = set()
        for elem in pairs_list:
            configured.add(elem[0])
            configured.add(elem[1])
        return list(configured)

    ### MINIMUM CAPITAL
    def table_of_minimum_capital(self) -> table:
        min_capital = minimum_capital_table(self.data)
        min_capital = min_capital.sort_values("minimum_capital")

        min_capital = nice_format_min_capital_table(min_capital)
        min_capital_table = table("Minimum capital in base currency", min_capital)

        return min_capital_table

    #### PROFIT AND LOSS ####
    def body_text_total_capital_pandl(self):
        total_capital_pandl = self.total_capital_pandl()

        return body_text("Total p&l is %.3f%%" % total_capital_pandl)

    def table_pandl_for_instruments_across_strategies(self):
        pandl_for_instruments_across_strategies_df = (
            self.pandl_for_instruments_across_strategies()
        )
        pandl_for_instruments_across_strategies_df = (
            pandl_for_instruments_across_strategies_df.round(1)
        )

        return table(
            "P&L by instrument for all strategies",
            pandl_for_instruments_across_strategies_df,
        )

    def body_text_total_pandl_for_futures(self):
        total_for_futures = self.total_pandl_for_futures()
        return body_text("Total futures p&l is %.3f%%" % total_for_futures)

    def total_pandl_for_futures(self) -> float:
        pandl_for_instruments_across_strategies = (
            self.pandl_for_instruments_across_strategies()
        )
        total_for_futures = pandl_for_instruments_across_strategies.pandl.sum()

        return total_for_futures

    def pandl_for_instruments_across_strategies(self) -> pd.DataFrame:
        try:
            pandl_for_instruments_across_strategies = getattr(
                self,
                "_pandl_for_instruments_across_strategies",
            )
        except AttributeError:
            pandl_for_instruments_across_strategies = (
                self._get_pandl_for_instruments_across_strategies()
            )
            setattr(
                self,
                "_pandl_for_instruments_across_strategies",
                pandl_for_instruments_across_strategies,
            )

        return pandl_for_instruments_across_strategies

    def _get_pandl_for_instruments_across_strategies(self) -> pd.DataFrame:
        pandl_for_instruments_across_strategies_df = self.pandl_calculator.get_ranked_list_of_pandl_by_instrument_all_strategies_in_date_range()

        return pandl_for_instruments_across_strategies_df

    def total_capital_pandl(self) -> float:
        try:
            total_capital_pandl = getattr(self, "_total_capital_pandl")
        except AttributeError:
            total_capital_pandl = self._get_total_capital_pandl()
            setattr(self, "_total_capital_pandl", total_capital_pandl)

        return total_capital_pandl

    def _get_total_capital_pandl(self) -> float:
        total_capital_pandl = get_total_capital_pandl(
            self.data, self.start_date, end_date=self.end_date
        )

        return total_capital_pandl

    def body_text_residual_pandl(self):
        residual = self.total_capital_pandl() - self.total_pandl_for_futures()
        return body_text("Residual p&l is %.3f%%" % residual)

    def table_strategy_pandl_and_residual(self):
        strategies_pandl_df = self.pandl_calculator.get_strategy_pandl_and_residual()
        strategies_pandl_df = strategies_pandl_df.round(2)

        return table("P&L by strategy", strategies_pandl_df)

    def table_sector_pandl(self):
        sector_pandl_df = self.pandl_calculator.get_sector_pandl()
        sector_pandl_df = sector_pandl_df.round(2)

        return table("P&L by asset class", sector_pandl_df)

    @property
    def pandl_calculator(self) -> pandlCalculateAndStore:
        try:
            pandl_calculator = getattr(self, "_pandl_calculator")
        except AttributeError:
            pandl_calculator = self._get_pandl_calculator()
            setattr(self, "_pandl_calculator", pandl_calculator)

        return pandl_calculator

    def _get_pandl_calculator(self) -> pandlCalculateAndStore:
        return pandlCalculateAndStore(
            self.data, start_date=self.start_date, end_date=self.end_date
        )

    ##### STATUS #####
    def table_of_control_config_list_for_all_processes(self):
        process = get_control_config_list_for_all_processes_as_df(self.data)
        process_table = table("Config for process control", process)

        return process_table

    def table_of_delayed_methods(self):
        method_status = get_control_data_list_for_all_methods_as_df(self.data)
        delay_methods_table = filter_data_for_delays_and_return_table(
            method_status,
            datetime_colum="last_start",
            max_delay_in_days=3,
            table_header="Delayed methods",
        )

        return delay_methods_table

    def table_of_delayed_prices(self):
        price = get_last_price_updates_as_df(self.data)
        price_delays = filter_data_for_delays_and_return_table(
            price,
            datetime_colum="last_update",
            max_delay_in_days=3,
            table_header="Delayed adjusted / FX prices",
        )

        return price_delays

    def table_of_delayed_optimal(self):
        position = get_last_optimal_position_updates_as_df(self.data)
        position_delays = filter_data_for_delays_and_return_table(
            position,
            datetime_colum="last_update",
            max_delay_in_days=3,
            table_header="Delayed optimal positions",
        )

        return position_delays

    def table_of_limited_trades(self):
        limits = get_trade_limits_as_df(self.data)
        at_limit = filter_data_for_max_value_and_return_table(
            limits,
            field_column="trade_capacity_remaining",
            max_value=0,
            table_header="Instruments at trade limit",
        )

        return at_limit

    def table_of_used_position_limits(self):
        position_limits = get_position_limits_as_df(self.data)
        at_limit = filter_data_for_max_value_and_return_table(
            position_limits,
            field_column="spare",
            max_value=0,
            table_header="Instruments at position limit",
        )

        return at_limit

    def table_of_db_overrides(self):
        overrides = get_overrides_in_db_as_df(self.data)
        overrides_table = table("Overrides in database consider deleting", overrides)

        return overrides_table

    def table_of_control_status_list_for_all_processes(self):
        process2 = get_control_status_list_for_all_processes_as_df(self.data)
        process2_table = table("Status of process control", process2)

        return process2_table

    def table_of_process_status_list_for_all_processes(self):
        process3 = get_process_status_list_for_all_processes_as_df(self.data)
        process3_table = table("Status of process control", process3)

        return process3_table

    def table_of_control_data_list_for_all_methods(self):
        method = get_control_data_list_for_all_methods_as_df(self.data)
        method_table = table("Status of methods", method)

        return method_table

    def table_of_last_price_updates(self):
        price = get_last_price_updates_as_df(self.data)
        price = annonate_df_index_with_positions_held(self.data, price)
        price_table = table("Status of adjusted price / FX price collection", price)

        return price_table

    def table_of_last_optimal_position_updates(self):
        position = get_last_optimal_position_updates_as_df(self.data)
        position_table = table("Status of optimal position generation", position)

        return position_table

    def table_of_trade_limits(self):
        limits = get_trade_limits_as_df(self.data)
        limits_table = table("Status of trade limits", limits)

        return limits_table

    def table_of_position_limits(self):
        position_limits = get_position_limits_as_df(self.data)
        position_limits_table = table("Status of position limits", position_limits)

        return position_limits_table

    def table_of_overrides(self):
        overrides = get_all_overrides_as_df(self.data)
        overrides_table = table("Status of overrides", overrides)

        return overrides_table

    def body_text_of_position_locks(self):
        locks = get_list_of_position_locks(self.data)
        locks_text = body_text(str(locks))

        return locks_text

    #### ROLL REPORT ####
    def table_of_roll_data(self, instrument_code: str = ALL_ROLL_INSTRUMENTS):
        result_pd = self._roll_data_as_pd(instrument_code)
        result_pd = nice_format_roll_table(result_pd)
        table_result = table("Status and time to roll in days", result_pd)

        return table_result

    def _roll_data_as_pd(self, instrument_code: str = ALL_ROLL_INSTRUMENTS):
        roll_data_dict = self.roll_data_dict(instrument_code)

        result_pd = pd.DataFrame.from_dict(roll_data_dict, orient="index")

        result_pd = result_pd.sort_values("roll_expiry")

        return result_pd

    def roll_data_dict(self, instrument_code: str = ALL_ROLL_INSTRUMENTS):
        return self.cache.get(self._get_roll_data_dict, instrument_code)

    def _get_roll_data_dict(self, instrument_code: str = ALL_ROLL_INSTRUMENTS):
        if instrument_code is ALL_ROLL_INSTRUMENTS:
            list_of_instruments = self._list_of_all_instruments()
        else:
            list_of_instruments = [instrument_code]
        data = self.data

        roll_data_dict = {}
        for instrument_code in list_of_instruments:
            roll_data = get_roll_data_for_instrument(instrument_code, data)
            roll_data_dict[instrument_code] = roll_data

        return roll_data_dict

    def _list_of_all_instruments(self):
        diag_prices = diagPrices(self.data)
        list_of_instruments = diag_prices.get_list_of_instruments_in_multiple_prices()

        return list_of_instruments

    #### RISK REPORT ####
    def body_text_margin_usage(self) -> body_text:
        margin_usage = self.get_margin_usage()
        perc_margin_usage = margin_usage * 100.0
        body_text_margin_usage = body_text(
            "Percentage of capital used for margin %.1f%%" % perc_margin_usage
        )

        return body_text_margin_usage

    def table_of_correlations(self) -> table:
        corr_data = get_correlation_matrix_all_instruments(self.data)
        corr_data = cluster_correlation_matrix(corr_data)
        corr_data = corr_data.as_pd().round(2)
        table_corr = table("Correlations", corr_data)

        return table_corr

    def table_of_instrument_risk(self):
        instrument_risk_data = self.instrument_risk_data()
        instrument_risk_data = nice_format_instrument_risk_table(instrument_risk_data)
        table_instrument_risk = table("Instrument risk", instrument_risk_data)
        return table_instrument_risk

    def table_of_strategy_risk(self):
        strategy_risk = get_portfolio_risk_across_strategies(self.data)
        strategy_risk = strategy_risk * 100.0
        strategy_risk = strategy_risk.round(1)
        table_strategy_risk = table(
            "Risk per strategy, annualised percentage", strategy_risk
        )

        return table_strategy_risk

    def table_of_risk_all_instruments(
        self,
        table_header="Risk of all instruments with data - sorted by annualised % standard deviation",
        sort_by="annual_perc_stdev",
    ):
        instrument_risk_all = self.instrument_risk_data_all_instruments()
        instrument_risk_sorted = instrument_risk_all.sort_values(sort_by)
        instrument_risk_sorted = instrument_risk_sorted[
            [
                "daily_price_stdev",
                "annual_price_stdev",
                "price",
                "daily_perc_stdev",
                "annual_perc_stdev",
                "point_size_base",
                "contract_exposure",
                "annual_risk_per_contract",
            ]
        ]
        instrument_risk_sorted = instrument_risk_sorted.round(
            {
                "daily_price_stdev": 4,
                "annual_price_stdev": 3,
                "price": 4,
                "daily_perc_stdev": 3,
                "annual_perc_stdev": 1,
                "point_size_base": 3,
                "contract_exposure": 0,
                "annual_risk_per_contract": 0,
            }
        )
        instrument_risk_sorted_table = table(table_header, instrument_risk_sorted)

        return instrument_risk_sorted_table

    def body_text_portfolio_risk_total(self):
        portfolio_risk_object = self.portfolio_risks
        portfolio_risk_total = (
            portfolio_risk_object.get_portfolio_risk_for_all_strategies()
        )
        portfolio_risk_total = portfolio_risk_total * 100.0
        portfolio_risk_total = portfolio_risk_total.round(1)
        portfolio_risk_total_text = body_text(
            "Total risk across all strategies, annualised percentage %.1f"
            % portfolio_risk_total
        )

        return portfolio_risk_total_text

    def table_of_risk_by_asset_class(self) -> table:
        portfolio_risk_object = self.portfolio_risks
        risk_by_asset_class = (
            portfolio_risk_object.get_pd_series_of_risk_by_asset_class()
        )
        risk_by_asset_class = risk_by_asset_class * 100
        risk_by_asset_class = risk_by_asset_class.round(1)
        risk_by_asset_class_table = table("Risk by asset class", risk_by_asset_class)

        return risk_by_asset_class_table

    def table_of_beta_loadings_by_asset_class(self):
        portfolio_risk_object = self.portfolio_risks
        beta_load_by_asset_class = (
            portfolio_risk_object.get_beta_loadings_by_asset_class()
        )
        beta_load_by_asset_class = beta_load_by_asset_class.round(2)
        beta_load_by_asset_class = beta_load_by_asset_class.sort_values()
        beta_load_by_asset_class_table = table(
            "Beta loadings of asset class positions on asset class",
            beta_load_by_asset_class,
        )

        return beta_load_by_asset_class_table

    def table_of_portfolio_beta_loadings_by_asset_class(self):
        portfolio_risk_object = self.portfolio_risks
        portfolio_beta_load_by_asset_class = (
            portfolio_risk_object.get_portfolio_beta_loadings_by_asset_class()
        )
        portfolio_beta_load_by_asset_class = portfolio_beta_load_by_asset_class.round(2)
        portfolio_beta_load_by_asset_class = (
            portfolio_beta_load_by_asset_class.sort_values()
        )
        portfolio_beta_load_by_asset_class_table = table(
            "Beta loadings of full portfolio positions on asset class",
            portfolio_beta_load_by_asset_class,
        )

        return portfolio_beta_load_by_asset_class_table

    @property
    def portfolio_risks(self) -> portfolioRisks:
        return self.cache.get(self._portfolio_risks)

    def _portfolio_risks(self) -> portfolioRisks:
        return portfolioRisks(data=self.data)

    def body_text_abs_total_all_risk_perc_capital(self):
        instrument_risk_data = self.instrument_risk_data()
        all_risk_perc_capital = instrument_risk_data.exposure_held_perc_capital
        abs_total_all_risk_perc_capital = all_risk_perc_capital.abs().sum()

        return body_text(
            "Sum of abs(notional exposure %% capital) %.1f"
            % abs_total_all_risk_perc_capital
        )

    def body_text_abs_total_all_risk_annualised(self):
        instrument_risk_data = self.instrument_risk_data()
        all_risk_annualised = instrument_risk_data.annual_risk_perc_capital
        abs_total_all_risk_annualised = all_risk_annualised.abs().sum()

        return body_text(
            "Sum of abs(annualised risk %% capital) %.1f"
            % abs_total_all_risk_annualised
        )

    def body_text_net_total_all_risk_annualised(self):
        instrument_risk_data = self.instrument_risk_data()
        all_risk_annualised = instrument_risk_data.annual_risk_perc_capital
        net_total_all_risk_annualised = all_risk_annualised.sum()

        return body_text(
            "Net sum of annualised risk %% capital %.1f "
            % net_total_all_risk_annualised
        )

    def get_margin_usage(self) -> float:
        return get_margin_usage(self.data)

    def instrument_risk_data(self):
        try:
            instrument_risk = getattr(self, "_instrument_risk")
        except AttributeError:
            instrument_risk = self._get_instrument_risk()
            setattr(self, "_instrument_risk", instrument_risk)

        return instrument_risk

    def _get_instrument_risk(self):
        instrument_risk_data = get_instrument_risk_table(self.data)
        return instrument_risk_data

    def instrument_risk_data_all_instruments(self) -> pd.DataFrame:
        try:
            instrument_risk_all = getattr(self, "_instrument_risk_all_instruments")
        except AttributeError:
            instrument_risk_all = self._get_instrument_risk_all_instruments()
            setattr(self, "_instrument_risk_all_instruments", instrument_risk_all)

        return instrument_risk_all

    def _get_instrument_risk_all_instruments(self):
        instrument_risk_all = get_instrument_risk_table(
            self.data, only_held_instruments=False
        )
        return instrument_risk_all

    ##### RECONCILE #####
    def table_of_optimal_positions(self):
        positions_optimal = get_optimal_positions(self.data)
        table_positions_optimal = table(
            "Optimal versus actual positions", positions_optimal
        )
        return table_positions_optimal

    def table_of_my_positions(self):
        positions_mine = get_my_positions(self.data)
        table_positions_mine = table("Positions in DB", positions_mine)

        return table_positions_mine

    def table_of_ib_positions(self):
        positions_ib = get_broker_positions(self.data)
        table_positions_ib = table("Positions broker", positions_ib)

        return table_positions_ib

    def body_text_position_breaks(self):
        position_breaks = get_position_breaks(self.data)
        text_position_breaks = body_text(position_breaks)

        return text_position_breaks

    def table_of_my_recent_trades_from_db(self):
        trades_mine = get_recent_trades_from_db_as_terse_df(self.data)
        table_trades_mine = table("Trades in DB", trades_mine)

        return table_trades_mine

    def table_of_recent_ib_trades(self):
        trades_ib = get_broker_trades_as_terse_df(self.data)
        table_trades_ib = table("Trades from broker", trades_ib)

        return table_trades_ib

    ##### LIQUIDITY ######
    def table_of_liquidity_contract_sort(self) -> table:
        all_liquidity_df = self.liquidity_data()
        all_liquidity_df = all_liquidity_df.sort_values("contracts")
        table_liquidity = table(
            " Sorted by contracts",
            all_liquidity_df,
        )

        return table_liquidity

    def table_of_liquidity_risk_sort(self) -> table:
        all_liquidity_df = self.liquidity_data()
        all_liquidity_df = all_liquidity_df.sort_values("risk")
        table_liquidity = table(
            "$m of annualised risk per day, sorted by risk",
            all_liquidity_df,
        )

        return table_liquidity

    def liquidity_data(self) -> pd.DataFrame:
        try:
            liquidity = getattr(self, "_liquidity_data")
        except AttributeError:
            liquidity = self._get_liquidity_data()
            setattr(self, "_liquidity_data", liquidity)

        liquidity = nice_format_liquidity_table(liquidity)
        return liquidity

    def _get_liquidity_data(self) -> pd.DataFrame:
        return get_liquidity_report_data(self.data)

    ##### COSTS ######
    def table_of_sr_costs(
        self, include_commission: bool = True, include_spreads: bool = True
    ) -> table:
        if not include_commission and not include_spreads:
            raise Exception("Must include commission or spreads!")
        elif not include_spreads:
            SR_costs = self.SR_costs_commission_only()
        elif not include_commission:
            SR_costs = self.SR_costs_spreads_only()
        else:
            SR_costs = self.SR_costs()

        SR_costs = SR_costs.round(5)
        SR_costs = annonate_df_index_with_positions_held(data=self.data, pd_df=SR_costs)
        formatted_table = table("SR costs (using stored slippage)", SR_costs)

        return formatted_table

    def SR_costs(self) -> pd.DataFrame:
        return self.cache.get(
            self._SR_costs, include_spread=True, include_commission=True
        )

    def SR_costs_commission_only(self) -> pd.DataFrame:
        return self.cache.get(
            self._SR_costs, include_spread=False, include_commission=True
        )

    def SR_costs_spreads_only(self) -> pd.DataFrame:
        return self.cache.get(
            self._SR_costs, include_spread=True, include_commission=False
        )

    def _SR_costs(
        self, include_commission: bool = True, include_spread: bool = True
    ) -> pd.DataFrame:
        SR_costs = get_table_of_SR_costs(
            self.data,
            include_commission=include_commission,
            include_spread=include_spread,
        )

        return SR_costs

    def table_of_slippage_comparison(self):
        combined_df_costs = self.combined_df_costs()
        combined_df_costs = nice_format_slippage_table(combined_df_costs)
        combined_df_costs = annonate_df_index_with_positions_held(
            self.data, pd_df=combined_df_costs
        )

        combined_df_costs_as_formatted_table = table(
            "Check of slippage, in price units", combined_df_costs
        )

        return combined_df_costs_as_formatted_table

    def table_of_slippage_comparison_tick_adjusted(self):
        combined_df_costs = self.combined_df_costs()
        combined_df_costs = adjust_df_costs_show_ticks(
            data=self.data, combined_df_costs=combined_df_costs
        )

        combined_df_costs = nice_format_slippage_table(combined_df_costs)
        combined_df_costs = annonate_df_index_with_positions_held(
            self.data, pd_df=combined_df_costs
        )

        combined_df_costs_as_formatted_table = table(
            "Check of slippage, in tick units", combined_df_costs
        )

        return combined_df_costs_as_formatted_table

    def combined_df_costs(self):
        return self.cache.get(self._combined_df_costs)

    def _combined_df_costs(self):
        combined_df_costs = get_combined_df_of_costs(
            self.data, start_date=self.start_date, end_date=self.end_date
        )

        return combined_df_costs

    ##### COMMISSIONS ####
    def table_of_commissions(self):
        df = self.df_commissions()
        df_as_formatted_table = table(
            "Commissions in base currency, configure and from broker", df
        )

        return df_as_formatted_table

    def df_commissions(self):
        return self.cache.get(self._df_commissions)

    def _df_commissions(self):
        combined_df_costs = df_of_configure_and_broker_block_cost_sorted_by_diff(
            self.data
        )

        return combined_df_costs

    ##### TRADES ######
    def table_of_orders_overview(self):
        broker_orders = self.broker_orders
        if len(broker_orders) == 0:
            return body_text("No trades")

        overview = broker_orders[
            [
                "instrument_code",
                "strategy_name",
                "contract_date",
                "fill_datetime",
                "fill",
                "filled_price",
            ]
        ]
        overview = overview.sort_values("instrument_code")
        overview_table = table("Broker orders", overview)

        return overview_table

    def table_of_order_delays(self):
        broker_orders = self.broker_orders
        if len(broker_orders) == 0:
            return body_text("No trades")

        delays = create_delay_df(broker_orders)

        table_of_delays = table("Delays", delays)

        return table_of_delays

    def table_of_raw_slippage(self):
        raw_slippage = self.raw_slippage
        if len(raw_slippage) == 0:
            return body_text("No trades")

        table_of_raw_slippage = table("Slippage (ticks per lot)", raw_slippage)

        return table_of_raw_slippage

    def table_of_vol_slippage(self):
        raw_slippage = self.raw_slippage
        if len(raw_slippage) == 0:
            return body_text("No trades")

        vol_slippage = create_vol_norm_slippage_df(raw_slippage, self.data)
        vol_slippage = vol_slippage.round(2)
        table_of_vol_slippage = table(
            "Slippage (normalised by annual vol, BP of annual SR)", vol_slippage
        )

        return table_of_vol_slippage

    def list_of_cash_summary_text(self) -> list:
        cash_slippage = self.cash_slippage
        if len(cash_slippage) == 0:
            return [body_text("No trades")]

        item_list = [
            "delay_cash",
            "bid_ask_cash",
            "execution_cash",
            "versus_limit_cash",
            "versus_parent_limit_cash",
            "total_trading_cash",
        ]
        detailed_cash_results = get_stats_for_slippage_groups(cash_slippage, item_list)

        list_of_summary_results = [
            body_text("%s\n%s" % (key, str(value)))
            for key, value in detailed_cash_results.items()
        ]

        return list_of_summary_results

    def table_of_cash_slippage(self):
        cash_slippage = self.cash_slippage
        if len(cash_slippage) == 0:
            return body_text("No trades")
        cash_slippage = cash_slippage.round(2)
        table_slippage = table("Slippage (In base currency)", cash_slippage)

        return table_slippage

    @property
    def cash_slippage(self) -> pd.DataFrame:
        try:
            cash_slippage = getattr(self, "_cash_slippage")
        except AttributeError:
            cash_slippage = self._get_cash_slippage()
            setattr(self, "_cash_slippage", cash_slippage)

        return cash_slippage

    def _get_cash_slippage(self) -> pd.DataFrame:
        raw_slippage = self.raw_slippage
        if len(raw_slippage) == 0:
            return pd.DataFrame()

        cash_slippage = create_cash_slippage_df(raw_slippage, self.data)

        return cash_slippage

    @property
    def raw_slippage(self) -> pd.DataFrame:
        try:
            raw_slippage = getattr(self, "_raw_slippage")
        except AttributeError:
            raw_slippage = self._get_raw_slippage()
            setattr(self, "_raw_slippage", raw_slippage)

        return raw_slippage

    def _get_raw_slippage(self) -> pd.DataFrame:
        broker_orders = self.broker_orders
        if len(broker_orders) == 0:
            return pd.DataFrame()
        raw_slippage = create_raw_slippage_df(broker_orders)

        return raw_slippage

    @property
    def broker_orders(self) -> pd.DataFrame:
        return self.cache.get(self._get_broker_orders)

    def _get_broker_orders(self) -> pd.DataFrame:
        broker_orders = get_recent_broker_orders(
            self.data, start_date=self.start_date, end_date=self.end_date
        )
        return broker_orders

    ##### DATA AND DATES #####
    @property
    def data(self) -> dataBlob:
        return self._data

    @property
    def start_date(self) -> datetime.datetime:
        start_and_end_dates = self.start_and_end_dates

        return start_and_end_dates[0]

    @property
    def end_date(self) -> datetime.datetime:
        start_and_end_dates = self.start_and_end_dates

        return start_and_end_dates[1]

    @property
    def start_and_end_dates(self) -> tuple:
        return self.cache.get(self._calculate_start_and_end_dates)

    def _calculate_start_and_end_dates(self) -> tuple:
        start_date, end_date = calculate_start_and_end_dates(
            calendar_days_back=self._calendar_days_back,
            start_date=self._passed_start_date,
            end_date=self._passed_end_date,
            start_period=self._start_period,
            end_period=self._end_period,
        )

        return start_date, end_date

    @property
    def cache(self) -> Cache:
        return self._cache


def get_liquidity_report_data(data: dataBlob) -> pd.DataFrame:
    all_liquidity_df = get_liquidity_data_df(data)
    all_liquidity_df = annonate_df_index_with_positions_held(data, all_liquidity_df)

    return all_liquidity_df


def filter_data_for_delays_and_return_table(
    data_with_datetime,
    datetime_colum="last_start",
    table_header="Only delayed data",
    max_delay_in_days=3,
):
    filtered_data = filter_data_for_delays(
        data_with_datetime,
        datetime_colum=datetime_colum,
        max_delay_in_days=max_delay_in_days,
    )
    if len(filtered_data) == 0:
        return body_text("%s: No delays" % table_header)
    else:
        return table(table_header, filtered_data)


def filter_data_for_delays(
    data_with_datetime, datetime_colum="last_start", max_delay_in_days=3
) -> pd.DataFrame:
    max_delay_in_seconds = max_delay_in_days * SECONDS_PER_DAY
    time_delays = datetime.datetime.now() - data_with_datetime[datetime_colum]
    delayed = [
        time_difference.total_seconds() > max_delay_in_seconds
        for time_difference in time_delays
    ]

    return data_with_datetime[delayed]


def filter_data_for_max_value_and_return_table(
    data_with_field, field_column="field", max_value=0, table_header=""
):
    filtered_data = filter_data_for_max_value(
        data_with_field, field_column=field_column, max_value=max_value
    )
    if len(filtered_data) == 0:
        return body_text("%s: No constraints" % table_header)
    else:
        return table(table_header, filtered_data)


def filter_data_for_max_value(
    data_with_field, field_column="field", max_value=0
) -> pd.DataFrame:
    field_values = data_with_field[field_column]
    filtered = [value <= max_value for value in field_values]

    return data_with_field[filtered]
