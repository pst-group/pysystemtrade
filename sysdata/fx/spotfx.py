"""
Spot fx prices
"""

import numpy as np
import pandas as pd
import datetime

from sysdata.base_data import baseData
from syscore.pandas.merge_data_keeping_past_data import SPIKE_IN_DATA

from syslogging import CURRENCY_CODE_LOG_LABEL
from sysobjects.spot_fx_prices import fxPrices, get_fx_tuple_from_code, DEFAULT_CURRENCY

DEFAULT_DATES = pd.date_range(
    start=datetime.datetime(1970, 1, 1), freq="B", end=datetime.datetime.now()
)
DEFAULT_RATE_SERIES = pd.Series(np.full(len(DEFAULT_DATES), 1.0), index=DEFAULT_DATES)

USE_CHILD_CLASS_ERROR = "You need to use a child class of fxPricesData"


class fxPricesData(baseData):
    """
    Read and write data class to get fx prices

    We'd inherit from this class for a specific implementation

    """

    def __repr__(self):
        return USE_CHILD_CLASS_ERROR

    def keys(self):
        return self.get_list_of_fxcodes()

    def __getitem__(self, code):
        return self.get_fx_prices(code)

    def get_fx_prices(self, fx_code: str) -> fxPrices:
        """
        Get a historical series of FX prices

        :param fx_code: currency code, in the form EURUSD
        :return: fxData object
        """
        try:
            currency1, currency2 = get_fx_tuple_from_code(fx_code)
        except:
            self.log.warning("Currency can't be located for %s using USD" % fx_code)
            return DEFAULT_RATE_SERIES

        if currency1 == currency2:
            # Trivial, just a bunch of 1's
            fx_data = DEFAULT_RATE_SERIES

        elif currency2 == DEFAULT_CURRENCY:
            # We ought to have data
            fx_data = self._get_standard_fx_prices(fx_code)

        elif currency1 == DEFAULT_CURRENCY:
            # inversion
            fx_data = self._get_fx_prices_for_inversion(fx_code)

        else:
            # Try a cross rate
            fx_data = self._get_fx_cross(fx_code)

        return fx_data

    def _get_standard_fx_prices(self, fx_code: str) -> fxPrices:
        currency1, currency2 = get_fx_tuple_from_code(fx_code)
        assert currency2 == DEFAULT_CURRENCY
        fx_data = self._get_fx_prices_vs_default(currency1)

        return fx_data

    def _get_fx_prices_for_inversion(self, fx_code: str) -> fxPrices:
        """
        Get a historical series of FX prices, must be USDXXX

        :param currency2
        :return: fxData
        """
        currency1, currency2 = get_fx_tuple_from_code(fx_code)
        assert currency1 == DEFAULT_CURRENCY

        raw_fx_data = self._get_fx_prices_vs_default(currency2)
        if raw_fx_data.empty:
            self.log.warning(
                "Data for %s is missing, needed to calculate %s"
                % (currency2 + DEFAULT_CURRENCY, DEFAULT_CURRENCY + currency2),
                **{CURRENCY_CODE_LOG_LABEL: fx_code, "method": "temp"},
            )
            return raw_fx_data

        inverted_fx_data = 1.0 / raw_fx_data

        return inverted_fx_data

    def _get_fx_cross(self, fx_code: str) -> fxPrices:
        """
        Get a currency cross rate XXXYYY, eg not XXXUSD or USDXXX or XXXXXX

        :return: fxPrices
        """
        currency1, currency2 = get_fx_tuple_from_code(fx_code)
        currency1_vs_default = self._get_fx_prices_vs_default(currency1)
        currency2_vs_default = self._get_fx_prices_vs_default(currency2)

        if currency1_vs_default.empty or currency2_vs_default.empty:
            return fxPrices.create_empty()

        (aligned_c1, aligned_c2) = currency1_vs_default.align(
            currency2_vs_default, join="outer"
        )

        fx_rate_series = aligned_c1.ffill() / aligned_c2.ffill()

        return fx_rate_series

    def _get_fx_prices_vs_default(self, currency1: str) -> fxPrices:
        """
        Get a historical series of FX prices, must be XXXUSD

        :param code: currency code, in the form EUR
        :return: fxData object
        """
        code = currency1 + DEFAULT_CURRENCY
        fx_data = self._get_fx_prices(code)

        return fx_data

    def _get_fx_prices(self, code: str) -> fxPrices:
        if not self.is_code_in_data(code):
            self.log.warning(
                "Currency %s is missing from list of FX data" % code,
                **{CURRENCY_CODE_LOG_LABEL: code, "method": "temp"},
            )

            return fxPrices.create_empty()

        data = self._get_fx_prices_without_checking(code)

        return data

    def delete_fx_prices(self, code: str, are_you_sure=False):
        log_attrs = {CURRENCY_CODE_LOG_LABEL: code, "method": "temp"}

        if are_you_sure:
            if self.is_code_in_data(code):
                self._delete_fx_prices_without_any_warning_be_careful(code)
                self.log.info(
                    "Deleted fx price data for %s" % code,
                    **log_attrs,
                )

            else:
                # doesn't exist anyway
                self.log.warning(
                    "Tried to delete non existent fx prices for %s" % code,
                    **log_attrs,
                )
        else:
            self.log.warning(
                "You need to call delete_fx_prices with a flag to be sure",
                **log_attrs,
            )

    def is_code_in_data(self, code: str) -> bool:
        if code in self.get_list_of_fxcodes():
            return True
        else:
            return False

    def add_fx_prices(
        self, code: str, fx_price_data: fxPrices, ignore_duplication: bool = False
    ):
        log_attrs = {CURRENCY_CODE_LOG_LABEL: code, "method": "temp"}
        if self.is_code_in_data(code):
            if ignore_duplication:
                pass
            else:
                self.log.warning(
                    "There is already %s in the data, you have to delete it first, or "
                    "set ignore_duplication=True, or use update_fx_prices" % code,
                    **log_attrs,
                )
                return None

        self._add_fx_prices_without_checking_for_existing_entry(code, fx_price_data)
        self.log.info("Added fx data for code %s" % code, **log_attrs)

    def update_fx_prices(
        self, code: str, new_fx_prices: fxPrices, check_for_spike=True
    ) -> int:
        """
        Checks existing data, adds any new data with a timestamp greater than the existing data

        :param code: FX code
        :param new_fx_prices: fxPrices object
        :return: int, number of rows added
        """
        log_attrs = {CURRENCY_CODE_LOG_LABEL: code, "method": "temp"}

        old_fx_prices = self.get_fx_prices(code)
        merged_fx_prices = old_fx_prices.add_rows_to_existing_data(
            new_fx_prices, check_for_spike=check_for_spike
        )

        if merged_fx_prices is SPIKE_IN_DATA:
            return SPIKE_IN_DATA

        rows_added = len(merged_fx_prices) - len(old_fx_prices)

        if rows_added == 0:
            if len(old_fx_prices) == 0:
                self.log.debug("No new or old prices for %s" % code, **log_attrs)

            else:
                self.log.debug(
                    "No additional data since %s for %s"
                    % (str(old_fx_prices.index[-1]), code),
                    **log_attrs,
                )
            return 0

        self.add_fx_prices(code, merged_fx_prices, ignore_duplication=True)

        self.log.debug(
            "Added %d additional rows for %s" % (rows_added, code),
            **log_attrs,
        )

        return rows_added

    def get_list_of_fxcodes(self):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def _add_fx_prices_without_checking_for_existing_entry(self, code, fx_price_data):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def _delete_fx_prices_without_any_warning_be_careful(self, code):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)

    def _get_fx_prices_without_checking(self, code):
        raise NotImplementedError(USE_CHILD_CLASS_ERROR)
