import datetime
from copy import copy

from ib_async import (
    Trade as ibTrade,
    OrderStatus as ibOrderStatus,
    Contract as ibContract,
)

from sysbrokers.IB.ib_futures_contracts_data import ibFuturesContractData
from sysbrokers.IB.ib_instruments_data import ibFuturesInstrumentData
from sysbrokers.IB.ib_translate_broker_order_objects import (
    create_broker_order_from_trade_with_contract,
    ibBrokerOrder,
)
from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.ib_translate_broker_order_objects import (
    tradeWithContract,
    ibOrderCouldntCreateException,
)
from sysbrokers.IB.client.ib_orders_client import ibOrdersClient
from sysbrokers.broker_execution_stack import brokerExecutionStackData
from sysdata.data_blob import dataBlob
from syscore.constants import arg_not_supplied, success
from syscore.exceptions import orderCannotBeModified
from sysexecution.order_stacks.order_stack import missingOrder
from sysexecution.orders.named_order_objects import missing_order

from sysexecution.order_stacks.broker_order_stack import orderWithControls
from sysexecution.orders.list_of_orders import listOfOrders
from sysexecution.orders.broker_orders import brokerOrder
from sysexecution.tick_data import tickerObject

from syslogging.logger import get_logger


def contract_for_instrument_lookup(contract_with_legs) -> ibContract:
    """
    Which IB contract to identify the instrument from.

    A combo (BAG) contract has no contract details of its own: IB never
    answers reqContractDetails for it, so looking the instrument up from the
    bag blocks forever. The legs are already resolved to ordinary futures
    contracts, so use the first one.
    """
    contract = contract_with_legs.ibcontract
    legs = contract_with_legs.legs
    if getattr(contract, "secType", "") == "BAG" and isinstance(legs, list) and legs:
        return legs[0]
    return contract


class ibOrderWithControls(orderWithControls):
    def __init__(
        self,
        trade_with_contract_from_ib: tradeWithContract,
        ibclient: ibOrdersClient,
        broker_order: brokerOrder = None,
        instrument_code: str = None,
        ticker_object: tickerObject = None,
    ):
        if broker_order is None:
            # This might happen if for example we are getting the orders from
            #   IB
            broker_order = create_broker_order_from_trade_with_contract(
                trade_with_contract_from_ib, instrument_code
            )

        super().__init__(
            control_object=trade_with_contract_from_ib,
            broker_order=broker_order,
            ticker_object=ticker_object,
        )

        self._ibclient = ibclient

    @property
    def trade_with_contract_from_IB(self):
        return self._control_object

    @property
    def ibclient(self) -> ibOrdersClient:
        return self._ibclient

    def update_order(self):
        # Update the broker order using the control object
        # Can be used when first submitted, or when polling objects
        # Basically copies across the details from the control object that are
        # likely to be updated
        self.ibclient.refresh()
        ib_broker_order = create_broker_order_from_trade_with_contract(
            self.trade_with_contract_from_IB, self.order.instrument_code
        )
        updated_broker_order = add_trade_info_to_broker_order(
            self.order, ib_broker_order
        )

        self._order = updated_broker_order

    def broker_limit_price(self):
        self.ibclient.refresh()
        ib_broker_order = create_broker_order_from_trade_with_contract(
            self.trade_with_contract_from_IB, self.order.instrument_code
        )
        if ib_broker_order.limit_price == 0.0:
            broker_limit_price = None
        else:
            broker_limit_price = ib_broker_order.limit_price

        return broker_limit_price


