import numpy as np
import pandas as pd
from sysquant.optimisation.weights import portfolioWeights
from syscore.pandas.pdutils import get_index_of_columns_in_df_with_at_least_one_value


def get_must_have_dict_from_data(data: pd.DataFrame) -> dict:
    must_have_list = get_index_of_columns_in_df_with_at_least_one_value(data)
    list_of_asset_names = list(data.columns)
    must_have_dict = dict(
        [
            (asset_name, must_have)
            for asset_name, must_have in zip(list_of_asset_names, must_have_list)
        ]
    )

    return must_have_dict


def clean_weights(
    weights: portfolioWeights, must_haves: dict, fraction: float = 0.5
) -> portfolioWeights:
    (
        asset_names,
        list_of_weights,
        list_of_must_haves,
    ) = get_lists_from_dicts_of_weights_and_must_haves(
        weights=weights, must_haves=must_haves
    )

    cleaned_list_of_weights = clean_list_of_weights(
        weights=list_of_weights, must_haves=list_of_must_haves, fraction=fraction
    )

    cleaned_weights = portfolioWeights.from_weights_and_keys(
        list_of_weights=cleaned_list_of_weights, list_of_keys=asset_names
    )

    return cleaned_weights


def get_lists_from_dicts_of_weights_and_must_haves(
    weights: portfolioWeights, must_haves: dict
) -> tuple:
    asset_names = list(weights.keys())
    list_of_weights = [weights[key] for key in asset_names]
    list_of_must_haves = [must_haves[key] for key in asset_names]

    return asset_names, list_of_weights, list_of_must_haves


def clean_list_of_weights(
    weights: list, must_haves: list = None, fraction: float = 0.5
) -> list:
    """
    Make's sure we *always* have some weights where they are needed, by replacing nans
    Allocates fraction of pro-rata weight equally

    :param weights: The weights to clean
    :type weights: list of float

    :param must_haves: The indices of things we must have weights for
    :type must_haves: list of bool

    :param fraction: The amount to reduce missing instrument weights by
    :type fraction: float

    :returns: list of float

    >>> clean_list_of_weights([1.0, np.nan, np.nan], fraction=1.0)
    [0.33333333333333337, 0.3333333333333333, 0.3333333333333333]
    >>> clean_list_of_weights([0.4, 0.6, np.nan],  fraction=1.0)
    [0.2666666666666667, 0.4, 0.3333333333333333]
    >>> clean_list_of_weights([0.4, 0.6, np.nan],  fraction=0.5)
    [0.33333333333333337, 0.5, 0.16666666666666666]
    >>> clean_list_of_weights([np.nan, np.nan, 1.0],  must_haves=[False,True,True], fraction=1.0)
    [0.0, 0.5, 0.5]
    >>> clean_list_of_weights([np.nan, np.nan, np.nan],  must_haves=[False,False,True], fraction=1.0)
    [0.0, 0.0, 1.0]
    >>> clean_list_of_weights([np.nan, np.nan, np.nan],  must_haves=[False,False,False], fraction=1.0)
    [0.0, 0.0, 0.0]
    """
    ###

    if must_haves is None:
        must_haves = [True] * len(weights)

    if not any(must_haves):
        return [0.0] * len(weights)

    needs_replacing = [(np.isnan(x)) and must_haves[i] for (i, x) in enumerate(weights)]
    keep_empty = [(np.isnan(x)) and not must_haves[i] for (i, x) in enumerate(weights)]
    no_replacement_needed = [
        (not keep_empty[i]) and (not needs_replacing[i])
        for (i, x) in enumerate(weights)
    ]

    if not any(needs_replacing):
        return weights

    missing_weights = sum(needs_replacing)

    total_for_missing_weights = (
        fraction
        * missing_weights
        / (float(np.nansum(no_replacement_needed) + np.nansum(missing_weights)))
    )

    adjustment_on_rest = 1.0 - total_for_missing_weights

    each_missing_weight = total_for_missing_weights / missing_weights

    def _good_weight(
        value, idx, needs_replacing, keep_empty, each_missing_weight, adjustment_on_rest
    ):
        if needs_replacing[idx]:
            return each_missing_weight
        if keep_empty[idx]:
            return 0.0
        else:
            return value * adjustment_on_rest

    weights = [
        _good_weight(
            value,
            idx,
            needs_replacing,
            keep_empty,
            each_missing_weight,
            adjustment_on_rest,
        )
        for (idx, value) in enumerate(weights)
    ]

    # This process will screw up weights - let's fix them
    xsum = sum(weights)
    weights = [float(x / xsum) for x in weights]

    return weights
