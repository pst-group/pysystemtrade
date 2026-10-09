import datetime
from syscore.exceptions import fillExceedsTrade
from sysexecution.orders.named_order_objects import (
    missing_order,
    no_children,
    no_parent,
)

from sysexecution.stack_handler.completed_orders import stackHandlerForCompletions

from sysproduction.data.broker import dataBroker

from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.instrument_orders import instrumentOrder
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.trade_qty import tradeQuantity

from sysproduction.data.positions import updatePositions


class stackHandlerForFills(stackHandlerForCompletions):
    def process_fills_stack(self):
        """
        Run a regular sweep across the stack
        Doing various things

        :return: success
        """

        self.pass_fills_from_broker_to_broker_stack()
        self.pass_fills_from_broker_up_to_contract()
        self.pass_fills_from_contract_up_to_instrument()

    def pass_fills_from_broker_to_broker_stack(self):
        list_of_broker_order_ids = self.broker_stack.get_list_of_order_ids()
        for broker_order_id in list_of_broker_order_ids:
            self.apply_broker_fill_from_broker_to_broker_database(broker_order_id)

    def apply_broker_fill_from_broker_to_broker_database(self, broker_order_id: int):
        db_broker_order = self.broker_stack.get_order_with_id_from_stack(
            broker_order_id
        )
        if db_broker_order is missing_order:
            return None

        fully_filled = db_broker_order.fill_equals_desired_trade()
        if fully_filled and db_broker_order.commission is not None:
            # A completed quantity may still be waiting for its commission.
            # We don't log or we'd be spamming like crazy
            return None

        data_broker = dataBroker(self.data)
        matched_broker_order = data_broker.match_db_broker_order_to_order_from_brokers(
            db_broker_order
        )

        if matched_broker_order is missing_order:
            self.log.warning(
                "Order in database %s does not match any broker orders: can't fill"
                % db_broker_order,
                **db_broker_order.log_attributes(),
                method="temp",
            )
            return None

        if fully_filled:
            if matched_broker_order.commission is None:
                return None
            if matched_broker_order.fill != db_broker_order.fill:
                self.log.warning(
                    "Cannot refresh commission: broker fill differs from recorded fill",
                    **db_broker_order.log_attributes(),
                )
                return None
            # Only the fee was outstanding. Do not revise an already recorded
            # fill's price, time or quantity while retrieving its commission.
            db_broker_order.commission = matched_broker_order.commission
            matched_broker_order = db_broker_order

        self.apply_broker_order_fills_to_database(
            broker_order_id=broker_order_id, broker_order=matched_broker_order
        )

    def apply_broker_order_fills_to_database(
        self, broker_order_id: int, broker_order: brokerOrder
    ):
        # Turn commissions into floats
        data_broker = dataBroker(self.data)
        broker_order_with_commissions = (
            data_broker.calculate_total_commission_for_broker_order(broker_order)
        )

        try:
            # This will add commissions, fills, etc
            self.broker_stack.add_execution_details_from_matched_broker_order(
                broker_order_id, broker_order_with_commissions
            )
        except fillExceedsTrade:
            self.log.warning(
                "Fill for exceeds trade for %s, ignoring fill... (hopefully will go away)"
                % (broker_order)
            )
            return None

        contract_order_id = broker_order.parent

        if contract_order_id is no_parent:
            self.log.error(
                "No parent for broker order %s %d"
                % (str(broker_order), broker_order_id),
                **broker_order.log_attributes(),
                method="temp",
            )
        else:
            # pass broker fills upwards
            self.apply_broker_fills_to_contract_order(contract_order_id)

    def pass_fills_from_broker_up_to_contract(self):
        list_of_contract_order_ids = self.contract_stack.get_list_of_order_ids()
        for contract_order_id in list_of_contract_order_ids:
            # this function is in 'core' since it's used elsewhere
            self.apply_broker_fills_to_contract_order(contract_order_id)

    def apply_broker_fills_to_contract_order(self, contract_order_id: int):
        contract_order_before_fill = self.contract_stack.get_order_with_id_from_stack(
            contract_order_id
        )

        children = contract_order_before_fill.children
        if children is no_children:
            # no children created yet, definitely no fills
            return None

        broker_order_list = self.broker_stack.get_list_of_orders_from_order_id_list(
            children
        )

        # We apply: total quantity, average price, highest datetime

        if broker_order_list.all_zero_fills():
            # nothing to do here
            return None

        final_fill_datetime = broker_order_list.final_fill_datetime()
        total_filled_qty = broker_order_list.total_filled_qty()
        average_fill_price = broker_order_list.average_fill_price()

        self.apply_fills_to_contract_order(
            contract_order_before_fill=contract_order_before_fill,
            filled_price=average_fill_price,
            filled_qty=total_filled_qty,
            fill_datetime=final_fill_datetime,
        )

    def apply_contract_order_fill_to_database(self, contract_order: contractOrder):
        contract_order_before_fill = self.contract_stack.get_order_with_id_from_stack(
            contract_order.order_id
        )
        self.apply_fills_to_contract_order(
            contract_order_before_fill=contract_order_before_fill,
            filled_qty=contract_order.fill,
            fill_datetime=contract_order.fill_datetime,
            filled_price=contract_order.filled_price,
        )

    def pass_fills_from_contract_up_to_instrument(self):
        list_of_child_order_ids = self.contract_stack.get_list_of_order_ids()
        for contract_order_id in list_of_child_order_ids:
            self.apply_contract_fill_to_instrument_order(contract_order_id)

    def apply_fills_to_contract_order(
        self,
        contract_order_before_fill: contractOrder,
        filled_qty: tradeQuantity,
        filled_price: float,
        fill_datetime: datetime.datetime,
    ):
        contract_order_id = contract_order_before_fill.order_id
        self.contract_stack.change_fill_quantity_for_order(
            contract_order_id,
            filled_qty,
            filled_price=filled_price,
            fill_datetime=fill_datetime,
        )

        # if fill has changed then update positions
        # we do this here, because we can get here either from fills process
        # or after an execution
        ## At this point the contract stack has changed the contract order to reflect the fill, but the contract_order
        ##    here reflects the original contract order before fills applied, this allows comparision
        self.apply_position_change_to_stored_contract_positions(
            contract_order_before_fill, filled_qty
        )

        ## We now pass it up to the next level
        self.apply_contract_fill_to_instrument_order(contract_order_id)

    def apply_position_change_to_stored_contract_positions(
        self,
        contract_order_before_fill: contractOrder,
        total_filled_qty: tradeQuantity,
        apply_entire_trade: bool = False,
    ):
        current_fills = contract_order_before_fill.fill

        if apply_entire_trade:
            # used for balance trades
            new_fills = current_fills
        else:
            new_fills = total_filled_qty - current_fills

        if new_fills.equals_zero():
            # nothing to do
            return None

        position_updater = updatePositions(self.data)
        position_updater.update_contract_position_table_with_contract_order(
            contract_order_before_fill, new_fills
        )

    def apply_contract_fill_to_instrument_order(self, contract_order_id: int):
        contract_order = self.contract_stack.get_order_with_id_from_stack(
            contract_order_id
        )
        if contract_order is missing_order:
            return None

        if contract_order.fill_equals_zero():
            # Nothing to do here
            return None

        instrument_order_id = contract_order.parent
        if instrument_order_id is no_parent:
            self.log.error(
                "No parent for contract order %s %d"
                % (str(contract_order), contract_order_id),
                **contract_order.log_attributes(),
                method="temp",
            )
            return None

        self.apply_contract_fills_for_instrument_order(
            instrument_order_id=instrument_order_id
        )

    def apply_contract_fills_for_instrument_order(self, instrument_order_id: int):
        instrument_order = self.instrument_stack.get_order_with_id_from_stack(
            instrument_order_id
        )
        list_of_contract_order_ids = instrument_order.children
        if list_of_contract_order_ids is no_children:
            return None

        if len(list_of_contract_order_ids) == 1:
            # easy, only one child
            contract_order_id = list_of_contract_order_ids[0]
            self.apply_contract_fill_to_parent_order_single_child(
                contract_order_id, instrument_order
            )
        else:
            self.apply_contract_fill_to_parent_order_multiple_children(
                list_of_contract_order_ids, instrument_order
            )

        ## Order is now potentially completed
        self.handle_completed_instrument_order(instrument_order_id)

    def apply_contract_fill_to_parent_order_single_child(
        self, contract_order_id: int, instrument_order: instrumentOrder
    ):
        contract_order = self.contract_stack.get_order_with_id_from_stack(
            contract_order_id
        )

        fill_for_contract = contract_order.fill
        filled_price = contract_order.filled_price
        fill_datetime = contract_order.fill_datetime
        if len(fill_for_contract) == 1:
            # Not a spread order, trivial
            self.fill_for_instrument_in_database(
                instrument_order, fill_for_contract, filled_price, fill_datetime
            )

        else:
            # Spread order: intra-market
            # Instrument order quantity is either zero (for a roll) or non zero
            # (for a spread)
            if instrument_order.is_zero_trade():
                # A forced leg roll; meaningless to do this
                pass
            else:
                # A spread order that isn't flat
                self.log.critical(
                    "Can't handle non-flat intra-market spread orders! Instrument order %s %s"
                    % (str(instrument_order), str(instrument_order.order_id)),
                    **contract_order.log_attributes(),
                    method="temp",
                )

    def apply_contract_fill_to_parent_order_multiple_children(
        self, list_of_contract_order_ids: list, instrument_order: instrumentOrder
    ):
        ## Three cases for multiple children (as normally one to one)
        # - Inter market spread: we can't handle these yet and we'll break
        # - Leg by leg flat spread eg forced roll order: do nothing since doesn't change instrument positions
        # Distributed roll order eg if we are short -2 front, want to buy 3, will do +2 front +1 next

        distributed_order = self.check_to_see_if_distributed_instrument_order(
            list_of_contract_order_ids, instrument_order
        )

        flat_order = instrument_order.is_zero_trade()

        if flat_order:
            # An inter-market flat spread
            # Meaningless to do this
            return None

        elif distributed_order:
            # a distributed order, all orders have the same sign as the
            # instrument order
            self.apply_contract_fill_to_parent_order_distributed_children(
                list_of_contract_order_ids, instrument_order
            )

        else:
            # A proper spread trade across markets can't do this
            self.log.critical(
                "Can't handle inter-market spread orders! Instrument order %s %s"
                % (str(instrument_order), str(instrument_order.order_id)),
                **instrument_order.log_attributes(),
                method="temp",
            )

    def check_to_see_if_distributed_instrument_order(
        self, list_of_contract_order_ids: list, instrument_order: instrumentOrder
    ) -> bool:
        # A distributed instrument order is like this: buy 2 EDOLLAR instrument order
        # split into buy 1 202306, buy 1 203209

        contract_orders = listOfOrders(
            [
                self.contract_stack.get_order_with_id_from_stack(contract_id)
                for contract_id in list_of_contract_order_ids
            ]
        )

        result = check_to_see_if_distributed_order(instrument_order, contract_orders)

        return result

    def apply_contract_fill_to_parent_order_distributed_children(
        self,
        list_of_contract_order_ids: list,
        original_instrument_order: instrumentOrder,
    ):
        # A distributed instrument order is like this: buy 2 EDOLLAR instrument order
        # split into buy 1 202306, buy 1 203209

        ##
        contract_orders = self.contract_stack.get_list_of_orders_from_order_id_list(
            list_of_contract_order_ids
        )

        # We apply: total quantity, average price, highest datetime

        final_fill_datetime = contract_orders.final_fill_datetime()
        total_filled_qty = contract_orders.total_filled_qty()
        average_fill_price = contract_orders.average_fill_price()

        self.fill_for_instrument_in_database(
            original_instrument_order,
            total_filled_qty,
            average_fill_price,
            final_fill_datetime,
        )

    def fill_for_instrument_in_database(
        self,
        original_instrument_order: instrumentOrder,
        fill_qty: tradeQuantity,
        fill_price: float,
        fill_datetime: datetime.datetime,
    ):
        # if fill has changed then update positions
        self.apply_position_change_to_instrument(original_instrument_order, fill_qty)

        self.instrument_stack.change_fill_quantity_for_order(
            original_instrument_order.order_id,
            fill_qty,
            filled_price=fill_price,
            fill_datetime=fill_datetime,
        )

    def apply_position_change_to_instrument(
        self,
        original_instrument_order: instrumentOrder,
        total_filled_qty: tradeQuantity,
        apply_entire_trade: bool = False,
    ):
        current_fill = original_instrument_order.fill

        if apply_entire_trade:
            new_fill = current_fill
        else:
            new_fill = total_filled_qty - current_fill

        if new_fill.equals_zero():
            return None

        position_updater = updatePositions(self.data)
        position_updater.update_strategy_position_table_with_instrument_order(
            original_instrument_order, new_fill
        )


def check_to_see_if_distributed_order(
    instrument_order: instrumentOrder, contract_orders: listOfOrders
) -> bool:
    trade_instrument_order = instrument_order.trade
    trade_contract_orders = [order.trade for order in contract_orders]

    instrument_code_from_instrument_order = instrument_order.instrument_code
    matching_instruments = [
        order.instrument_code == instrument_code_from_instrument_order
        for order in contract_orders
    ]
    all_instruments_match = all(matching_instruments)

    matching_signs = [
        trade.sign_equal(trade_instrument_order) for trade in trade_contract_orders
    ]
    all_signs_match = all(matching_signs)

    # contract orders are spawned from instruments, so the size of the required trade should match
    sum_contract_orders = sum(trade_contract_orders)
    sums_match = sum_contract_orders == trade_instrument_order

    if all_signs_match and sums_match and all_instruments_match:
        return True
    else:
        return False