class ibExecutionStackData(brokerExecutionStackData):
    def __init__(
        self,
        ibconnection: connectionIB,
        data: dataBlob,
        log=get_logger("ibExecutionStackData"),
    ):
        super().__init__(log=log, data=data)
        self._ibconnection = ibconnection

    def __repr__(self):
        return "IB orders %s" % str(self.ib_client)

    @property
    def ibconnection(self) -> connectionIB:
        return self._ibconnection

    @property
    def ib_client(self) -> ibOrdersClient:
        client = getattr(self, "_ib_client", None)
        if client is None:
            client = self._ib_client = ibOrdersClient(
                ibconnection=self.ibconnection, log=self.log
            )

        return client

    @property
    def traded_object_store(self) -> dict:
        store = getattr(self, "_traded_object_store", None)
        if store is None:
            store = self._traded_object_store = {}

        return store

    def _add_order_with_controls_to_store(
        self, order_with_controls: ibOrderWithControls
    ):
        storage_key = order_with_controls.order.broker_tempid
        self.traded_object_store[storage_key] = order_with_controls

    @property
    def futures_contract_data(self) -> ibFuturesContractData:
        return self.data.broker_futures_contract

    @property
    def futures_instrument_data(self) -> ibFuturesInstrumentData:
        return self.data.broker_futures_instrument

    def get_list_of_broker_orders_with_account_id(
        self, account_id: str = arg_not_supplied
    ) -> listOfOrders:
        """
        Get list of broker orders from IB, and return as my broker_order objects

        :return: list of brokerOrder objects
        """
        list_of_control_objects = self.get_list_of_broker_control_orders(
            account_id=account_id
        )
        order_list = [
            order_with_control.order for order_with_control in list_of_control_objects
        ]

        order_list = listOfOrders(order_list)

        return order_list

    def _get_dict_of_broker_control_orders(
        self, account_id: str = arg_not_supplied
    ) -> dict:
        control_order_list = self.get_list_of_broker_control_orders(
            account_id=account_id
        )
        dict_of_control_orders = dict(
            [
                (control_order.order.broker_tempid, control_order)
                for control_order in control_order_list
            ]
        )
        return dict_of_control_orders

    def get_list_of_broker_control_orders(
        self, account_id: str = arg_not_supplied
    ) -> list:
        """
        Get list of broker orders from IB, and return as list of orders with controls

        :return: list of brokerOrder objects
        """

        list_of_raw_orders_as_trade_objects = self.ib_client.broker_get_orders(
            account_id=account_id
        )

        broker_order_with_controls_list = [
            self._create_broker_control_order_object(broker_trade_object_results)
            for broker_trade_object_results in list_of_raw_orders_as_trade_objects
        ]

        broker_order_with_controls_list = [
            broker_order_with_controls
            for broker_order_with_controls in broker_order_with_controls_list
            if broker_order_with_controls is not missing_order
        ]

        return broker_order_with_controls_list

    def _create_broker_control_order_object(
        self, trade_with_contract_from_ib: tradeWithContract
    ):
        """
        Map from the data IB gives us to my broker order object, to order with controls

        :param trade_with_contract_from_ib: tradeWithContract
        :return: brokerOrder
        """
        try:
            try:
                lookup_contract = contract_for_instrument_lookup(
                    trade_with_contract_from_ib.ibcontract_with_legs
                )
                instrument_code = self.futures_instrument_data.get_instrument_code_from_broker_contract_object(
                    lookup_contract
                )
            except:
                raise ibOrderCouldntCreateException()

            broker_order_with_controls = ibOrderWithControls(
                trade_with_contract_from_ib,
                ibclient=self.ib_client,
                instrument_code=instrument_code,
            )
        except ibOrderCouldntCreateException:
            self.log.warning(
                "Couldn't create order from ib returned order %s, usual behaviour for FX and equities trades"
                % str(trade_with_contract_from_ib)
            )
            return missing_order

        return broker_order_with_controls

    def get_list_of_orders_from_storage(self) -> listOfOrders:
        dict_of_stored_orders = self._get_dict_of_orders_from_storage()
        list_of_orders = listOfOrders(dict_of_stored_orders.values())

        return list_of_orders

    def _get_dict_of_orders_from_storage(self) -> dict:
        # Get dict from storage, update, return just the orders
        dict_of_orders_with_control = self._get_dict_of_control_orders_from_storage()
        order_dict = dict(
            [
                (key, order_with_control.order)
                for key, order_with_control in dict_of_orders_with_control.items()
            ]
        )

        return order_dict

    def _get_dict_of_control_orders_from_storage(self) -> dict:
        dict_of_orders_with_control = self.traded_object_store
        __ = [
            order_with_control.update_order()
            for order_with_control in dict_of_orders_with_control.values()
        ]

        return dict_of_orders_with_control

    def put_order_on_stack(self, broker_order: brokerOrder) -> ibOrderWithControls:
        """

        :param broker_order: key properties are instrument_code, contract_id, quantity
        :return: ibOrderWithControls or missing_order
        """
        trade_with_contract_from_ib = self._send_broker_order_to_IB(
            broker_order, what_if=False
        )

        placed_broker_order_with_controls = (
            self._return_place_order_given_ib_trade_with_contract(
                trade_with_contract_from_ib=trade_with_contract_from_ib,
                broker_order=broker_order,
            )
        )

        return placed_broker_order_with_controls

    def what_if_order(self, broker_order: brokerOrder) -> tradeWithContract:
        """

        :param broker_order: key properties are instrument_code, contract_id, quantity
        :return: ibOrderWithControls or missing_order
        """
        trade_with_contract_from_ib = self._send_broker_order_to_IB(
            broker_order, what_if=True
        )

        return trade_with_contract_from_ib

    def _return_place_order_given_ib_trade_with_contract(
        self, trade_with_contract_from_ib: tradeWithContract, broker_order: brokerOrder
    ) -> ibOrderWithControls:
        if trade_with_contract_from_ib is missing_order:
            return missing_order

        order_time = datetime.datetime.now()

        placed_broker_order_with_controls = ibOrderWithControls(
            trade_with_contract_from_ib,
            ibclient=self.ib_client,
            broker_order=broker_order,
        )

        placed_broker_order_with_controls.order.submit_datetime = order_time

        # We do this so the tempid is accurate
        placed_broker_order_with_controls.update_order()

        # We do this so we can cancel stuff and get things back more easily
        self._add_order_with_controls_to_store(placed_broker_order_with_controls)

        return placed_broker_order_with_controls

    def _send_broker_order_to_IB(
        self, broker_order: brokerOrder, what_if: bool = False
    ) -> tradeWithContract:
        """

        :param broker_order: key properties are instrument_code, contract_id, quantity
        :return: tradeWithContract object or missing_order

        """

        log_attrs = {**broker_order.log_attributes(), "method": "temp"}
        self.log.debug(
            "Going to submit order %s to IB" % str(broker_order), **log_attrs
        )

        trade_list = broker_order.trade
        order_type = broker_order.order_type
        limit_price = broker_order.limit_price
        account_id = broker_order.broker_account

        contract_object = broker_order.futures_contract
        contract_object_with_ib_data = (
            self.futures_contract_data.get_contract_object_with_IB_data(contract_object)
        )

        placed_broker_trade_object = self.ib_client.broker_submit_order(
            contract_object_with_ib_data,
            trade_list=trade_list,
            account_id=account_id,
            order_type=order_type,
            limit_price=limit_price,
            what_if=what_if,
        )
        if placed_broker_trade_object is missing_order:
            self.log.warning("Couldn't submit order", **log_attrs)
            return missing_order

        self.log.debug("Order submitted to IB", **log_attrs)

        return placed_broker_trade_object

    def match_db_broker_order_to_order_from_brokers(
        self, broker_order_to_match: brokerOrder
    ) -> brokerOrder:
        matched_control_order = (
            self.match_db_broker_order_to_control_order_from_brokers(
                broker_order_to_match
            )
        )
        if matched_control_order is missing_order:
            return missing_order

        broker_order = matched_control_order.order

        return broker_order

    def match_db_broker_order_to_control_order_from_brokers(
        self, broker_order_to_match: brokerOrder
    ) -> ibOrderWithControls:
        """

        :return: brokerOrder coming from broker
        """

        # check stored orders first
        dict_of_stored_control_orders = self._get_dict_of_control_orders_from_storage()
        matched_control_order = match_control_order_from_dict(
            dict_of_stored_control_orders, broker_order_to_match
        )
        if matched_control_order is not missing_order:
            return matched_control_order

        # try getting from broker
        # match on temp id and clientid
        account_id = broker_order_to_match.broker_account
        dict_of_broker_control_orders = self._get_dict_of_broker_control_orders(
            account_id=account_id
        )
        matched_control_order = match_control_order_from_dict(
            dict_of_broker_control_orders, broker_order_to_match
        )
        if matched_control_order is not missing_order:
            return matched_control_order

        # Match on permid
        matched_control_order = match_control_order_on_permid(
            dict_of_broker_control_orders, broker_order_to_match
        )

        return matched_control_order

    def cancel_order_on_stack(self, broker_order: brokerOrder):
        log_attrs = {**broker_order.log_attributes(), "method": "temp"}
        matched_control_order = (
            self.match_db_broker_order_to_control_order_from_brokers(broker_order)
        )
        if matched_control_order is missing_order:
            self.log.warning("Couldn't cancel non existent order", **log_attrs)
            return None

        self.cancel_order_given_control_object(matched_control_order)
        self.log.debug("Sent cancellation for %s" % str(broker_order), **log_attrs)

    def cancel_order_given_control_object(
        self, broker_orders_with_controls: ibOrderWithControls
    ):
        original_order_object = broker_orders_with_controls.control_object.trade.order
        self.ib_client.ib_cancel_order(original_order_object)

        return success

    def check_order_is_cancelled(self, broker_order: brokerOrder) -> bool:
        matched_control_order = (
            self.match_db_broker_order_to_control_order_from_brokers(broker_order)
        )
        if matched_control_order is missing_order:
            raise missingOrder
        cancellation_status = self.check_order_is_cancelled_given_control_object(
            matched_control_order
        )

        return cancellation_status

    def check_order_is_cancelled_given_control_object(
        self, broker_order_with_controls: ibOrderWithControls
    ) -> bool:
        status = self.get_status_for_control_object(broker_order_with_controls)
        cancellation_status = (
            status in ibOrderStatus.DoneStates and status != ibOrderStatus.Filled
        )

        return cancellation_status

    def _get_status_for_trade_object(self, original_trade_object: ibTrade) -> str:
        self.ib_client.refresh()
        return original_trade_object.orderStatus.status

    def modify_limit_price_given_control_object(
        self, broker_order_with_controls: ibOrderWithControls, new_limit_price: float
    ) -> ibOrderWithControls:
        """
        NOTE this does not update the internal state of orders, which will retain the original order

        :param broker_order_with_controls:
        :param new_limit_price:
        :return:
        """

        ## throws orderCannotBeModified
        self.check_order_can_be_modified_given_control_object_throw_error_if_not(
            broker_order_with_controls
        )

        original_order_object = broker_order_with_controls.control_object.trade.order
        original_contract_object_with_legs = (
            broker_order_with_controls.control_object.ibcontract_with_legs
        )

        _not_used_new_trade_object = (
            self.ib_client.modify_limit_price_given_original_objects(
                original_order_object,
                original_contract_object_with_legs,
                new_limit_price,
            )
        )

        # we don't actually replace the trade object
        # otherwise if the limit order isn't changed, it will think it has been
        broker_order_with_controls.order.limit_price = new_limit_price
        broker_order_with_controls.update_order()

        return broker_order_with_controls

    def check_order_can_be_modified_given_control_object_throw_error_if_not(
        self, broker_order_with_controls: ibOrderWithControls
    ):
        status = self.get_status_for_control_object(broker_order_with_controls)
        STATUS_WE_CAN_MODIFY_IN = ["Submitted"]
        can_be_modified = status in STATUS_WE_CAN_MODIFY_IN
        if not can_be_modified:
            raise orderCannotBeModified(
                "Order can't be modified as status is %s, not in %s"
                % (status, STATUS_WE_CAN_MODIFY_IN)
            )

    def get_status_for_control_object(
        self, broker_order_with_controls: ibOrderWithControls
    ) -> str:
        original_trade_object = broker_order_with_controls.control_object.trade
        status = self._get_status_for_trade_object(original_trade_object)

        return status


