"""

Code used when we interact with users (displaying stuff, getting input, monitoring progress)

"""

from typing import Union

from syscore.genutils import str2Bool
from syscore.constants import none_type


def true_if_answer_is_yes(
    prompt: str = "", allow_empty_to_return_none: bool = False
) -> Union[bool, none_type]:
    invalid = True
    while invalid:
        x = input(prompt)
        if x == "":
            if allow_empty_to_return_none:
                return None
        else:
            first_character = x[0].lower()
            if first_character == "y":
                return True
            elif first_character == "n":
                return False

        print("Need one of yes/no, Yes/No, y/n, Y/N")


"""

    GET INPUT AND CAST TO TYPE

"""


def get_input_from_user_and_convert_to_type(
    prompt: str,
    type_expected=int,
    allow_default: bool = True,
    default_value=0,
    default_str: str = None,
    check_type: bool = True,
):
    input_str = prompt + " "
    if allow_default:
        if default_str is None:
            input_str = input_str + "<RETURN for default %s> " % str(default_value)
        else:
            input_str = input_str + "<RETURN for %s> " % default_str

    result = _get_input_and_check_type(
        input_str=input_str,
        type_expected=type_expected,
        allow_default=allow_default,
        default_value=default_value,
        check_type=check_type,
    )

    return result


def _get_input_and_check_type(
    input_str: str,
    type_expected=int,
    allow_default: bool = True,
    default_value=0,
    check_type: bool = True,
):
    invalid = True
    while invalid:
        user_input = input(input_str)

        if user_input == "" and allow_default:
            return default_value
        if not check_type:
            ## not typecasting
            return user_input

        try:
            result = _convert_type_or_throw_expection(
                user_input=user_input, type_expected=type_expected
            )
            return result
        except BaseException:
            ## keep going
            continue


def _convert_type_or_throw_expection(user_input: str, type_expected=int):
    try:
        if type_expected is bool:
            result = str2Bool(user_input)
        else:
            result = type_expected(user_input)
    except:
        print("%s is not of expected type %s" % (user_input, type_expected.__name__))
        raise Exception()

    return result


"""

    INPUT TUPLE DATA

"""


def input_field_names_for_named_tuple(named_tuple_instance):
    original_tuple_as_dict = named_tuple_as_dict(named_tuple_instance)
    for key_name in original_tuple_as_dict.keys():
        original_tuple_entry = original_tuple_as_dict[key_name]
        original_tuple_entry_class = original_tuple_entry.__class__
        input_result = get_input_from_user_and_convert_to_type(
            key_name,
            type_expected=original_tuple_entry_class,
            default_value=original_tuple_entry,
        )

        original_tuple_as_dict[key_name] = input_result

    new_tuple = override_tuple_fields(named_tuple_instance, original_tuple_as_dict)

    return new_tuple


def override_tuple_fields(original_tuple_instance, dict_of_new_fields: dict):
    original_tuple_instance_as_dict = named_tuple_as_dict(original_tuple_instance)
    combined_dict = dict(original_tuple_instance_as_dict, **dict_of_new_fields)
    original_tuple_class = original_tuple_instance.__class__
    try:
        new_named_tuple = original_tuple_class(**combined_dict)
    except:
        raise Exception(
            "One or more of new fields %s don't belong in named tuple %s"
            % (str(dict_of_new_fields), str(original_tuple_instance))
        )
    return new_named_tuple


def named_tuple_as_dict(original_tuple_instance) -> dict:
    return dict(
        [
            (field_name, getattr(original_tuple_instance, field_name))
            for field_name in original_tuple_instance._fields
        ]
    )
