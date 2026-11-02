"""
Roll adjusted and multiple prices for a given contract, after checking that we do not have positions

NOTE: this does not update the roll calendar .csv files stored elsewhere. Under DRY the sole source of production
  roll info is the multiple prices series
"""

from dataclasses import dataclass
import numpy as np

from syscore.interactive.input import (
    get_input_from_user_and_convert_to_type,
    true_if_answer_is_yes,
)
from syscore.interactive.menus import print_menu_of_values_and_get_response
from syscore.constants import named_object, status, success, failure
from syscore.interactive.display import (
    print_with_landing_strips_around,
    landing_strip,
)

from sysdata.data_blob import dataBlob


from sysobjects.contracts import futuresContract
from sysobjects.production.roll_state import (
    default_state,
    roll_adj_state,
    explain_roll_state_str,
    allowable_roll_state_from_current_and_position,
    RollState,
    no_open_state,
    is_double_sided_trade_roll_state,
    list_of_all_roll_states,
)
from sysproduction.reporting.api import reportingApi

from sysproduction.reporting.report_configs import roll_report_config
from sysproduction.reporting.reporting_functions import run_report_with_data_blob
from sysproduction.reporting.data.rolls import volume_contracts_in_forward_contract

from sysproduction.data.positions import diagPositions, updatePositions
from sysproduction.data.controls import updateOverrides, dataTradeLimits
from sysproduction.data.contracts import dataContracts
from sysproduction.data.prices import diagPrices, get_valid_instrument_code_from_user

from sysproduction.reporting.data.rolls import (
    rollingAdjustedAndMultiplePrices,
    relative_volume_in_forward_contract_versus_price,
)


no_change_required = named_object("No roll required")
EXIT_CODE = "EXIT"


def interactive_update_roll_status():
    with dataBlob(log_name="Interactive_Update-Roll-Status") as data:
        api = reportingApi(data)
        function_to_call = get_rolling_master_function()
        function_to_call(api=api, data=data)


def get_rolling_master_function():
    MANUAL_INPUT = "Manually input instrument codes and manually decide when to roll"
    MENU_OPTIONS = [
        MANUAL_INPUT,
        "Cycle through instrument codes automatically, but manually decide when to roll",
        "Cycle through instrument codes automatically, auto decide when to roll, manually confirm rolls",
        "Cycle through instrument codes automatically, auto decide when to roll, automatically roll",
    ]

    function_list = [
        update_roll_status_manual_cycle,
        update_roll_status_auto_cycle_manual_decide,
        update_roll_status_auto_cycle_manual_confirm,
        update_roll_status_full_auto,
    ]

    print("How do you want to do your rolls today?")
    selection = print_menu_of_values_and_get_response(
        MENU_OPTIONS, default_str=MANUAL_INPUT
    )
    selection_idx = MENU_OPTIONS.index(selection)

    function_to_call = function_list[selection_idx]

    return function_to_call


@dataclass
class RollDataWithStateReporting(object):
    instrument_code: str
    original_roll_status: RollState
    position_priced_contract: int
    allowable_roll_states_as_list_of_str: list
    days_until_roll: int
    relative_volume: float
    absolute_forward_volume: int
    days_until_expiry: int

    @property
    def original_roll_status_as_string(self):
        return self.original_roll_status.name

    def display_roll_query_banner(self):
        print(landing_strip(80))
        print("Current State: %s" % self.original_roll_status)
        print(
            "Current position in priced contract %d (if zero can Roll Adjusted prices)"
            % self.position_priced_contract
        )
        print("")
        print("These are your options:")
        print("")

        for state_number, state in enumerate(self.allowable_roll_states_as_list_of_str):
            print("%s: %s" % (state, explain_roll_state_str(state)))

        print("")


