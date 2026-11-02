from syscore.exceptions import missingData
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey
from syslogging.logger import get_logger

from sysexecution.order_stacks.order_stack import orderStackData
from sysexecution.orders.named_order_objects import missing_order
from sysexecution.orders.base_orders import Order
from sysexecution.orders.instrument_orders import instrumentOrder
from sysexecution.order_stacks.instrument_order_stack import instrumentOrderStackData
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.order_stacks.contract_order_stack import contractOrderStackData
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.order_stacks.broker_order_stack import brokerOrderStackData

ORDER_ID_STORE_KEY = "_ORDER_ID_STORE_KEY"
MAX_ORDER_KEY = "max_order_id"


class mongoOrderStackData(orderStackData):
    """
    Read and write data class to get roll state data


    """

    def _collection_name(self):
        raise NotImplementedError("Need to inherit for a specific data type")

    def _order_class(self):
        return Order

    def __init__(self, mongo_db=None, log=get_logger("mongoOrderStackData")):
        # Not needed as we don't store anything in _state attribute used in parent class
        # If we did have _state would risk breaking if we forgot to override methods
        # super().__init__()
        collection_name = self._collection_name()
        self._mongo_data = mongoDataWithSingleKey(
            collection_name, "order_id", mongo_db=mongo_db
        )

        super().__init__(log=log)

    @property
    def mongo_data(self):
        return self._mongo_data

    def __repr__(self):
        return "%s: %s with %d active orders" % (
            self._name,
            str(self.mongo_data),
            self.number_of_orders_on_stack(),
        )

    def get_order_with_id_from_stack(self, order_id: int):
        try:
            result_dict = self.mongo_data.get_result_dict_for_key(order_id)
        except missingData:
            return missing_order

        order_class = self._order_class()
        order = order_class.from_dict(result_dict)

        return order

    def _get_list_of_all_order_ids(self) -> list:
        order_ids = self.mongo_data.get_list_of_keys()
        try:
            order_ids.pop(order_ids.index(ORDER_ID_STORE_KEY))
        except:
            pass

        return order_ids

    def _change_order_on_stack_no_checking(self, order_id: int, order):
        order_as_dict = order.as_dict()

        self.mongo_data.add_data(order_id, order_as_dict, allow_overwrite=True)

    def _put_order_on_stack_no_checking(self, order: Order):
        order_as_dict = order.as_dict()

        self.mongo_data.add_data(
            int(order.order_id), order_as_dict, allow_overwrite=False
        )

    # ORDER ID
    def _get_next_order_id(self) -> int:
        max_orderid = self._get_current_max_order_id()
        new_orderid = int(max_orderid + 1)
        self._update_max_order_id(new_orderid)

        return new_orderid

    def _get_current_max_order_id(self) -> int:
        try:
            result_dict = self.mongo_data.get_result_dict_for_key(ORDER_ID_STORE_KEY)
        except missingData:
            orderid = self._create_and_return_max_order_id()
            return orderid

        order_id = result_dict[MAX_ORDER_KEY]

        return int(order_id)

    def _update_max_order_id(self, max_order_id: int):
        self.mongo_data.add_data(
            ORDER_ID_STORE_KEY, {MAX_ORDER_KEY: max_order_id}, allow_overwrite=True
        )

    def _create_and_return_max_order_id(self):
        first_order_id = 1
        self._update_max_order_id(first_order_id)

        return first_order_id

    def _remove_order_with_id_from_stack_no_checking(self, order_id):
        self.mongo_data.delete_data_without_any_warning(order_id)


class mongoInstrumentOrderStackData(mongoOrderStackData, instrumentOrderStackData):
    def _collection_name(self):
        return "INSTRUMENT_ORDER_STACK"

    def _order_class(self):
        return instrumentOrder


class mongoContractOrderStackData(mongoOrderStackData, contractOrderStackData):
    def _collection_name(self):
        return "CONTRACT_ORDER_STACK"

    def _order_class(self):
        return contractOrder


class mongoBrokerOrderStackData(mongoOrderStackData, brokerOrderStackData):
    def _collection_name(self):
        return "BROKER_ORDER_STACK"

    def _order_class(self):
        return brokerOrder
