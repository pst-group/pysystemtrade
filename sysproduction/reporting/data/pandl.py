import datetime
from collections import namedtuple

import pandas as pd

from syscore.exceptions import missingContract, missingData
from syscore.constants import arg_not_supplied
from sysobjects.contracts import futuresContract
from sysobjects.production.tradeable_object import instrumentStrategy

from sysproduction.data.capital import dataCapital
from sysproduction.data.currency_data import dataCurrency
from sysproduction.data.instruments import diagInstruments
from sysproduction.data.orders import dataOrders
from sysproduction.data.positions import diagPositions
from sysproduction.data.prices import diagPrices
from systems.accounts.pandl_calculators.pandl_using_fills import (
    pandlCalculationWithFills,
)


def get_total_capital_series(data):
    data_capital_object = dataCapital(data)

    return data_capital_object.get_series_of_maximum_capital()


def get_strategy_capital_series(data, strategy_name):
    data_capital_object = dataCapital(data)

    return df_to_series(
        data_capital_object.get_capital_pd_series_for_strategy(strategy_name)
    )


def df_to_series(x):
    return x._series[x.keys()[0]]


def get_daily_perc_pandl(data):
    data_capital_object = dataCapital(data)

    # This is for 'non compounding' p&l
    total_pandl_series = data_capital_object.get_series_of_accumulated_capital()
    daily_pandl_series = total_pandl_series.ffill().diff()

    all_capital = get_total_capital_series(data)

    perc_pandl_series = daily_pandl_series / all_capital

    return perc_pandl_series * 100


def get_total_capital_pandl(data, start_date, end_date=arg_not_supplied):
    if end_date is arg_not_supplied:
        end_date = datetime.datetime.now()
    perc_pandl_series = get_daily_perc_pandl(data)

    relevant_pandl = perc_pandl_series[start_date:end_date]
    pandl_in_period = relevant_pandl.sum()

    return pandl_in_period


PandL = namedtuple("PandL", ["code", "pandl"])