def update_roll_status_manual_cycle(api: reportingApi, data: dataBlob):
    auto_parameters = get_auto_roll_parameters_potentially_using_default(
        data=data, use_default=True
    )
    do_another = True
    while do_another:
        instrument_code = get_valid_instrument_code_from_user(
            data=api.data, allow_exit=True, exit_code=EXIT_CODE
        )
        if instrument_code is EXIT_CODE:
            # belt and braces
            do_another = False
        else:
            roll_data = setup_roll_data_with_state_reporting(api.data, instrument_code)
            manually_report_and_update_roll_state_for_code(
                api=api,
                instrument_code=instrument_code,
                auto_parameters=auto_parameters,
                roll_data=roll_data,
            )

    return success


def update_roll_status_auto_cycle_manual_decide(api: reportingApi, data: dataBlob):
    days_ahead = get_days_ahead_to_consider_when_auto_cycling()
    instrument_list = get_list_of_instruments_to_auto_cycle(
        api.data, days_ahead=days_ahead
    )
    auto_parameters = get_auto_roll_parameters_potentially_using_default(
        data=data, use_default=True
    )
    for instrument_code in instrument_list:
        roll_data = setup_roll_data_with_state_reporting(api.data, instrument_code)
        manually_report_and_update_roll_state_for_code(
            api=api,
            instrument_code=instrument_code,
            auto_parameters=auto_parameters,
            roll_data=roll_data,
        )

    return success


def update_roll_status_auto_cycle_manual_confirm(api: reportingApi, data: dataBlob):
    days_ahead = get_days_ahead_to_consider_when_auto_cycling()
    auto_parameters = get_auto_roll_parameters(data)
    instrument_list = get_list_of_instruments_to_auto_cycle(
        api.data, days_ahead=days_ahead
    )

    for instrument_code in instrument_list:
        roll_data = setup_roll_data_with_state_reporting(api.data, instrument_code)
        roll_state_required = auto_selected_roll_state_instrument(
            api=api, roll_data=roll_data, auto_parameters=auto_parameters
        )

        if roll_state_required is no_change_required:
            warn_not_rolling(instrument_code, auto_parameters)
        else:
            modify_roll_state(
                data=api.data,
                instrument_code=instrument_code,
                original_roll_state=roll_data.original_roll_status,
                roll_state_required=roll_state_required,
                confirm_adjusted_price_change=True,
            )


def update_roll_status_full_auto(api: reportingApi, data: dataBlob):
    days_ahead = get_days_ahead_to_consider_when_auto_cycling()
    instrument_list = get_list_of_instruments_to_auto_cycle(
        api.data, days_ahead=days_ahead
    )
    auto_parameters = get_auto_roll_parameters(data)

    for instrument_code in instrument_list:
        roll_data = setup_roll_data_with_state_reporting(api.data, instrument_code)
        roll_state_required = auto_selected_roll_state_instrument(
            api=api, roll_data=roll_data, auto_parameters=auto_parameters
        )

        if roll_state_required is no_change_required:
            warn_not_rolling(instrument_code, auto_parameters)
        else:
            modify_roll_state(
                data=api.data,
                instrument_code=instrument_code,
                original_roll_state=roll_data.original_roll_status,
                roll_state_required=roll_state_required,
                confirm_adjusted_price_change=False,
            )


def get_days_ahead_to_consider_when_auto_cycling() -> int:
    days_ahead = get_input_from_user_and_convert_to_type(
        "How many days ahead should I look for expiries?",
        type_expected=int,
        allow_default=True,
        default_value=10,
    )

    return days_ahead


def get_list_of_instruments_to_auto_cycle(data: dataBlob, days_ahead: int = 10) -> list:
    diag_prices = diagPrices()
    list_of_potential_instruments = (
        diag_prices.get_list_of_instruments_in_multiple_prices()
    )
    instrument_list = [
        instrument_code
        for instrument_code in list_of_potential_instruments
        if include_instrument_in_auto_cycle(
            data=data, instrument_code=instrument_code, days_ahead=days_ahead
        )
    ]

    print_with_landing_strips_around(
        "Identified following instruments that are near expiry %s"
        % str(instrument_list)
    )

    return instrument_list


