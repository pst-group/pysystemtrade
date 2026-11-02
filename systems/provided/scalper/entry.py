from time import sleep

import numpy as np
import pickle
from systems.provided.scalper.broker import BrokerController
from systems.provided.scalper.configuration import (
    SECONDS_PER_UNIT,
    BARS_REQUIRED_FOR_ESTIMATION,
    StratParameters,
    init_paramaters,
    display_diags,
    interactively_modify_parameters,
    TIME_BETWEEN_HEARTBEATS,
    estimate_R_from_prices,
    get_final_price,
)
from syscore.constants import arg_not_supplied
from syscore.exceptions import marketClosed
from syscore.interactive.progress_bar import progressBar
from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysproduction.data.instruments import diagInstruments

from systems.provided.scalper.components import (
    State,
    action_given_current_state,
    ActionFromState,
    FillAndOrder,
)
from sysexecution.orders.named_order_objects import missing_order
from sysproduction.data.currency_data import dataCurrency
import datetime
import sys
from typing import List, Tuple

import pandas as pd

from sysexecution.tick_data import tickerObject, oneTick
from sysobjects.contracts import futuresContract
from sysproduction.data.prices import diagPrices


## WRITE ORDERS TO DB IN QUIET PERIODS
## RATIO OF R, CHECK HORIZON SOMEHOW (WITH MORE DATA)


