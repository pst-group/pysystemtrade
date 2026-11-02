from collections import namedtuple

import pandas as pd

from syscore.exceptions import missingFile
from syscore.fileutils import resolve_path_and_filename_for_package

IB_CCY_CONFIG_FILE = resolve_path_and_filename_for_package(
    "sysbrokers.IB.config.ib_config_spot_FX.csv"
)


ibFXConfig = namedtuple("ibFXConfig", ["ccy1", "ccy2", "invert"])


def get_ib_config_from_file(log) -> pd.DataFrame:
    try:
        config_data = pd.read_csv(IB_CCY_CONFIG_FILE)
    except Exception as e:
        log.warning("Can't read file %s" % IB_CCY_CONFIG_FILE)
        raise missingFile from e

    return config_data


def config_info_for_code(config_data: pd.DataFrame, currency_code) -> ibFXConfig:
    ccy1 = config_data[config_data.CODE == currency_code].CCY1.values[0]
    ccy2 = config_data[config_data.CODE == currency_code].CCY2.values[0]
    invert = config_data[config_data.CODE == currency_code].INVERT.values[0] == "YES"

    ib_config_for_code = ibFXConfig(ccy1, ccy2, invert)

    return ib_config_for_code


def get_list_of_codes(config_data: pd.DataFrame) -> list:
    list_of_codes = list(config_data.CODE)

    return list_of_codes