def include_instrument_in_auto_cycle(
    data: dataBlob, instrument_code: str, days_ahead: int = 10
) -> bool:
    days_until_expiry = days_until_earliest_expiry(data, instrument_code)
    return days_until_expiry <= days_ahead


def days_until_earliest_expiry(data: dataBlob, instrument_code: str) -> int:
    data_contracts = dataContracts(data)
    carry_days = data_contracts.days_until_carry_expiry(instrument_code)
    roll_days = data_contracts.days_until_roll(instrument_code)
    price_days = data_contracts.days_until_price_expiry(instrument_code)

    return min([carry_days, roll_days, price_days])


@dataclass
class autoRollParameters:
    auto_roll_if_relative_volume_higher_than: float
    min_relative_volume: float
    min_absolute_volume: float
    near_expiry_days: int
    default_roll_state_if_undecided: RollState
    auto_roll_expired: bool


ASK_FOR_STATE = "Ask"


def get_auto_roll_parameters(data: dataBlob) -> autoRollParameters:
    default_parameters = default_auto_roll_parameters(data)
    print("Auto roll parameters: %s" % str(default_parameters))
    use_default = true_if_answer_is_yes("Use default parameters? [no to change]")
    auto_parameters = get_auto_roll_parameters_potentially_using_default(
        data=data, use_default=use_default
    )
    describe_roll_rules_from_parameters(auto_parameters)
    input("Press return to continue (or CTRL-C to abort)")

    return auto_parameters


def get_auto_roll_parameters_potentially_using_default(
    data: dataBlob, use_default: bool = False
) -> autoRollParameters:
    default_parameters = default_auto_roll_parameters(data)

    auto_roll_if_relative_volume_higher_than = default_parameters[
        "auto_roll_if_relative_volume_higher_than"
    ]
    min_relative_volume = default_parameters["min_relative_volume"]
    min_absolute_volume = default_parameters["min_absolute_volume"]
    near_expiry_days = default_parameters["near_expiry_days"]
    default_roll_state_if_undecided = default_parameters[
        "default_roll_state_if_undecided"
    ]
    auto_roll_expired = default_parameters["auto_roll_expired"]

    if use_default:
        pass
    else:
        auto_roll_if_relative_volume_higher_than = get_input_from_user_and_convert_to_type(
            "Minimum relative volume (forward volume/priced volume) before rolling automatically, regardless of contract volume",
            type_expected=float,
            allow_default=True,
            default_value=auto_roll_if_relative_volume_higher_than,
        )

        min_relative_volume = get_input_from_user_and_convert_to_type(
            "Relative volume threshold (forward volume/priced volume) before rolling if contract volume threshold also met",
            type_expected=float,
            allow_default=True,
            default_value=min_relative_volume,
        )

        min_absolute_volume = get_input_from_user_and_convert_to_type(
            "Minimum absolute volume in contracts for forward contract before rolling automatically, if relative volume threshold met",
            type_expected=float,
            allow_default=True,
            default_value=min_absolute_volume,
        )

        near_expiry_days = get_input_from_user_and_convert_to_type(
            "Days before desired roll date when we switch to NO_OPEN instead of NO_ROLL (if forward not liquid), or switch to using the roll status specified next instead of PASSIVE (if forward is liquid)",
            type_expected=int,
            allow_default=True,
            default_value=near_expiry_days,
        )

        default_roll_state_if_undecided = get_input_from_user_and_convert_to_type(
            "Roll state if we are undecided; has to be one of %s (recommend Force, Force_Outright or Close), or %s when we prompt for state on each instrument)"
            % (str(list_of_all_roll_states), ASK_FOR_STATE),
            type_expected=str,
            allow_default=True,
            default_value=ASK_FOR_STATE,
        )

        auto_roll_expired = true_if_answer_is_yes(
            "Automatically roll adjusted prices when a priced contract has expired and no position?"
        )

    auto_parameters = autoRollParameters(
        min_absolute_volume=min_absolute_volume,
        min_relative_volume=min_relative_volume,
        default_roll_state_if_undecided=default_roll_state_if_undecided,
        auto_roll_if_relative_volume_higher_than=auto_roll_if_relative_volume_higher_than,
        near_expiry_days=near_expiry_days,
        auto_roll_expired=auto_roll_expired,
    )

    return auto_parameters


