from dataclasses import dataclass
import pandas as pd

from sysbrokers.IB.ib_instruments import (
    futuresInstrumentWithIBConfigData,
    NOT_REQUIRED_FOR_IB,
    ibInstrumentConfigData,
)
from syscore.exceptions import missingData, missingInstrument, missingFile
from syscore.fileutils import resolve_path_and_filename_for_package
from syscore.genutils import return_another_value_if_nan
from syslogging.logger import *
from sysobjects.instruments import futuresInstrument


class IBconfig(pd.DataFrame):
    pass


IB_FUTURES_CONFIG_FILE = resolve_path_and_filename_for_package(
    "sysbrokers.IB.config.ib_config_futures.csv"
)


def read_ib_config_from_file(log=get_logger("")) -> IBconfig:
    try:
        df = pd.read_csv(IB_FUTURES_CONFIG_FILE)
    except Exception as e:
        log.warning("Can't read file %s" % IB_FUTURES_CONFIG_FILE)
        raise missingFile from e

    return IBconfig(df)


def get_instrument_object_from_config(
    instrument_code: str, config: IBconfig = None, log=get_logger("")
) -> futuresInstrumentWithIBConfigData:
    log_attrs = {INSTRUMENT_CODE_LOG_LABEL: instrument_code, "method": "temp"}

    if config is None:
        try:
            config = read_ib_config_from_file()
        except missingFile as e:
            log.warning(
                "Can't get config for instrument %s as IB configuration file missing"
                % instrument_code,
                **log_attrs,
            )
            raise missingInstrument from e

    list_of_instruments = get_instrument_list_from_ib_config(config=config)
    try:
        assert instrument_code in list_of_instruments
    except:
        log.warning(
            "Instrument %s is not in IB configuration file" % instrument_code,
            **log_attrs,
        )
        raise missingInstrument

    futures_instrument_with_ib_data = _get_instrument_object_from_valid_config(
        instrument_code=instrument_code, config=config
    )

    return futures_instrument_with_ib_data


def _get_instrument_object_from_valid_config(
    instrument_code: str, config: IBconfig = None
) -> futuresInstrumentWithIBConfigData:
    config_row = config[config.Instrument == instrument_code]
    symbol = config_row.IBSymbol.values[0]
    exchange = config_row.IBExchange.values[0]
    currency = return_another_value_if_nan(
        config_row.IBCurrency.values[0], NOT_REQUIRED_FOR_IB
    )
    ib_multiplier = return_another_value_if_nan(
        config_row.IBMultiplier.values[0], NOT_REQUIRED_FOR_IB
    )
    price_magnifier = return_another_value_if_nan(
        config_row.priceMagnifier.values[0], 1.0
    )
    ignore_weekly = config_row.IgnoreWeekly.values[0]

    # We use the flexibility of futuresInstrument to add additional arguments
    instrument = futuresInstrument(instrument_code)
    ib_data = ibInstrumentConfigData(
        symbol,
        exchange,
        currency=currency,
        ibMultiplier=ib_multiplier,
        priceMagnifier=price_magnifier,
        ignoreWeekly=ignore_weekly,
    )

    futures_instrument_with_ib_data = futuresInstrumentWithIBConfigData(
        instrument, ib_data
    )

    return futures_instrument_with_ib_data


@dataclass
class IBInstrumentIdentity:
    ib_code: str
    ib_multiplier: float
    ib_exchange: str
    ib_valid_exchange: str


def get_instrument_code_from_broker_instrument_identity(
    config: IBconfig,
    ib_instrument_identity: IBInstrumentIdentity,
    log=get_logger(""),
) -> str:
    ib_code = ib_instrument_identity.ib_code
    ib_multiplier = ib_instrument_identity.ib_multiplier
    ib_exchange = ib_instrument_identity.ib_exchange
    ib_valid_exchange = ib_instrument_identity.ib_valid_exchange

    config_rows = _get_relevant_config_rows_from_broker_instrument_identity_fields(
        config=config,
        ib_code=ib_code,
        ib_multiplier=ib_multiplier,
        ib_exchange=ib_exchange,
    )

    if len(config_rows) == 0:
        ## try something else
        ## might have a weird exchange, but the exchange we want is in validExchanges
        try:
            config_rows = _get_relevant_config_rows_from_broker_instrument_identity_using_multiple_valid_exchanges(
                config=config, ib_instrument_identity=ib_instrument_identity
            )

        except:
            msg = (
                "Broker symbol %s (exchange:%s, valid_exchange:%s multiplier:%f) not found in configuration file!"
                % (
                    ib_code,
                    ib_exchange,
                    ib_valid_exchange,
                    ib_multiplier,
                )
            )
            log.critical(msg)
            raise Exception(msg)

    if len(config_rows) > 1:
        msg = (
            "Broker symbol %s (%s, %f) appears more than once in configuration file!"
            % (ib_code, ib_exchange, ib_multiplier)
        )
        log.critical(msg)
        raise Exception(msg)

    return config_rows.iloc[0].Instrument


def _get_relevant_config_rows_from_broker_instrument_identity_using_multiple_valid_exchanges(
    config: IBconfig, ib_instrument_identity: IBInstrumentIdentity
) -> pd.Series:
    ib_code = ib_instrument_identity.ib_code
    ib_multiplier = ib_instrument_identity.ib_multiplier
    ib_valid_exchange = ib_instrument_identity.ib_valid_exchange

    valid_exchanges = ib_valid_exchange.split(",")

    for ib_exchange in valid_exchanges:
        config_rows = _get_relevant_config_rows_from_broker_instrument_identity_fields(
            config=config,
            ib_code=ib_code,
            ib_multiplier=ib_multiplier,
            ib_exchange=ib_exchange,
        )

        if len(config_rows) == 1:
            ## we have a match!
            return config_rows

    raise missingData


def _get_relevant_config_rows_from_broker_instrument_identity_fields(
    config: IBconfig, ib_code: str, ib_multiplier: float, ib_exchange: str
) -> pd.Series:
    # A blank IBMultiplier is a product whose multiplier varies by delivery
    # month (eg TTF gas: the hours in the month), so it matches any multiplier
    config_rows = config[
        (config.IBSymbol == ib_code)
        & ((config.IBMultiplier == ib_multiplier) | config.IBMultiplier.isna())
        & (config.IBExchange == ib_exchange)
    ]

    return config_rows


def get_instrument_list_from_ib_config(config: IBconfig):
    instrument_list = list(config.Instrument)
    return instrument_list
