from sysexecution.orders.named_order_objects import no_children

from sysexecution.stack_handler.stackHandlerCore import stackHandlerCore, orderFamily
from sysproduction.data.orders import dataOrders


class stackHandlerForCompletions(stackHandlerCore):
    def handle_completed_orders(
        self,
        allow_partial_completions: bool = False,
        allow_zero_completions: bool = False,
        treat_inactive_as_complete: bool = False,
    ):
        list_of_completed_instrument_orders = (
            self.instrument_stack.list_of_completed_order_ids(
                allow_partial_completions=allow_partial_completions,
                allow_zero_completions=allow_zero_completions,
                treat_inactive_as_complete=treat_inactive_as_complete,
            )
        )

        for instrument_order_id in list_of_completed_instrument_orders:
            self.handle_completed_instrument_order(
                instrument_order_id,
                allow_partial_completions=allow_partial_completions,
                allow_zero_completions=allow_zero_completions,
            )

    def handle_completed_instrument_order(
        self,
        instrument_order_id: int,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=False,
    ):
        # Check children all done

        completely_filled = self.confirm_all_children_and_grandchildren_are_filled(
            instrument_order_id,
            allow_partial_completions=allow_partial_completions,
            allow_zero_completions=allow_zero_completions,
            treat_inactive_as_complete=treat_inactive_as_complete,
        )

        if not completely_filled:
            return None

        # If we have got this far then all our children are filled, and the
        # parent is filled

        # the 'order family' will now include split orders
        order_family = self.get_order_family_for_instrument_order_id(
            instrument_order_id
        )

        # Make orders inactive
        # A subsequent process will delete them
        self.deactivate_family_of_orders(order_family)

        self.add_order_family_to_historic_orders_database(order_family)

    def get_order_family_for_instrument_order_id(
        self, instrument_order_id: int
    ) -> orderFamily:
        instrument_order = self.instrument_stack.get_order_with_id_from_stack(
            instrument_order_id
        )
        list_of_contract_order_id = instrument_order.children
        if list_of_contract_order_id is no_children:
            # childless, grandchildless
            return orderFamily(instrument_order_id, [], [])

        list_of_broker_order_id = (
            self.get_all_grandchildren_from_list_of_contract_order_id(
                list_of_contract_order_id
            )
        )

        order_family = orderFamily(
            instrument_order_id=instrument_order_id,
            list_of_contract_order_id=list_of_contract_order_id,
            list_of_broker_order_id=list_of_broker_order_id,
        )

        return order_family

    def get_all_grandchildren_from_list_of_contract_order_id(
        self, list_of_contract_order_id: list
    ) -> list:
        list_of_broker_order_id = []

        for contract_order_id in list_of_contract_order_id:
            contract_order = self.contract_stack.get_order_with_id_from_stack(
                contract_order_id
            )

            broker_order_children = contract_order.children
            if broker_order_children is not no_children:
                list_of_broker_order_id = (
                    list_of_broker_order_id + broker_order_children
                )

        list_of_broker_order_id = list(set(list_of_broker_order_id))

        return list_of_broker_order_id

    def confirm_all_children_and_grandchildren_are_filled(
        self,
        instrument_order_id: int,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=True,
    ):
        order_family = self.get_order_family_for_instrument_order_id(
            instrument_order_id
        )

        children_filled = self.check_list_of_contract_orders_complete(
            order_family.list_of_contract_order_id,
            allow_partial_completions=allow_partial_completions,
            allow_zero_completions=allow_zero_completions,
            treat_inactive_as_complete=treat_inactive_as_complete,
        )

        grandchildren_filled = self.check_list_of_broker_orders_complete(
            order_family.list_of_broker_order_id,
            allow_partial_completions=allow_partial_completions,
            allow_zero_completions=allow_zero_completions,
            treat_inactive_as_complete=treat_inactive_as_complete,
        )

        if grandchildren_filled and children_filled:
            return True
        else:
            return False

    def check_list_of_contract_orders_complete(
        self,
        list_of_contract_order_id: list,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=False,
    ) -> bool:
        for contract_order_id in list_of_contract_order_id:
            completely_filled = self.contract_stack.is_completed(
                contract_order_id,
                allow_zero_completions=allow_zero_completions,
                allow_partial_completions=allow_partial_completions,
                treat_inactive_as_complete=treat_inactive_as_complete,
            )
            if not completely_filled:
                # OK We can't do this unless *all* our children are filled
                return False

        # all filled
        return True

    def check_list_of_broker_orders_complete(
        self,
        list_of_broker_order_id: list,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=False,
    ):
        for broker_order_id in list_of_broker_order_id:
            completely_filled = self.broker_stack.is_completed(
                broker_order_id,
                allow_zero_completions=allow_zero_completions,
                allow_partial_completions=allow_partial_completions,
                treat_inactive_as_complete=treat_inactive_as_complete,
            )
            if not completely_filled:
                # OK We can't do this unless all our children are filled
                return False

            broker_order = self.broker_stack.get_order_with_id_from_stack(
                broker_order_id
            )
            if not broker_order.fill_equals_zero() and broker_order.commission is None:
                # Keep ordinary completed fills available to the fill sweep until
                # their commissions arrive. Explicit cleanup must remain possible.
                if not (allow_partial_completions or allow_zero_completions):
                    return False
                self.log.warning(
                    "Completing broker order with commission still unavailable",
                    **broker_order.log_attributes(),
                )

        return True

    def add_order_family_to_historic_orders_database(self, order_family: orderFamily):
        instrument_order = self.instrument_stack.get_order_with_id_from_stack(
            order_family.instrument_order_id
        )
        contract_order_list = self.contract_stack.get_list_of_orders_from_order_id_list(
            order_family.list_of_contract_order_id
        )
        broker_order_list = self.broker_stack.get_list_of_orders_from_order_id_list(
            order_family.list_of_broker_order_id
        )

        # Update historic order database
        order_data = dataOrders(self.data)
        order_data.add_historic_orders_to_data(
            instrument_order, contract_order_list, broker_order_list
        )

    def deactivate_family_of_orders(self, order_family: orderFamily):
        # Make orders inactive
        # A subsequent process will delete them
        self.instrument_stack.deactivate_order(order_family.instrument_order_id)

        for contract_order_id in order_family.list_of_contract_order_id:
            self.contract_stack.deactivate_order(contract_order_id)

        for broker_order_id in order_family.list_of_broker_order_id:
            self.broker_stack.deactivate_order(broker_order_id)
