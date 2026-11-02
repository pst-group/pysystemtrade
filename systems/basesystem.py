from syscore.constants import arg_not_supplied
from sysdata.config.configdata import Config
from sysdata.config.instruments import (
    get_duplicate_list_of_instruments_to_remove_from_config,
    get_list_of_bad_instruments_in_config,
    get_list_of_ignored_instruments_in_config,
    get_list_of_untradeable_instruments_in_config,
)
from sysdata.sim.sim_data import simData
from syslogging.logger import get_logger
from systems.system_cache import systemCache, base_system_cache

from systems.tools.autogroup import (
    calculate_autogroup_weights_given_parameters,
    config_is_auto_group,
    resolve_config_into_parameters_and_weights_for_autogrouping,
)

"""
This is used for items which affect an entire system, not just one instrument
"""
ALL_KEYNAME = "all"


class System(object):
    """
    system objects are used for signal processing in a 'tree' like framework


    This is the base class which all systems inherit

    Systems are:

        made up of stages

       take a data, and optionally a config object

    The system only has one method 'of its own' which is get_instrument_list

    """

    def __init__(
        self,
        stage_list: list,
        data: simData,
        config: Config = arg_not_supplied,
        log=get_logger("base_system"),
    ):
        """
        Create a system object for doing simulations or live trading

        :param stage_list: A list of stages
        :type stage_list: list of systems.stage.SystemStage (or anything that inherits from it)

        :param data: data for doing simulations
        :type data: sysdata.data.simData (or anything that inherits from that)

        :param config: Optional configuration
        :type config: sysdata.configdata.Config

        :returns: new system object

        >>> from systems.stage import SystemStage
        >>> stage=SystemStage()
        >>> from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
        >>> data=csvFuturesSimData()
        >>> System([stage], data)
        System base_system with .config, .data, and .stages: Need to replace method when inheriting

        """

        if config is arg_not_supplied:
            # Default - for very dull systems this is sufficient
            config = Config()

        self._data = data
        self._config = config
        self._log = log

        self.config.system_init()
        self.data.system_init(self)
        self._setup_stages(stage_list)
        self._cache = systemCache(self)

    def _setup_stages(self, stage_list: list):
        stage_names = []

        try:
            iter(stage_list)
        except AssertionError:
            raise Exception(
                "You didn't pass a list into this System instance; even just one stage should be System([stage_instance])"
            )

        for stage in stage_list:
            """
            This is where we put the methods to store various stages of the process

            """

            # Stages have names, which are also how we find them in the system
            # attributes
            current_stage_name = stage.name

            # Each stage has a link back to the parent system
            # This init sets this, and also passes the system logging object
            stage.system_init(self)

            if current_stage_name in stage_names:
                raise Exception(
                    "You have duplicate subsystems with the name %s. Remove "
                    "one of them, or change a name." % current_stage_name
                )

            setattr(self, current_stage_name, stage)
            stage_names.append(current_stage_name)

        self._stage_names = stage_names

    def __repr__(self):
        sslist = ", ".join(self.stage_names)
        description = "System %s with .config, .data, and .stages: " % self.name

        return description + sslist

    @property
    def log(self):
        return self._log

    @property
    def data(self):
        return self._data

    @property
    def config(self):
        return self._config

    @property
    def name(self):
        return "base_system"

    @property
    def cache(self):
        return self._cache

    @property
    def stage_names(self):
        return self._stage_names

    # note we have to use this special cache here, or we get recursion problems
    @base_system_cache()
    def get_instrument_list(
        self,
        remove_duplicates=True,
        remove_ignored=True,
        remove_trading_restrictions=False,
        remove_bad_markets=False,
        remove_short_history=False,
        days_required=750,
        force_to_passed_list=arg_not_supplied,
    ) -> list:
        """
        Get the instrument list

        :returns: list of instrument_code str
        """
        if force_to_passed_list is not arg_not_supplied:
            instrument_list = force_to_passed_list
        else:
            instrument_list = self._get_instrument_list_from_config(
                remove_duplicates=remove_duplicates,
                remove_short_history=remove_short_history,
                remove_bad_markets=remove_bad_markets,
                remove_ignored=remove_ignored,
                remove_trading_restrictions=remove_trading_restrictions,
                days_required=days_required,
            )

        return instrument_list

    def _get_instrument_list_from_config(
        self,
        remove_duplicates=True,
        remove_ignored=True,
        remove_trading_restrictions=False,
        remove_bad_markets=False,
        remove_short_history=False,
        days_required=750,
    ) -> list:
        instrument_list = self._get_raw_instrument_list_from_config()
        instrument_list = self._remove_instruments_from_instrument_list(
            instrument_list,
            remove_duplicates=remove_duplicates,
            remove_short_history=remove_short_history,
            remove_bad_markets=remove_bad_markets,
            remove_ignored=remove_ignored,
            remove_trading_restrictions=remove_trading_restrictions,
            days_required=days_required,
        )

        instrument_list = sorted(set(list(instrument_list)))

        return instrument_list

    def _get_raw_instrument_list_from_config(self) -> list:
        config = self.config
        try:
            # if instrument weights specified in config ...
            instrument_weights = get_instrument_weights_from_config(config)
            instrument_list = list(instrument_weights.keys())
        except:
            try:
                # alternative place if no instrument weights
                instrument_list = config.instruments
            except:
                try:
                    # okay maybe not, must be in data
                    instrument_list = self.data.get_instrument_list()
                except:
                    raise Exception("Can't find instrument_list anywhere!")

        return instrument_list

    def _remove_instruments_from_instrument_list(
        self,
        instrument_list,
        remove_duplicates=True,
        remove_ignored=True,
        remove_trading_restrictions=False,
        remove_bad_markets=False,
        remove_short_history=False,
        days_required: int = 750,
    ):
        list_of_instruments_to_remove = self.get_list_of_instruments_to_remove(
            remove_duplicates=remove_duplicates,
            remove_short_history=remove_short_history,
            remove_bad_markets=remove_bad_markets,
            remove_ignored=remove_ignored,
            remove_trading_restrictions=remove_trading_restrictions,
            days_required=days_required,
        )

        self.log.debug(
            "Following instruments removed entirely from sim: %s"
            % str(list_of_instruments_to_remove)
        )

        instrument_list = [
            instrument
            for instrument in instrument_list
            if instrument not in list_of_instruments_to_remove
        ]

        return instrument_list

    @base_system_cache()
    def get_list_of_markets_not_trading_but_with_data(
        self,
        remove_duplicates=True,
        remove_ignored=True,
        remove_trading_restrictions=True,
        remove_bad_markets=True,
        remove_short_history=False,
        days_required=750,
    ) -> list:
        not_trading = self.get_list_of_instruments_to_remove(
            remove_duplicates=remove_duplicates,
            remove_short_history=remove_short_history,
            remove_bad_markets=remove_bad_markets,
            remove_ignored=remove_ignored,
            remove_trading_restrictions=remove_trading_restrictions,
            days_required=days_required,
        )

        instrument_list = self.get_instrument_list()

        ## don't bother if already removed
        not_trading_in_instrument_list = list(
            set(instrument_list).intersection(set(not_trading))
        )

        self.log.debug(
            "Following instruments marked as not trading %s"
            % str(not_trading_in_instrument_list)
        )

        return not_trading_in_instrument_list

    def get_list_of_instruments_to_remove(
        self,
        remove_duplicates=True,
        remove_ignored=True,
        remove_trading_restrictions=False,
        remove_bad_markets=False,
        remove_short_history=False,
        days_required=750,
    ) -> list:
        list_to_remove = []
        if remove_duplicates:
            list_of_duplicates = self.get_list_of_duplicate_instruments_to_remove()
            list_to_remove.extend(list_of_duplicates)

        if remove_ignored:
            list_of_ignored = self.get_list_of_ignored_instruments_to_remove()
            list_to_remove.extend(list_of_ignored)

        if remove_bad_markets:
            list_of_bad = self.get_list_of_bad_markets()
            list_to_remove.extend(list_of_bad)

        if remove_trading_restrictions:
            list_of_restricted = self.get_list_of_markets_with_trading_restrictions()
            list_to_remove.extend(list_of_restricted)

        if remove_short_history:
            list_of_short = self.get_list_of_short_history(days_required=days_required)
            list_to_remove.extend(list_of_short)

        list_to_remove = list(set(list_to_remove))
        list_to_remove.sort()

        return list_to_remove

    def get_list_of_duplicate_instruments_to_remove(self):
        duplicate_list = get_duplicate_list_of_instruments_to_remove_from_config(
            self.config
        )
        duplicate_list.sort()
        if len(duplicate_list) > 0:
            self.log.debug(
                "Following instruments are 'duplicate_markets' %s "
                % str(duplicate_list)
            )

        return duplicate_list

    def get_list_of_ignored_instruments_to_remove(self) -> list:
        ignore_instruments = get_list_of_ignored_instruments_in_config(self.config)
        ignore_instruments.sort()
        if len(ignore_instruments) > 0:
            self.log.debug(
                "Following instruments are marked as 'ignore_instruments': not included: %s"
                % str(ignore_instruments)
            )

        return ignore_instruments

    def get_list_of_markets_with_trading_restrictions(self) -> list:
        trading_restrictions = get_list_of_untradeable_instruments_in_config(
            self.config
        )
        trading_restrictions.sort()
        if len(trading_restrictions) > 0:
            ## will only log once as cached
            self.log.debug(
                "Following instruments have restricted trading:  %s "
                % str(trading_restrictions)
            )
        return trading_restrictions

    def get_list_of_bad_markets(self) -> list:
        bad_markets = get_list_of_bad_instruments_in_config(self.config)
        bad_markets.sort()
        if len(bad_markets) > 0:
            ## will only log once as cached
            self.log.debug(
                "Following instruments are marked as 'bad_markets':  %s"
                % str(bad_markets)
            )

        return bad_markets

    def get_list_of_short_history(self, days_required: int = 750) -> list:
        instrument_list = self.data.get_instrument_list()

        too_short = [
            instrument_code
            for instrument_code in instrument_list
            if self.data.length_of_history_in_days_for_instrument(instrument_code)
            < days_required
        ]

        too_short.sort()

        if len(too_short) > 0:
            self.log.debug(
                "Following instruments have insufficient history: %s" % str(too_short)
            )

        return too_short


def get_instrument_weights_from_config(config: Config) -> dict:
    instrument_weights_config = getattr(config, "instrument_weights", None)
    if instrument_weights_config is None:
        raise Exception("Instrument config not available")

    if config_is_auto_group(instrument_weights_config):
        instrument_weights_dict = _get_instrument_weights_with_autogrouping(
            instrument_weights_config
        )
    else:
        instrument_weights_dict = instrument_weights_config

    return instrument_weights_dict


def _get_instrument_weights_with_autogrouping(instrument_weights_config: dict) -> dict:
    (
        auto_group_parameters,
        auto_group_weights,
    ) = resolve_config_into_parameters_and_weights_for_autogrouping(
        instrument_weights_config
    )

    group_weights = calculate_autogroup_weights_given_parameters(
        auto_group_weights=auto_group_weights,
        auto_group_parameters=auto_group_parameters,
    )

    return group_weights


if __name__ == "__main__":
    import doctest

    doctest.testmod()
