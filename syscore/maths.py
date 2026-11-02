"""
Low level calculations that don't fit anywhere else
"""

import math as maths

import numpy as np

from copy import copy


def calculate_weighted_average_with_nans(
    weights: list, list_of_values: list, sum_of_weights_should_be: float = 1.0
) -> float:
    """
    Calculate a weighted average when the weights and/or values might be nans
    >>> calculate_weighted_average_with_nans([0.2, 0.2, np.nan, 0.4],[2, np.nan, 3, np.nan])
    2.0
    >>> calculate_weighted_average_with_nans([np.nan, 0.2, np.nan, 0.4],[2, np.nan, 3, np.nan])
    0.0

    """
    ## easier to work in np space
    np_weights = np.array(weights)
    np_values = np.array(list_of_values)

    # get safe weights
    np_weights_without_nans_in_weights_or_values = (
        calculate_np_weights_without_nans_in_weights_or_values(
            np_weights=np_weights, np_values=np_values
        )
    )

    normalised_weights = renormalise_array_of_values_to_sum(
        np_weights_without_nans_in_weights_or_values,
        renormalise_sum_to=sum_of_weights_should_be,
    )

    weighted_value = calculate_weighted_average(
        np_weights=normalised_weights, np_values=np_values
    )

    return weighted_value


def calculate_np_weights_without_nans_in_weights_or_values(
    np_weights: np.array, np_values: np.array
) -> np.array:
    """
    Get set of weights where neithier the value or the weight is nan
    >>> calculate_np_weights_without_nans_in_weights_or_values(np.array([0.2, 0.2, np.nan, 0.4]),np.array([2, np.nan, 3, np.nan]))
    array([0.2, 0. , 0. , 0. ])
    """

    weights_times_values_as_np = np_weights * np_values
    empty_weights = np.isnan(weights_times_values_as_np)

    weights_without_nan = copy(np_weights)
    weights_without_nan[empty_weights] = 0.0

    return weights_without_nan


def renormalise_array_of_values_to_sum(
    array_of_values: np.array, renormalise_sum_to: float = 1.0
) -> np.array:
    """
    Most commonly used to renormalise weights to 1.0

    >>> renormalise_array_of_values_to_sum(np.array([0.125, 0.125, 0.25, 0.0]), 2.0)
    array([0.5, 0.5, 1. , 0. ])

    """
    sum_of_values = np.nansum(array_of_values)
    renormalise_multiplier = renormalise_sum_to / sum_of_values
    new_values = array_of_values * renormalise_multiplier

    return new_values


def calculate_weighted_average(np_weights: np.array, np_values: np.array) -> float:
    """
    Implicit replaces nan with zeros

    >>> calculate_weighted_average(np.array([0.2, 0.2, 0, 0.4]),np.array([2, np.nan, 3, np.nan]))
    0.4
    """
    weights_times_values_as_np = np_weights * np_values

    return np.nansum(weights_times_values_as_np)


if __name__ == "__main__":
    import doctest

    doctest.testmod()


def magnitude(x):
    """
    Magnitude of a positive numeber. Used for calculating significant figures
    """
    return int(maths.log10(x))
