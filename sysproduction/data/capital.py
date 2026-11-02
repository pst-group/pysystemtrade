import datetime
import pandas as pd

from syscore.constants import arg_not_supplied
from syscore.exceptions import missingData

from sysdata.production.capital import capitalData, totalCapitalCalculationData
from sysdata.production.margin import marginData, seriesOfMargin

from sysdata.mongodb.mongo_margin import mongoMarginData
from sysdata.data_blob import dataBlob

from sysproduction.data.generic_production_data import productionDataLayerGeneric
from sysproduction.data.production_data_objects import (
    get_class_for_data_type,
    CAPITAL_DATA,
)

from systems.accounts.from_returns import account_curve_from_returns


class dataCapital(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        capital_data_class = get_class_for_data_type(CAPITAL_DATA)
        data.add_class_object(capital_data_class)

        return data

    @property
    def db_capital_data(self) -> capitalData:
        return self.data.db_capital

    ## TOTAL CAPITAL...

    def get_percentage_returns_as_account_curve(self) -> pd.DataFrame:
        return account_curve_from_returns(self.get_percentage_returns_as_pd())

    def get_percentage_returns_as_pd(self) -> pd.DataFrame:
        return self.total_capital_calculator.get_percentage_returns_as_pd()

    def get_current_total_capital(self) -> float:
        return self.total_capital_calculator.get_current_total_capital()

    def get_current_broker_account_value(self) -> float:
        return self.total_capital_calculator.get_current_broker_account()

    def get_current_maximum_capital(self) -> float:
        return self.total_capital_calculator.get_current_maximum_capital()

    def get_current_accumulated_pandl(self) -> float:
        return self.total_capital_calculator.get_current_accumulated_pandl()

    def check_for_total_capital_data(self) -> bool:
        total_capital_data_exists = (
            self.total_capital_calculator.check_for_total_capital_data()
        )

        return total_capital_data_exists

    def update_and_return_total_capital_with_new_broker_account_value(
        self, total_account_value_in_base_currency: float, check_limit: float = 0.1
    ) -> float:
        result = self.total_capital_calculator.update_and_return_total_capital_with_new_broker_account_value(
            total_account_value_in_base_currency, check_limit=check_limit
        )

        return result

    def get_series_of_all_global_capital(self) -> pd.DataFrame:
        all_capital_data = self.total_capital_calculator.get_df_of_all_global_capital()

        return all_capital_data

    def get_series_of_maximum_capital(self) -> pd.Series:
        return self.total_capital_calculator.get_maximum_account()

    def get_series_of_accumulated_capital(self) -> pd.Series:
        return self.total_capital_calculator.get_profit_and_loss_account()

    def create_initial_capital(
        self,
        broker_account_value: float,
        total_capital: float = arg_not_supplied,
        maximum_capital: float = arg_not_supplied,
        acc_pandl: float = arg_not_supplied,
        are_you_really_sure: bool = False,
    ):
        self.total_capital_calculator.create_initial_capital(
            broker_account_value=broker_account_value,
            total_capital=total_capital,
            maximum_capital=maximum_capital,
            acc_pandl=acc_pandl,
            are_you_really_sure=are_you_really_sure,
        )

    def return_str_with_effect_of_delta_adjustment(self, capital_delta: float):
        old_capital = self.total_capital_calculator.capital_data.get_current_broker_account_value()
        new_capital = old_capital + capital_delta
        return "Old brokerage capital %f, adjustment %f, New capital %f" % (
            old_capital,
            capital_delta,
            new_capital,
        )

    def adjust_broker_account_for_delta(self, capital_delta: float):
        self.total_capital_calculator.adjust_broker_account_for_delta(capital_delta)

    def modify_account_values(
        self,
        broker_account_value: float = arg_not_supplied,
        total_capital: float = arg_not_supplied,
        maximum_capital: float = arg_not_supplied,
        acc_pandl: float = arg_not_supplied,
        date: datetime.datetime = arg_not_supplied,
        are_you_sure: bool = False,
    ):
        self.total_capital_calculator.modify_account_values(
            broker_account_value=broker_account_value,
            total_capital=total_capital,
            maximum_capital=maximum_capital,
            acc_pandl=acc_pandl,
            date=date,
            are_you_sure=are_you_sure,
        )

    @property
    def total_capital_calculator(self) -> totalCapitalCalculationData:
        # cache because could be slow getting calculation method from yaml
        total_capital_calculator = getattr(self, "_total_capital_calculator", None)
        if total_capital_calculator is None:
            total_capital_calculator = self._get_total_capital_calculator()
            self._total_capital_calculator = total_capital_calculator

        return total_capital_calculator

    def _get_total_capital_calculator(self) -> totalCapitalCalculationData:
        calc_method = self.get_capital_calculation_method()
        total_capital_calculator = totalCapitalCalculationData(
            self.db_capital_data, calc_method=calc_method
        )

        return total_capital_calculator

    def get_capital_calculation_method(self) -> str:
        config = self.data.config

        return config.production_capital_method

    ## STRATEGY CAPITAL
    def get_capital_pd_series_for_strategy(self, strategy_name: str) -> pd.Series:
        capital_series = self.db_capital_data.get_capital_pd_df_for_strategy(
            strategy_name
        )
        return capital_series.squeeze()

    def get_list_of_strategies_with_capital(self) -> list:
        strat_list = self.db_capital_data.get_list_of_strategies_with_capital()
        return strat_list

    def get_current_capital_for_strategy(self, strategy_name: str) -> float:
        try:
            capital_value = self.db_capital_data.get_current_capital_for_strategy(
                strategy_name
            )
        except missingData:
            self.data.log.error("Capital data is missing for %s" % strategy_name)
            raise

        return capital_value

    def update_capital_value_for_strategy(
        self,
        strategy_name: str,
        new_capital_value: float,
        date: datetime.datetime = arg_not_supplied,
    ):
        self.db_capital_data.update_capital_value_for_strategy(
            strategy_name, new_capital_value, date=date
        )

    def delete_recent_global_capital(
        self, last_date: datetime.datetime, are_you_sure: bool = False
    ):
        self.total_capital_calculator.delete_recent_capital(
            last_date, are_you_sure=are_you_sure
        )

    def delete_all_global_capital(self, are_you_really_sure: bool = False):
        self.total_capital_calculator.delete_all_global_capital(
            are_you_really_sure=are_you_really_sure
        )


class dataMargin(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_object(mongoMarginData)

        return data

    @property
    def db_margin_data(self) -> marginData:
        return self.data.db_margin

    def get_series_of_total_margin(self) -> seriesOfMargin:
        return self.db_margin_data.get_series_of_total_margin()

    def get_current_total_margin(self) -> float:
        return self.db_margin_data.get_current_total_margin()

    def add_total_margin_entry(self, margin_entry: float):
        self.db_margin_data.add_total_margin_entry(margin_entry)

    def get_list_of_strategies_with_margin(self) -> list:
        return self.db_margin_data.get_list_of_strategies_with_margin()

    def get_current_strategy_margin(self, strategy_name: str) -> float:
        return self.db_margin_data.get_current_strategy_margin(strategy_name)

    def add_strategy_margin_entry(self, margin_entry: float, strategy_name: str):
        self.db_margin_data.add_strategy_margin_entry(
            margin_entry=margin_entry, strategy_name=strategy_name
        )

    def get_series_of_strategy_margin(self, strategy_name: str) -> seriesOfMargin:
        return self.db_margin_data.get_series_of_strategy_margin(strategy_name)


def capital_for_strategy(data, strategy_name):
    data_capital = dataCapital(data)
    try:
        capital = data_capital.get_current_capital_for_strategy(strategy_name)
    except missingData:
        return 0.00001

    return capital