def default_auto_roll_parameters(data: dataBlob) -> dict:
    try:
        default_parameters = data.config.roll_status_auto_update
    except:
        raise Exception(
            "defaults.yaml or private_config.yaml should contain element 'roll_status_auto_update'"
        )

    return default_parameters


def describe_roll_rules_from_parameters(auto_parameters: autoRollParameters):
    print(
        "AUTO ROLL RULES:\n\n"
        + "%s\n\n" % describe_action_for_auto_roll_expired(auto_parameters)
        + "The test for forward being liquid:\n"
        + "  - if relative volume between current and forward contract > %f, then considered liquid (and no need to check absolute volume)\n"
        % (auto_parameters.auto_roll_if_relative_volume_higher_than)
        + "  - if relative volume between current and forward contract > %f, and if absolute volume contracts>%d, then considered liquid\n\n"
        % (auto_parameters.min_relative_volume, auto_parameters.min_absolute_volume)
        + "Forward is not liquid. Are we close to the roll point? (is distance to desired roll date<%d days)\n"
        % (auto_parameters.near_expiry_days)
        + "   -  No, miles away from needing to roll. Trade as normal: NO_ROLL\n"
        + "   -  Yes, going to roll quite soon. Roll status should be NO_OPEN\n\n "
        + "Forward is liquid. Do we have a position on in the price contract??\n"
        + "   - We have no position in the priced contract: ROLL ADJUSTED\n"
        + "   - If we have a position on then:\n"
        + "      - Do we have plenty of time? (is distance to desired roll date>%d days)?\n"
        % auto_parameters.near_expiry_days
        + "         - Yes, We have plenty of time PASSIVE ROLL\n"
        + "         - No, we don't. %s\n"
        % describe_action_for_default_roll_state_if_undecided(auto_parameters)
    )


def describe_action_for_default_roll_state_if_undecided(
    auto_parameters: autoRollParameters,
) -> str:
    if auto_parameters.default_roll_state_if_undecided == ASK_FOR_STATE:
        return "We will prompt user for required roll state"
    else:
        return "Roll state will be set to %s automatically" % str(
            auto_parameters.default_roll_state_if_undecided
        )


def describe_action_for_auto_roll_expired(
    auto_parameters: autoRollParameters,
) -> str:
    if auto_parameters.auto_roll_expired:
        return "Irrespective of the following, we will automatically roll if a contract has expired and no position"
    else:
        return ""


def auto_selected_roll_state_instrument(
    api: reportingApi,
    roll_data: RollDataWithStateReporting,
    auto_parameters: autoRollParameters,
) -> RollState:
    run_roll_report(api, roll_data.instrument_code)
    roll_state_required = suggest_roll_state_for_instrument(
        roll_data=roll_data, auto_parameters=auto_parameters
    )
    if roll_state_required == ASK_FOR_STATE:
        print("Have to input roll state (recommend Force, Force_Outright or Close)")
        roll_state_required = get_roll_state_required(roll_data)

    original_roll_status = roll_data.original_roll_status
    if original_roll_status == roll_state_required:
        print_with_landing_strips_around(
            "Roll status already set to %s for %s: not changing"
            % (original_roll_status, roll_data.instrument_code)
        )
        return no_change_required

    print_with_landing_strips_around(
        "Automatically changing state from %s to %s for %s"
        % (original_roll_status, roll_state_required, roll_data.instrument_code)
    )

    return roll_state_required


