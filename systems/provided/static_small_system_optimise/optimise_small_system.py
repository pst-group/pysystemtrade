from copy import copy
import numpy as np
from syscore.constants import arg_not_supplied
from syscore.dateutils import WEEKS_IN_YEAR


from sysquant.optimisation.optimisers.handcraft import handcraftPortfolio
from sysquant.estimators.estimates import (
    Estimates,
    meanEstimates,
    stdevEstimates,
    correlationEstimate,
)
from sysquant.optimisation.shared import neg_SR

## THIS MIGHT NEED TWEAKING, DEPENDING ON CAPITAL


def find_best_ordered_set_of_instruments(
    system,
    corr_matrix: correlationEstimate = arg_not_supplied,
    max_instrument_weight=0.05,
    notional_starting_IDM=1.0,
    capital=500000,
) -> list:
    ## 'system' can be precalculated up to the combined forecast stage to save time

    system.config.notional_trading_capital = capital
    system.config.instrument_correlation_estimate["floor_at_zero"] = False

    list_of_instruments = system.portfolio.get_instrument_list(
        for_instrument_weights=True, auto_remove_bad_instruments=True
    )
    if corr_matrix is arg_not_supplied:
        corr_matrix = get_correlation_matrix(system)

    minimum_instrument_weight_idm = max_instrument_weight * notional_starting_IDM

    best_market = find_best_market(
        system=system,
        list_of_instruments=list_of_instruments,
        minimum_instrument_weight_idm=minimum_instrument_weight_idm,
    )
    set_of_instruments_used = [best_market]

    unused_list_of_instruments = copy(list_of_instruments)
    unused_list_of_instruments.remove(best_market)

    max_SR = 0.0
    while len(unused_list_of_instruments) > 0:
        new_SR, selected_market = find_next_instrument(
            system,
            unused_list_of_instruments=unused_list_of_instruments,
            set_of_instruments_used=set_of_instruments_used,
            corr_matrix=corr_matrix,
            minimum_instrument_weight_idm=minimum_instrument_weight_idm,
        )
        if (new_SR) < (max_SR * 0.9):
            print("PORTFOLIO TOO BIG! SR falling")
            break
        print("Portfolio %s SR %.2f" % (str(set_of_instruments_used), new_SR))

        set_of_instruments_used.append(selected_market)
        unused_list_of_instruments.remove(selected_market)
        if new_SR > max_SR:
            max_SR = new_SR

    return set_of_instruments_used


def get_correlation_matrix(system) -> correlationEstimate:
    system.portfolio.get_instrument_list(
        for_instrument_weights=True, auto_remove_bad_instruments=True
    )
    list_of_correlations = system.portfolio.get_instrument_correlation_matrix()
    corr_matrix = list_of_correlations.corr_list[-1]

    return corr_matrix


def find_best_market(
    system, list_of_instruments: list, minimum_instrument_weight_idm: float
) -> str:
    all_results = []
    for instrument_code in list_of_instruments:
        all_results.append(
            (
                instrument_code,
                net_SR_for_instrument_in_system(
                    system,
                    instrument_code,
                    minimum_instrument_weight_idm=minimum_instrument_weight_idm,
                    instrument_weight_idm=minimum_instrument_weight_idm,
                ),
            )
        )

    all_results = sorted(all_results, key=lambda tup: tup[1])

    best_market = all_results[-1][0]

    return best_market


def find_next_instrument(
    system,
    unused_list_of_instruments: list,
    set_of_instruments_used: list,
    corr_matrix: correlationEstimate,
    minimum_instrument_weight_idm: float,
):
    SR_list = []
    for instrument_code in unused_list_of_instruments:
        instrument_list = set_of_instruments_used + [instrument_code]

        portfolio_sizes, SR_this_instrument = SR_for_instrument_list(
            system,
            corr_matrix=corr_matrix,
            instrument_list=instrument_list,
            minimum_instrument_weight_idm=minimum_instrument_weight_idm,
        )
        SR_list.append((instrument_code, SR_this_instrument))

    SR_list = sorted(SR_list, key=lambda tup: tup[1])
    selected_market = SR_list[-1][0]
    new_SR = SR_list[-1][1]

    return new_SR, selected_market


def SR_for_instrument_list(
    system, corr_matrix, instrument_list, minimum_instrument_weight_idm
):
    estimates = build_estimates(
        instrument_list=instrument_list, corr_matrix=corr_matrix
    )

    handcraft_portfolio = handcraftPortfolio(estimates)
    risk_weights = handcraft_portfolio.risk_weights()

    SR = estimate_SR_given_weights(
        system=system,
        risk_weights=risk_weights,
        handcraft_portfolio=handcraft_portfolio,
        minimum_instrument_weight_idm=minimum_instrument_weight_idm,
    )

    portfolio_sizes = estimate_portfolio_sizes_given_weights(
        system, risk_weights=risk_weights, handcraft_portfolio=handcraft_portfolio
    )

    return portfolio_sizes, SR


