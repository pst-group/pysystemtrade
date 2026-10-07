import datetime
from copy import copy
from sysexecution.orders.named_order_objects import (
    missing_order,
    no_order_id,
    no_children,
)

from syslogging.logger import *
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.orders.base_orders import Order, overFilledOrder
from sysexecution.trade_qty import tradeQuantity


class missingOrder(Exception):
    pass


class lockedOrder(Exception):
    pass


class failureWithRollback(Exception):
    pass


class orderStackData(object):
    """
    An order stack is designed to hold orders.
    This is a base class, specific stacks are used for virtual and contract level stacks

    Will also inherit from this for specific implementations, eg mongo

    What kind of stuff do we do in stacks:
     - put an order on the stack, where no order existed
     - modify: put an order on the stack which replaces an existing order
     - view an order with certain characteristics from the stack
     - get an order from the stack with the intention of executing it. This also locks the order.
     - 'lock' an order so it can't be modified, 'gotten' or removed
     - unlock an order
     - remove a filled or cancelled order from the stack
     - empty the stack entirely (done at the end of every day)
     - view all the orders on the stack

     Stacks are pure state and so don't need archive data creating

     This kind of stack doesn't have to worry about partial executions
     If a partial is generated then the entire order will be removed, and on the next cycle
         a new order generated which will include the net order unless something has changed

    """

    def __init__(self, log=get_logger("order-stack")):
        self.log = log

    def __repr__(self):
        return "%s: with %d active orders" % (
            self._name,
            self.number_of_orders_on_stack(),
        )

    @property
    def _name(self):
        return "Order stack"

    def number_of_orders_on_stack(self):
        order_id_list = self.get_list_of_order_ids()
        return len(order_id_list)

    def put_list_of_orders_on_stack(
        self, list_of_orders: listOfOrders, unlock_when_finished=True
    ):
        """
        Put a list of new orders on the stack. We lock these before placing on.

        If any do not return order_id (so something has gone wrong) we remove all the relevant orders and return failure

        If all work out okay, we unlock the orders

        We may choose not to unlock the orders, if for example we're doing a transaction that involves
           adding something to another stack

        :param list_of_orders:
        :return: list of order_ids or failure
        """
        if len(list_of_orders) == 0:
            return []

        list_of_order_ids = []
        for order in list_of_orders:
            order.lock_order()
            try:
                order_id = self.put_order_on_stack(order)
            except Exception as e:
                self.log.warning(
                    "Failed to put order %s on stack error %s, rolling back entire transaction"
                    % (str(order), str(e)),
                    **order.log_attributes(),
                    method="temp",
                )

                # rollback any orders we did manage to add
                self.rollback_list_of_orders_on_stack(list_of_order_ids)
                error_msg = (
                    "Didn't put list of %d orders on stack but did manage to rollback"
                    % len(list_of_orders)
                )
                self.log.warning(error_msg)
                raise failureWithRollback(error_msg) from e

            else:
                list_of_order_ids.append(order_id)

        # success, unlock orders that we've just placed on the stack
        # it's good practice to do this to stop some of the orders we've just placed being altered

        if unlock_when_finished:
            self.unlock_list_of_orders(list_of_order_ids)

        return list_of_order_ids

    def rollback_list_of_orders_on_stack(self, list_of_order_ids: list):
        if len(list_of_order_ids) == 0:
            return None

        self.log.warning("Rolling back addition of orders %s" % str(list_of_order_ids))

        for order_id in list_of_order_ids:
            self.unlock_order_on_stack(order_id)
            self.deactivate_order(order_id)
            self.remove_order_with_id_from_stack(order_id)

    def unlock_list_of_orders(self, list_of_order_ids: list):
        for order_id in list_of_order_ids:
            self.unlock_order_on_stack(order_id)

    def put_order_on_stack(self, new_order: Order):
        """
        Put an order on the stack

        :param new_order: Order
        :return: order_id or failure condition: duplicate_order, failure
        """
        order_id = self._put_order_on_stack_and_get_order_id(new_order)

        return order_id

    # FIND AND LIST ORDERS

    def get_list_of_orders(self, exclude_inactive_orders: bool = True) -> list:
        list_of_order_ids = self.get_list_of_order_ids(
            exclude_inactive_orders=exclude_inactive_orders
        )
        list_of_orders = self.get_list_of_orders_from_order_id_list(list_of_order_ids)

        return list_of_orders

    def get_list_of_orders_from_order_id_list(self, list_of_order_ids) -> listOfOrders:
        order_list = []
        for order_id in list_of_order_ids:
            order = self.get_order_with_id_from_stack(order_id)
            order_list.append(order)

        return listOfOrders(order_list)

    def get_list_of_order_ids(self, exclude_inactive_orders: bool = True) -> list:
        order_ids = self._get_list_of_all_order_ids()

        if exclude_inactive_orders:
            all_orders = [
                self.get_order_with_id_from_stack(order_id) for order_id in order_ids
            ]
            order_ids = [order.order_id for order in all_orders if order.active]

        return order_ids

    def list_of_new_orders(self) -> list:
        order_ids = self.get_list_of_order_ids()
        new_order_ids = [
            order_id for order_id in order_ids if self.is_new_order(order_id)
        ]

        return new_order_ids

    def is_new_order(self, order_id: int) -> bool:
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            return False
        if existing_order.children is not no_children:
            return False
        if not existing_order.active:
            return False
        if not existing_order.fill_equals_zero():
            return False

        return True

    def list_of_completed_order_ids(
        self,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=False,
    ) -> list:
        order_ids = self.get_list_of_order_ids()
        completed_order_ids = [
            order_id
            for order_id in order_ids
            if self.is_completed(
                order_id,
                allow_partial_completions=allow_partial_completions,
                allow_zero_completions=allow_zero_completions,
                treat_inactive_as_complete=treat_inactive_as_complete,
            )
        ]

        return completed_order_ids

    def is_completed(
        self,
        order_id: int,
        allow_partial_completions=False,
        allow_zero_completions=False,
        treat_inactive_as_complete=False,
    ) -> bool:
        existing_order = self.get_order_with_id_from_stack(order_id)

        if allow_zero_completions:
            return True

        if existing_order is missing_order:
            return False

        order_inactive = not existing_order.active
        treat_inactive_orders_as_incomplete = not treat_inactive_as_complete

        if order_inactive and treat_inactive_orders_as_incomplete:
            return False

        if allow_partial_completions:
            trade_with_no_fills = existing_order.fill_equals_zero()
            partially_completed = not trade_with_no_fills
            return partially_completed

        fully_filled = existing_order.fill_equals_desired_trade()
        is_completed = fully_filled is True
        return is_completed

    # CHILD ORDERS
    def add_children_to_order_without_existing_children(
        self, order_id: int, new_children: list
    ):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't add children to non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        already_have_children = not existing_order.no_children()
        if already_have_children:
            error_msg = (
                "Can't add children to order that already has children %s"
                % str(existing_order.children)
            )
            self.log.warning(
                error_msg,
                **existing_order.log_attributes(),
                method="temp",
            )
            raise Exception(error_msg)

        new_order = copy(existing_order)
        new_order.add_a_list_of_children(new_children)

        self._change_order_on_stack(order_id, new_order)

    def add_another_child_to_order(self, order_id: int, new_child: int):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't add children to non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        existing_order.add_another_child(new_child)

        self._change_order_on_stack(order_id, existing_order)

    def remove_children_from_order(self, order_id: int):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't remove children from non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        new_order = copy(existing_order)
        new_order.remove_all_children()

        self._change_order_on_stack(order_id, new_order)

    def mark_as_manual_fill_for_order_id(self, order_id: int):
        order = self.get_order_with_id_from_stack(order_id)
        order.manual_fill = True
        self._change_order_on_stack(order_id, order)

    # FILLS
    def change_fill_quantity_for_order(
        self,
        order_id: int,
        fill_qty: tradeQuantity,
        filled_price: float = None,
        fill_datetime: datetime.datetime = None,
    ):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't apply fill to non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        if existing_order.fill == fill_qty:
            # nout to do here, fills are cumulative
            return None

        log_attrs = {**existing_order.log_attributes(), "method": "temp"}

        new_order = copy(existing_order)
        try:
            new_order.fill_order(
                fill_qty, filled_price=filled_price, fill_datetime=fill_datetime
            )
        except overFilledOrder as e:
            self.log.warning(str(e), **log_attrs)
            raise overFilledOrder(e)

        self._change_order_on_stack(order_id, new_order)

        self.log.debug(
            "Changed fill qty from %s to %s for order %s"
            % (str(existing_order.fill), str(fill_qty), str(existing_order)),
            **log_attrs,
        )

    def zero_out(self, order_id: int):
        # zero out an order, i.e. remove its trades and fills and deactivate it

        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't zero out non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        if not existing_order.active:
            # already inactive
            self.log.warning(
                "Can't zero out order which is already inactive",
                **existing_order.log_attributes(),
                method="temp",
            )
            return None

        new_order = copy(existing_order)
        new_order.zero_out()

        # This will fail if being modified or locked
        self._change_order_on_stack(order_id, new_order, check_if_inactive=False)

    # DEACTIVATE ORDER (Because filled or cancelled)

    def deactivate_order(self, order_id: int):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't deactivate non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        if not existing_order.active:
            # already inactive
            return None

        new_order = copy(existing_order)
        new_order.deactivate()

        # This will fail if being modified or locked
        self._change_order_on_stack(order_id, new_order, check_if_inactive=False)

    # REMOVE DEACTIVATED ORDERS (ARCHIVE IN HISTORICAL RECORDS FIRST!)
    def remove_all_deactivated_orders_from_stack(self):
        inactive_orders = self.get_list_of_inactive_order_ids()
        for order_id in inactive_orders:
            self.remove_order_with_id_from_stack(order_id)

    def get_list_of_inactive_order_ids(self) -> list:
        all_order_ids = self._get_list_of_all_order_ids()
        all_orders = [
            self.get_order_with_id_from_stack(order_id) for order_id in all_order_ids
        ]
        order_ids = [order.order_id for order in all_orders if not order.active]

        return order_ids

    def remove_order_with_id_from_stack(self, order_id: int):
        order_on_stack = self.get_order_with_id_from_stack(order_id)
        if order_on_stack is missing_order:
            raise missingOrder(
                "Can't remove non existent order %s from stack" % order_id
            )

        if order_on_stack.is_order_locked():
            raise Exception("Can't remove locked order %s from stack" % order_on_stack)

        if order_on_stack.active:
            raise Exception("Can't remove active order %s from stack" % order_on_stack)

        self._remove_order_with_id_from_stack_no_checking(order_id)

    # CHANGING AN ORDER ON THE STACK

    def _change_order_on_stack(
        self, order_id: int, new_order: Order, check_if_inactive: bool = True
    ):
        # Make any kind of general change to an order, checking for locks
        # Doesn't check for other conditions, eg beingactive or not

        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            error_msg = "Can't change non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        log_attrs = {**existing_order.log_attributes(), "method": "temp"}

        lock_status = existing_order.is_order_locked()
        if lock_status is True:
            # already locked can't change
            error_msg = "Can't change locked order %s" % str(existing_order)
            self.log.warning(error_msg, **log_attrs)
            raise Exception(error_msg)

        if check_if_inactive:
            existing_order_is_inactive = not existing_order.active
            if existing_order_is_inactive:
                error_msg = "Can't change order %s as inactive" % str(existing_order)
                self.log.warning(error_msg, **log_attrs)

        self._change_order_on_stack_no_checking(order_id, new_order)

    def unlock_order_on_stack(self, order_id: int):
        order = self.get_order_with_id_from_stack(order_id)
        if order is missing_order:
            error_msg = "Can't unlock non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        order.unlock_order()
        self._change_order_on_stack_no_checking(order_id, order)

    def lock_order_on_stack(self, order_id: int):
        order = self.get_order_with_id_from_stack(order_id)
        if order is missing_order:
            error_msg = "Can't lock non existent order %d" % order_id
            self.log.warning(error_msg)
            raise missingOrder(error_msg)

        order.lock_order()
        self._change_order_on_stack_no_checking(order_id, order)

    # LOW LEVEL PUT AND CHANGE ORDERS

    def _put_order_on_stack_and_get_order_id(self, order: Order) -> int:
        order_has_existing_id = not order.order_id is no_order_id
        if order_has_existing_id:
            self.log.warning(
                "Order %s already has order ID will be ignored and allocated a new ID!"
                % str(order),
                **order.log_attributes(),
                method="temp",
            )

        order_to_add = copy(order)
        order_id = self._get_next_order_id()
        order_to_add.order_id = order_id

        self._put_order_on_stack_no_checking(order_to_add)

        return order_id

    # ORDER ID

    # FINDING ORDERS AND LIST OF ORDERS

    def _get_list_of_orderids_with_same_tradeable_object_on_stack(
        self, order: Order
    ) -> list:
        """
        Try and get an order with the same tradeable object off the stack

        :param order: Order to check
        :return: Existing order or missing_order or identical_order
        """
        order_key = order.key
        existing_order_ids = self._get_list_of_order_ids_with_key_from_stack(order_key)
        if len(existing_order_ids) == 0:
            return missing_order

        return existing_order_ids

    def _get_list_of_order_ids_with_key_from_stack(
        self, order_key: str, exclude_inactive_orders: bool = True
    ) -> list:
        all_order_ids = self.get_list_of_order_ids(
            exclude_inactive_orders=exclude_inactive_orders
        )

        all_orders = [
            self.get_order_with_id_from_stack(order_id) for order_id in all_order_ids
        ]

        order_ids = [order.order_id for order in all_orders if order.key == order_key]

        return order_ids

    def _delete_entire_stack_without_checking_only_use_when_debugging(self):
        order_id_list = self.get_list_of_order_ids(exclude_inactive_orders=False)

        for order_id in order_id_list:
            self._remove_order_with_id_from_stack_no_checking(order_id)

    # LOW LEVEL OPERATIONS to include in specific implementation

    def _get_list_of_all_order_ids(self) -> list:
        # probably will be overridden in data implementation
        raise NotImplementedError

    # deleting

    def _remove_order_with_id_from_stack_no_checking(self, order_id: int):
        # probably will be overridden in data implementation

        raise NotImplementedError

    def _change_order_on_stack_no_checking(self, order_id: int, order: Order):
        #
        # probably will be overridden in data implementation

        raise NotImplementedError

    def get_order_with_id_from_stack(self, order_id: int) -> Order:
        # probably will be overridden in data implementation
        # return missing_order if not found
        raise NotImplementedError

    def _put_order_on_stack_no_checking(self, order: Order):
        # probably will be overridden in data implementation

        raise NotImplementedError

    def _get_next_order_id(self):
        # MUST override in data implementation
        # The maximum orderid should ideally live on in permanent storage
        # Otherwise we rely on this stack persisting while downstream stacks
        # rely on mapping orderids

        raise NotImplementedError