class pandlCalculateAndStore(object):
    def __init__(
        self, data, start_date: datetime.datetime, end_date: datetime.datetime
    ):
        self.data = data
        self.start_date = start_date
        self.end_date = end_date

    def get_strategy_pandl_and_residual(self):
        strategies_pandl = self.get_ranked_list_of_pandl_by_strategy_in_date_range()

        total_pandl_strategies = strategies_pandl.pandl.sum()
        total_pandl = get_total_capital_pandl(self.data, self.start_date, self.end_date)
        residual_pandl = total_pandl - total_pandl_strategies
        residual_dfrow = pd.DataFrame(dict(codes=["residual"], pandl=residual_pandl))
        strategies_pandl = strategies_pandl._append(residual_dfrow)
        strategies_pandl.pandl = strategies_pandl.pandl

        return strategies_pandl

    def get_ranked_list_of_pandl_by_instrument_all_strategies_in_date_range(self):
        list_pandl = self.get_period_perc_pandl_for_all_instruments_all_strategies_in_date_range()
        list_pandl = [pandl for pandl in list_pandl if pandl.pandl != 0]
        list_pandl.sort(key=lambda r: r.pandl)

        pandl_as_df = list_pandl_to_df(list_pandl)

        return pandl_as_df

    def get_sector_pandl(self):
        list_pandl = self.get_period_perc_pandl_for_all_sectors_in_date_range()
        list_pandl = [pandl for pandl in list_pandl if pandl.pandl != 0]
        list_pandl.sort(key=lambda r: r.pandl)

        pandl_as_df = list_pandl_to_df(list_pandl)

        return pandl_as_df

    def get_ranked_list_of_pandl_by_strategy_in_date_range(self):
        list_pandl = self.get_period_perc_pandl_for_all_strategies_in_date_range()
        list_pandl.sort(key=lambda r: r.pandl)

        pandl_as_df = list_pandl_to_df(list_pandl)

        return pandl_as_df

    def get_period_perc_pandl_for_all_instruments_all_strategies_in_date_range(self):
        diag_positions = diagPositions(self.data)
        instrument_list = diag_positions.get_list_of_instruments_with_any_position()

        list_pandl = [
            PandL(
                instrument_code,
                self.get_period_perc_pandl_for_instrument_all_strategies_in_date_range(
                    instrument_code
                ),
            )
            for instrument_code in instrument_list
        ]

        return list_pandl

    def get_period_perc_pandl_for_all_sectors_in_date_range(self):
        diag_instruments = diagInstruments(self.data)
        asset_classes = diag_instruments.get_all_asset_classes()
        list_pandl = [
            PandL(
                asset_class,
                self.get_period_perc_pandl_for_sector_in_date_range(asset_class),
            )
            for asset_class in asset_classes
        ]

        return list_pandl

    def get_period_perc_pandl_for_all_strategies_in_date_range(self):
        strategy_list = get_list_of_strategies(self.data)
        list_pandl = [
            PandL(
                strategy_name,
                self.get_period_perc_pandl_for_strategy_in_date_range(
                    strategy_name=strategy_name
                ),
            )
            for strategy_name in strategy_list
        ]

        return list_pandl

    def get_period_perc_pandl_for_sector_in_date_range(self, asset_class: str):
        diag_instruments = diagInstruments(self.data)
        list_of_instruments = diag_instruments.get_all_instruments_in_asset_class(
            asset_class
        )
        instrument_pandl = [
            self.get_period_perc_pandl_for_instrument_all_strategies_in_date_range(
                instrument_code
            )
            for instrument_code in list_of_instruments
        ]
        asset_class_pandl = sum(instrument_pandl)

        return asset_class_pandl

    def get_period_perc_pandl_for_instrument_all_strategies_in_date_range(
        self, instrument_code: str
    ) -> float:
        self.data.log.info("Getting p&l for %s" % instrument_code)

        try:
            pandl_across_contracts = self.pandl_for_instrument_across_contracts(
                instrument_code
            )
        except missingContract:
            return 0.0

        pandl_series = pandl_across_contracts.sum(axis=1)

        return pandl_series.sum()

    def pandl_for_instrument_across_contracts(
        self, instrument_code: str
    ) -> pd.DataFrame:
        ## can return missing contract
        pandl_store = self.instrument_pandl_store
        try:
            pandl_for_instrument = pandl_store[instrument_code]
        except KeyError:
            pandl_for_instrument = self._get_pandl_for_instrument_across_contracts(
                instrument_code
            )
            pandl_store[instrument_code] = pandl_for_instrument

        return pandl_for_instrument

    @property
    def instrument_pandl_store(self):
        try:
            store = getattr(self, "_instrument_pandl_store")
        except AttributeError:
            store = {}
            setattr(self, "_instrument_pandl_store", store)
        return store

    def _get_pandl_for_instrument_across_contracts(
        self, instrument_code: str
    ) -> pd.DataFrame:
        pandl_df_all_data = get_df_of_perc_pandl_series_for_instrument_all_strategies_across_contracts_in_date_range(
            self.data, instrument_code, self.start_date, self.end_date
        )

        pandl_df = pandl_df_all_data[self.start_date : self.end_date]

        return pandl_df

    def get_period_perc_pandl_for_strategy_in_date_range(self, strategy_name: str):
        self.data.log.info("Getting p&l for %s" % strategy_name)
        try:
            pandl_df = self.get_df_of_perc_pandl_series_for_strategy_all_instruments(
                strategy_name
            )
        except missingData:
            return 0.0

        pandl_df = pandl_df[self.start_date : self.end_date]
        pandl_series = pandl_df.sum(axis=1, skipna=True)
        pandl_series = pandl_series.dropna()

        return pandl_series.sum()

    def get_df_of_perc_pandl_series_for_strategy_all_instruments(
        self, strategy_name: str
    ) -> pd.DataFrame:
        (
            instrument_list,
            pandl_list,
        ) = self.get_list_of_perc_pandl_series_for_strategy_all_instruments(
            strategy_name
        )

        pandl_df = pd.concat(pandl_list, axis=1)
        pandl_df.columns = instrument_list

        return pandl_df

    def get_list_of_perc_pandl_series_for_strategy_all_instruments(
        self, strategy_name: str
    ):
        instrument_list = get_list_of_instruments_held_for_a_strategy(
            self.data, strategy_name
        )
        if len(instrument_list) == 0:
            raise missingData

        pandl_list = [
            self.perc_pandl_series_for_strategy_instrument_vs_total_capital(
                instrumentStrategy(strategy_name, instrument_code)
            )
            for instrument_code in instrument_list
        ]

        return instrument_list, pandl_list

    def perc_pandl_series_for_strategy_instrument_vs_total_capital(
        self, instrument_strategy: instrumentStrategy
    ):
        strategy_pandl_store = self.strategy_pandl_store
        store_key = instrument_strategy.key

        try:
            pandl_series = strategy_pandl_store[store_key]
        except KeyError:
            pandl_series = (
                self._get_perc_pandl_series_for_strategy_instrument_vs_total_capital(
                    instrument_strategy
                )
            )
            strategy_pandl_store[store_key] = pandl_series

        return pandl_series

    def _get_perc_pandl_series_for_strategy_instrument_vs_total_capital(
        self, instrument_strategy: instrumentStrategy
    ):
        pandl_series = get_perc_pandl_series_for_strategy_instrument_vs_total_capital(
            self.data, instrument_strategy
        )

        return pandl_series

    @property
    def strategy_pandl_store(self):
        try:
            store = getattr(self, "_strategy_pandl_store")
        except AttributeError:
            store = {}
            setattr(self, "_strategy_pandl_store", store)
        return store