def suggest_roll_state_for_instrument(
    roll_data: RollDataWithStateReporting,
    auto_parameters: autoRollParameters,
) -> RollState:
    forward_liquid = check_if_forward_liquid(
        roll_data=roll_data, auto_parameters=auto_parameters
    )
    getting_close_to_desired_roll_date = check_if_getting_close_to_desired_roll_date(
        roll_data=roll_data, auto_parameters=auto_parameters
    )
    no_position_held = roll_data.position_priced_contract == 0
    expired_and_auto_rolling_expired = check_if_expired_and_auto_rolling_expired(
        roll_data=roll_data, auto_parameters=auto_parameters
    )

    if expired_and_auto_rolling_expired and no_position_held:
        ## contract expired so roll regardless of liquidity
        return RollState.Roll_Adjusted

    if forward_liquid:
        if no_position_held:
            ## liquid forward, with no position
            return RollState.Roll_Adjusted
        else:
            ## liquid forward, with position held
            if getting_close_to_desired_roll_date:
                ## liquid forward, with position, close to expiry
                ##   Up to the user to decide
                return auto_parameters.default_roll_state_if_undecided
            else:
                ## liquid forward, with position held, not close to expiring
                return RollState.Passive
    else:
        # forward illiquid
        if getting_close_to_desired_roll_date:
            ## forward illiquid and getting close
            # We don't want to trade the forward - it's not liquid yet.
            # And we don't want to open a position or increase it in the current
            #   priced contract, since we will only have to close it again soon.
            # But we do want to allow ourselves to close any position
            #   we have in the current priced contract.
            return RollState.No_Open
        else:
            ## forward illiquid and miles away. Don't roll yet.
            return RollState.No_Roll


def check_if_forward_liquid(
    roll_data: RollDataWithStateReporting,
    auto_parameters: autoRollParameters,
) -> bool:
    very_high_forward_volume = (
        roll_data.relative_volume
        > auto_parameters.auto_roll_if_relative_volume_higher_than
    )
    relative_threshold_met = (
        roll_data.relative_volume > auto_parameters.min_relative_volume
    )
    absolute_threshold_met = (
        roll_data.absolute_forward_volume > auto_parameters.min_absolute_volume
    )

    if very_high_forward_volume:
        return True

    if relative_threshold_met and absolute_threshold_met:
        return True

    return False


def check_if_getting_close_to_desired_roll_date(
    roll_data: RollDataWithStateReporting,
    auto_parameters: autoRollParameters,
):
    ## close to desired roll date, not technically 'expiry'
    return roll_data.days_until_roll < auto_parameters.near_expiry_days


def check_if_expired_and_auto_rolling_expired(
    roll_data: RollDataWithStateReporting, auto_parameters: autoRollParameters
) -> bool:
    expired = roll_data.days_until_expiry <= 0
    auto_rolling_expired = auto_parameters.auto_roll_expired

    return expired and auto_rolling_expired


def warn_not_rolling(instrument_code: str, auto_parameters: autoRollParameters):
    print_with_landing_strips_around(
        "\nNo change to rolling status for %s given parameters %s\n"
        % (instrument_code, str(auto_parameters))
    )


def manually_report_and_update_roll_state_for_code(
    api: reportingApi,
    instrument_code: str,
    auto_parameters: autoRollParameters,
    roll_data: RollDataWithStateReporting,
):
    run_roll_report(api, instrument_code)
    manually_update_roll_state_for_code(
        data=api.data,
        instrument_code=instrument_code,
        auto_parameters=auto_parameters,
        roll_data=roll_data,
    )


