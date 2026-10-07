from syscore.genutils import np_convert
import datetime
from copy import copy

from syscore.dateutils import month_from_contract_letter, FUTURES_MONTH_LIST
from sysobjects.contract_dates_and_expiries import contractDate, contract_given_tuple

forward = 1
backwards = -1


class rollCycle(object):
    """
    A cycle determining how one contract rolls to the next

    Only works with monthly contracts
    """

    def __init__(self, cyclestring: str):
        assert isinstance(cyclestring, str)

        self._cyclestring = "".join(sorted(cyclestring))

    def __repr__(self):
        return self.cyclestring

    def __len__(self) -> int:
        return len(self.cyclestring)

    def __eq__(self, other):
        return self.cyclestring == other.cyclestring

    @property
    def cyclestring(self):
        return self._cyclestring

    def iterate_contract_date(
        self, direction: int, contract_date: contractDate
    ) -> contractDate:
        year_value, month_str = contract_date.date_str_to_year_month()
        if direction == forward:
            new_year_value, new_month_str = self._next_year_month_given_tuple(
                year_value, month_str
            )
        elif direction == backwards:
            new_year_value, new_month_str = self._previous_year_month_given_tuple(
                year_value, month_str
            )
        else:
            raise Exception(
                "Direction %d has to be %s or %s" % (direction, forward, backwards)
            )

        return contract_given_tuple(contract_date, new_year_value, new_month_str)

    def _previous_year_month_given_tuple(
        self, year_value: int, month_str: str
    ) -> (int, str):
        """
        Returns a tuple (year, month: str)

        :param month_str: str
        :param year_value: int
        :return: tuple (int, str)
        """

        new_month_as_str = self._previous_month(month_str)
        if self._month_is_first(month_str):
            year_value = year_value - 1

        return year_value, new_month_as_str

    def _next_year_month_given_tuple(
        self, year_value: int, month_str: str
    ) -> (int, str):
        """
        Returns a tuple (year, month: str)

        :param month_str: str
        :param year_value: int
        :return: tuple (int, str)
        """

        new_month_as_str = self._next_month(month_str)
        if self._month_is_last(month_str):
            year_value = year_value + 1

        return year_value, new_month_as_str

    def _next_month(self, current_month: str) -> str:
        """
        Move one month forward in expiry cycle

        :param current_month: Current month as a str
        :return: new month as str
        """

        return self._offset_month(current_month, 1)

    def _previous_month(self, current_month: str) -> str:
        """
        Move one month back in expiry cycle

        :param current_month: Current month as a str
        :return: new month as str
        """

        return self._offset_month(current_month, -1)

    def _offset_month(self, current_month: str, offset: int) -> str:
        """
        Move a number of months in the expiry cycle

        :param current_month: Current month as a str
        :param offset: number of months to go forwards or backwards
        :return: new month as str
        """

        current_index = self._where_month(current_month)
        len_cycle = len(self._cyclestring)
        new_index = current_index + offset
        cycled_index = new_index % len_cycle

        return self.cyclestring[cycled_index]

    def _where_month(self, current_month: str) -> int:
        """
        Return the index value (0 is first) of month in expiry

        :param current_month: month as str
        :return: int
        """
        if not self.check_is_month_in_rollcycle(current_month):
            raise Exception("%s not in cycle %s" % (current_month, self._cyclestring))

        return self.cyclestring.index(current_month)

    def _month_is_first(self, current_month: str) -> bool:
        """
        Is this the first month in the expiry cycle?

        :param current_month: month as str
        :return: bool
        """

        return self._where_month(current_month) == 0

    def _month_is_last(self, current_month: str) -> bool:
        """
        Is this the last month in the expiry cycle?

        :param current_month: month as str
        :return: bool
        """

        return self._where_month(current_month) == len(self._cyclestring) - 1

    def _as_list(self) -> list:
        """

        :return: list with int values referring to month numbers eg January =12 etc
        """
        return [
            month_from_contract_letter(contract_letter)
            for contract_letter in self.cyclestring
        ]

    def check_is_month_in_rollcycle(self, current_month: str) -> bool:
        """
        Is current_month in our expiry cycle?

        :param current_month: month as str
        :return: bool
        """
        if current_month in self._cyclestring:
            return True
        else:
            return False


GLOBAL_ROLLCYCLE = rollCycle("".join(FUTURES_MONTH_LIST))


