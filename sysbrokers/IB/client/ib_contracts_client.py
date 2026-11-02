from copy import copy
from ib_async import Contract

from syscore.cache import Cache
from syscore.exceptions import missingData, missingContract
from sysbrokers.IB.client.ib_client import ibClient
from sysbrokers.IB.ib_instruments import (
    ib_futures_instrument_just_symbol,
    futuresInstrumentWithIBConfigData,
    ib_futures_instrument,
)
from sysbrokers.IB.ib_trading_hours import (
    get_trading_hours_from_contract_details,
    get_saved_trading_hours,
)
from sysbrokers.IB.ib_contracts import (
    ibcontractWithLegs,
    get_ib_contract_with_specific_expiry,
    resolve_unique_contract_from_ibcontract_list,
    _add_legs_to_ib_contract,
)


from sysobjects.contracts import futuresContract, contractDate
from sysobjects.production.trading_hours.intersection_of_weekly_and_specific_trading_hours import (
    intersection_of_any_weekly_and_list_of_normal_trading_hours,
)
from sysobjects.production.trading_hours.dict_of_weekly_trading_hours_any_day import (
    dictOfDictOfWeekdayTradingHours,
)
from sysobjects.production.trading_hours.weekly_trading_hours_any_day import (
    weekdayDictOfListOfTradingHoursAnyDay,
)
from sysobjects.production.trading_hours.trading_hours import listOfTradingHours
from sysexecution.trade_qty import tradeQuantity


