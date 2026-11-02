"""
This is the original 'best execution' algo I used in my legacy system
"""

import time
from typing import Union
from syscore.exceptions import missingData, marketClosed, orderCannotBeModified
from sysexecution.orders.named_order_objects import missing_order

from sysexecution.algos.algo import (
    Algo,
    limit_price_from_offside_price,
)
from sysexecution.algos.common_functions import (
    post_trade_processing,
    MESSAGING_FREQUENCY,
    cancel_order,
    check_current_limit_price_at_inside_spread,
    limit_price_is_at_inside_spread,
)
from sysexecution.tick_data import tickerObject, analysisTick
from sysexecution.order_stacks.broker_order_stack import orderWithControls
from sysexecution.orders.base_orders import Order
from sysexecution.orders.broker_orders import (
    market_order_type,
    limit_order_type,
    brokerOrder,
)
from sysexecution.orders.contract_orders import best_order_type, contractOrder


# Here are the algo parameters
# Hard coded; if you want to try different parameters make a hard copy and
# give it a different reference

# delay times
PASSIVE_TIME_OUT = 300
TOTAL_TIME_OUT = 600

# Don't trade with an algo in last 30 minutes
HOURS_BEFORE_MARKET_CLOSE_TO_SWITCH_TO_MARKET = 0.5

# imbalance
# if more than 5 times on the bid (if we're buying) than the offer, AND less than
# three times our quantity on the offer, then go aggressive
IMBALANCE_THRESHOLD = 5
IMBALANCE_ADJ_FACTOR = 3

# we only do one contract at a time
SIZE_LIMIT = 1

no_need_to_switch = "_NO_NEED_TO_SWITCH"