def manually_update_roll_state_for_code(
    data: dataBlob,
    instrument_code: str,
    auto_parameters: autoRollParameters,
    roll_data: RollDataWithStateReporting,
):
    # First get the roll info
    # This will also update to console

    roll_state_suggested = suggest_roll_state_for_instrument(
        roll_data=roll_data, auto_parameters=auto_parameters
    )
    if roll_state_suggested == ASK_FOR_STATE:
        print(
            "No specific state suggested: recommend one of Force, "
            "Force_Outright or Close"
        )
        default_state = roll_data.original_roll_status.name
    else:
        roll_state_suggested_str = roll_state_suggested.name
        print(
            "Suggested roll state based on roll parameters in config: %s"
            % roll_state_suggested_str
        )
        default_state = roll_state_suggested_str

    roll_state_required = get_roll_state_required(
        roll_data, default_state=default_state
    )

    modify_roll_state(
        data=data,
        instrument_code=instrument_code,
        original_roll_state=roll_data.original_roll_status,
        roll_state_required=roll_state_required,
        confirm_adjusted_price_change=True,
    )

    return success


def run_roll_report(api: reportingApi, instrument_code: str):
    config = roll_report_config.new_config_with_modified_output("console")
    config.modify_kwargs(instrument_code=instrument_code, reporting_api=api)
    report_results = run_report_with_data_blob(config, api.data)
    if report_results is failure:
        raise Exception("Can't run roll report, so can't change status")


def get_roll_state_required(
    roll_data: RollDataWithStateReporting, default_state: str = "No_Roll"
) -> RollState:
    invalid_input = True
    while invalid_input:
        roll_state_required_as_str = print_menu_of_values_and_get_response(
            roll_data.allowable_roll_states_as_list_of_str, default_str=default_state
        )

        if roll_state_required_as_str != roll_data.original_roll_status_as_string:
            # check if changing
            print("")
            okay_to_change = true_if_answer_is_yes(
                "Changing roll state for %s from %s to %s, are you sure y/n to try again/<RETURN> to exit: "
                % (
                    roll_data.instrument_code,
                    roll_data.original_roll_status_as_string,
                    roll_state_required_as_str,
                ),
                allow_empty_to_return_none=True,
            )
            print("")
            if okay_to_change is None:
                return roll_data.original_roll_status

            if okay_to_change:
                # happy
                return RollState[roll_state_required_as_str]
            else:
                print("OK. Choose again.")
                # back to top of loop
                continue
        else:
            print("No change")
            return roll_data.original_roll_status
    return None


def setup_roll_data_with_state_reporting(
    data: dataBlob, instrument_code: str
) -> RollDataWithStateReporting:
    diag_positions = diagPositions(data)
    diag_contracts = dataContracts(data)

    original_roll_status = diag_positions.get_roll_state(instrument_code)
    priced_contract_date = diag_contracts.get_priced_contract_id(instrument_code)

    contract = futuresContract(instrument_code, priced_contract_date)

    position_priced_contract = int(diag_positions.get_position_for_contract(contract))

    allowable_roll_states = allowable_roll_state_from_current_and_position(
        original_roll_status, position_priced_contract
    )

    days_until_roll = diag_contracts.days_until_roll(instrument_code)
    days_until_expiry = diag_contracts.days_until_price_expiry(instrument_code)

    relative_volume = relative_volume_in_forward_contract_versus_price(
        data=data, instrument_code=instrument_code
    )
    absolute_forward_volume = int(
        volume_contracts_in_forward_contract(data=data, instrument_code=instrument_code)
    )
    if np.isnan(relative_volume):
        relative_volume = 0.0
    if np.isnan(absolute_forward_volume):
        absolute_forward_volume = 0

    roll_data_with_state = RollDataWithStateReporting(
        instrument_code=instrument_code,
        original_roll_status=original_roll_status,
        position_priced_contract=position_priced_contract,
        allowable_roll_states_as_list_of_str=allowable_roll_states,
        days_until_roll=days_until_roll,
        relative_volume=relative_volume,
        absolute_forward_volume=absolute_forward_volume,
        days_until_expiry=days_until_expiry,
    )

    return roll_data_with_state


