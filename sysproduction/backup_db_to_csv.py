from pathlib import Path
import os
import pandas as pd

from syscore.exceptions import missingData
from syscore.pandas.pdutils import check_df_equals, check_ts_equals
from syscore.dateutils import CALENDAR_DAYS_IN_YEAR
from sysdata.config.production_config import get_production_config
from sysdata.data_blob import dataBlob

from sysdata.csv.csv_futures_contracts import csvFuturesContractData
from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData
from sysdata.csv.csv_futures_contract_prices import csvFuturesContractPriceData
from sysdata.csv.csv_multiple_prices import csvFuturesMultiplePricesData
from sysdata.csv.csv_spot_fx import csvFxPricesData
from sysdata.csv.csv_contract_position_data import csvContractPositionData
from sysdata.csv.csv_strategy_position_data import csvStrategyPositionData
from sysdata.csv.csv_historic_orders import (
    csvStrategyHistoricOrdersData,
    csvContractHistoricOrdersData,
    csvBrokerHistoricOrdersData,
)
from sysdata.csv.csv_capital_data import csvCapitalData
from sysdata.csv.csv_optimal_position import csvOptimalPositionData
from sysdata.csv.csv_spread_costs import csvSpreadCostData
from sysdata.csv.csv_roll_state_storage import csvRollStateData
from sysdata.csv.csv_spreads import csvSpreadsForInstrumentData


from sysobjects.contracts import futuresContract
from sysobjects.production.tradeable_object import instrumentStrategy

from sysproduction.data.directories import get_csv_backup_directory, get_csv_dump_dir
from sysproduction.data.strategies import get_list_of_strategies

from sysproduction.data.production_data_objects import (
    get_class_for_data_type,
    CAPITAL_DATA,
    FUTURES_ADJUSTED_PRICE_DATA,
    FUTURES_CONTRACT_PRICE_DATA,
    FUTURES_MULTIPLE_PRICE_DATA,
    FX_DATA,
    STORED_SPREAD_DATA,
    BROKER_HISTORIC_ORDERS_DATA,
    CONTRACT_HISTORIC_ORDERS_DATA,
    STRATEGY_HISTORIC_ORDERS_DATA,
    CONTRACT_POSITION_DATA,
    STRATEGY_POSITION_DATA,
    FUTURES_CONTRACT_DATA,
    OPTIMAL_POSITION_DATA,
    ROLL_STATE_DATA,
    HISTORIC_SPREAD_DATA,
)


def backup_db_to_csv():
    data = dataBlob(log_name="backup_db_to_csv")
    backup_object = backupDbToCsv(data)
    backup_object.backup_db_to_csv()

    return None


# FIXME SOMEWHAT HACKY
# SHOULD BE A 'BACKUP X' OPTION UNDER DIAGNOSTICS OR CONTROL?
def quick_backup_of_all_price_data_including_expired():
    backup_data = get_data_and_create_csv_directories("Quick backup of all price data")
    backup_futures_contract_prices_to_csv(backup_data, ignore_long_expired=False)


class backupDbToCsv:
    def __init__(self, data):
        self.data = data

    def backup_db_to_csv(self):
        backup_data = get_data_and_create_csv_directories(self.data.log_name)
        log = self.data.log

        log.debug("Dumping from db, mongo to .csv files")
        backup_adj_to_csv(backup_data)
        backup_futures_contract_prices_to_csv(backup_data)
        backup_spreads_to_csv(backup_data)
        backup_fx_to_csv(backup_data)
        backup_multiple_to_csv(backup_data)
        backup_strategy_position_data(backup_data)
        backup_contract_position_data(backup_data)
        backup_historical_orders(backup_data)
        backup_capital(backup_data)
        backup_contract_data(backup_data)
        backup_spread_cost_data(backup_data)
        backup_optimal_positions(backup_data)
        backup_roll_state_data(backup_data)
        log.debug("Copying to offsystem backup directory")
        backup_csv_dump(self.data)


