"""
Allocate which algo is doing a list of contract orders

Depends on instrument order and type of order

"""

from dataclasses import dataclass, field
from sysexecution.orders.named_order_objects import missing_order
from sysdata.data_blob import dataBlob
from sysexecution.orders.instrument_orders import (
    instrumentOrder,
    zero_roll_order_type,
    balance_order_type,
    best_order_type,
    limit_order_type,
    market_order_type,
)
from sysexecution.orders.contract_orders import contractOrder
from sysexecution.orders.list_of_orders import listOfOrders


def get_list_of_algos(data: dataBlob):
    config = get_algo_allocation_config(data)

    return [config.market_algo, config.default_algo]


def allocate_algo_to_list_of_contract_orders(
    data: dataBlob,
    list_of_contract_orders: listOfOrders,
    instrument_order: instrumentOrder,
) -> listOfOrders:
    """

    :param data: dataBlog
    :param instrument_order: parent instrument order
    :param list_of_contract_orders:
    :return: list of contract orders with algo added
    """
    new_list_of_contract_orders = []
    for contract_order in list_of_contract_orders:
        contract_order = check_and_if_required_allocate_algo_to_single_contract_order(
            data=data,
            contract_order=contract_order,
            instrument_order=instrument_order,
        )
        new_list_of_contract_orders.append(contract_order)

    new_list_of_contract_orders = listOfOrders(new_list_of_contract_orders)

    return new_list_of_contract_orders


@dataclass
class AlgoConfig:
    default_algo: str
    market_algo: str
    limit_order_algo: str
    best_algo: str
    algo_overrides: field(default_factory=dict)


def get_algo_allocation_config(data: dataBlob) -> AlgoConfig:
    config = data.config.get_element("execution_algos")

    return AlgoConfig(
        default_algo=config["default_algo"],
        market_algo=config["market_algo"],
        limit_order_algo=config["limit_order_algo"],
        algo_overrides=config["algo_overrides"],
        best_algo=config["best_algo"],
    )


def check_and_if_required_allocate_algo_to_single_contract_order(
    data: dataBlob,
    contract_order: contractOrder,
    instrument_order: instrumentOrder,
) -> contractOrder:
    config = get_algo_allocation_config(data)
    log_attrs = {**contract_order.log_attributes(), "method": "temp"}

    if already_has_algo_allocated(contract_order):
        # Already done
        return contract_order

    instrument_order_type = instrument_order.order_type

    # not used yet, but maybe in the future
    is_roll_order = instrument_order.roll_order

    if algo_allocation_is_overridden_for_instrument(
        contract_order=contract_order, config=config
    ):
        contract_order = allocate_algo_for_specific_instrument_with_override(
            contract_order=contract_order, config=config
        )
    elif instrument_order_type == market_order_type:
        data.log.debug(
            "Market order type, so allocating to algo_market",
            **log_attrs,
        )
        contract_order = allocate_market_algo(
            contract_order=contract_order, config=config
        )

    elif (
        instrument_order_type == best_order_type
        or instrument_order_type == zero_roll_order_type
    ):
        contract_order = allocate_for_best_execution_no_limit(
            config=config, data=data, contract_order=contract_order
        )

    elif instrument_order_type == limit_order_type:
        contract_order = allocate_for_limit_order(
            data=data, config=config, contract_order=contract_order
        )

    elif instrument_order_type == balance_order_type:
        data.log.critical(
            "Balance orders aren't executed, shouldn't even be here!",
            **log_attrs,
        )
        return missing_order
    else:
        data.log.warning(
            "Don't recognise order type %s so allocating to default %s"
            % (instrument_order_type, config.default_algo),
            **log_attrs,
        )
        contract_order = allocate_default_algo(
            contract_order=contract_order, config=config
        )

    return contract_order


def already_has_algo_allocated(contract_order: contractOrder) -> bool:
    return contract_order.algo_to_use != ""


def algo_allocation_is_overridden_for_instrument(
    contract_order: contractOrder, config: AlgoConfig
) -> bool:
    instrument_code = contract_order.instrument_code
    instruments_with_keys = list(config.algo_overrides.keys())

    return instrument_code in instruments_with_keys


def allocate_algo_for_specific_instrument_with_override(
    config: AlgoConfig, contract_order: contractOrder
) -> contractOrder:
    instrument_code = contract_order.instrument_code
    default_algo = config.default_algo
    algo_to_use = config.algo_overrides.get(instrument_code, default_algo)

    contract_order.algo_to_use = algo_to_use

    return contract_order


def allocate_market_algo(
    contract_order: contractOrder, config: AlgoConfig
) -> contractOrder:
    contract_order.algo_to_use = config.market_algo
    return contract_order


def allocate_for_best_execution_no_limit(
    data: dataBlob, config: AlgoConfig, contract_order: contractOrder
) -> contractOrder:
    # in the future could be randomized...
    data.log.debug(
        "'Best' order so allocating to original_best",
        **contract_order.log_attributes(),
        method="temp",
    )
    contract_order.algo_to_use = config.best_algo

    return contract_order


def allocate_for_limit_order(
    data: dataBlob, config: AlgoConfig, contract_order: contractOrder
) -> contractOrder:
    # in the future could be randomized...
    data.log.debug(
        "Allocating to limit order",
        **contract_order.log_attributes(),
        method="temp",
    )
    contract_order.algo_to_use = config.limit_order_algo

    return contract_order


def allocate_default_algo(
    contract_order: contractOrder, config: AlgoConfig
) -> contractOrder:
    contract_order.algo_to_use = config.default_algo
    return contract_order