def modify_roll_state(
    data: dataBlob,
    instrument_code: str,
    original_roll_state: RollState,
    roll_state_required: RollState,
    confirm_adjusted_price_change: bool = True,
):
    if roll_state_required == original_roll_state:
        return

    if original_roll_state is no_open_state:
        roll_state_was_no_open_now_something_else(data, instrument_code)

    update_positions = updatePositions(data)
    update_positions.set_roll_state(instrument_code, roll_state_required)

    if roll_state_required is no_open_state:
        roll_state_is_now_no_open(data, instrument_code)

    if roll_state_required is roll_adj_state:
        state_change_to_roll_adjusted_prices(
            data=data,
            instrument_code=instrument_code,
            original_roll_state=original_roll_state,
            confirm_adjusted_price_change=confirm_adjusted_price_change,
        )

    ## Following roll states require trading: force, forceoutright, close
    check_trading_limits_for_roll_state(
        data=data,
        roll_state_required=roll_state_required,
        instrument_code=instrument_code,
    )


def roll_state_was_no_open_now_something_else(data: dataBlob, instrument_code: str):
    print(
        "Roll state is no longer no open, so removing temporary reduce only constraint"
    )
    update_overrides = updateOverrides(data)
    update_overrides.remove_temporary_override_for_instrument(instrument_code)


def roll_state_is_now_no_open(data: dataBlob, instrument_code: str):
    print("Roll state is no open, so adding temporary reduce only constraint")
    update_overrides = updateOverrides(data)
    update_overrides.add_temporary_reduce_only_for_instrument(instrument_code)


def state_change_to_roll_adjusted_prices(
    data: dataBlob,
    instrument_code: str,
    original_roll_state: RollState,
    confirm_adjusted_price_change: bool = True,
):
    # Going to roll adjusted prices
    update_positions = updatePositions(data)

    roll_result = roll_adjusted_and_multiple_prices(
        data=data,
        instrument_code=instrument_code,
        confirm_adjusted_price_change=confirm_adjusted_price_change,
    )

    if roll_result is success:
        # Return the state back to default (no roll) state
        data.log.debug(
            "Successful roll! Returning roll state of %s to %s"
            % (instrument_code, default_state)
        )

        update_positions.set_roll_state(instrument_code, default_state)
    else:
        data.log.debug(
            "Something has gone wrong with rolling adjusted of %s! Returning roll state to previous state of %s"
            % (instrument_code, original_roll_state)
        )
        update_positions.set_roll_state(instrument_code, original_roll_state)


def roll_adjusted_and_multiple_prices(
    data: dataBlob, instrument_code: str, confirm_adjusted_price_change: bool = True
) -> status:
    """
    Roll multiple and adjusted prices

    THE POSITION MUST BE ZERO IN THE PRICED CONTRACT! WE DON'T CHECK THIS HERE

    :param data: dataBlob
    :param instrument_code: str
    :return:
    """
    print(landing_strip(80))
    print("")
    print("Rolling adjusted prices!")
    print("")
    rolling_adj_and_mult_object = get_roll_adjusted_multiple_prices_object(
        data=data, instrument_code=instrument_code
    )
    if rolling_adj_and_mult_object is failure:
        print("Error when trying to calculate roll prices")
        return failure

    ## prints to screen
    rolling_adj_and_mult_object.compare_old_and_new_prices()

    if confirm_adjusted_price_change:
        is_okay_to_roll = true_if_answer_is_yes(
            "Confirm roll adjusted prices for %s are you sure y/n:" % instrument_code
        )
        if not is_okay_to_roll:
            print(
                "\nUSER DID NOT WANT TO ROLL: Setting roll status back to previous state"
            )
            return failure
    else:
        print_with_landing_strips_around("AUTO ROLLING - NO USER CONFIRMATION REQUIRED")

    try:
        rolling_adj_and_mult_object.write_new_rolled_data()
    except Exception as e:
        data.log.warning(
            "%s went wrong when rolling: Going to roll-back to original multiple/adjusted prices"
            % e
        )
        rolling_adj_and_mult_object.rollback()
        return failure

    return success