def get_data_and_create_csv_directories(logname):
    csv_dump_dir = get_csv_dump_dir()

    class_paths = dict(
        csvBrokerHistoricOrdersData="broker_orders",
        csvCapitalData="capital",
        csvContractHistoricOrdersData="contract_orders",
        csvContractPositionData="contract_positions",
        csvFuturesAdjustedPricesData="adjusted_prices",
        csvFuturesContractData="contracts_data",
        csvFuturesContractPriceData="contract_prices",
        csvFuturesMultiplePricesData="multiple_prices",
        csvFxPricesData="fx_prices",
        csvOptimalPositionData="optimal_positions",
        csvRollStateData="roll_state",
        csvSpreadCostData="spread_costs",
        csvSpreadsForInstrumentData="spreads",
        csvStrategyHistoricOrdersData="strategy_orders",
        csvStrategyPositionData="strategy_positions",
    )

    for class_name, path in class_paths.items():
        dir_name = Path(csv_dump_dir, path)
        class_paths[class_name] = str(dir_name)
        Path(dir_name).mkdir(exist_ok=True)

        data = dataBlob(csv_data_paths=class_paths, log_name=logname)

    data.add_class_list(
        [
            csvBrokerHistoricOrdersData,
            csvCapitalData,
            csvContractHistoricOrdersData,
            csvContractPositionData,
            csvFuturesAdjustedPricesData,
            csvFuturesContractData,
            csvFuturesContractPriceData,
            csvFuturesMultiplePricesData,
            csvFxPricesData,
            csvOptimalPositionData,
            csvRollStateData,
            csvSpreadCostData,
            csvSpreadsForInstrumentData,
            csvStrategyHistoricOrdersData,
            csvStrategyPositionData,
        ],
        use_prefix="csv",
    )

    data.add_class_list(
        [
            get_class_for_data_type(CAPITAL_DATA),
            get_class_for_data_type(FUTURES_ADJUSTED_PRICE_DATA),
            get_class_for_data_type(FUTURES_CONTRACT_PRICE_DATA),
            get_class_for_data_type(FUTURES_MULTIPLE_PRICE_DATA),
            get_class_for_data_type(FX_DATA),
            get_class_for_data_type(STORED_SPREAD_DATA),
            get_class_for_data_type(BROKER_HISTORIC_ORDERS_DATA),
            get_class_for_data_type(CONTRACT_HISTORIC_ORDERS_DATA),
            get_class_for_data_type(STRATEGY_HISTORIC_ORDERS_DATA),
            get_class_for_data_type(CONTRACT_POSITION_DATA),
            get_class_for_data_type(STRATEGY_POSITION_DATA),
            get_class_for_data_type(FUTURES_CONTRACT_DATA),
            get_class_for_data_type(OPTIMAL_POSITION_DATA),
            get_class_for_data_type(ROLL_STATE_DATA),
            get_class_for_data_type(HISTORIC_SPREAD_DATA),
        ],
        use_prefix="db",
    )

    return data


# Write function for each thing we want to backup
# Think about how to check for duplicates (data frame equals?)


# Futures contract data
def backup_futures_contract_prices_to_csv(data, ignore_long_expired: bool = True):
    instrument_list = data.db_futures_contract_price.get_list_of_instrument_codes_with_merged_price_data()
    for instrument_code in instrument_list:
        backup_futures_contract_prices_for_instrument_to_csv(
            data=data,
            instrument_code=instrument_code,
            ignore_long_expired=ignore_long_expired,
        )


def backup_futures_contract_prices_for_instrument_to_csv(
    data: dataBlob, instrument_code: str, ignore_long_expired: bool = True
):
    list_of_contracts = data.db_futures_contract_price.contracts_with_merged_price_data_for_instrument_code(
        instrument_code
    )

    for futures_contract in list_of_contracts:
        backup_futures_contract_prices_for_contract_to_csv(
            data=data,
            futures_contract=futures_contract,
            ignore_long_expired=ignore_long_expired,
        )


def backup_futures_contract_prices_for_contract_to_csv(
    data: dataBlob, futures_contract: futuresContract, ignore_long_expired: bool = True
):
    if ignore_long_expired:
        if futures_contract.days_since_expiry() > CALENDAR_DAYS_IN_YEAR:
            ## Almost certainly expired, skip
            data.log.debug("Skipping expired contract %s" % str(futures_contract))

            return None

    db_data = data.db_futures_contract_price.get_merged_prices_for_contract_object(
        futures_contract
    )

    csv_data = data.csv_futures_contract_price.get_merged_prices_for_contract_object(
        futures_contract
    )

    if check_df_equals(db_data, csv_data):
        # No update needed, move on
        data.log.debug("No prices backup needed for %s" % str(futures_contract))
    else:
        # Write backup
        try:
            data.csv_futures_contract_price.write_merged_prices_for_contract_object(
                futures_contract,
                db_data,
                ignore_duplication=True,
            )
            data.log.debug(
                "Written backup .csv of prices for %s" % str(futures_contract)
            )
        except BaseException:
            data.log.warning(
                "Problem writing .csv of prices for %s" % str(futures_contract)
            )


