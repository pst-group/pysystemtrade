from copy import copy
from dataclasses import dataclass
from math import isfinite

from syscore.exceptions import missingContract, missingData
from syscore.constants import arg_not_supplied
from sysexecution.orders.named_order_objects import missing_order

from sysdata.data_blob import dataBlob

from sysexecution.orders.broker_orders import (
    create_new_broker_order_from_contract_order,
    brokerOrderType,
    market_order_type,
    limit_order_type,
    stop_loss_order_type,
)
from sysexecution.tick_data import tickerObject
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.order_stacks.broker_order_stack import orderWithControls

from sysproduction.data.broker import dataBroker

limit_price_from_input = "input"
limit_price_from_side_price = "side_price"
limit_price_from_offside_price = "offside_price"
sources_of_limit_price = [
    limit_price_from_offside_price,
    limit_price_from_side_price,
    limit_price_from_input,
]


@dataclass
class benchmarkPriceCollection(object):
    side_price: float = None
    offside_price: float = None
    mid_price: float = None


class Algo(object):
    def __init__(self, data: dataBlob, contract_order: contractOrder):
        self._data = data
        self._contract_order = contract_order
        self._data_broker = dataBroker(data)

    @property
    def data(self):
        return self._data

    @property
    def blocking_algo_requires_management(self) -> bool:
        return True

    @property
    def data_broker(self):
        return self._data_broker

    @property
    def contract_order(self):
        return self._contract_order

    def submit_trade(self) -> orderWithControls:
        """

        :return: broker order with control  or missing_order
        """
        raise NotImplementedError

    def manage_trade(
        self, broker_order_with_controls: orderWithControls
    ) -> orderWithControls:
        """

        :return: broker order with control
        """
        raise NotImplementedError

    def get_and_submit_broker_order_for_contract_order(
        self,
        contract_order: contractOrder,
        input_limit_price: float = None,
        order_type: brokerOrderType = market_order_type,
        limit_price_from: str = limit_price_from_input,
        ticker_object: tickerObject = None,
        broker_account: str = arg_not_supplied,
    ):
        broker = self.data_broker.get_broker_name()

        if broker_account is arg_not_supplied:
            broker_account = self.data_broker.get_broker_account()

        broker_clientid = self.data_broker.get_broker_clientid()

        if ticker_object is None:
            ticker_object = self.data_broker.get_ticker_object_for_order(contract_order)

        try:
            collected_prices = self.get_market_data_for_order_modifies_ticker_object(
                ticker_object, contract_order
            )
        except missingData:
            # no data available, no can do
            return missing_order

        ## We want to preserve these otherwise there is a danger they will dynamically change
        collected_prices = copy(collected_prices)

        if order_type == limit_order_type or order_type == stop_loss_order_type:
            limit_price = self.set_limit_price(
                contract_order=contract_order,
                collected_prices=collected_prices,
                limit_price_from=limit_price_from,
                input_limit_price=input_limit_price,
            )
        else:
            limit_price = None

        broker_order = create_new_broker_order_from_contract_order(
            contract_order,
            order_type=order_type,
            side_price=collected_prices.side_price,
            mid_price=collected_prices.mid_price,
            offside_price=collected_prices.offside_price,
            broker=broker,
            broker_account=broker_account,
            broker_clientid=broker_clientid,
            limit_price=limit_price,
        )

        self.data.log.debug(
            "Created a broker order %s (not yet submitted or written to local DB)"
            % str(broker_order),
            **contract_order.log_attributes(),
            method="temp",
        )

        placed_broker_order_with_controls = self.data_broker.submit_broker_order(
            broker_order
        )

        if placed_broker_order_with_controls is missing_order:
            self.data.log.warning(
                "Order could not be submitted",
                **contract_order.log_attributes(),
                method="temp",
            )
            return missing_order

        self.data.log.debug(
            "Submitted order to IB %s" % str(placed_broker_order_with_controls.order),
            **placed_broker_order_with_controls.order.log_attributes(),
            method="temp",
        )

        placed_broker_order_with_controls.add_or_replace_ticker(ticker_object)

        return placed_broker_order_with_controls

    def get_market_data_for_order_modifies_ticker_object(
        self, ticker_object: tickerObject, contract_order: contractOrder
    ) -> benchmarkPriceCollection:
        # We use prices for a couple of reasons:
        # to provide a benchmark for execution purposes
        # (optionally) to set limit prices
        ##

        # Get the first 'reference' tick
        try:
            reference_tick = (
                ticker_object.wait_for_valid_bid_and_ask_and_return_current_tick(
                    wait_time_seconds=10
                )
            )
        except missingData:
            self.data.log.warning(
                "Can't get market data for %s so not trading with limit order %s"
                % (contract_order.instrument_code, str(contract_order)),
                **contract_order.log_attributes(),
                method="temp",
            )
            raise

        tick_analysis = ticker_object.analyse_for_tick(reference_tick)

        ticker_object.clear_and_add_reference_as_first_tick(reference_tick)

        # These prices will be used for limit price purposes
        # They are scalars
        collected_prices = benchmarkPriceCollection(
            offside_price=tick_analysis.offside_price,
            side_price=tick_analysis.side_price,
            mid_price=tick_analysis.mid_price,
        )

        return collected_prices

    def set_limit_price(
        self,
        contract_order: contractOrder,
        collected_prices: benchmarkPriceCollection,
        input_limit_price: float = None,
        limit_price_from: str = limit_price_from_input,
    ) -> float:
        if limit_price_from == limit_price_from_input:
            assert input_limit_price is not None
            limit_price = input_limit_price

        elif limit_price_from == limit_price_from_side_price:
            limit_price = collected_prices.side_price

        elif limit_price_from == limit_price_from_offside_price:
            limit_price = collected_prices.offside_price

        else:
            raise Exception("Limit price from %s not known" % limit_price_from)

        if (
            limit_price_from
            in (limit_price_from_side_price, limit_price_from_offside_price)
            and contract_order.futures_contract.is_spread_contract()
            and isfinite(limit_price)
        ):
            # Preserve a quoted spread price: a single leg's tick size can
            # differ from the spread's, so rounding to it can invalidate the quote.
            # Explicit input limits and non-finite values keep the existing path.
            return limit_price

        limit_price_rounded = self.round_limit_price_to_tick_size(
            contract_order, limit_price
        )

        return limit_price_rounded

    def round_limit_price_to_tick_size(
        self, contract_order: contractOrder, limit_price: float
    ) -> float:
        contract = contract_order.futures_contract

        try:
            min_tick = self.data_broker.get_min_tick_size_for_contract(contract)
        except missingContract:
            self.data.log.warning(
                "Couldn't find min tick size for %s, not rounding limit price %f"
                % (str(contract), limit_price),
                **contract_order.log_attributes(),
                method="temp",
            )

            return limit_price

        rounded_limit_price = min_tick * round(limit_price / min_tick)

        return rounded_limit_price

    def file_log_report_market_order(
        self, broker_order_with_controls: orderWithControls
    ):
        ticker_object = broker_order_with_controls.ticker
        current_tick = str(ticker_object.current_tick())

        log_report = "Market order execution current tick %s" % current_tick

        self.data.log.debug(
            log_report,
            **broker_order_with_controls.order.log_attributes(),
            method="temp",
        )
