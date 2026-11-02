import datetime

from syscore.exceptions import missingData
from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order
from sysdata.mongodb.mongo_generic import mongoDataWithSingleKey

from sysexecution.orders.base_orders import Order
from sysexecution.orders.instrument_orders import instrumentOrder
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.broker_orders import brokerOrder

from syslogging.logger import get_logger
from sysdata.production.historic_orders import (
    genericOrdersData,
    strategyHistoricOrdersData,
    contractHistoricOrdersData,
    brokerHistoricOrdersData,
)

from sysobjects.production.tradeable_object import (
    instrumentStrategy,
    futuresContractStrategy,
)

ORDER_ID_STORE_KEY = "_ORDER_ID_STORE_KEY"


class mongoGenericHistoricOrdersData(genericOrdersData):
    """
    Read and write data class to get roll state data


    """

    def _collection_name(self):
        raise NotImplementedError("Need to inherit for a specific data type")

    def _order_class(self):
        raise NotImplementedError("Need to inherit for a specific data type")

    def _name(self):
        return "Historic orders"

    def __init__(self, mongo_db=None, log=get_logger("mongoGenericHistoricOrdersData")):
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
        return "%s (%s)" % (self._name, str(self.mongo_data))

    def add_order_to_data(self, order: Order, ignore_duplication: bool = False):
        # Duplicates will be overridden, so be careful
        order_id = order.order_id
        no_existing_order = self.get_order_with_orderid(order_id) is missing_order
        if no_existing_order:
            return self._add_order_to_data_no_checking(order)
        else:
            if ignore_duplication:
                return self.update_order_with_orderid(order_id, order)
            else:
                raise Exception(
                    "Can't add order %s as order id %d already exists!"
                    % (str(order), order_id)
                )

    def _add_order_to_data_no_checking(self, order: Order):
        # Duplicates will be overridden, so be careful
        mongo_record = order.as_dict()

        self.mongo_data.add_data(order.order_id, mongo_record, allow_overwrite=True)

    def get_order_with_orderid(self, order_id: int):
        try:
            result_dict = self.mongo_data.get_result_dict_for_key(order_id)
        except missingData:
            return missing_order

        order_class = self._order_class()
        order = order_class.from_dict(result_dict)

        return order

    def _delete_order_with_orderid_without_checking(self, order_id):
        self.mongo_data.delete_data_without_any_warning(order_id)

    def update_order_with_orderid(self, order_id, order):
        mongo_record = order.as_dict()
        self.mongo_data.add_data(order_id, mongo_record)

    def get_list_of_order_ids(self) -> list:
        order_ids = self.mongo_data.get_list_of_keys()

        return order_ids

    def get_list_of_order_ids_in_date_range(
        self,
        period_start: datetime.datetime,
        period_end: datetime.datetime = arg_not_supplied,
    ) -> list:
        if period_end is arg_not_supplied:
            period_end = datetime.datetime.now()

        find_dict = dict(fill_datetime={"$gte": period_start, "$lt": period_end})

        list_of_order_dicts = self.mongo_data.get_list_of_result_dict_for_custom_dict(
            find_dict
        )
        order_ids = [order_dict["order_id"] for order_dict in list_of_order_dicts]

        return order_ids


class mongoStrategyHistoricOrdersData(
    mongoGenericHistoricOrdersData, strategyHistoricOrdersData
):
    def _collection_name(self):
        return "_STRATEGY_HISTORIC_ORDERS"

    def _order_class(self):
        return instrumentOrder

    def _name(self):
        return "Historic instrument/strategy orders"

    def get_list_of_order_ids_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> list:
        old_list_of_order_id = (
            self._get_list_of_order_ids_for_instrument_strategy_specify_key(
                instrument_strategy, "old_key"
            )
        )
        new_list_of_order_id = (
            self._get_list_of_order_ids_for_instrument_strategy_specify_key(
                instrument_strategy, "key"
            )
        )

        return old_list_of_order_id + new_list_of_order_id

    def _get_list_of_order_ids_for_instrument_strategy_specify_key(
        self, instrument_strategy: instrumentStrategy, keyfield: str
    ) -> list:
        object_key = getattr(instrument_strategy, keyfield)
        custom_dict = dict(key=object_key)
        list_of_result_dicts = self.mongo_data.get_list_of_result_dict_for_custom_dict(
            custom_dict
        )

        list_of_order_id = [result["order_id"] for result in list_of_result_dicts]

        return list_of_order_id


class mongoContractHistoricOrdersData(
    mongoGenericHistoricOrdersData, contractHistoricOrdersData
):
    def _collection_name(self):
        return "_CONTRACT_HISTORIC_ORDERS"

    def _order_class(self):
        return contractOrder

    def _name(self):
        return "Historic contract orders"


class mongoBrokerHistoricOrdersData(
    mongoGenericHistoricOrdersData, brokerHistoricOrdersData
):
    def _collection_name(self):
        return "_BROKER_HISTORIC_ORDERS"

    def _order_class(self):
        return brokerOrder

    def _name(self):
        return "Historic broker orders"

    def get_list_of_order_ids_for_instrument_and_contract_str(
        self, instrument_code: str, contract_str: str
    ) -> list:
        order_id_list = self.get_list_of_order_ids()
        key_list = [
            self.mongo_data.get_result_dict_for_key(order_id)["key"]
            for order_id in order_id_list
        ]
        contract_strategies = [
            futuresContractStrategy.from_key(key) for key in key_list
        ]

        def _contains_both(
            futures_contract_strategy: futuresContractStrategy,
            instrument_code: str,
            contract_str: str,
        ):
            list_of_date_str = futures_contract_strategy.contract_date.list_of_date_str
            if (
                futures_contract_strategy.instrument_code == instrument_code
                and contract_str in list_of_date_str
            ):
                return True
            else:
                return False

        order_ids = [
            orderid
            for orderid, futures_contract_strategy in zip(
                order_id_list, contract_strategies
            )
            if _contains_both(
                futures_contract_strategy,
                instrument_code=instrument_code,
                contract_str=contract_str,
            )
        ]

        return order_ids
