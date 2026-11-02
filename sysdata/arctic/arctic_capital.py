from syscore.exceptions import missingData
from sysdata.production.capital import capitalData

CAPITAL_COLLECTION = "arctic_capital"

from sysdata.arctic.arctic_connection import arcticData
from syslogging.logger import get_logger
import pandas as pd


class arcticCapitalData(capitalData):
    """
    Class to read / write multiple total capital data to and from arctic
    """

    def __init__(self, mongo_db=None, log=get_logger("arcticCapitalData")):
        super().__init__(log=log)

        self._arctic = arcticData(CAPITAL_COLLECTION, mongo_db=mongo_db)

    def __repr__(self):
        return repr(self._arctic)

    @property
    def arctic(self):
        return self._arctic

    def _get_list_of_strategies_with_capital_including_total(self) -> list:
        return self.arctic.get_keynames()

    def get_capital_pd_df_for_strategy(self, strategy_name: str) -> pd.DataFrame:
        try:
            pd_series = self.arctic.read(strategy_name)
        except:
            raise missingData(
                "Unable to get capital data from arctic for strategy %s" % strategy_name
            )

        return pd_series

    def _delete_all_capital_for_strategy_no_checking(self, strategy_name: str):
        self.arctic.delete(strategy_name)

    def update_capital_pd_df_for_strategy(
        self, strategy_name: str, updated_capital_df: pd.DataFrame
    ):
        self.arctic.write(strategy_name, updated_capital_df)