def get_roll_adjusted_multiple_prices_object(
    data: dataBlob,
    instrument_code: str,
) -> rollingAdjustedAndMultiplePrices:
    ## returns failure if goes wrong
    try:
        rolling_adj_and_mult_object = rollingAdjustedAndMultiplePrices(
            data, instrument_code
        )
        ## We do this as getting the object doesn't guarantee it works
        _unused_ = rolling_adj_and_mult_object.updated_multiple_prices
        _unused_ = rolling_adj_and_mult_object.new_adjusted_prices

    except Exception as e:
        print("Error %s when trying to calculate roll prices" % str(e))
        ## Possibly forward fill
        rolling_adj_and_mult_object = (
            _get_roll_adjusted_multiple_prices_object_ffill_option(
                data, instrument_code
            )
        )

    return rolling_adj_and_mult_object


def _get_roll_adjusted_multiple_prices_object_ffill_option(
    data: dataBlob, instrument_code: str
) -> rollingAdjustedAndMultiplePrices:
    ## returns failure if goes wrong
    try_forward_fill = true_if_answer_is_yes(
        "Do you want to try forward filling prices first (less accurate, but guarantees roll)? [y/n]"
    )

    if not try_forward_fill:
        print("OK, nothing I can do")
        return failure

    try:
        rolling_adj_and_mult_object = rollingAdjustedAndMultiplePrices(
            data, instrument_code, allow_forward_fill=True
        )
        ## We do this as getting the object doesn't guarantee it works
        _unused_ = rolling_adj_and_mult_object.updated_multiple_prices

    except Exception as e:
        print(
            "Error %s when trying to calculate roll prices, even when forward filling"
            % str(e)
        )
        return failure

    return rolling_adj_and_mult_object


def check_trading_limits_for_roll_state(
    data: dataBlob, roll_state_required: RollState, instrument_code: str
):
    trading_required = roll_state_required in [
        RollState.Force,
        RollState.Force_Outright,
        RollState.Close,
    ]
    if not trading_required:
        return

    abs_trades_required_for_roll = calculate_abs_trades_required_for_roll(
        data=data,
        roll_state_required=roll_state_required,
        instrument_code=instrument_code,
    )
    trades_possible = get_remaining_trades_possible_today_in_contracts_for_instrument(
        data=data,
        instrument_code=instrument_code,
        proposed_trade_qty=abs_trades_required_for_roll,
    )
    if trades_possible < abs_trades_required_for_roll:
        print("**** WARNING ****")
        print(
            "Roll for %s requires %d contracts, but we can only trade %d today"
            % (instrument_code, abs_trades_required_for_roll, trades_possible)
        )
        print(
            "Use interactive controls/trade limits to set higher limit (and don't forget to reset afterwards)"
        )


def calculate_abs_trades_required_for_roll(
    data: dataBlob, roll_state_required: RollState, instrument_code: str
) -> float:
    data_contacts = dataContracts(data)
    diag_positions = diagPositions(data)
    current_priced_contract_id = data_contacts.get_priced_contract_id(
        instrument_code=instrument_code
    )
    position = diag_positions.get_position_for_contract(
        futuresContract(
            instrument_object=instrument_code,
            contract_date_object=current_priced_contract_id,
        )
    )

    if is_double_sided_trade_roll_state(roll_state_required):
        position = position * 2
    abs_position = abs(position)

    return abs_position


def get_remaining_trades_possible_today_in_contracts_for_instrument(
    data: dataBlob, instrument_code: str, proposed_trade_qty
) -> int:
    data_trade_limits = dataTradeLimits(data)
    return data_trade_limits.what_trade_qty_possible_for_instrument_code(
        instrument_code=instrument_code, proposed_trade_qty=proposed_trade_qty
    )


if __name__ == "__main__":
    interactive_update_roll_status()