def get_df_of_perc_pandl_series_for_instrument_all_strategies_across_contracts_in_date_range(
    data, instrument_code, start_date, end_date
):
    (
        contract_list,
        pandl_list,
    ) = get_list_of_perc_pandl_series_for_instrument_all_strategies_across_contracts_in_date_range(
        data, instrument_code, start_date, end_date
    )

    pandl_df = pd.concat(pandl_list, axis=1)
    pandl_df.columns = contract_list

    return pandl_df


def get_list_of_perc_pandl_series_for_instrument_all_strategies_across_contracts_in_date_range(
    data, instrument_code, start_date, end_date
):
    contract_list = get_list_of_contracts_held_for_an_instrument_in_date_range(
        data, instrument_code, start_date, end_date
    )
    if len(contract_list) == 0:
        raise missingContract

    pandl_list = [
        get_perc_pandl_series_for_contract(data, instrument_code, contract_id)
        for contract_id in contract_list
    ]

    return contract_list, pandl_list


def get_list_of_contracts_held_for_an_instrument_in_date_range(
    data, instrument_code, start_date, end_date
):
    diag_positions = diagPositions(data)

    contract_list = diag_positions.get_list_of_contracts_with_any_contract_position_for_instrument_in_date_range(
        instrument_code, start_date, end_date
    )

    return contract_list


def get_list_of_instruments_held_for_a_strategy(data, strategy_name):
    diag_positions = diagPositions(data)
    instrument_list = diag_positions.get_list_of_instruments_for_strategy_with_position(
        strategy_name
    )

    return instrument_list


def get_perc_pandl_series_for_contract(data, instrument_code, contract_id):
    capital = get_total_capital_series(data)
    fx = get_fx_series_for_instrument(data, instrument_code)
    diag_instruments = diagInstruments(data)
    value_per_point = diag_instruments.get_point_size(instrument_code)

    positions = get_position_series_for_contract(data, instrument_code, contract_id)
    prices = get_price_series_for_contract(data, instrument_code, contract_id)
    fills = get_fills_for_contract(data, instrument_code, contract_id)

    calculator = pandlCalculationWithFills.using_positions_and_prices_merged_from_fills(
        prices,
        positions=positions,
        fills=fills,
        fx=fx,
        capital=capital,
        value_per_point=value_per_point,
    )

    perc_pandl = calculator.percentage_pandl()

    return perc_pandl


