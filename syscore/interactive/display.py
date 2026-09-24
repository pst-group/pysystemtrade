import pandas as pd

from syscore.maths import magnitude


def print_with_landing_strips_around(str_to_match: str, strip: str = "*"):
    """
    >>> print_with_landing_strips_around("abc")
    ***
    abc
    ***
    """
    str_to_print = landing_strip_around_string(str_to_match, strip)
    print(str_to_print)


def landing_strip_around_string(str_to_match: str, strip: str = "*") -> str:
    """
    >>> landing_strip_around_string("abc", "x")
    'xxx\\nabc\\nxxx'
    """
    strip = landing_strip_from_str(str_to_match, strip=strip)
    return strip + "\n" + str_to_match + "\n" + strip


def landing_strip_from_str(str_to_match: str, strip: str = "=") -> str:
    """
    >>> landing_strip_from_str("abc", "x")
    'xxx'
    """
    str_width = measure_width(str_to_match)
    return landing_strip(width=str_width, strip=strip)


def landing_strip(width: int = 80, strip: str = "*") -> str:
    return strip * width


def centralise_text(text: str, str_to_match: str, pad_with: str = " ") -> str:
    """
    >>> centralise_text('blach', 'ipusm porsis')
    '   blach    '
    >>> centralise_text('blanch', 'ipusm porsis')
    '   blanch   '
    """
    match_len = measure_width(str_to_match)
    text_len = len(text)
    if text_len >= match_len:
        return text
    pad_left = int((match_len - text_len) / 2.0)
    pad_right = match_len - pad_left - text_len
    pad_left_text = pad_with * pad_left
    pad_right_text = pad_with * pad_right

    new_text = "%s%s%s" % (pad_left_text, text, pad_right_text)

    return new_text


def measure_width(text: str) -> int:
    first_cr = text.find("\n")
    if first_cr == -1:
        first_cr = len(text)

    return first_cr


def calculate_multiplication_factor_for_nice_repr_of_value(some_value: float) -> float:
    """
    Work out a multiplication factor to avoid having to print a mantissa repr
    >>> calculate_multiplication_factor_for_nice_repr_of_value(3.2)
    1.0
    >>> calculate_multiplication_factor_for_nice_repr_of_value(0.032)
    1.0
    >>> calculate_multiplication_factor_for_nice_repr_of_value(0.0032)
    100.0
    >>> calculate_multiplication_factor_for_nice_repr_of_value(0.00032)
    1000.0
    >>> calculate_multiplication_factor_for_nice_repr_of_value(0.000000000000000001)
    1e+18
    """
    BIG_ENOUGH = 0.01
    ARBITRARY_LARGE_MULTIPLIER = 1000000
    NO_MULTIPLIER_REQUIRED = 1.0

    if some_value > BIG_ENOUGH:
        return NO_MULTIPLIER_REQUIRED

    if some_value == 0:
        return ARBITRARY_LARGE_MULTIPLIER

    mag = magnitude(some_value)
    mult_factor = 10.0 ** (-mag)

    return mult_factor


def set_pd_print_options():
    ## avoid annoying truncation in reports
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.max_columns", 100)
    pd.set_option("display.width", 1000)
