from typing import List, Dict
from copy import copy
import pandas as pd
import datetime

from syscore.constants import arg_not_supplied, success, failure
from syscore.exceptions import ContractNotFound
from sysexecution.orders.named_order_objects import missing_order


from sysdata.production.roll_state import rollStateData
from sysdata.production.historic_contract_positions import contractPositionData
from sysdata.production.historic_strategy_positions import (
    strategyPositionData,
    listOfInstrumentStrategyPositions,
)

from sysdata.data_blob import dataBlob

from sysexecution.trade_qty import tradeQuantity
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.instrument_orders import instrumentOrder

from sysobjects.production.positions import listOfContractPositions, contractPosition
from sysobjects.production.tradeable_object import (
    listOfInstrumentStrategies,
    instrumentStrategy,
)
from sysobjects.production.roll_state import (
    RollState,
    is_roll_state_requiring_order_generation,
    is_double_sided_trade_roll_state,
    passive_roll_state,
)
from sysobjects.contracts import futuresContract

from sysproduction.data.generic_production_data import productionDataLayerGeneric
from sysproduction.data.contracts import dataContracts
from sysproduction.data.production_data_objects import (
    get_class_for_data_type,
    ROLL_STATE_DATA,
    STRATEGY_POSITION_DATA,
    CONTRACT_POSITION_DATA,
)


