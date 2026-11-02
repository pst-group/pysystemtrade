### An inheritance of a general order stack that includes methods for actually talking to the broker
from syscore.constants import arg_not_supplied
from sysdata.data_blob import dataBlob

from sysexecution.order_stacks.broker_order_stack import brokerOrderStackData
from sysexecution.order_stacks.broker_order_stack import orderWithControls

from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.orders.broker_orders import brokerOrder

from syslogging.logger import get_logger


class brokerExecutionStackData(brokerOrderStackData):
    def __init__(self, data: dataBlob, log=get_logger("brokerExecutionStackData")):
        super().__init__(log=log)
        self._data = data

    def get_list_of_broker_orders_with_account_id(
        self, account_id: str = arg_not_supplied
    ) -> listOfOrders:
        raise NotImplementedError

    def get_list_of_orders_from_storage(self) -> listOfOrders:
        raise NotImplementedError

    def match_db_broker_order_to_order_from_brokers(
        self, broker_order_to_match: brokerOrder
    ) -> brokerOrder:
        raise NotImplementedError

    def cancel_order_given_control_object(
        self, broker_orders_with_controls: orderWithControls
    ):
        raise NotImplementedError

    def cancel_order_on_stack(self, broker_order: brokerOrder):
        raise NotImplementedError

    def check_order_is_cancelled(self, broker_order: brokerOrder) -> bool:
        raise NotImplementedError

    def check_order_is_cancelled_given_control_object(
        self, broker_order_with_controls: orderWithControls
    ) -> bool:
        raise NotImplementedError

    def modify_limit_price_given_control_object(
        self, broker_order_with_controls: orderWithControls, new_limit_price: float
    ) -> orderWithControls:
        # throw orderCannotBeModified if can't be modified
        raise NotImplementedError

    @property
    def data(self):
        return self._data