class rollParameters(object):
    """
    A rollParameters object contains information about roll cycles and how we hold contracts

    When combined with a contractDate we get a rollWithData which we can use to manipulate the contractDate
       according to the rules of rollParameters

    """

    def __init__(
        self,
        hold_rollcycle: str,
        priced_rollcycle: str,
        roll_offset_day: int = 0,
        carry_offset: int = -1,
        approx_expiry_offset: int = 0,
    ):
        """

        :param hold_rollcycle: The rollcycle which we actually want to hold, str
        :param priced_rollcycle: The entire rollcycle for which prices are available, str
        :param roll_offset_day: The day, relative to the expiry date, when we usually roll; int
        :param carry_offset: The number of contracts forward or backwards we look for to define carry in the priced roll cycle; int
        :param approx_expiry_offset: The offset, relative to the 1st of the contract month, when an expiry date usually occurs; int

        """

        self._hold_rollcycle = rollCycle(hold_rollcycle)
        self._priced_rollcycle = rollCycle(priced_rollcycle)
        self._global_rollcycle = GLOBAL_ROLLCYCLE

        self._roll_offset_day = int(roll_offset_day)
        self._carry_offset = int(carry_offset)
        self._approx_expiry_offset = int(approx_expiry_offset)

    @property
    def roll_offset_day(self):
        return self._roll_offset_day

    @property
    def carry_offset(self):
        return self._carry_offset

    @property
    def approx_expiry_offset(self):
        return self._approx_expiry_offset

    def __eq__(self, other):
        return (
            (self.hold_rollcycle == other.hold_rollcycle)
            & (self.priced_rollcycle == other.priced_rollcycle)
            & (self.global_rollcycle == other.global_rollcycle)
            & (self.roll_offset_day == other.roll_offset_day)
            & (self.carry_offset == other.carry_offset)
            & (self.approx_expiry_offset == other.approx_expiry_offset)
        )

    def __repr__(self):
        dict_rep = self.as_dict()
        str_rep = ", ".join(
            ["%s:%s" % (key, str(dict_rep[key])) for key in dict_rep.keys()]
        )
        return "Rollcycle parameters " + str_rep

    @property
    def priced_rollcycle(self) -> rollCycle:
        return self._priced_rollcycle

    @property
    def hold_rollcycle(self) -> rollCycle:
        return self._hold_rollcycle

    @property
    def global_rollcycle(self):
        return self._global_rollcycle

    @classmethod
    def create_from_dict(rollData, roll_data_dict: dict):
        futures_instrument_roll_data = rollData(**roll_data_dict)

        return futures_instrument_roll_data

    def as_dict(self) -> dict:
        return dict(
            hold_rollcycle=self.hold_rollcycle.cyclestring,
            priced_rollcycle=self.priced_rollcycle.cyclestring,
            roll_offset_day=self.roll_offset_day,
            carry_offset=self.carry_offset,
            approx_expiry_offset=self.approx_expiry_offset,
        )

    def rolls_per_year_in_hold_cycle(self) -> int:
        hold_cycle = self.hold_rollcycle
        return len(hold_cycle)