def get_perc_pandl_series_for_strategy_instrument_vs_total_capital(
    data, instrument_strategy: instrumentStrategy
):
    data.log.info("Data for %s" % instrument_strategy)
    instrument_code = instrument_strategy.instrument_code
    strategy_name = instrument_strategy.strategy_name

    capital = get_total_capital_series(data)
    fx = get_fx_series_for_instrument(data, instrument_code)

    diag_instruments = diagInstruments(data)
    value_per_point = diag_instruments.get_point_size(instrument_code)

    positions = get_position_series_for_instrument_strategy(
        data, instrument_code=instrument_code, strategy_name=strategy_name
    )
    prices = get_current_contract_price_series_for_instrument(
        data, instrument_code=instrument_code
    )
    fills = get_fills_for_instrument(
        data, instrument_code=instrument_code, strategy_name=strategy_name
    )

    calculator = pandlCalculationWithFills.using_positions_and_prices_merged_from_fills(
        prices,
        positions=positions,
        fills=fills,
        fx=fx,
        capital=capital,
        value_per_point=value_per_point,
    )

    perc_pandl = calculator.percentage_pandl()

    return perc_pandl


def get_fx_series_for_instrument(data, instrument_code):
    diag_instruments = diagInstruments(data)
    currency = diag_instruments.get_currency(instrument_code)
    currency_data = dataCurrency(data)
    fx_series = currency_data.get_fx_prices_to_base(currency)

    return fx_series


def get_price_series_for_contract(data, instrument_code, contract_id):
    diag_prices = diagPrices(data)
    contract = futuresContract(instrument_code, contract_id)
    all_prices = diag_prices.get_merged_prices_for_contract_object(contract)
    price_series = all_prices.return_final_prices()

    return price_series


def get_current_contract_price_series_for_instrument(data, instrument_code):
    diag_prices = diagPrices(data)
    price_series = diag_prices.get_current_priced_contract_prices_for_instrument(
        instrument_code
    )

    return price_series


def get_position_series_for_instrument_strategy(data, instrument_code, strategy_name):
    diag_positions = diagPositions(data)
    instrument_strategy = instrumentStrategy(
        strategy_name=strategy_name, instrument_code=instrument_code
    )

    try:
        pos_series = diag_positions.get_position_series_for_instrument_strategy(
            instrument_strategy
        )
    except missingData:
        return pd.Series()

    return pos_series


def get_fills_for_contract(data, instrument_code, contract_id):
    data_orders = dataOrders(data)
    contract = futuresContract(instrument_code, contract_id)
    list_of_fills = data_orders.get_fills_history_for_contract(contract)

    return list_of_fills


def get_fills_for_instrument(data, instrument_code, strategy_name):
    data_orders = dataOrders(data)
    instrument_strategy = instrumentStrategy(
        instrument_code=instrument_code, strategy_name=strategy_name
    )

    list_of_fills = data_orders.get_fills_history_for_instrument_strategy(
        instrument_strategy
    )

    return list_of_fills


def get_position_series_for_contract(data, instrument_code: str, contract_id: str):
    diag_positions = diagPositions(data)
    contract = futuresContract(instrument_code, contract_id)

    try:
        pos_series = diag_positions.get_position_series_for_contract(contract)
    except missingData:
        return pd.Series()

    return pos_series


def get_list_of_strategies(data):
    diag_positions = diagPositions(data)
    return diag_positions.get_list_of_strategies_with_positions()


def list_pandl_to_df(list_pandl):
    code_list = [pandl.code for pandl in list_pandl]
    pandl_list = [pandl.pandl for pandl in list_pandl]

    return pd.DataFrame(dict(codes=code_list, pandl=pandl_list))