def build_estimates(instrument_list, corr_matrix, notional_years_data=30):
    ## We don't take SR into account
    mean_estimates = meanEstimates(
        dict([(instrument_code, 1.0) for instrument_code in instrument_list])
    )

    stdev_estimates = stdevEstimates(
        dict([(instrument_code, 1.0) for instrument_code in instrument_list])
    )

    estimates = Estimates(
        correlation=corr_matrix.subset(instrument_list),
        mean=mean_estimates,
        stdev=stdev_estimates,
        frequency="W",
        data_length=notional_years_data * WEEKS_IN_YEAR,
    )

    return estimates


def estimate_SR_given_weights(
    system,
    risk_weights,
    handcraft_portfolio: handcraftPortfolio,
    minimum_instrument_weight_idm: float,
):
    instrument_list = list(risk_weights.keys())

    mean_estimates = mean_estimates_from_SR_function_actual_weights(
        system,
        risk_weights=risk_weights,
        handcraft_portfolio=handcraft_portfolio,
        minimum_instrument_weight_idm=minimum_instrument_weight_idm,
    )

    wt = np.array(risk_weights.as_list_given_keys(instrument_list))
    mu = np.array(mean_estimates.list_in_key_order(instrument_list))
    cm = handcraft_portfolio.estimates.covariance_matrix

    SR = -neg_SR(wt, cm, mu)

    return SR


def mean_estimates_from_SR_function_actual_weights(
    system,
    risk_weights,
    handcraft_portfolio: handcraftPortfolio,
    minimum_instrument_weight_idm: float,
):
    instrument_list = list(risk_weights.keys())
    actual_idm = min(2.5, handcraft_portfolio.div_mult(risk_weights))
    mean_estimates = meanEstimates(
        dict(
            [
                (
                    instrument_code,
                    net_SR_for_instrument_in_system(
                        system,
                        instrument_code,
                        instrument_weight_idm=actual_idm
                        * risk_weights[instrument_code],
                        minimum_instrument_weight_idm=minimum_instrument_weight_idm,
                    ),
                )
                for instrument_code in instrument_list
            ]
        )
    )

    return mean_estimates


def estimate_portfolio_sizes_given_weights(
    system, risk_weights, handcraft_portfolio: handcraftPortfolio
):
    instrument_list = list(risk_weights.keys())
    idm = handcraft_portfolio.div_mult(risk_weights)

    portfolio_sizes = dict(
        [
            (
                instrument_code,
                round(
                    calculate_maximum_position(
                        system,
                        instrument_code,
                        instrument_weight_idm=risk_weights[instrument_code] * idm,
                    ),
                    1,
                ),
            )
            for instrument_code in instrument_list
        ]
    )

    return portfolio_sizes


def net_SR_for_instrument_in_system(
    system,
    instrument_code,
    minimum_instrument_weight_idm: float,
    instrument_weight_idm: float,
):
    if instrument_weight_idm == 0:
        return 0.0

    if instrument_weight_idm > minimum_instrument_weight_idm:
        instrument_weight_idm = copy(minimum_instrument_weight_idm)

    maximum_pos_final = calculate_maximum_position(
        system, instrument_code, instrument_weight_idm=instrument_weight_idm
    )
    trading_cost = calculate_trading_cost(system, instrument_code)

    return net_SR_for_instrument(
        maximum_position=maximum_pos_final, trading_cost=trading_cost
    )


def calculate_maximum_position(system, instrument_code, instrument_weight_idm=0.25):
    pos_at_average = system.positionSize.get_average_position_at_subsystem_level(
        instrument_code
    )
    pos_at_average_in_system = pos_at_average * instrument_weight_idm
    forecast_multiplier = (
        system.combForecast.get_forecast_cap() / system.positionSize.avg_abs_forecast()
    )

    maximum_pos_final = pos_at_average_in_system.iloc[-1] * forecast_multiplier

    return maximum_pos_final


def calculate_trading_cost(system, instrument_code):
    turnover = system.accounts.subsystem_turnover(instrument_code)
    SR_cost_per_trade = system.accounts.get_SR_cost_per_trade_for_instrument(
        instrument_code
    )

    trading_cost = turnover * SR_cost_per_trade

    return trading_cost


def net_SR_for_instrument(
    maximum_position, trading_cost, notional_SR=0.5, cost_multiplier=1.0
):
    return (
        notional_SR - (trading_cost * cost_multiplier) - size_penalty(maximum_position)
    )


def size_penalty(maximum_position):
    if maximum_position < 0.5:
        return 9999

    return 0.125 / maximum_position**2