class diagPositions(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_list(
            [
                get_class_for_data_type(ROLL_STATE_DATA),
                get_class_for_data_type(STRATEGY_POSITION_DATA),
                get_class_for_data_type(CONTRACT_POSITION_DATA),
            ]
        )
        return data

    @property
    def data_contracts(self) -> dataContracts:
        return dataContracts(self.data)

    @property
    def db_roll_state_data(self) -> rollStateData:
        return self.data.db_roll_state

    @property
    def db_contract_position_data(self) -> contractPositionData:
        return self.data.db_contract_position

    @property
    def db_strategy_position_data(self) -> strategyPositionData:
        return self.data.db_strategy_position

    def is_double_sided_trade_roll_state(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_forced_roll_required = is_double_sided_trade_roll_state(roll_state)

        return is_forced_roll_required

    def is_roll_state_requiring_order_generation(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_forced_roll_required = is_roll_state_requiring_order_generation(roll_state)

        return is_forced_roll_required

    def is_roll_state_passive(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_roll_state_passive = roll_state == passive_roll_state

        return is_roll_state_passive

    def is_roll_state_no_roll(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_roll_state_no_roll = roll_state == RollState.No_Roll

        return is_roll_state_no_roll

    def is_roll_state_force(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_roll_state_force = roll_state == RollState.Force

        return is_roll_state_force

    def is_roll_state_force_outright(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)
        is_roll_state_force_outright = roll_state == RollState.Force_Outright

        return is_roll_state_force_outright

    def is_roll_state_close(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)

        is_roll_state_close = roll_state == RollState.Close

        return is_roll_state_close

    def is_roll_state_no_open(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)

        is_roll_state_no_open = roll_state == RollState.No_Open

        return is_roll_state_no_open

    def is_roll_state_adjusted(self, instrument_code: str) -> bool:
        roll_state = self.get_roll_state(instrument_code)

        is_roll_state_adjusted = roll_state == RollState.Roll_Adjusted

        return is_roll_state_adjusted

    def get_name_of_roll_state(self, instrument_code: str) -> RollState:
        roll_state_name = self.db_roll_state_data.get_name_of_roll_state(
            instrument_code
        )

        return roll_state_name

    def get_roll_state(self, instrument_code: str) -> RollState:
        roll_state = self.db_roll_state_data.get_roll_state(instrument_code)

        return roll_state

    def get_dict_of_actual_positions_for_strategy(
        self, strategy_name: str
    ) -> Dict[str, int]:
        list_of_instruments = self.get_list_of_instruments_for_strategy_with_position(
            strategy_name
        )
        list_of_instrument_strategies = [
            instrumentStrategy(
                strategy_name=strategy_name, instrument_code=instrument_code
            )
            for instrument_code in list_of_instruments
        ]

        actual_positions = dict(
            [
                (
                    instrument_strategy.instrument_code,
                    self.get_current_position_for_instrument_strategy(
                        instrument_strategy
                    ),
                )
                for instrument_strategy in list_of_instrument_strategies
            ]
        )

        return actual_positions

    def get_position_series_for_contract(self, contract: futuresContract) -> pd.Series:
        df_object = (
            self.db_contract_position_data.get_position_as_series_for_contract_object(
                contract
            )
        )

        return df_object

    def get_position_series_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> pd.Series:
        position_series = self.db_strategy_position_data.get_position_as_series_for_instrument_strategy_object(
            instrument_strategy
        )

        return position_series

    def get_positions_for_instrument_and_contract_list(
        self, instrument_code: str, list_of_contract_date_str: list
    ) -> list:
        list_of_contracts = [
            futuresContract(instrument_code, contract_date_str)
            for contract_date_str in list_of_contract_date_str
        ]

        list_of_positions = [
            self.get_position_for_contract(contract) for contract in list_of_contracts
        ]

        return list_of_positions

    def get_position_for_contract(self, contract: futuresContract) -> float:
        position = (
            self.db_contract_position_data.get_current_position_for_contract_object(
                contract
            )
        )

        return position

    def get_current_position_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> int:
        position = self.db_strategy_position_data.get_current_position_for_instrument_strategy_object(
            instrument_strategy
        )

        return position

    def get_list_of_instruments_for_strategy_with_position(
        self, strategy_name: str, ignore_zero_positions=True
    ) -> List[str]:
        instrument_list = self.db_strategy_position_data.get_list_of_instruments_for_strategy_with_position(
            strategy_name, ignore_zero_positions=ignore_zero_positions
        )
        return instrument_list

    def get_list_of_instruments_with_any_position(self) -> list:
        instrument_list = (
            self.db_contract_position_data.get_list_of_instruments_with_any_position()
        )

        return instrument_list

    def get_list_of_instruments_with_current_positions(self) -> list:
        instrument_list = self.db_contract_position_data.get_list_of_instruments_with_current_positions()

        return instrument_list

    def get_list_of_strategies_with_positions(self) -> list:
        list_of_strategies = (
            self.db_strategy_position_data.get_list_of_strategies_with_positions()
        )

        return list_of_strategies

    def get_list_of_strategies_and_instruments_with_positions(
        self,
    ) -> listOfInstrumentStrategies:
        return self.db_strategy_position_data.get_list_of_strategies_and_instruments_with_positions()

    def get_all_current_contract_positions_with_db_expiries(
        self,
    ) -> listOfContractPositions:
        list_of_current_positions = self.db_contract_position_data.get_all_current_positions_as_list_with_contract_objects()
        list_of_current_positions_with_expiries = (
            self.update_expiries_for_position_list(list_of_current_positions)
        )

        return list_of_current_positions_with_expiries

    def get_all_current_contract_positions(self) -> listOfContractPositions:
        list_of_current_positions = self.db_contract_position_data.get_all_current_positions_as_list_with_contract_objects()

        return list_of_current_positions

    def update_expiries_for_position_list(
        self, original_position_list: listOfContractPositions
    ) -> listOfContractPositions:
        new_position_list = listOfContractPositions()
        for position_entry in original_position_list:
            new_position_entry = self.update_expiry_for_single_position(position_entry)
            new_position_list.append(new_position_entry)

        return new_position_list

    def update_expiry_for_single_position(
        self, position_entry: contractPosition
    ) -> contractPosition:
        original_contract = position_entry.contract
        new_contract = self.update_expiry_for_single_contract(original_contract)

        position = position_entry.position
        new_position_entry = contractPosition(position, new_contract)

        return new_position_entry

    def update_expiry_for_single_contract(
        self, original_contract: futuresContract
    ) -> futuresContract:
        data_contracts = dataContracts(self.data)
        try:
            actual_expiry = data_contracts.get_actual_expiry(
                original_contract.instrument_code, original_contract.contract_date
            )
        except ContractNotFound:
            self.data.log.warning(
                "Contract %s is missing from database - expiry not found and will mismatch"
                % str(original_contract),
                **original_contract.log_attributes(),
                method="temp",
            )
            new_contract = copy(original_contract)
        else:
            expiry_date_as_str = actual_expiry.as_str()
            instrument_code = original_contract.instrument_code
            new_contract = futuresContract(instrument_code, expiry_date_as_str)

        return new_contract

    def get_all_current_strategy_instrument_positions(
        self,
    ) -> listOfInstrumentStrategyPositions:
        list_of_current_positions = self.db_strategy_position_data.get_all_current_positions_as_list_with_instrument_objects()

        return list_of_current_positions

    def get_current_instrument_position_across_strategies(
        self, instrument_code: str
    ) -> int:
        all_positions = self.get_all_current_strategy_instrument_positions()
        all_positions_sum_over_instruments = all_positions.sum_for_instrument()
        position = all_positions_sum_over_instruments.position_for_instrument(
            instrument_code
        )

        return position

    def get_list_of_breaks_between_contract_and_strategy_positions(self) -> list:
        contract_positions = self.get_all_current_contract_positions()
        instrument_positions_from_contract = contract_positions.sum_for_instrument()
        strategy_instrument_positions = (
            self.get_all_current_strategy_instrument_positions()
        )
        instrument_positions_from_strategies = (
            strategy_instrument_positions.sum_for_instrument()
        )

        list_of_breaks = instrument_positions_from_contract.return_list_of_breaks(
            instrument_positions_from_strategies
        )
        return list_of_breaks

    def get_list_of_contracts_with_any_contract_position_for_instrument(
        self, instrument_code: str
    ):
        list_of_date_str = self.db_contract_position_data.get_list_of_contract_date_str_with_any_position_for_instrument(
            instrument_code
        )

        return list_of_date_str

    def get_list_of_contracts_with_any_contract_position_for_instrument_in_date_range(
        self,
        instrument_code: str,
        start_date: datetime.datetime,
        end_date: datetime.datetime = arg_not_supplied,
    ) -> list:
        if end_date is arg_not_supplied:
            end_date = datetime.datetime.now()

        list_of_date_str_with_position = self.db_contract_position_data.get_list_of_contract_date_str_with_any_position_for_instrument_in_date_range(
            instrument_code, start_date, end_date
        )

        return list_of_date_str_with_position

    def get_position_in_priced_contract_for_instrument(
        self, instrument_code: str
    ) -> float:
        contract_id = self.data_contracts.get_priced_contract_id(instrument_code)
        position = self.get_position_for_contract(
            futuresContract(instrument_code, contract_id)
        )

        return position


class updatePositions(productionDataLayerGeneric):
    def _add_required_classes_to_data(self, data) -> dataBlob:
        data.add_class_list(
            [
                get_class_for_data_type(ROLL_STATE_DATA),
                get_class_for_data_type(STRATEGY_POSITION_DATA),
                get_class_for_data_type(CONTRACT_POSITION_DATA),
            ]
        )
        return data

    @property
    def db_roll_state_data(self) -> rollStateData:
        return self.data.db_roll_state

    @property
    def db_strategy_position_data(self) -> strategyPositionData:
        return self.data.db_strategy_position

    @property
    def db_contract_position_data(self) -> contractPositionData:
        return self.data.db_contract_position

    @property
    def diag_positions(self):
        return diagPositions(self.data)

    def set_roll_state(self, instrument_code: str, roll_state_required: RollState):
        return self.db_roll_state_data.set_roll_state(
            instrument_code, roll_state_required
        )

    def check_and_auto_update_roll_state(self, instrument_code: str):
        current_roll_state = self.diag_positions.get_roll_state(instrument_code)
        priced_contract_position = (
            self.diag_positions.get_position_in_priced_contract_for_instrument(
                instrument_code
            )
        )
        has_no_priced_contract_position = priced_contract_position == 0.0
        roll_state_requires_order_generation = is_roll_state_requiring_order_generation(
            current_roll_state
        )

        if has_no_priced_contract_position and roll_state_requires_order_generation:
            self.set_roll_state(instrument_code, passive_roll_state)
            self.log.critical(
                "Set roll state to passive for %s because no longer have position in priced contract"
                % instrument_code
            )

    def update_strategy_position_table_with_instrument_order(
        self, original_instrument_order: instrumentOrder, new_fill: tradeQuantity
    ):
        """
        Alter the strategy position table according to new_fill value

        :param original_instrument_order:
        :return:
        """

        instrument_strategy = original_instrument_order.instrument_strategy

        current_position_as_int = (
            self.diag_positions.get_current_position_for_instrument_strategy(
                instrument_strategy
            )
        )
        trade_done_as_int = new_fill.as_single_trade_qty_or_error()
        if trade_done_as_int is missing_order:
            self.log.critical("Instrument orders can't be spread orders!")
            return failure

        new_position_as_int = current_position_as_int + trade_done_as_int

        self.db_strategy_position_data.update_position_for_instrument_strategy_object(
            instrument_strategy, new_position_as_int
        )

        self.log.debug(
            "Updated position of %s from %d to %d because of trade %s %d fill %s"
            % (
                str(instrument_strategy),
                current_position_as_int,
                new_position_as_int,
                str(original_instrument_order),
                original_instrument_order.order_id,
                str(new_fill),
            ),
            **original_instrument_order.log_attributes(),
            method="temp",
        )

        return success

    def update_contract_position_table_with_contract_order(
        self, contract_order_before_fills: contractOrder, fill_list: tradeQuantity
    ):
        """
        Alter the strategy position table according to contract order fill value

        :param contract_order_before_fills:
        :return:
        """
        futures_contract_entire_order = contract_order_before_fills.futures_contract
        list_of_individual_contracts = (
            futures_contract_entire_order.as_list_of_individual_contracts()
        )

        time_date = datetime.datetime.now()

        for contract, trade_done in zip(list_of_individual_contracts, fill_list):
            self._update_positions_for_individual_contract_leg(
                contract=contract, trade_done=trade_done, time_date=time_date
            )
            self.log.debug(
                "Updated position of %s because of trade %s ID:%d with fills %d"
                % (
                    str(contract),
                    str(contract_order_before_fills),
                    contract_order_before_fills.order_id,
                    trade_done,
                ),
                **contract_order_before_fills.log_attributes(),
                method="temp",
            )

    def _update_positions_for_individual_contract_leg(
        self, contract: futuresContract, trade_done: int, time_date: datetime.datetime
    ):
        current_position = self.diag_positions.get_position_for_contract(contract)

        new_position = current_position + trade_done

        self.db_contract_position_data.update_position_for_contract_object(
            contract, new_position, date=time_date
        )
        # check
        new_position_db = self.diag_positions.get_position_for_contract(contract)

        self.log.debug(
            "Updated position of %s from %d to %d; new position in db is %d"
            % (
                str(contract),
                current_position,
                new_position,
                new_position_db,
            ),
            **contract.log_attributes(),
            method="temp",
        )


def annonate_df_index_with_positions_held(data: dataBlob, pd_df: pd.DataFrame):
    instrument_code_list = list(pd_df.index)
    held_instruments = get_list_of_instruments_with_current_positions(data)

    def _annotate(instrument_code, held_instruments):
        if instrument_code in held_instruments:
            return "%s*" % instrument_code
        else:
            return instrument_code

    instrument_code_list = [
        _annotate(instrument_code, held_instruments)
        for instrument_code in instrument_code_list
    ]
    pd_df.index = instrument_code_list

    return pd_df


def get_list_of_instruments_with_current_positions(data: dataBlob) -> List[str]:
    diag_positions = diagPositions(data)
    all_contract_positions = diag_positions.get_all_current_contract_positions()

    return all_contract_positions.unique_list_of_instruments()