class contractDateWithRollParameters(object):
    """ """

    def __init__(self, contract_date: contractDate, roll_parameters: rollParameters):
        """
        Roll data plus a specific contract date means we can do things like iterate the roll cycle etc
        """

        self._roll_parameters = roll_parameters
        self._contract_date = contract_date

    @property
    def roll_parameters(self):
        return self._roll_parameters

    @property
    def contract_date(self):
        return self._contract_date

    @property
    def date_str(self):
        return self.contract_date.date_str

    def __repr__(self):
        return "%s with roll parameters %s" % (
            str(self.contract_date),
            str(self.roll_parameters),
        )

    def next_priced_contract(self):
        contract = self._closest_previous_valid_priced_contract()
        return contract._iterate_contract(forward, "priced_rollcycle")

    def previous_priced_contract(self):
        contract = self._closest_next_valid_priced_contract()
        return contract._iterate_contract(backwards, "priced_rollcycle")

    def next_held_contract(self):
        contract = self._closest_previous_valid_held_contract()
        return contract._iterate_contract(forward, "hold_rollcycle")

    def previous_held_contract(self):
        contract = self._closest_next_valid_held_contract()
        return contract._iterate_contract(backwards, "hold_rollcycle")

    def _closest_next_valid_priced_contract(self):
        # returns current contract if a valid priced contract, or next one in
        # cycle that is
        valid_contract_to_return = self
        while not valid_contract_to_return._valid_date_in_priced_rollcycle():
            valid_contract_to_return = valid_contract_to_return._next_month_contract()
        return valid_contract_to_return

    def _closest_previous_valid_priced_contract(self):
        # returns current contract if a valid priced contract, or previous one
        # in cycle that is
        valid_contract_to_return = self
        while not valid_contract_to_return._valid_date_in_priced_rollcycle():
            valid_contract_to_return = (
                valid_contract_to_return._previous_month_contract()
            )
        return valid_contract_to_return

    def _closest_next_valid_held_contract(self):
        # returns current contract if a valid held contract, or next one in
        # cycle that is
        valid_contract_to_return = self
        while not valid_contract_to_return._valid_date_in_hold_rollcycle():
            valid_contract_to_return = valid_contract_to_return._next_month_contract()
        return valid_contract_to_return

    def _closest_previous_valid_held_contract(self):
        # returns current contract if a valid held contract, or previous one in
        # cycle that is
        valid_contract_to_return = self
        while not valid_contract_to_return._valid_date_in_hold_rollcycle():
            valid_contract_to_return = (
                valid_contract_to_return._previous_month_contract()
            )
        return valid_contract_to_return

    def _next_month_contract(self):
        return self._iterate_contract(forward, "global_rollcycle")

    def _previous_month_contract(self):
        return self._iterate_contract(backwards, "global_rollcycle")

    def _iterate_contract(self, direction: int, rollcycle_name: str):
        """
        Used for going backward or forwards

        :param direction_function_name: str, attribute method of a roll cycle, either 'next_year_month' or 'previous_year_month'
        :param rollcycle_name: str, attribute method of self.roll_parameters, either 'priced_rollcycle' or 'held_rollcycle'
        :return: new contractDate object
        """
        rollcycle_to_use = getattr(self.roll_parameters, rollcycle_name)

        try:
            assert self._valid_date_in_named_rollcycle(rollcycle_name) is True
        except BaseException:
            raise Exception(
                "ContractDate %s must be in %s %s"
                % (str(self.contract_date), rollcycle_name, str(rollcycle_to_use))
            )

        new_contract_date = rollcycle_to_use.iterate_contract_date(
            direction, self.contract_date
        )

        existing_roll_parameters = self.roll_parameters

        new_contract_date_with_roll_data_object = contractDateWithRollParameters(
            new_contract_date, existing_roll_parameters
        )

        return new_contract_date_with_roll_data_object

    def _valid_date_in_priced_rollcycle(self) -> bool:
        return self._valid_date_in_named_rollcycle("priced_rollcycle")

    def _valid_date_in_hold_rollcycle(self) -> bool:
        return self._valid_date_in_named_rollcycle("hold_rollcycle")

    def _valid_date_in_named_rollcycle(self, rollcycle_name: str) -> bool:
        relevant_rollcycle = getattr(self.roll_parameters, rollcycle_name)
        current_month = self.contract_date.letter_month()

        return relevant_rollcycle.check_is_month_in_rollcycle(current_month)

    def carry_contract(self):
        if self.roll_parameters.carry_offset == -1:
            return self.previous_priced_contract()
        elif self.roll_parameters.carry_offset == 1:
            return self.next_priced_contract()
        else:
            raise Exception("carry_offset needs to be +1 or -1")

    @property
    def desired_roll_date(self) -> datetime.datetime:
        return self.contract_date.expiry_date + datetime.timedelta(
            days=np_convert(self.roll_parameters.roll_offset_day)
        )

    def get_contracts_from_recently_to_contract_date(self):
        """
        Returns all the unexpired contracts between now and the contract date

        We go back 3 months in case of a mismatch between roll parameters and actual expiries when setting up data

        :return: list of contractDate
        """

        datetime_now = datetime.datetime.now() - datetime.timedelta(100)
        contract_dates = []
        current_contract_date_with_roll_parameters = copy(self)

        while (
            current_contract_date_with_roll_parameters.contract_date.expiry_date
            >= datetime_now
        ):
            current_contract_date = (
                current_contract_date_with_roll_parameters.contract_date
            )
            contract_dates.append(current_contract_date)
            current_contract_date_with_roll_parameters = (
                current_contract_date_with_roll_parameters.previous_priced_contract()
            )

        return contract_dates