class MRRunner:
    def __init__(self, instrument: str):
        self.data = dataBlob()
        self.set_instrument(instrument)
        self._broker_controller = BrokerController(
            self.data, futures_contract=self.futures_contract
        )

    def start(self):
        okay_to_start = pre_start_checks_okay_to_start(self)
        if not okay_to_start:
            print("Binned it")
            exit()

        print("Final parameters %s" % str(self.strategy_parameters))

        self.wait_then_run()

    def wait_then_run(self):
        position_matches = self.broker_controller.check_for_position_match(
            0, self.futures_contract_with_actual_expiry
        )
        if not position_matches:
            print("Can't start, position doesn't match - fix before restarting")
            exit()

        print("Waiting till okay to trade")
        not_okay = True
        while not_okay:
            okay_to_start = self.okay_to_start_trading()
            if okay_to_start:
                not_okay = False
            else:
                self.heartbeat("Waiting to start trading")
                sleep(5)

        self.state = State.start(self.strategy_parameters)
        self.save_history()
        self.run()

    def run(self):
        try:
            while self.okay_to_trade():
                self.heartbeat()
                self.update_state_from_broker()

                if (
                    self.state.flat_with_no_orders()
                    and not self.okay_to_open_new_orders()
                ):
                    break

                if self.broker_state_matches():
                    self.calculate_and_submit_orders()
        except Exception as e:
            print("Error %s or user aborted" % str(e))

        print("Time to go home. Final position was %d" % self.state.position)
        self.finished()

    def update_state_from_broker(self):
        list_of_fills_and_orders = self.broker_controller.get_fills_from_broker()
        if len(list_of_fills_and_orders) == 0:
            return
        else:
            print("Fills received from broker %s" % str(list_of_fills_and_orders))
            self.update_state_from_broker_when_fills_exist(list_of_fills_and_orders)

    def update_state_from_broker_when_fills_exist(
        self, list_of_fills_and_orders: List[FillAndOrder]
    ):
        for fill_and_order in list_of_fills_and_orders:
            self.update_state_given_fill_and_order(fill_and_order)

        if self.state.flat_with_no_orders():
            self.action_when_flat_and_state_changed()

    def update_state_given_fill_and_order(self, fill_and_order: FillAndOrder):
        print("Update state from %s" % fill_and_order)
        current_price = self.current_mid_price()
        current_state = self.state
        new_state = current_state.update_given_broker_fill_and_latest_price(
            fill=fill_and_order.fill,
            order=fill_and_order.order,
            current_price=current_price,
        )
        print("New state %s" % new_state)
        self.update_state_and_list_of_states(new_state)
        self.add_fill_and_order(fill_and_order)

    def action_when_flat_and_state_changed(self):
        ## FIXME SAVE ORDERS IN DB
        self.save_history()

    def save_history(self):
        print("Saving states, fills and orders")
        data_to_save = dict(
            list_of_states=self.list_of_states,
            fills_and_orders=self.complete_fills_and_orders,
        )
        with open(
            "/home/rob/temp/mrfile_%s_%s"
            % (str(datetime.date.today()), self.instrument),
            "wb",
        ) as f:
            pickle.dump(data_to_save, f)  ## ignore stupid pycharm error

    def broker_state_matches(self):
        position_matches = self.broker_controller.check_for_position_match(
            self.state.position, self.futures_contract_with_actual_expiry
        )

        return position_matches

    def calculate_and_submit_orders(self):
        action = action_given_current_state(
            current_state=self.state,
            current_price_getter=self.current_mid_price_blocking,
            R_calculator=self.estimate_of_R_range_with_min_and_max_applied,
        )

        if action.is_no_action:
            return

        print("New action is %s" % action)
        if action.cancel_orders:
            # action not updated, assume cancel goes through
            # if not will be a (temporary - hopefully) position mismatch
            print("Cancel orders")
            self.broker_controller.cancel_all_orders()
        else:
            ## we update the action in case we get issues
            print("Create orders")
            action = self.create_limit_orders_and_return_updated_action(action)

        new_state = self.state.update_from_action(action)
        self.update_state_and_list_of_states(new_state)

    def create_limit_orders_and_return_updated_action(self, action: ActionFromState):
        for order in action.new_orders:
            executed_order = self.broker_controller.create_limit_order(order)
            if executed_order is missing_order:
                print("Order %s couldn't be placed, abandoning for now" % order)
                action = ActionFromState.create_no_action()
                return action

        return action

    def finished(self):
        self.cancel_all_orders_and_update_state_when_finished()
        self.save_history()
        self.data_broker.cancel_market_data_for_contract(self.futures_contract)
        print("Finished")
        exit()

    def cancel_all_orders_and_update_state_when_finished(self):
        action = ActionFromState.create_cancel_orders()
        self.broker_controller.cancel_all_orders()
        new_state = self.state.update_from_action(action)
        self.update_state_and_list_of_states(new_state)

    ## PRICES
    def estimate_of_R_range_with_min_and_max_applied(self):
        empirical_R = self.estimate_of_R_range_blocking()
        min_R = self.strategy_parameters.min_R
        max_R = self.strategy_parameters.max_R
        use_R = max([min([empirical_R, max_R]), min_R])

        print(
            "Using R %f, estimate %f, max %f, min %f",
            (use_R, empirical_R, max_R, min_R),
        )

        return use_R

    def estimate_of_R_range_blocking(self):
        print(
            "getting R may take %d seconds"
            % (
                (1 + BARS_REQUIRED_FOR_ESTIMATION)
                * self.strategy_parameters.horizon_seconds
            )
        )

        self.set_progress(
            (1 + BARS_REQUIRED_FOR_ESTIMATION)
            * self.strategy_parameters.horizon_seconds
        )
        last_few_bar_ranges = self.get_minimum_number_of_bar_ranges_blocking()
        self.clear_progress()
        print("")
        print("Last few bar ranges %s" % str(last_few_bar_ranges))
        return np.mean(last_few_bar_ranges)

    def get_minimum_number_of_bar_ranges_blocking(self):
        bar_count = 0
        bar_ranges_excluding_last = pd.Series()  ## avoid python warning

        while bar_count < (
            BARS_REQUIRED_FOR_ESTIMATION
        ):  ## need one extra as last one is live
            bar_ranges = self.get_bar_ranges()
            bar_ranges_excluding_last = bar_ranges[:-1]
            bar_count = len(bar_ranges_excluding_last)

        return bar_ranges_excluding_last[-BARS_REQUIRED_FOR_ESTIMATION:]

    def get_bar_ranges(self, horizon_multiplier: int = 1):
        ts_list = self.update_and_return_time_series_of_unit_samples()
        if len(ts_list) == 0:
            return ts_list
        ts_list_resampled_unit = ts_list.resample("%ds" % SECONDS_PER_UNIT).ffill()
        ts_list_resampled_unit = ts_list_resampled_unit.dropna()
        resample_to = (
            "%ds" % self.strategy_parameters.horizon_seconds * horizon_multiplier
        )
        r_min = ts_list_resampled_unit.resample(resample_to).min()
        r_max = ts_list_resampled_unit.resample(resample_to).max()

        range = r_max - r_min

        return range

    def current_mid_price_blocking(self) -> float:
        mid_price = np.nan
        while np.isnan(mid_price):
            mid_price = self.current_mid_price()

        return mid_price

    def current_mid_price(self) -> float:
        samples = self.update_and_return_time_series_of_unit_samples()
        mid_price = float(samples.values[-1])

        return mid_price

    def update_and_return_time_series_of_unit_samples(self) -> pd.DataFrame:
        ts_list = self.ts_list_of_unit_samples
        if len(ts_list) == 0:
            return self.update_and_return_time_series_of_unit_samples_without_checks()

        last_time = ts_list.index[-1]
        time_since = datetime.datetime.now() - last_time
        if time_since.seconds < SECONDS_PER_UNIT:
            return ts_list

        return self.update_and_return_time_series_of_unit_samples_without_checks()

    def update_and_return_time_series_of_unit_samples_without_checks(
        self,
    ) -> pd.DataFrame:
        if self.progress is not None:
            self.progress.iterate()
        tick = self.next_tick()
        mid_price = np.mean([tick.ask_price, tick.bid_price])
        new_item = pd.Series(
            [mid_price], index=pd.DatetimeIndex([datetime.datetime.now()])
        )

        ts_list = self.ts_list_of_unit_samples
        if len(ts_list) == 0:
            ts_list = new_item
        else:
            ts_list = pd.concat([ts_list, new_item])

        self._tslist = ts_list

        return ts_list

    @property
    def ts_list_of_unit_samples(self) -> pd.DataFrame:
        ts_list = getattr(self, "_tslist", pd.DataFrame())
        return ts_list

    def next_tick(self) -> oneTick:
        ticker = self.ticker
        return ticker.current_tick()

    @property
    def ticker(self):
        ticker = getattr(self, "_ticker", None)
        if ticker is None:
            self._ticker = ticker = self.get_ticker()

        return ticker

    def get_ticker(self) -> tickerObject:
        contract = self.futures_contract
        return self.data_broker.get_ticker_object_for_contract(contract)

    ### PROGRESS
    def set_progress(self, length: int):
        self._progress = progressBar(length)

    def clear_progress(self):
        self._progress = None

    @property
    def progress(self) -> progressBar:
        return getattr(self, "_progress", None)

    ##HEARTBEATS
    def heartbeat(self, msg=arg_not_supplied):
        if self.time_since_last_heartbeat() > TIME_BETWEEN_HEARTBEATS:
            if msg is arg_not_supplied:
                self.default_heartbeat_msg()
            else:
                print(msg)
            self.reset_heartbeat()

    def default_heartbeat_msg(self):
        mid_price = self.current_mid_price()
        print(
            "Current mid price %s, position %d, orders %s, running net p&l %f. Ctrl-C to abort and cancel orders."
            % (
                mid_price,
                self.state.position,
                self.state.orders,
                self.state.pandl.net_pandl(),
            )
        )
        if not self.broker_state_matches():
            print(
                "Position mismatch %s"
                % self.broker_controller.check_for_position_match_msg(
                    self.state.position, self.futures_contract_with_actual_expiry
                )
            )

    def time_since_last_heartbeat(self):
        diff = datetime.datetime.now() - self.last_heartbeat
        return diff.total_seconds()

    def reset_heartbeat(self):
        self._heartbeat = datetime.datetime.now()

    @property
    def last_heartbeat(self):
        heartbeat = getattr(self, "_heartbeat", None)
        if heartbeat is None:
            heartbeat = self._heartbeat = datetime.datetime.now()
        return heartbeat

    ## STATUS CHECK
    def okay_to_start_trading(self):
        too_late_to_open_orders = self.too_late_to_open_new_orders()

        if too_late_to_open_orders:
            return False

        return self.data_broker.is_contract_okay_to_trade(self.futures_contract)

    def okay_to_trade(self):
        current_horizon_in_hours = self.strategy_parameters.horizon_seconds / 3600.0
        try:
            market_nearly_closed = (
                self.data_broker.less_than_N_hours_of_trading_left_for_contract(
                    self.futures_contract,
                    N_hours=current_horizon_in_hours,  ## to be on safe side
                )
            )
        except marketClosed:
            market_nearly_closed = True

        return not market_nearly_closed

    def okay_to_open_new_orders(self):
        too_late_to_open_new_orders = self.too_late_to_open_new_orders()

        daily_stop = -self.strategy_parameters.stoploss_ccy
        daily_loss = self.state.pandl.net_pandl()
        stop_hit = daily_loss < daily_stop
        if stop_hit:
            print("DAILY STOP LOSS HIT")

        not_too_late = not too_late_to_open_new_orders
        stop_not_hit = not stop_hit

        return not_too_late and stop_not_hit

    def too_late_to_open_new_orders(self):
        current_horizon_in_hours = self.strategy_parameters.horizon_seconds / 3600.0
        try:
            too_late_to_open_new_orders = (
                self.data_broker.less_than_N_hours_of_trading_left_for_contract(
                    self.futures_contract,
                    N_hours=current_horizon_in_hours * 3,  ## to be on safe side
                )
            )
        except marketClosed:
            too_late_to_open_new_orders = True

        return too_late_to_open_new_orders

    ## STORE FILLS AND ORDERS
    def add_fill_and_order(self, fill_and_order: FillAndOrder):
        fills_and_orders = self.complete_fills_and_orders
        fills_and_orders.append(fill_and_order)
        self.complete_fills_and_orders = fills_and_orders

    @property
    def complete_fills_and_orders(self) -> List[FillAndOrder]:
        fills_and_orders = getattr(self, "_Fills_and_orders", [])
        return fills_and_orders

    @complete_fills_and_orders.setter
    def complete_fills_and_orders(self, fills_and_orders: List[FillAndOrder]):
        self._Fills_and_orders = fills_and_orders

    ## STORE STATE
    def update_state_and_list_of_states(self, new_state: State):
        print("Update state to %s" % new_state)

        list_of_states = self.list_of_states
        list_of_states.append((new_state, datetime.datetime.now()))
        self.list_of_states = list_of_states
        print("Now %d states stored" % len(self.list_of_states))
        self.state = new_state

    @property
    def list_of_states(self) -> List[Tuple[State, datetime.datetime]]:
        list_of_states = getattr(self, "_list_of_state", [])

        return list_of_states

    @list_of_states.setter
    def list_of_states(self, list_of_states: List[Tuple[State, datetime.datetime]]):
        self._list_of_state = list_of_states

    @property
    def state(self) -> State:
        state = getattr(self, "_state")

        return state

    @state.setter
    def state(self, state: State):
        self._state = state

    ## PARAMETERS
    @property
    def strategy_parameters(self):
        parameters = getattr(self, "_parameters", None)
        if parameters is None:
            self._parameters = parameters = self._get_parameters()

        return parameters

    @strategy_parameters.setter
    def strategy_parameters(self, strategy_parameters: StratParameters):
        self._parameters = strategy_parameters

    def _get_parameters(self) -> StratParameters:
        instrument = self.instrument
        commission_ccy = self.diag_instruments.get_cost_object(
            instrument
        ).value_of_block_commission
        multiplier = self.diag_instruments.get_point_size(instrument)
        tick_size = self.data_broker.get_min_tick_size_for_contract(
            self.futures_contract
        )
        slippage_ccy = self.diag_instruments.get_spread_cost(instrument)
        slippage_ticks = slippage_ccy / tick_size
        ccy = self.diag_instruments.get_currency(instrument)
        fx = self.data_currency.get_last_fx_rate_to_base(ccy)

        return StratParameters(
            fx=fx,
            cost_ccy_C=commission_ccy,
            tick_size=tick_size,
            cancel_cost_ccy_C=commission_ccy,
            multiplier_M=multiplier,
            slippage_ticks=slippage_ticks,
        )

    ## CONTRACT
    @property
    def futures_contract_with_actual_expiry(self) -> futuresContract:
        contract = getattr(self, "_contract_actual_expiry", None)
        if contract is None:
            contract = self._contract_actual_expiry = (
                self.get_futures_contract_with_actual_expiry()
            )

        return contract

    def get_futures_contract_with_actual_expiry(self):
        futures_contract = self.futures_contract

        expiry = self.data_contracts.get_actual_expiry(
            futures_contract.instrument_code, futures_contract.contract_date
        ).as_str()

        return futuresContract(futures_contract.instrument_code, expiry)

    @property
    def futures_contract(self) -> futuresContract:
        contract = getattr(self, "_contract", None)
        if contract is None:
            contract = self._contract = self.get_futures_contract()

        return contract

    def get_futures_contract(self) -> futuresContract:
        data_contracts = self.data_contracts

        priced_contract_date = data_contracts.get_priced_contract_id(self.instrument)

        return futuresContract(
            instrument_object=self.instrument, contract_date_object=priced_contract_date
        )

    @property
    def instrument(self):
        return self._instrument_code

    def set_instrument(self, instrument_code):
        self._instrument_code = instrument_code

    ## SUB COMPONENTS

    @property
    def broker_controller(self) -> BrokerController:
        return self._broker_controller

    @property
    def diag_instruments(self):
        return diagInstruments(self.data)

    @property
    def data_currency(self):
        return dataCurrency(self.data)

    @property
    def data_broker(self):
        return dataBroker(self.data)

    @property
    def data_contracts(self):
        return dataContracts(self.data)

    @property
    def data_prices(self):
        return diagPrices(self.data)


