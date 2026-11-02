from dateutil.tz import tz

import datetime
import pandas as pd

from ib_async import Contract as ibContract
from ib_async import util

from sysbrokers.IB.client.ib_client import PACING_INTERVAL_SECONDS
from sysbrokers.IB.client.ib_contracts_client import ibContractsClient
from sysbrokers.IB.ib_positions import resolveBS_for_list
from syscore.exceptions import missingContract, missingData

from syscore.dateutils import (
    replace_midnight_with_notional_closing_time,
    strip_timezone_fromdatetime,
    Frequency,
    DAILY_PRICE_FREQ,
)


from sysobjects.contracts import futuresContract
from sysexecution.trade_qty import tradeQuantity

TIMEOUT_SECONDS_ON_HISTORICAL_DATA = 20


class tickerWithBS(object):
    def __init__(self, ticker, BorS: str):
        self.ticker = ticker
        self.BorS = BorS


# we don't include ibClient since we get that through contracts client
class ibPriceClient(ibContractsClient):
    def broker_get_historical_futures_data_for_contract(
        self,
        contract_object_with_ib_broker_config: futuresContract,
        bar_freq: Frequency = DAILY_PRICE_FREQ,
        whatToShow="TRADES",
        allow_expired=False,
    ) -> pd.DataFrame:
        """
        Get historical daily data

        :param contract_object_with_ib_broker_config: contract where instrument has ib metadata
        :param freq: str; one of D, H, 5M, M, 10S, S
        :return: futuresContractPriceData
        """
        self.log.debug(
            "Updating log attributes",
            **contract_object_with_ib_broker_config.log_attributes(),
        )

        try:
            ibcontract = self.ib_futures_contract(
                contract_object_with_ib_broker_config, allow_expired=allow_expired
            )
        except missingContract:
            self.log.warning(
                "Can't resolve IB contract %s"
                % str(contract_object_with_ib_broker_config)
            )
            raise missingData

        price_data = self._get_generic_data_for_contract(
            ibcontract, bar_freq=bar_freq, whatToShow=whatToShow
        )

        self.log.debug("Log attributes reset", method="clear")

        return price_data

    def get_ticker_object_with_BS(
        self,
        contract_object_with_ib_data: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ) -> tickerWithBS:
        ib_ticker = self.get_ib_ticker_object(
            contract_object_with_ib_data, trade_list_for_multiple_legs
        )
        if trade_list_for_multiple_legs is None:
            ib_BS_str = ""
        else:
            ib_BS_str, __ = resolveBS_for_list(trade_list_for_multiple_legs)

        ticker_with_bs = tickerWithBS(ib_ticker, ib_BS_str)

        return ticker_with_bs

    def get_ib_ticker_object(
        self,
        contract_object_with_ib_data: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ) -> "ib.ticker":
        try:
            ibcontract = self.ib_futures_contract(
                contract_object_with_ib_data,
                trade_list_for_multiple_legs=trade_list_for_multiple_legs,
            )
        except missingContract:
            self.log.warning(
                "Can't find matching IB contract for %s"
                % str(contract_object_with_ib_data),
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise

        self.ib.reqMarketDataType(3)
        self.ib.reqMktData(ibcontract, "", False, False)
        ticker = self.ib.ticker(ibcontract)

        return ticker

    def cancel_market_data_for_contract(
        self, contract_object_with_ib_data: futuresContract
    ):
        self.cancel_market_data_for_contract_and_trade_qty(contract_object_with_ib_data)

    def cancel_market_data_for_contract_and_trade_qty(
        self,
        contract_object_with_ib_data: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ):
        try:
            ibcontract = self.ib_futures_contract(
                contract_object_with_ib_data,
                trade_list_for_multiple_legs=trade_list_for_multiple_legs,
            )
        except missingContract:
            self.log.warning(
                "Can't find matching IB contract for %s"
                % str(contract_object_with_ib_data),
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise

        self.ib.cancelMktData(ibcontract)

    def _ib_get_recent_bid_ask_tick_data_using_reqHistoricalTicks(
        self,
        contract_object_with_ib_data: futuresContract,
        tick_count=200,
    ) -> list:
        ## FIXME DEPRECATE AS DOESN'T WORK WITH DELAYED DATA
        """

        :param contract_object_with_ib_data:
        :return:
        """
        log_attrs = {**contract_object_with_ib_data.log_attributes(), "method": "temp"}
        if contract_object_with_ib_data.is_spread_contract():
            error_msg = "Can't get historical data for combo"
            self.log.critical(error_msg, **log_attrs)
            raise Exception(error_msg)

        try:
            ibcontract = self.ib_futures_contract(contract_object_with_ib_data)
        except missingContract:
            self.log.warning(
                "Can't find matching IB contract for %s"
                % str(contract_object_with_ib_data),
                **log_attrs,
            )
            raise

        recent_time = datetime.datetime.now() - datetime.timedelta(seconds=60)

        self.ib.reqMarketDataType(3)
        tick_data = self.ib.reqHistoricalTicks(
            ibcontract, recent_time, "", tick_count, "BID_ASK", useRth=False
        )

        return tick_data

    def _get_generic_data_for_contract(
        self,
        ibcontract: ibContract,
        bar_freq: Frequency = DAILY_PRICE_FREQ,
        whatToShow: str = "TRADES",
    ) -> pd.DataFrame:
        """
        Get historical daily data

        :param contract_object_with_ib_data: contract where instrument has ib metadata
        :param freq: str; one of D, H, 5M, M, 10S, S
        :return: futuresContractPriceData
        """

        try:
            barSizeSetting, durationStr = self._get_barsize_and_duration_from_frequency(
                bar_freq
            )
        except Exception as exception:
            self.log.warning(exception)
            raise missingData

        price_data_raw = self._ib_get_historical_data_of_duration_and_barSize(
            ibcontract,
            durationStr=durationStr,
            barSizeSetting=barSizeSetting,
            whatToShow=whatToShow,
        )

        price_data_as_df = self._raw_ib_data_to_df(
            price_data_raw=price_data_raw,
        )

        return price_data_as_df

    def _raw_ib_data_to_df(self, price_data_raw: pd.DataFrame) -> pd.DataFrame:
        if price_data_raw is None:
            self.log.warning("No price data from IB")
            raise missingData

        price_data_as_df = price_data_raw[["open", "high", "low", "close", "volume"]]

        price_data_as_df.columns = ["OPEN", "HIGH", "LOW", "FINAL", "VOLUME"]

        date_index = [
            self._ib_timestamp_to_datetime(price_row)
            for price_row in price_data_raw["date"]
        ]
        price_data_as_df.index = date_index

        return price_data_as_df

    ### TIMEZONE STUFF
    def _ib_timestamp_to_datetime(self, timestamp_ib) -> datetime.datetime:
        """
        Turns IB timestamp into pd.datetime as plays better with arctic, converts IB time (UTC?) to local,
        and adjusts yyyymm to closing vector

        :param timestamp_str: datetime.datetime
        :return: datetime.datetime
        """

        timestamp = self._adjust_ib_time_to_local(timestamp_ib)

        adjusted_ts = replace_midnight_with_notional_closing_time(timestamp)

        return adjusted_ts

    def _adjust_ib_time_to_local(self, timestamp_ib) -> datetime.datetime:
        if getattr(timestamp_ib, "tz_localize", None) is None:
            # daily, nothing to do
            return timestamp_ib

        # IB timestamp already includes tz
        timestamp_ib_with_tz = timestamp_ib
        local_timestamp_ib_with_tz = timestamp_ib_with_tz.astimezone(tz.tzlocal())
        local_timestamp_ib = strip_timezone_fromdatetime(local_timestamp_ib_with_tz)

        return local_timestamp_ib

    # HISTORICAL DATA
    # Works for FX and futures
    def _ib_get_historical_data_of_duration_and_barSize(
        self,
        ibcontract: ibContract,
        durationStr: str = "1 Y",
        barSizeSetting: str = "1 day",
        whatToShow="TRADES",
    ) -> pd.DataFrame:
        """
        Returns historical prices for a contract, up to today
        ibcontract is a Contract
        :returns list of prices in 4 tuples: Open high low close volume
        """

        last_call = self.last_historic_price_calltime
        self._avoid_pacing_violation(last_call)

        ## If live data is available a request for delayed data would be ignored by TWS.
        self.ib.reqMarketDataType(3)
        bars = self.ib.reqHistoricalData(
            ibcontract,
            endDateTime="",
            durationStr=durationStr,
            barSizeSetting=barSizeSetting,
            whatToShow=whatToShow,
            useRTH=True,
            formatDate=2,
            timeout=TIMEOUT_SECONDS_ON_HISTORICAL_DATA,
        )
        df = util.df(bars)

        self.last_historic_price_calltime = datetime.datetime.now()

        return df

    @staticmethod
    def _get_barsize_and_duration_from_frequency(bar_freq: Frequency) -> (str, str):
        barsize_lookup = dict(
            [
                (Frequency.Day, "1 day"),
                (Frequency.Hour, "1 hour"),
                (Frequency.Minutes_15, "15 mins"),
                (Frequency.Minutes_5, "5 mins"),
                (Frequency.Minute, "1 min"),
                (Frequency.Seconds_10, "10 secs"),
                (Frequency.Second, "1 secs"),
            ]
        )

        duration_lookup = dict(
            [
                (Frequency.Day, "1 Y"),
                (Frequency.Hour, "1 M"),
                (Frequency.Minutes_15, "1 W"),
                (Frequency.Minutes_5, "1 W"),
                (Frequency.Minute, "1 D"),
                (Frequency.Seconds_10, "14400 S"),
                (Frequency.Second, "1800 S"),
            ]
        )
        try:
            assert bar_freq in barsize_lookup.keys()
            assert bar_freq in duration_lookup.keys()
        except:
            raise Exception(
                "Barsize %s not recognised should be one of %s"
                % (str(bar_freq), str(barsize_lookup.keys()))
            )

        ib_barsize = barsize_lookup[bar_freq]
        ib_duration = duration_lookup[bar_freq]

        return ib_barsize, ib_duration

    def _avoid_pacing_violation(self, last_call_datetime: datetime.datetime):
        printed_warning_already = False
        while self._pause_for_pacing(last_call_datetime):
            if not printed_warning_already:
                self.log.debug(
                    "Pausing %f seconds to avoid pacing violation"
                    % (
                        last_call_datetime
                        + datetime.timedelta(seconds=PACING_INTERVAL_SECONDS)
                        - datetime.datetime.now()
                    ).total_seconds()
                )
                printed_warning_already = True
            pass

    @staticmethod
    def _pause_for_pacing(last_call_datetime: datetime.datetime):
        time_since_last_call = datetime.datetime.now() - last_call_datetime
        seconds_since_last_call = time_since_last_call.total_seconds()
        should_pause = seconds_since_last_call < PACING_INTERVAL_SECONDS

        return should_pause