# fx
def backup_fx_to_csv(data):
    fx_codes = data.db_fx_prices.get_list_of_fxcodes()
    for fx_code in fx_codes:
        db_data = data.db_fx_prices.get_fx_prices(fx_code)
        csv_data = data.csv_fx_prices.get_fx_prices(fx_code)
        if check_ts_equals(db_data, csv_data):
            data.log.debug("No fx backup needed for %s" % fx_code)
        else:
            # Write backup
            try:
                data.csv_fx_prices.add_fx_prices(
                    fx_code, db_data, ignore_duplication=True
                )
                data.log.debug("Written .csv backup for %s" % fx_code)
            except BaseException:
                data.log.warning("Problem writing .csv backup for %s" % fx_code)


def backup_multiple_to_csv(data):
    instrument_list = data.db_futures_multiple_prices.get_list_of_instruments()
    for instrument_code in instrument_list:
        backup_multiple_to_csv_for_instrument(data, instrument_code)


def backup_multiple_to_csv_for_instrument(data, instrument_code: str):
    db_data = data.db_futures_multiple_prices.get_multiple_prices(instrument_code)
    csv_data = data.csv_futures_multiple_prices.get_multiple_prices(instrument_code)

    if check_df_equals(db_data, csv_data):
        data.log.debug("No multiple prices backup needed for %s" % instrument_code)
        pass
    else:
        try:
            data.csv_futures_multiple_prices.add_multiple_prices(
                instrument_code, db_data, ignore_duplication=True
            )
            data.log.debug(
                "Written .csv backup multiple prices for %s" % instrument_code
            )
        except BaseException:
            data.log.warning(
                "Problem writing .csv backup multiple prices for %s" % instrument_code
            )


def backup_adj_to_csv(data):
    instrument_list = data.db_futures_adjusted_prices.get_list_of_instruments()
    for instrument_code in instrument_list:
        backup_adj_to_csv_for_instrument(data, instrument_code)


def backup_adj_to_csv_for_instrument(data: dataBlob, instrument_code: str):
    db_data = data.db_futures_adjusted_prices.get_adjusted_prices(instrument_code)
    csv_data = data.csv_futures_adjusted_prices.get_adjusted_prices(instrument_code)

    if check_ts_equals(db_data, csv_data):
        data.log.debug("No adjusted prices backup needed for %s" % instrument_code)
        pass
    else:
        try:
            data.csv_futures_adjusted_prices.add_adjusted_prices(
                instrument_code, db_data, ignore_duplication=True
            )
            data.log.debug(
                "Written .csv backup for adjusted prices %s" % instrument_code
            )
        except BaseException:
            data.log.warning(
                "Problem writing .csv backup for adjusted prices %s" % instrument_code
            )


def backup_spreads_to_csv(data: dataBlob):
    instrument_list = data.db_spreads_for_instrument.get_list_of_instruments()
    for instrument_code in instrument_list:
        backup_spreads_to_csv_for_instrument(data, instrument_code)


def backup_spreads_to_csv_for_instrument(data: dataBlob, instrument_code: str):
    db_data = data.db_spreads_for_instrument.get_spreads(instrument_code)
    csv_data = data.csv_spreads_for_instrument.get_spreads(instrument_code)

    if check_ts_equals(db_data, csv_data):
        data.log.debug("No spreads backup needed for %s" % instrument_code)
        pass
    else:
        try:
            data.csv_spreads_for_instrument.add_spreads(
                instrument_code, db_data, ignore_duplication=True
            )
            data.log.debug("Written .csv backup for spreads %s" % instrument_code)
        except BaseException:
            data.log.warning(
                "Problem writing .csv backup for spreads %s" % instrument_code
            )


def backup_contract_position_data(data):
    instrument_list = (
        data.db_contract_position.get_list_of_instruments_with_any_position()
    )
    for instrument_code in instrument_list:
        contract_list = (
            data.db_contract_position.get_list_of_contracts_for_instrument_code(
                instrument_code
            )
        )
        for contract in contract_list:
            try:
                db_data = data.db_contract_position.get_position_as_series_for_contract_object(
                    contract
                )
            except missingData:
                print("No data to write to .csv")
            else:
                data.csv_contract_position.overwrite_position_series_for_contract_object_without_checking(
                    contract, db_data
                )
            data.log.debug(
                "Backed up %s %s contract position data" % (instrument_code, contract)
            )


def backup_strategy_position_data(data):
    strategy_list = get_list_of_strategies(data)
    instrument_list = (
        data.db_contract_position.get_list_of_instruments_with_any_position()
    )
    for strategy_name in strategy_list:
        for instrument_code in instrument_list:
            instrument_strategy = instrumentStrategy(
                strategy_name=strategy_name, instrument_code=instrument_code
            )
            try:
                db_data = data.db_strategy_position.get_position_as_series_for_instrument_strategy_object(
                    instrument_strategy
                )
            except missingData:
                continue
            data.csv_strategy_position.overwrite_position_series_for_instrument_strategy_without_checking(
                instrument_strategy, db_data
            )
            data.log.debug(
                "Backed up %s %s strategy position data"
                % (instrument_code, strategy_name)
            )