class algoOriginalBest(Algo):
    """
    This is the original 'best execution' algo I used in my legacy system
    It's behaviour is described here
       https://qoppac.blogspot.com/2014/10/the-worlds-simplest-execution-algorithim.html

    """

    def submit_trade(self) -> orderWithControls:
        placed_broker_order_with_controls = self.prepare_and_submit_trade()
        if placed_broker_order_with_controls is missing_order:
            return missing_order

        return placed_broker_order_with_controls

    def manage_trade(
        self, placed_broker_order_with_controls: orderWithControls
    ) -> orderWithControls:
        data = self.data
        placed_broker_order_with_controls = self.manage_live_trade(
            placed_broker_order_with_controls
        )
        placed_broker_order_with_controls = post_trade_processing(
            data, placed_broker_order_with_controls
        )

        return placed_broker_order_with_controls

    def prepare_and_submit_trade(self) -> orderWithControls:
        data = self.data
        contract_order = self.contract_order
        log_attrs = {**contract_order.log_attributes(), "method": "temp"}

        ## check order type is 'best' not 'limit' or 'market'
        if not contract_order.order_type == best_order_type:
            data.log.critical(
                "Order has been allocated to algo 'original-best' but order type is %s"
                % str(contract_order.order_type),
                **log_attrs,
            )
            return missing_order

        cut_down_contract_order = (
            contract_order.reduce_trade_size_proportionally_so_smallest_leg_is_max_size(
                SIZE_LIMIT
            )
        )
        if cut_down_contract_order.trade != contract_order.trade:
            data.log.debug(
                "Cut down order from size %s to %s because of algo size limit"
                % (str(contract_order.trade), str(cut_down_contract_order.trade)),
                **log_attrs,
            )

        ticker_object = self.data_broker.get_ticker_object_for_order(
            cut_down_contract_order
        )
        try:
            okay_to_do_limit_trade = self.limit_trade_viable(
                ticker_object=ticker_object,
                order=cut_down_contract_order,
            )
        except missingData:
            ## Safer not to trade at all
            return missing_order

        if okay_to_do_limit_trade:
            # create and issue limit order
            broker_order_with_controls = (
                self.get_and_submit_broker_order_for_contract_order(
                    cut_down_contract_order,
                    order_type=limit_order_type,
                    limit_price_from=limit_price_from_offside_price,
                    ticker_object=ticker_object,
                )
            )
        else:
            # do a market order
            data.log.debug(
                "Conditions are wrong so doing market trade instead of limit trade",
                **log_attrs,
            )
            broker_order_with_controls = (
                self.get_and_submit_broker_order_for_contract_order(
                    cut_down_contract_order, order_type=market_order_type
                )
            )

        return broker_order_with_controls

    def manage_live_trade(self, order_control: orderWithControls) -> orderWithControls:
        data = self.data
        log_attrs = {
            **order_control.order.log_attributes(),
            "method": "temp",
        }

        trade_open = True
        is_aggressive = False
        data.log.debug(
            "Managing trade %s with algo 'original-best'" % str(order_control.order),
            **log_attrs,
        )

        is_limit_trade = order_control.order.order_type == limit_order_type

        while trade_open:
            time.sleep(0.001)
            if order_control.message_required(
                messaging_frequency_seconds=MESSAGING_FREQUENCY
            ):
                self.file_log_report(is_aggressive, order_control)

            if is_limit_trade:
                if is_aggressive:
                    ## aggressive keep limit price in line
                    self.set_aggressive_limit_price(
                        broker_order_with_controls=order_control,
                    )
                else:
                    # passive limit trade
                    reason_to_switch = self.reason_to_switch_to_aggressive(
                        broker_order_with_controls=order_control,
                    )
                    need_to_switch = self.required_to_switch_to_aggressive(
                        reason_to_switch
                    )

                    if need_to_switch:
                        data.log.debug(
                            "Switch to aggressive because %s" % reason_to_switch,
                            **log_attrs,
                        )
                        is_aggressive = True
            else:
                # market trade nothing to do
                pass

            order_completed = order_control.completed()
            if order_completed:
                data.log.debug("Trade completed", **log_attrs)
                break

            order_timeout = order_control.seconds_since_submission() > TOTAL_TIME_OUT
            if order_timeout:
                data.log.debug(
                    "Run out of time: cancelling",
                    **log_attrs,
                )
                order_control = cancel_order(data, order_control)
                break

            order_cancelled = (
                self.data_broker.check_order_is_cancelled_given_control_object(
                    order_control
                )
            )
            if order_cancelled:
                data.log.warning("Order has been cancelled: not by algo", **log_attrs)
                break

        return order_control

    def limit_trade_viable(
        self,
        order: contractOrder,
        ticker_object: tickerObject,
    ) -> bool:
        log_attrs = {**order.log_attributes(), "method": "temp"}

        # no point doing limit order if we've got imbalanced size issues, as we'd
        # switch to aggressive immediately
        raise_adverse_size_issue = self.adverse_size_issue(
            ticker_object, order, wait_for_valid_tick=True
        )

        if raise_adverse_size_issue:
            self.data.log.debug("Limit trade not viable", **log_attrs)
            return False

        # or if not enough time left
        if self.is_market_about_to_close(order=order):
            self.data.log.debug(
                "Market about to close or stack handler nearly close - "
                "doing market order",
                **log_attrs,
            )
            return False

        return True

    def file_log_report(
        self, is_aggressive: bool, broker_order_with_controls: orderWithControls
    ):
        limit_trade = broker_order_with_controls.order.order_type == limit_order_type
        if limit_trade:
            self.file_log_report_limit_order(is_aggressive, broker_order_with_controls)
        else:
            self.file_log_report_market_order(broker_order_with_controls)

    def file_log_report_limit_order(
        self, is_aggressive: bool, broker_order_with_controls: orderWithControls
    ):
        if is_aggressive:
            agg_txt = "Aggressive"
        else:
            agg_txt = "Passive"

        limit_price = broker_order_with_controls.order.limit_price
        broker_limit_price = broker_order_with_controls.broker_limit_price()

        ticker_object = broker_order_with_controls.ticker
        current_tick = str(ticker_object.current_tick())

        log_report = (
            "%s execution with limit price desired:%f actual:%f last tick %s"
            % (
                agg_txt,
                limit_price,
                broker_limit_price,
                current_tick,
            )
        )

        self.data.log.debug(
            log_report,
            **broker_order_with_controls.order.log_attributes(),
            method="temp",
        )

    def reason_to_switch_to_aggressive(
        self,
        broker_order_with_controls: orderWithControls,
    ) -> str:
        ticker_object = broker_order_with_controls.ticker

        too_much_time = (
            broker_order_with_controls.seconds_since_submission() > PASSIVE_TIME_OUT
        )
        if too_much_time:
            return (
                "Time out after %f seconds"
                % broker_order_with_controls.seconds_since_submission()
            )

        market_about_to_close = self.is_market_about_to_close(
            order=broker_order_with_controls.order,
        )
        if market_about_to_close:
            return "Market is closing soon or stack handler will end soon"

        try:
            adverse_price = ticker_object.adverse_price_movement_vs_reference()
            if adverse_price:
                return "Adverse price movement"

            adverse_size = self.adverse_size_issue(
                ticker_object,
                broker_order_with_controls.order,
                wait_for_valid_tick=False,
            )
            if adverse_size:
                return (
                    "Imbalance ratio of %f exceeds threshold"
                    % ticker_object.latest_imbalance_ratio()
                )

            ## everything is fine, stay with aggressive
            return no_need_to_switch

        except:
            return "Problem with data, switch to aggressive"

    def is_market_about_to_close(
        self,
        order: Union[brokerOrder, contractOrder],
    ) -> bool:
        try:
            short_of_time = (
                self.data_broker.less_than_N_hours_of_trading_left_for_contract(
                    order.futures_contract,
                    N_hours=HOURS_BEFORE_MARKET_CLOSE_TO_SWITCH_TO_MARKET,
                )
            )
        except marketClosed:
            self.data.log.warning(
                "Market has closed for active limit order %s!" % str(order),
                **order.log_attributes(),
                method="temp",
            )
            return True

        return short_of_time

    @staticmethod
    def required_to_switch_to_aggressive(reason: str) -> bool:
        if reason == no_need_to_switch:
            return False
        else:
            return True

    def adverse_size_issue(
        self, ticker_object: tickerObject, order: Order, wait_for_valid_tick=False
    ) -> bool:
        if wait_for_valid_tick:
            current_tick_analysis = (
                ticker_object.wait_for_valid_bid_and_ask_and_analyse_current_tick()
            )
        else:
            current_tick_analysis = ticker_object.current_tick_analysis

        latest_imbalance_ratio_exceeded = self._is_imbalance_ratio_exceeded(
            current_tick_analysis, order
        )
        insufficient_size_on_our_preferred_side = (
            self._is_insufficient_size_on_our_preferred_side(
                ticker_object, current_tick_analysis, order
            )
        )

        if latest_imbalance_ratio_exceeded and insufficient_size_on_our_preferred_side:
            return True
        else:
            return False

    def _is_imbalance_ratio_exceeded(
        self, current_tick_analysis: analysisTick, order: Order
    ) -> bool:
        latest_imbalance_ratio = current_tick_analysis.imbalance_ratio
        latest_imbalance_ratio_exceeded = latest_imbalance_ratio > IMBALANCE_THRESHOLD

        if latest_imbalance_ratio_exceeded:
            self.data.log.debug(
                "Imbalance ratio for ticker %s %f exceeds threshold %f"
                % (
                    str(current_tick_analysis),
                    latest_imbalance_ratio,
                    IMBALANCE_THRESHOLD,
                ),
                **order.log_attributes(),
                method="temp",
            )

        return latest_imbalance_ratio_exceeded

    def _is_insufficient_size_on_our_preferred_side(
        self,
        ticker_object: tickerObject,
        current_tick_analysis: analysisTick,
        order: Order,
    ) -> bool:
        abs_size_we_wish_to_trade = abs(ticker_object.qty)
        size_we_require_to_trade_limit = (
            IMBALANCE_ADJ_FACTOR * abs_size_we_wish_to_trade
        )
        available_size_on_our_preferred_side = abs(current_tick_analysis.side_qty)

        insufficient_size_on_our_preferred_side = (
            available_size_on_our_preferred_side < size_we_require_to_trade_limit
        )

        if insufficient_size_on_our_preferred_side:
            self.data.log.debug(
                "On ticker %s we require size of %f (our trade %f * adjustment %f) "
                "for a limit order but only %f available"
                % (
                    str(current_tick_analysis),
                    size_we_require_to_trade_limit,
                    abs_size_we_wish_to_trade,
                    IMBALANCE_ADJ_FACTOR,
                    available_size_on_our_preferred_side,
                ),
                **order.log_attributes(),
                method="temp",
            )

        return insufficient_size_on_our_preferred_side

    def set_aggressive_limit_price(
        self, broker_order_with_controls: orderWithControls
    ) -> orderWithControls:
        limit_trade = broker_order_with_controls.order.order_type == limit_order_type
        if not limit_trade:
            # market trade, don't bother
            return broker_order_with_controls

        new_limit_price = check_current_limit_price_at_inside_spread(
            broker_order_with_controls
        )
        if new_limit_price is limit_price_is_at_inside_spread:
            pass
        else:
            broker_order_with_controls = self.set_best_limit_price(
                broker_order_with_controls, new_limit_price
            )

        return broker_order_with_controls

    def set_best_limit_price(
        self,
        broker_order_with_controls: orderWithControls,
        new_limit_price: float,
    ):
        log_attrs = {
            **broker_order_with_controls.order.log_attributes(),
            "method": "temp",
        }

        try:
            broker_order_with_controls = (
                self.data_broker.modify_limit_price_given_control_object(
                    broker_order_with_controls, new_limit_price
                )
            )
            self.data.log.debug(
                "Tried to change limit price to %f" % new_limit_price,
                **log_attrs,
            )
        except orderCannotBeModified as error:
            self.data.log.debug(
                "Can't modify limit price for order, error %s" % str(error),
                **log_attrs,
            )

        return broker_order_with_controls
