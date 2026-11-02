## uncomment if using in interactive mode
# import matplotlib
# matplotlib.use("TkAgg")
from matplotlib.pyplot import show
import pandas as pd
from syscore.interactive.input import (
    true_if_answer_is_yes,
    get_input_from_user_and_convert_to_type,
)
from sysdata.data_blob import dataBlob
from sysinit.futures.rollcalendars_from_db_prices_to_csv import (
    build_and_write_roll_calendar,
)
from sysinit.futures.multipleprices_from_db_prices_and_csv_calendars_to_db import (
    process_multiple_prices_single_instrument,
)
from sysinit.futures.adjustedprices_from_db_multiple_to_db import (
    process_adjusted_prices_single_instrument,
)
from sysobjects.rolls import rollParameters
from sysproduction.data.prices import (
    get_valid_instrument_code_from_user,
    INSTRUMENT_CODE_SOURCE_CONFIG,
    diagPrices,
    updatePrices,
)
from sysproduction.data.contracts import dataContracts


def safely_modify_roll_parameters(data: dataBlob):
    print("Strongly suggest you backup and/or do this on a test machine first")
    print("Enter instrument code: Must be defined in database config")
    instrument_code = get_valid_instrument_code_from_user(
        data, source=INSTRUMENT_CODE_SOURCE_CONFIG
    )
    new_roll_parameters = modified_roll_parameters(
        data, instrument_code=instrument_code
    )

    output_path_for_temp_csv_files = input(
        "Path for writing roll calendar and roll parameters; must be absolute with leading "
        "\\ or / eg /home/rob/pysystemtrade/data/futures/roll_calendars_csv/? "
    )
    build_and_write_roll_calendar(
        instrument_code,
        roll_parameters=new_roll_parameters,
        output_datapath=output_path_for_temp_csv_files,
    )

    ans = true_if_answer_is_yes(
        "Inspect roll calendar, and if required manually hack or "
        "change roll parameters. Happy to continue?"
    )
    if not ans:
        print("Doing nothing")
        # return None

    new_multiple_prices = process_multiple_prices_single_instrument(
        instrument_code=instrument_code,
        csv_roll_data_path=output_path_for_temp_csv_files,
        ADD_TO_DB=False,
        ADD_TO_CSV=False,
    )
    new_adjusted_prices = process_adjusted_prices_single_instrument(
        instrument_code,
        multiple_prices=new_multiple_prices,
        ADD_TO_DB=False,
        ADD_TO_CSV=False,
    )

    diag_prices = diagPrices(data)
    existing_multiple_prices = diag_prices.get_multiple_prices(instrument_code)
    existing_adj_prices = diag_prices.get_adjusted_prices(instrument_code)

    do_the_plots = true_if_answer_is_yes(
        "Display diagnostic plots? Answer NO on headless server"
    )

    if do_the_plots:
        prices = pd.concat(
            [new_multiple_prices.PRICE, existing_multiple_prices.PRICE], axis=1
        )
        prices.columns = ["New", "Existing"]

        prices.plot(title="Prices of current contract")

        carry_price = pd.concat(
            [new_multiple_prices.CARRY, existing_multiple_prices.CARRY], axis=1
        )
        carry_price.columns = ["New", "Existing"]
        carry_price.plot(title="Price of carry contract")

        net_carry_existing = carry_price.Existing - prices.Existing
        net_carry_new = carry_price.New - prices.New
        net_carry_compare = pd.concat([net_carry_new, net_carry_existing], axis=1)
        net_carry_compare.columns = ["New", "Existing"]
        net_carry_compare.plot(title="Raw carry difference")

        adj_compare = pd.concat([existing_adj_prices, new_adjusted_prices], axis=1)
        adj_compare.columns = ["Existing", "New"]
        adj_compare.plot(title="Adjusted prices")
        input("Press return to see plots")
        show()

    sure = true_if_answer_is_yes(
        "Happy to continue? Saying YES will overwrite existing data!"
    )
    if not sure:
        print("No changes made")
        # return None

    ## Overwrite roll parameters
    data_csv = dataBlob(
        csv_data_paths=dict(csvFuturesContractData=output_path_for_temp_csv_files)
    )
    data_contracts = dataContracts(data_csv)

    data_contracts.update_roll_parameters(
        instrument_code=instrument_code,
        roll_parameters=new_roll_parameters,
        areyoureallysure=True,
    )
    print(
        "Updated roll parameters. Copy them to /data/futures/csvconfig/rollconfig.csv ***NOW*** (and perhaps reinstall pst)"
    )
    input("Press return when copy and reinstall done")
    ## Overwrite multiple prices
    update_prices = updatePrices(data)
    update_prices.add_multiple_prices(
        instrument_code=instrument_code,
        updated_multiple_prices=new_multiple_prices,
        ignore_duplication=True,
    )
    print("Updated multiple prices in database: copy backup files for .csv")

    ## Overwrite adjusted prices
    update_prices.add_adjusted_prices(
        instrument_code=instrument_code,
        updated_adjusted_prices=new_adjusted_prices,
        ignore_duplication=True,
    )
    print("Updated adjusted prices in database: copy backup files for .csv")

    print("All done!")
    print(
        "Run update_sampled_contracts and interactive_update_roll_status to make sure no issues"
    )


def modified_roll_parameters(data: dataBlob, instrument_code) -> rollParameters:
    print("Existing roll parameters: Must be defined in CSV config")
    data_contracts = dataContracts(data)
    roll_parameters = data_contracts.get_roll_parameters(instrument_code)
    print(str(roll_parameters))
    unhappy = True
    while unhappy:
        hold_rollcycle = get_input_from_user_and_convert_to_type(
            "Hold rollcycle (use FGHJKMNQUVXZ)",
            type_expected=str,
            default_value=str(roll_parameters.hold_rollcycle),
        )
        priced_rollcycle = get_input_from_user_and_convert_to_type(
            "Priced rollcycle (use FGHJKMNQUVXZ)",
            type_expected=str,
            default_value=str(roll_parameters.priced_rollcycle),
        )
        roll_offset_day = get_input_from_user_and_convert_to_type(
            "Roll offset days versus expiry (normally negative)",
            type_expected=int,
            default_value=roll_parameters.roll_offset_day,
        )
        carry_offset = get_input_from_user_and_convert_to_type(
            "Carry offset (ideally -1, 1 if trading front)",
            type_expected=int,
            default_value=roll_parameters.carry_offset,
        )
        approx_expiry_offset = get_input_from_user_and_convert_to_type(
            "Approximate expiry day in month",
            type_expected=int,
            default_value=roll_parameters.approx_expiry_offset,
        )

        try:
            new_roll_parameters = rollParameters(
                hold_rollcycle=hold_rollcycle,
                priced_rollcycle=priced_rollcycle,
                roll_offset_day=roll_offset_day,
                carry_offset=carry_offset,
                approx_expiry_offset=approx_expiry_offset,
            )
        except Exception as e:
            print("Problem parsing parameters %s" % str(e))
            continue

        print("New parameters: %s " % str(new_roll_parameters))
        happy = true_if_answer_is_yes(
            "Happy with these? (Be especially careful if deleting hold contracts which we actually hold)"
        )
        unhappy = not happy

    return new_roll_parameters


if __name__ == "__main__":
    data = dataBlob()
    safely_modify_roll_parameters(data)