def backup_historical_orders(data):
    data.log.debug("Backing up strategy orders...")
    list_of_orders = [
        data.db_strategy_historic_orders.get_order_with_orderid(id)
        for id in data.db_strategy_historic_orders.get_list_of_order_ids()
    ]
    data.csv_strategy_historic_orders.write_orders(list_of_orders)
    data.log.debug("Done")

    data.log.debug("Backing up contract orders...")
    list_of_orders = [
        data.db_contract_historic_orders.get_order_with_orderid(order_id)
        for order_id in data.db_contract_historic_orders.get_list_of_order_ids()
    ]
    data.csv_contract_historic_orders.write_orders(list_of_orders)
    data.log.debug("Done")

    data.log.debug("Backing up broker orders...")
    list_of_orders = [
        data.db_broker_historic_orders.get_order_with_orderid(order_id)
        for order_id in data.db_broker_historic_orders.get_list_of_order_ids()
    ]
    data.csv_broker_historic_orders.write_orders(list_of_orders)
    data.log.debug("Done")


def backup_capital(data):
    strategy_capital_dict = get_dict_of_strategy_capital(data)
    capital_data_df = add_total_capital_to_strategy_capital_dict_return_df(
        data, strategy_capital_dict
    )
    capital_data_df = capital_data_df.ffill()

    data.csv_capital.write_backup_df_of_all_capital(capital_data_df)


def get_dict_of_strategy_capital(data: dataBlob) -> dict:
    strategy_list = get_list_of_strategies(data)
    strategy_capital_data = dict()
    for strategy_name in strategy_list:
        strategy_capital_data[strategy_name] = (
            data.db_capital.get_capital_pd_df_for_strategy(strategy_name)
        )

    return strategy_capital_data


def add_total_capital_to_strategy_capital_dict_return_df(
    data: dataBlob, capital_data: dict
) -> pd.DataFrame:
    strategy_capital_as_df = pd.concat(capital_data, axis=1)
    total_capital = data.db_capital.get_df_of_all_global_capital()
    capital_data = pd.concat([strategy_capital_as_df, total_capital], axis=1)

    capital_data = capital_data.ffill()

    return capital_data


def backup_optimal_positions(data):
    strategy_instrument_list = data.db_optimal_position.get_list_of_instrument_strategies_with_optimal_position()

    for instrument_strategy in strategy_instrument_list:
        try:
            db_data = data.db_optimal_position.get_optimal_position_as_df_for_instrument_strategy(
                instrument_strategy
            )
        except missingData:
            continue
        data.csv_optimal_position.write_optimal_position_as_df_for_instrument_strategy_without_checking(
            instrument_strategy, db_data
        )
        data.log.debug("Backed up %s  optimal position data" % str(instrument_strategy))


def backup_spread_cost_data(data):
    spread_cost_as_series = data.db_spread_cost.get_spread_costs_as_series()
    data.csv_spread_cost.write_all_instrument_spreads(spread_cost_as_series)
    data.log.debug("Backed up spread cost data")


def backup_roll_state_data(data):
    instrument_list = data.db_roll_state.get_list_of_instruments()
    roll_state_list = []
    for instrument_code in instrument_list:
        roll_state = data.db_roll_state.get_name_of_roll_state(instrument_code)
        roll_state_list.append(roll_state)

    roll_state_df = pd.DataFrame(roll_state_list, index=instrument_list)
    roll_state_df.columns = ["state"]
    data.csv_roll_state.write_all_instrument_data(roll_state_df)
    data.log.debug("Backed up roll state")


def backup_contract_data(data):
    instrument_list = (
        data.db_futures_contract.get_list_of_all_instruments_with_contracts()
    )
    for instrument_code in instrument_list:
        contract_list = (
            data.db_futures_contract.get_all_contract_objects_for_instrument_code(
                instrument_code
            )
        )
        data.csv_futures_contract.write_contract_list_as_df(
            instrument_code, contract_list
        )
        data.log.debug("Backed up contract data for %s" % instrument_code)


def backup_csv_dump(data):
    source_path = get_csv_dump_dir()
    destination_path = get_csv_backup_directory()
    data.log.debug("Copy from %s to %s" % (source_path, destination_path))
    options = get_production_config().get_element("offsystem_backup_options")
    os.system(f"rsync {options} {source_path} {destination_path}")


if __name__ == "__main__":
    backup_db_to_csv()
