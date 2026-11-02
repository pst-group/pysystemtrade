"""

Historic orders

Orders which are still being executed live in the order stack type; see sysexecution

Note orderID here are different from ones used in order stack (which are temporary)

We store three types of orders: strategy level, contract level and broker level

Use to analyse execution and also construct strategy/contract level p&l

Doesn't have to reconcile with positions!

"""

import datetime

from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order

from sysdata.base_data import baseData
from sysobjects.fills import ListOfFills, fill_from_order
from sysexecution.orders.base_orders import Order
from sysexecution.orders.broker_orders import single_fill_from_broker_order
from sysexecution.order_stacks.order_stack import missingOrder
from sysexecution.orders.list_of_orders import listOfOrders

from sysobjects.production.tradeable_object import instrumentStrategy, futuresContract

from syslogging.logger import get_logger


class genericOrdersData(baseData):
    def __init__(self, log=get_logger("")):
        super().__init__(log=log)

    def __repr__(self):
        return "genericOrdersData object"

    def delete_order_with_orderid(self, order_id: int):
        order = self.get_order_with_orderid(order_id)
        if order is missing_order:
            raise missingOrder
        self._delete_order_with_orderid_without_checking(order_id)

    def add_order_to_data(self, order: Order, ignore_duplication=False):
        raise NotImplementedError

    def get_list_of_order_ids(self) -> list:
        raise NotImplementedError

    def get_order_with_orderid(self, order_id: int):
        # return missing_order if not found
        raise NotImplementedError

    def _delete_order_with_orderid_without_checking(self, order_id: int):
        raise NotImplementedError

    def update_order_with_orderid(self, order_id: int, order: Order):
        raise NotImplementedError

    def get_list_of_order_ids_in_date_range(
        self,
        period_start: datetime.datetime,
        period_end: datetime.datetime = arg_not_supplied,
    ) -> list:
        raise NotImplementedError


class strategyHistoricOrdersData(genericOrdersData):
    def get_fills_history_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> ListOfFills:
        """

        :param instrument_code:  str
        :param contract_id: str
        :return: fillHistory object, with fill and price
        """
        order_list = self.get_list_of_orders_for_instrument_strategy(
            instrument_strategy
        )
        order_list_as_fills = [fill_from_order(order) for order in order_list]
        list_of_fills = ListOfFills(order_list_as_fills)

        return list_of_fills

    def get_list_of_orders_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ) -> listOfOrders:
        list_of_ids = self.get_list_of_order_ids_for_instrument_strategy(
            instrument_strategy
        )
        order_list = []
        for order_id in list_of_ids:
            order = self.get_order_with_orderid(order_id)
            order_list.append(order)

        order_list = listOfOrders(order_list)

        return order_list

    def get_list_of_order_ids_for_instrument_strategy(
        self, instrument_strategy: instrumentStrategy
    ):
        raise NotImplementedError


class contractHistoricOrdersData(genericOrdersData):
    pass


class brokerHistoricOrdersData(contractHistoricOrdersData):
    def get_fills_history_for_contract(
        self, futures_contract: futuresContract
    ) -> ListOfFills:
        """

        :param instrument_code:  str
        :param contract_id: str
        :return: fillHistory object, with fill and price
        """
        instrument_code = futures_contract.instrument_code
        contract_str = futures_contract.date_str

        list_of_order_ids = self.get_list_of_order_ids_for_instrument_and_contract_str(
            instrument_code=instrument_code, contract_str=contract_str
        )
        list_of_fills = [
            self.get_fill_from_order_id(orderid, contract_str)
            for orderid in list_of_order_ids
        ]
        list_of_fills = [fill for fill in list_of_fills if fill is not missing_order]
        list_of_fills = ListOfFills(list_of_fills)

        return list_of_fills

    def get_fill_from_order_id(self, orderid, contract_str: str):
        order = self.get_order_with_orderid(orderid)
        fill = single_fill_from_broker_order(order, contract_str)

        return fill

    def get_list_of_order_ids_for_instrument_and_contract_str(
        self, instrument_code: str, contract_str: str
    ) -> list:
        raise NotImplementedError
