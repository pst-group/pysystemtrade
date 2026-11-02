## Buffer class used in both position sizing and portfolio
import pandas as pd

from sysdata.config.configdata import Config
from syslogging.logger import get_logger
from syscore.constants import arg_not_supplied


def calculate_actual_buffers(
    buffers: pd.DataFrame, cap_multiplier: pd.Series
) -> pd.DataFrame:
    """
    Used when rescaling capital for accumulation
    """

    cap_multiplier = cap_multiplier.reindex(buffers.index).ffill()
    cap_multiplier = pd.concat([cap_multiplier, cap_multiplier], axis=1)
    cap_multiplier.columns = buffers.columns

    actual_buffers_for_position = buffers * cap_multiplier

    return actual_buffers_for_position


def apply_buffers_to_position(position: pd.Series, buffer: pd.Series) -> pd.DataFrame:
    top_position = position.ffill() + buffer.ffill()
    bottom_position = position.ffill() - buffer.ffill()

    pos_buffers = pd.concat([top_position, bottom_position], axis=1)
    pos_buffers.columns = ["top_pos", "bot_pos"]

    return pos_buffers


def calculate_buffers(
    instrument_code: str,
    position: pd.Series,
    config: Config,
    vol_scalar: pd.Series,
    instr_weights: pd.DataFrame = arg_not_supplied,
    idm: pd.Series = arg_not_supplied,
    log=get_logger(""),
) -> pd.Series:
    log.debug(
        "Calculating buffers for %s" % instrument_code,
        instrument_code=instrument_code,
    )

    buffer_method = config.buffer_method

    if buffer_method == "forecast":
        log.debug(
            "Calculating forecast method buffers for %s" % instrument_code,
            instrument_code=instrument_code,
        )
        if instr_weights is arg_not_supplied:
            instr_weight_this_code = arg_not_supplied
        else:
            instr_weight_this_code = instr_weights[instrument_code]

        buffer = get_forecast_method_buffer(
            instr_weight_this_code=instr_weight_this_code,
            vol_scalar=vol_scalar,
            idm=idm,
            position=position,
            config=config,
        )

    elif buffer_method == "position":
        log.debug(
            "Calculating position method buffer for %s" % instrument_code,
            instrument_code=instrument_code,
        )

        buffer = get_position_method_buffer(config=config, position=position)
    elif buffer_method == "none":
        log.debug(
            "None method, no buffering for %s" % instrument_code,
            instrument_code=instrument_code,
        )

        buffer = get_buffer_if_not_buffering(position=position)
    else:
        log.critical("Buffer method %s not recognised - not buffering" % buffer_method)
        buffer = get_buffer_if_not_buffering(position=position)

    return buffer


def get_forecast_method_buffer(
    position: pd.Series,
    vol_scalar: pd.Series,
    config: Config,
    instr_weight_this_code: pd.Series = arg_not_supplied,
    idm: pd.Series = arg_not_supplied,
) -> pd.Series:
    """
    Gets the buffers for positions, using proportion of average forecast method


    :param instrument_code: instrument to get values for
    :type instrument_code: str

    :returns: Tx1 pd.DataFrame
    """

    buffer_size = config.buffer_size

    buffer = _calculate_forecast_buffer_method(
        buffer_size=buffer_size,
        position=position,
        idm=idm,
        instr_weight_this_code=instr_weight_this_code,
        vol_scalar=vol_scalar,
    )

    return buffer


def get_position_method_buffer(
    position: pd.Series,
    config: Config,
) -> pd.Series:
    """
    Gets the buffers for positions, using proportion of position method

    """

    buffer_size = config.buffer_size
    abs_position = abs(position)

    buffer = abs_position * buffer_size

    buffer.columns = ["buffer"]

    return buffer


def get_buffer_if_not_buffering(position: pd.Series) -> pd.Series:
    EPSILON_POSITION = 0.001
    buffer = pd.Series([EPSILON_POSITION] * position.shape[0], index=position.index)

    return buffer


def _calculate_forecast_buffer_method(
    position: pd.Series,
    buffer_size: float,
    vol_scalar: pd.Series,
    idm: pd.Series = arg_not_supplied,
    instr_weight_this_code: pd.Series = arg_not_supplied,
):
    if instr_weight_this_code is arg_not_supplied:
        instr_weight_this_code_indexed = 1.0
    else:
        instr_weight_this_code_indexed = instr_weight_this_code.reindex(
            position.index
        ).ffill()

    if idm is arg_not_supplied:
        idm_indexed = 1.0
    else:
        idm_indexed = idm.reindex(position.index).ffill()

    vol_scalar_indexed = vol_scalar.reindex(position.index).ffill()

    average_position = abs(
        vol_scalar_indexed * instr_weight_this_code_indexed * idm_indexed
    )

    buffer = average_position * buffer_size

    return buffer
