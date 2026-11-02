"""
Stack handler is a giant object, so we split it up into files/classes

This 'core' is inherited by all the other classes and just initialises, plus does some common functions

"""

from collections import namedtuple
from syscore.constants import arg_not_supplied, success, failure

from sysdata.data_blob import dataBlob

from sysexecution.order_stacks.order_stack import orderStackData, failureWithRollback
from sysexecution.orders.base_orders import Order
from sysexecution.orders.list_of_orders import listOfOrders

from sysproduction.data.orders import dataOrders
from sysproduction.data.prices import diagPrices, updatePrices
from sysproduction.data.contracts import dataContracts
from sysproduction.data.broker import dataBroker


class stackHandlerCore(object):
    def __init__(self, data: dataBlob = arg_not_supplied):
        if data is arg_not_supplied:
            data = dataBlob()

        self._data = data
        self._log = data.log

        order_data = dataOrders(data)

        instrument_stack = order_data.db_instrument_stack_data
        contract_stack = order_data.db_contract_stack_data
        broker_stack = order_data.db_broker_stack_data

        self._instrument_stack = instrument_stack
        self._contract_stack = contract_stack
        self._broker_stack = broker_stack

    @property
    def data(self):
        return self._data

    @property
    def log(self):
        return self._log

    @property
    def instrument_stack(self):
        return self._instrument_stack

    @property
    def contract_stack(self):
        return self._contract_stack

    @property
    def broker_stack(self):
        return self._broker_stack

    @property
    def diag_prices(self) -> diagPrices:
        diag_prices = getattr(self, "_diag_prices", None)
        if diag_prices is None:
            diag_prices = diagPrices(self.data)
            self._diag_prices = diag_prices

        return diag_prices

    @property
    def data_contracts(self) -> dataContracts:
        data_contracts = getattr(self, "_data_contracts", None)
        if data_contracts is None:
            data_contracts = dataContracts(self.data)
            self._data_contracts = data_contracts

        return data_contracts

    @property
    def data_broker(self) -> dataBroker:
        data_broker = getattr(self, "_data_broker", None)
        if data_broker is None:
            data_broker = dataBroker(self.data)
            self._data_broker = data_broker

        return data_broker

    @property
    def update_prices(self) -> updatePrices:
        update_prices = getattr(self, "_update_prices", None)
        if update_prices is None:
            update_prices = updatePrices(self.data)
            self._update_prices = update_prices

        return update_prices

    def put_children_on_stack(
        self,
        child_stack: orderStackData,
        parent_order: Order,
        list_of_child_orders: listOfOrders,
    ) -> list:
        log_attrs = {**parent_order.log_attributes(), "method": "temp"}

        try:
            list_of_child_ids = child_stack.put_list_of_orders_on_stack(
                list_of_child_orders
            )
        except failureWithRollback as e:
            self.log.warning(
                "Tried to add child orders but %s; rolled back so can try again (parent %s)"
                % (str(e), str(parent_order)),
                **log_attrs,
            )
            return []

        except Exception as e:
            self.log.critical(
                "Tried to add child orders, error %s and couldn't roll back! Order stack may well be corrupted!"
                % str(e),
                **log_attrs,
            )
            return []

        return list_of_child_ids

    def add_children_to_parent_or_rollback_children(
        self,
        parent_order: Order,
        list_of_child_ids: list,
        parent_stack: orderStackData,
        child_stack: orderStackData,
    ):
        log_attrs = {**parent_order.log_attributes(), "method": "temp"}

        try:
            parent_stack.add_children_to_order_without_existing_children(
                parent_order.order_id, list_of_child_ids
            )
        except Exception as e:
            try:
                child_stack.rollback_list_of_orders_on_stack(list_of_child_ids)
                self.log.warning(
                    "Tried to add child orders to parent but %s; rolled back so can try again (parent %s)"
                    % (str(e), str(parent_order)),
                    **log_attrs,
                )
                return failure
            except:
                self.log.critical(
                    "Tried to add child orders, error %s and couldn't roll back! Order stack may well be corrupted!"
                    % str(e),
                    **log_attrs,
                )
                return failure

        return success

    def log_successful_adding(
        self,
        list_of_child_orders: listOfOrders,
        list_of_child_ids: list,
        parent_order: Order,
    ):
        for child_order, child_id in zip(list_of_child_orders, list_of_child_ids):
            self.log.debug(
                "Put child order %s on stack with ID %d from parent order %s"
                % (str(child_order), child_id, str(parent_order)),
                **child_order.log_attributes(),
                method="temp",
            )

    def rollback_parents_and_children_and_handle_exceptions(
        self,
        parent_stack: orderStackData,
        child_stack: orderStackData,
        parent_order: Order,
        list_of_child_order_ids: list,
        error_from_adding_child_orders: Exception,
    ):
        ##
        log_attrs = {**parent_order.log_attributes(), "method": "temp"}
        try:
            rollback_parents_and_children(
                child_stack=child_stack,
                parent_stack=parent_stack,
                list_of_child_order_ids=list_of_child_order_ids,
                parent_order_id=parent_order.order_id,
            )
            self.log.warning(
                "Error %s when adding a set of parents and children but managed to rollback"
                % str(error_from_adding_child_orders),
                **log_attrs,
            )
            return None

        except Exception as rollback_exception:
            ## bloody hell even the rollback has failed, throw everything out of the pram
            self.log.critical(
                "Error %s when adding a set of parents and children and couldn't rollback got error %s! Stack may be corrupted"
                % (str(error_from_adding_child_orders), str(rollback_exception)),
                **log_attrs,
            )
            return None


def rollback_parents_and_children(
    parent_stack: orderStackData,
    child_stack: orderStackData,
    parent_order_id: int,
    list_of_child_order_ids: list,
):
    ## parent order might be locked
    parent_stack.unlock_order_on_stack(parent_order_id)
    parent_stack.deactivate_order(parent_order_id)
    parent_stack.remove_order_with_id_from_stack(parent_order_id)

    # If any children, roll them back also
    if len(list_of_child_order_ids) > 0:
        child_stack.rollback_list_of_orders_on_stack(list_of_child_order_ids)


orderFamily = namedtuple(
    "orderFamily",
    ["instrument_order_id", "list_of_contract_order_id", "list_of_broker_order_id"],
)
