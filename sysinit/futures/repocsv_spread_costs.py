"""
Populate a mongo DB collection with spread costs

"""

from syscore.genutils import new_removing_existing
from syscore.interactive.input import true_if_answer_is_yes
from sysdata.mongodb.mongo_spread_costs import mongoSpreadCostData
from sysdata.csv.csv_spread_costs import csvSpreadCostData
from sysdata.futures.spread_costs import spreadCostData
from sysdata.data_blob import dataBlob


def copy_spread_costs_from_csv_to_mongo(data: dataBlob):
    data_out = mongoSpreadCostData(data.mongo_db)
    data_in = csvSpreadCostData()

    print("Transferring from %s to %s" % (str(data_in), str(data_out)))

    new_instrument_list = data_in.get_list_of_instruments()
    existing_instrument_list = data_out.get_list_of_instruments()

    changes_made = new_removing_existing(
        original_list=existing_instrument_list, new_list=new_instrument_list
    )

    new_instruments = changes_made.new
    deleted_instruments = changes_made.removing
    modified_instruments = changes_made.existing

    process_new_instruments(
        data_in=data_in, data_out=data_out, new_instruments=new_instruments
    )

    process_deleted_instruments(
        data_out=data_out, deleted_instruments=deleted_instruments
    )

    process_modified_instruments(
        data_in=data_in, data_out=data_out, modified_instruments=modified_instruments
    )


def process_new_instruments(
    data_in: spreadCostData, data_out: spreadCostData, new_instruments: list
):
    if len(new_instruments) == 0:
        return None

    print("New instruments %s " % str(new_instruments))
    check_on_add = true_if_answer_is_yes(
        "Check when adding new instruments? (say no if doing in bulk)"
    )

    for instrument_code in new_instruments:
        spread_for_instrument = data_in.get_spread_cost(instrument_code)
        if check_on_add:
            okay_to_add = true_if_answer_is_yes(
                "Add cost of %f for %s to database?"
                % (spread_for_instrument, instrument_code)
            )
            if not okay_to_add:
                continue

        data_out.update_spread_cost(instrument_code, spread_for_instrument)


def process_modified_instruments(
    data_in: spreadCostData, data_out: spreadCostData, modified_instruments: list
):
    actually_modified_instruments = []
    for instrument_code in modified_instruments:
        spread_for_instrument = data_in.get_spread_cost(instrument_code)
        existing_spread = data_out.get_spread_cost(instrument_code)
        if spread_for_instrument == existing_spread:
            # no change don't bother
            continue
        actually_modified_instruments.append(instrument_code)

    if len(actually_modified_instruments) == 0:
        return None

    print(
        "Existing instruments which may be updated %s"
        % str(actually_modified_instruments)
    )
    check_on_modify = true_if_answer_is_yes(
        "Check when modifying instruments? (probably should be yes except for bulk modify)"
    )

    for instrument_code in actually_modified_instruments:
        new_spread = data_in.get_spread_cost(instrument_code)
        existing_spread = data_out.get_spread_cost(instrument_code)

        if check_on_modify:
            okay_to_modify = true_if_answer_is_yes(
                "%s: Okay to replace %f with %f"
                % (instrument_code, existing_spread, new_spread)
            )
            if not okay_to_modify:
                continue

        data_out.update_spread_cost(instrument_code, new_spread)


def process_deleted_instruments(data_out: spreadCostData, deleted_instruments: list):
    if len(deleted_instruments) == 0:
        return None

    print("Deleted instruments which will be removed %s" % str(deleted_instruments))
    check_on_delete = true_if_answer_is_yes("Check when deleting instruments?")

    for instrument_code in deleted_instruments:
        if check_on_delete:
            okay_to_delete = true_if_answer_is_yes(
                "Okay to delete %s?" % instrument_code
            )
            if not okay_to_delete:
                continue

        data_out.delete_spread_cost(instrument_code)


if __name__ == "__main__":
    print("Transfer instrument config from csv to mongo DB")
    # modify flags as required
    copy_spread_costs_from_csv_to_mongo(dataBlob())
