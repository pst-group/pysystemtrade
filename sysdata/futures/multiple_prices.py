"""
A multiple price object is a:

pd. dataframe with the 6 columns PRICE, CARRY, PRICE_CONTRACT, CARRY_CONTRACT, FORWARD, FORWARD_CONTRACT
s
All contracts are in yyyymm format

We require these to calculate back adjusted prices and also to work out carry

They can be stored, or worked out 'on the fly'
"""

from syscore.exceptions import existingData
from sysdata.base_data import baseData
from syslogging import INSTRUMENT_CODE_LOG_LABEL

# These are used when inferring prices in an incomplete series
from sysobjects.multiple_prices import futuresMultiplePrices

USE_CHILD_CLASS_ERROR = "You need to use a child class of futuresMultiplePricesData"


class futuresMultiplePricesData(baseData):
    """
    Read and write data class to get multiple prices for a specific future

    We'd inherit from this class for a specific implementation

    """

    def __repr__(self):
        return "futuresMultiplePricesData base class - DO NOT USE"

    def keys(self):
        return self.get_list_of_instruments()

    def __getitem__(self, instrument_code: str) -> futuresMultiplePrices:
        return self.get_multiple_prices(instrument_code)

    def get_multiple_prices(self, instrument_code: str) -> futuresMultiplePrices:
        if self.is_code_in_data(instrument_code):
            multiple_prices = self._get_multiple_prices_without_checking(
                instrument_code
            )
        else:
            multiple_prices = futuresMultiplePrices.create_empty()

        return multiple_prices

    def delete_multiple_prices(self, instrument_code: str, are_you_sure=False):
        log_attrs = {INSTRUMENT_CODE_LOG_LABEL: instrument_code, "method": "temp"}

        if are_you_sure:
            if self.is_code_in_data(instrument_code):
                self._delete_multiple_prices_without_any_warning_be_careful(
                    instrument_code
                )
                self.log.info(
                    "Deleted multiple price data for %s" % instrument_code,
                    **log_attrs,
                )

            else:
                # doesn't exist anyway
                self.log.warning(
                    "Tried to delete non existent multiple prices for %s"
                    % instrument_code,
                    **log_attrs,
                )
        else:
            self.log.error(
                "You need to call delete_multiple_prices with a flag to be sure",
                **log_attrs,
            )
            raise Exception("You need to be sure!")

    def is_code_in_data(self, instrument_code: str) -> bool:
        if instrument_code in self.get_list_of_instruments():
            return True
        else:
            return False

    def add_multiple_prices(
        self,
        instrument_code: str,
        multiple_price_data: futuresMultiplePrices,
        ignore_duplication=False,
    ):
        log_attrs = {INSTRUMENT_CODE_LOG_LABEL: instrument_code, "method": "temp"}
        if self.is_code_in_data(instrument_code):
            if ignore_duplication:
                pass
            else:
                self.log.error(
                    "There is already %s in the data, you have to delete it first"
                    % instrument_code,
                    **log_attrs,
                )
                raise existingData

        self._add_multiple_prices_without_checking_for_existing_entry(
            instrument_code, multiple_price_data
        )

        self.log.info("Added data for instrument %s" % instrument_code, **log_attrs)

    def _add_multiple_prices_without_checking_for_existing_entry(
        self, instrument_code: str, multiple_price_data: futuresMultiplePrices
    ):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def get_list_of_instruments(self) -> list:
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def _get_multiple_prices_without_checking(
        self, instrument_code: str
    ) -> futuresMultiplePrices:
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def _delete_multiple_prices_without_any_warning_be_careful(
        self, instrument_code: str
    ):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)