def pre_start_checks_okay_to_start(custom_mr: MRRunner):
    strategy_parameters = custom_mr.strategy_parameters
    strategy_parameters = init_paramaters(strategy_parameters)
    not_ready = True
    print(
        "Pre start check up:  %s %s with %s"
        % (
            str(custom_mr.data.mongo_db),
            str(custom_mr.data_broker.get_broker_name()),
            custom_mr.futures_contract,
        )
    )
    final_price = get_final_price(
        custom_mr.data_prices, futures_contract=custom_mr.futures_contract
    )
    while not_ready:
        starting_R = estimate_R_from_prices(
            custom_mr.data_prices,
            horizon=strategy_parameters.horizon_seconds,
            futures_contract=custom_mr.futures_contract,
        )
        display_diags(
            parameters=strategy_parameters, starting_R=starting_R, price=final_price
        )
        the_input = input(
            "Go with these parameters (y/Y/yes/Yes/YES), input different ones (n/N/no/No/NO), or abort and exit (other)"
        )

        if len(the_input) == 0:
            return False

        the_input = the_input.lower()[0]
        if the_input == "y":
            custom_mr.strategy_parameters = strategy_parameters
            return True
        elif the_input == "n":
            strategy_parameters = interactively_modify_parameters(strategy_parameters)
            custom_mr.strategy_parameters = strategy_parameters
        else:
            return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise Exception("Need to pass instrument code")
    instrument = sys.argv[1]
    custom = MRRunner(instrument=instrument)
    custom.start()