def add_trade_info_to_broker_order(
    broker_order: brokerOrder, broker_order_from_trade_object: ibBrokerOrder
) -> brokerOrder:
    new_broker_order = copy(broker_order)
    keys_to_replace = [
        "broker_permid",
        "commission",
        "algo_comment",
        "broker_tempid",
        "leg_filled_price",
    ]

    for key in keys_to_replace:
        new_broker_order._order_info[key] = broker_order_from_trade_object._order_info[
            key
        ]

    broker_order_is_filled = not broker_order_from_trade_object.fill.equals_zero()
    if broker_order_is_filled:
        new_broker_order.fill_order(
            broker_order_from_trade_object.fill,
            broker_order_from_trade_object.filled_price,
            broker_order_from_trade_object.fill_datetime,
        )

    return new_broker_order


def match_control_order_on_permid(
    dict_of_broker_control_orders: dict, broker_order_to_match: brokerOrder
):
    list_of_broker_control_orders = list(dict_of_broker_control_orders.values())
    list_of_broker_orders = [
        control_order.order for control_order in list_of_broker_control_orders
    ]

    permid_to_match = broker_order_to_match.broker_permid
    if permid_to_match == "" or permid_to_match == 0:
        return missing_order

    permid_list = [order.broker_permid for order in list_of_broker_orders]
    try:
        permid_idx = permid_list.index(permid_to_match)
    except ValueError:
        return missing_order

    matched_control_order = list_of_broker_control_orders[permid_idx]

    return matched_control_order


def match_control_order_from_dict(
    dict_of_broker_control_orders: dict, broker_order_to_match: brokerOrder
):
    matched_control_order_from_dict = dict_of_broker_control_orders.get(
        broker_order_to_match.broker_tempid, missing_order
    )

    return matched_control_order_from_dict