class ibContractsClient(ibClient):
    def broker_get_futures_contract_list(
        self,
        futures_instrument_with_ib_data: futuresInstrumentWithIBConfigData,
        allow_expired: bool = False,
    ) -> list:
        ## Returns list of contract date strings YYYYMMDD

        ibcontract_pattern = ib_futures_instrument(futures_instrument_with_ib_data)
        contract_list = self.ib_get_contract_chain(
            ibcontract_pattern, allow_expired=allow_expired
        )
        # if no contracts found will be empty

        # Extract expiry date strings from these
        contract_dates = [
            ibcontract.lastTradeDateOrContractMonth for ibcontract in contract_list
        ]

        return contract_dates

    def broker_get_single_contract_expiry_date(
        self,
        futures_contract_with_ib_data: futuresContract,
        allow_expired: bool = False,
    ) -> str:
        """
        Return the exact expiry date for a given contract

        :param futures_contract_with_ib_data:  contract where instrument has ib metadata
        :return: YYYYMMDD str
        """
        log_attrs = {**futures_contract_with_ib_data.log_attributes(), "method": "temp"}
        if futures_contract_with_ib_data.is_spread_contract():
            self.log.warning(
                "Can only find expiry for single leg contract!", **log_attrs
            )
            raise missingContract

        try:
            ibcontract = self.ib_futures_contract(
                futures_contract_with_ib_data,
                allow_expired=allow_expired,
                always_return_single_leg=True,
            )
        except missingContract:
            self.log.warning("Contract is missing can't get expiry", **log_attrs)
            raise missingContract

        expiry_date = ibcontract.lastTradeDateOrContractMonth
        expiry_date = expiry_date[:8]  ## in case of weird '... GB format'

        return expiry_date

    def ib_get_trading_hours(
        self, contract_object_with_ib_data: futuresContract
    ) -> listOfTradingHours:
        ## Expensive calculations so we cache
        return self.cache.get(
            self._ib_get_uncached_trading_hours, contract_object_with_ib_data
        )

    def _ib_get_uncached_trading_hours(
        self, contract_object_with_ib_data: futuresContract
    ) -> listOfTradingHours:
        try:
            trading_hours_from_ib = self.ib_get_trading_hours_from_IB(
                contract_object_with_ib_data
            )
        except Exception as e:
            self.log.warning(
                "%s when getting trading hours from %s!"
                % (str(e), str(contract_object_with_ib_data)),
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise missingData

        try:
            saved_weekly_trading_hours = (
                self.ib_get_saved_weekly_trading_hours_for_contract(
                    contract_object_with_ib_data
                )
            )
        except:
            ## no saved hours, use IB
            return trading_hours_from_ib

        ## OK use the intersection
        trading_hours = intersection_of_any_weekly_and_list_of_normal_trading_hours(
            trading_hours_from_ib, saved_weekly_trading_hours
        )

        return trading_hours

    def ib_get_trading_hours_from_IB(
        self, contract_object_with_ib_data: futuresContract
    ) -> listOfTradingHours:
        try:
            ib_contract_details = self.ib_get_contract_details(
                contract_object_with_ib_data
            )
            trading_hours_from_ib = get_trading_hours_from_contract_details(
                ib_contract_details
            )
        except Exception as e:
            self.log.warning(
                "%s when getting trading hours from %s!"
                % (str(e), str(contract_object_with_ib_data)),
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise missingData

        return trading_hours_from_ib

    def ib_get_saved_weekly_trading_hours_for_contract(
        self, contract_object_with_ib_data: futuresContract
    ) -> weekdayDictOfListOfTradingHoursAnyDay:
        try:
            weekly_hours_for_timezone = (
                self.ib_get_saved_weekly_trading_hours_for_timezone_of_contract(
                    contract_object_with_ib_data
                )
            )
        except missingData:
            weekly_hours_for_timezone = None

        try:
            specific_weekly_hours_for_contract = (
                self.ib_get_saved_weekly_trading_hours_custom_for_contract(
                    contract_object_with_ib_data
                )
            )
        except missingData:
            specific_weekly_hours_for_contract = None

        if (
            specific_weekly_hours_for_contract is None
            and weekly_hours_for_timezone is None
        ):
            raise missingData

        if specific_weekly_hours_for_contract is None:
            return weekly_hours_for_timezone

        if weekly_hours_for_timezone is None:
            return specific_weekly_hours_for_contract

        intersected_trading_hours = weekly_hours_for_timezone.intersect(
            specific_weekly_hours_for_contract
        )

        return intersected_trading_hours

    def ib_get_saved_weekly_trading_hours_custom_for_contract(
        self, contract_object_with_ib_data: futuresContract
    ) -> weekdayDictOfListOfTradingHoursAnyDay:
        instrument_code = contract_object_with_ib_data.instrument_code
        all_saved_trading_hours = self.get_all_saved_weekly_trading_hours()
        specific_weekly_hours_for_contract = all_saved_trading_hours.get(
            instrument_code, None
        )

        if specific_weekly_hours_for_contract is None:
            # no warning necessary this is normal
            empty_hours = weekdayDictOfListOfTradingHoursAnyDay.create_empty()
            raise missingData

        return specific_weekly_hours_for_contract

    def ib_get_saved_weekly_trading_hours_for_timezone_of_contract(
        self, contract_object_with_ib_data: futuresContract
    ) -> weekdayDictOfListOfTradingHoursAnyDay:
        log_attrs = {**contract_object_with_ib_data.log_attributes(), "method": "temp"}

        try:
            time_zone_id = self.ib_get_timezoneid(contract_object_with_ib_data)
        except missingData:
            # problem getting timezoneid
            self.log.warning(
                "No time zone ID, can't get trading hours for timezone for %s"
                % str(contract_object_with_ib_data),
                **log_attrs,
            )
            raise missingData

        all_saved_trading_hours = self.get_all_saved_weekly_trading_hours()
        weekly_hours_for_timezone = all_saved_trading_hours.get(time_zone_id, None)

        if weekly_hours_for_timezone is None:
            # this means IB have changed something critical or missing file so we bork and alert
            error_msg = (
                "Check ib_config_trading_hours in sysbrokers/IB or private directory, hours for timezone %s not found!"
                % time_zone_id
            )
            self.log.critical(error_msg, **log_attrs)
            raise missingData

        return weekly_hours_for_timezone

    def ib_get_timezoneid(self, contract_object_with_ib_data: futuresContract) -> str:
        try:
            ib_contract_details = self.ib_get_contract_details(
                contract_object_with_ib_data
            )
            time_zone_id = ib_contract_details.timeZoneId
        except Exception as e:
            self.log.warning(
                "%s when getting time zone from %s!"
                % (str(e), str(contract_object_with_ib_data)),
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise missingData

        return time_zone_id

    def get_all_saved_weekly_trading_hours(self) -> dictOfDictOfWeekdayTradingHours:
        return self.cache.get(self._get_all_saved_weekly_trading_hours_from_file)

    def _get_all_saved_weekly_trading_hours_from_file(self):
        try:
            saved_hours = get_saved_trading_hours()
        except:
            self.log.critical(
                "Saved trading hours file missing - will use only IB hours"
            )
            return dictOfDictOfWeekdayTradingHours({})

        return saved_hours

    def ib_get_min_tick_size(
        self, contract_object_with_ib_data: futuresContract
    ) -> float:
        log_attrs = {**contract_object_with_ib_data.log_attributes(), "method": "temp"}
        try:
            ib_contract = self.ib_futures_contract(
                contract_object_with_ib_data, always_return_single_leg=True
            )
        except missingContract:
            self.log.warning(
                "Can't get tick size as contract missing",
                **log_attrs,
            )
            raise

        ib_contract_details = self.ib.reqContractDetails(ib_contract)[0]

        try:
            min_tick = ib_contract_details.minTick
        except Exception as e:
            self.log.warning(
                "%s when getting min tick size from %s!"
                % (str(e), str(ib_contract_details)),
                **log_attrs,
            )
            raise missingContract

        return min_tick

    def ib_get_price_magnifier(
        self, contract_object_with_ib_data: futuresContract
    ) -> float:
        log_attrs = {**contract_object_with_ib_data.log_attributes(), "method": "temp"}
        try:
            ib_contract = self.ib_futures_contract(
                contract_object_with_ib_data, always_return_single_leg=True
            )
        except missingContract:
            self.log.warning(
                "Can't get price magnifier as contract missing", **log_attrs
            )
            raise

        ib_contract_details = self.ib.reqContractDetails(ib_contract)[0]

        try:
            price_magnifier = ib_contract_details.priceMagnifier
        except Exception as e:
            self.log.warning(
                "%s when getting price magnifier from %s!"
                % (str(e), str(ib_contract_details)),
                **log_attrs,
            )
            raise missingContract

        return price_magnifier

    def ib_get_contract_details(self, contract_object_with_ib_data: futuresContract):
        try:
            ib_contract = self.ib_futures_contract(
                contract_object_with_ib_data, always_return_single_leg=True
            )
        except missingContract:
            self.log.warning(
                "Can't get trading hours as contract is missing",
                **contract_object_with_ib_data.log_attributes(),
                method="temp",
            )
            raise

        # returns a list but should only have one element
        ib_contract_details_list = self.ib.reqContractDetails(ib_contract)
        ib_contract_details = ib_contract_details_list[0]

        return ib_contract_details

    def ib_futures_contract(
        self,
        futures_contract_with_ib_data: futuresContract,
        allow_expired=False,
        always_return_single_leg=False,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ) -> Contract:
        ibcontract_with_legs = self.ib_futures_contract_with_legs(
            futures_contract_with_ib_data=futures_contract_with_ib_data,
            allow_expired=allow_expired,
            always_return_single_leg=always_return_single_leg,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
        )
        return ibcontract_with_legs.ibcontract

    def ib_futures_contract_with_legs(
        self,
        futures_contract_with_ib_data: futuresContract,
        allow_expired: bool = False,
        always_return_single_leg: bool = False,
        trade_list_for_multiple_legs: tradeQuantity = None,
    ) -> ibcontractWithLegs:
        """
        Return a complete and unique IB contract that matches contract_object_with_ib_data
        Doesn't actually get the data from IB, tries to get from cache

        :param futures_contract_with_ib_data: contract, containing instrument metadata suitable for IB
        :return: a single ib contract object
        """
        contract_object_to_use = copy(futures_contract_with_ib_data)
        if always_return_single_leg and contract_object_to_use.is_spread_contract():
            contract_object_to_use = (
                contract_object_to_use.new_contract_with_first_contract_date()
            )

        ibcontract_with_legs = self._get_stored_or_live_contract(
            contract_object_to_use=contract_object_to_use,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
            allow_expired=allow_expired,
        )

        return ibcontract_with_legs

    def _get_stored_or_live_contract(
        self,
        contract_object_to_use: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
        allow_expired: bool = False,
    ):
        ibcontract_with_legs = self.cache.get(
            self._get_ib_futures_contract_from_broker,
            contract_object_to_use,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
            allow_expired=allow_expired,
        )

        return ibcontract_with_legs

    ## FIXME USE GENERIC CACHING CODE
    @property
    def cache(self) -> Cache:
        ## dynamically create because don't have access to __init__ method
        cache = getattr(self, "_cache", None)
        if cache is None:
            cache = self._cache = Cache(self)

        return cache

    def _get_ib_futures_contract_from_broker(
        self,
        contract_object_with_ib_data: futuresContract,
        trade_list_for_multiple_legs: tradeQuantity = None,
        allow_expired: bool = False,
    ) -> ibcontractWithLegs:
        """
        Return a complete and unique IB contract that matches futures_contract_object
        This is expensive so not called directly, only by ib_futures_contract which does caching

        :param contract_object_with_ib_data: contract, containing instrument metadata suitable for IB
        :return: a single ib contract object
        """
        # Convert to IB world
        futures_instrument_with_ib_data = contract_object_with_ib_data.instrument
        contract_date = contract_object_with_ib_data.contract_date

        if contract_object_with_ib_data.is_spread_contract():
            ibcontract_with_legs = self._get_spread_ib_futures_contract(
                futures_instrument_with_ib_data,
                contract_date,
                allow_expired=allow_expired,
                trade_list_for_multiple_legs=trade_list_for_multiple_legs,
            )
        else:
            ibcontract_with_legs = self._get_vanilla_ib_futures_contract_with_legs(
                futures_instrument_with_ib_data=futures_instrument_with_ib_data,
                allow_expired=allow_expired,
                contract_date=contract_date,
            )

        return ibcontract_with_legs

    def _get_vanilla_ib_futures_contract_with_legs(
        self,
        futures_instrument_with_ib_data: futuresInstrumentWithIBConfigData,
        contract_date: contractDate,
        allow_expired: bool = False,
    ) -> ibcontractWithLegs:
        ibcontract = self._get_vanilla_ib_futures_contract(
            futures_instrument_with_ib_data, contract_date, allow_expired=allow_expired
        )
        legs = []

        return ibcontractWithLegs(ibcontract, legs)

    def _get_spread_ib_futures_contract(
        self,
        futures_instrument_with_ib_data: futuresInstrumentWithIBConfigData,
        contract_date: contractDate,
        trade_list_for_multiple_legs: tradeQuantity = None,
        allow_expired: bool = False,
    ) -> ibcontractWithLegs:
        """
        Return a complete and unique IB contract that matches contract_object_with_ib_data
        This is expensive so not called directly, only by ib_futures_contract which does caching

        :param contract_object_with_ib_data: contract, containing instrument metadata suitable for IB
        :return: a single ib contract object
        """
        if trade_list_for_multiple_legs is None:
            raise Exception("Multiple leg order must have trade list")

        # Convert to IB world
        ibcontract = ib_futures_instrument(futures_instrument_with_ib_data)
        ibcontract.secType = "BAG"

        list_of_contract_dates = contract_date.list_of_single_contract_dates
        resolved_legs = [
            self._get_vanilla_ib_futures_contract(
                futures_instrument_with_ib_data,
                contract_date,
                allow_expired=allow_expired,
            )
            for contract_date in list_of_contract_dates
        ]

        ibcontract_with_legs = _add_legs_to_ib_contract(
            ibcontract=ibcontract,
            resolved_legs=resolved_legs,
            trade_list_for_multiple_legs=trade_list_for_multiple_legs,
        )

        return ibcontract_with_legs

    def _get_vanilla_ib_futures_contract(
        self,
        futures_instrument_with_ib_data: futuresInstrumentWithIBConfigData,
        contract_date: contractDate,
        allow_expired: bool = False,
    ) -> Contract:
        """
        Return a complete and unique IB contract that matches contract_object_with_ib_data
        This is expensive so not called directly, only by ib_futures_contract which does caching

        :param contract_object_with_ib_data: contract, containing instrument metadata suitable for IB
        :return: a single ib contract object
        """

        ibcontract = get_ib_contract_with_specific_expiry(
            contract_date=contract_date,
            futures_instrument_with_ib_data=futures_instrument_with_ib_data,
        )

        # We could get multiple contracts here in case we have 'yyyymm' and not
        #    specified expiry date for VIX
        ibcontract_list = self.ib_get_contract_chain(
            ibcontract, allow_expired=allow_expired
        )

        try:
            resolved_contract = resolve_unique_contract_from_ibcontract_list(
                ibcontract_list=ibcontract_list,
                futures_instrument_with_ib_data=futures_instrument_with_ib_data,
            )
        except Exception as exception:
            self.log.warning(
                "%s could not resolve contracts: %s"
                % (str(futures_instrument_with_ib_data), exception.args[0])
            )
            raise missingContract

        return resolved_contract

    def ib_resolve_unique_contract(self, ibcontract_pattern, log=None):
        """
        Returns the 'resolved' IB contract based on a pattern. We expect a unique contract.

        This is used for FX only, since for futures things are potentially funkier

        :param ibcontract_pattern: ibContract
        :param log: log object
        :return: ibContract or missing_contract
        """
        if log is None:
            log = self.log

        contract_chain = self.ib_get_contract_chain(ibcontract_pattern)

        if len(contract_chain) > 1:
            log.warning(
                "Got multiple contracts for %s when only expected a single contract: Check contract date"
                % str(ibcontract_pattern)
            )
            raise missingContract

        if len(contract_chain) == 0:
            log.warning("Failed to resolve contract %s" % str(ibcontract_pattern))
            raise missingContract

        resolved_contract = contract_chain[0]

        return resolved_contract

    def ib_get_contract_with_conId(self, symbol: str, conId) -> Contract:
        contract_chain = self._get_contract_chain_for_symbol(symbol)
        conId_list = [contract.conId for contract in contract_chain]
        try:
            contract_idx = conId_list.index(conId)
        except ValueError:
            raise missingContract

        required_contract = contract_chain[contract_idx]

        return required_contract

    def _get_contract_chain_for_symbol(self, symbol: str) -> list:
        ibcontract_pattern = ib_futures_instrument_just_symbol(symbol)
        contract_chain = self.ib_get_contract_chain(ibcontract_pattern)

        return contract_chain

    def ib_get_contract_chain(
        self, ibcontract_pattern: Contract, allow_expired: bool = False
    ) -> list:
        """
        Get all the IB contracts matching a pattern.

        :param ibcontract_pattern: ibContract which may not fully specify the contract
        :return: list of ibContracts
        """

        new_contract_details_list = self.get_contract_details(
            ibcontract_pattern,
            allow_expired=allow_expired,
            allow_multiple_contracts=True,
        )

        ibcontract_list = [
            contract_details.contract for contract_details in new_contract_details_list
        ]

        return ibcontract_list
