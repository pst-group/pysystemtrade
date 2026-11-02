from syscore.exceptions import missingData, missingFile
from sysdata.production.capital import capitalData

CAPITAL_COLLECTION = "capital"

from sysdata.parquet.parquet_access import ParquetAccess
from syslogging.logger import get_logger
import pandas as pd


class parquetCapitalData(capitalData):
    """
    Class to read / write multiple total capital data to and from arctic
    """

    def __init__(
        self, parquet_access: ParquetAccess, log=get_logger("parquetCapitalData")
    ):
        super().__init__(log=log)
        self._parquet = parquet_access

    def __repr__(self):
        return "parquetCapitalData"

    @property
    def parquet(self) -> ParquetAccess:
        return self._parquet

    def _get_list_of_strategies_with_capital_including_total(self) -> list:
        return self.parquet.get_all_identifiers_with_data_type(
            data_type=CAPITAL_COLLECTION
        )

    def get_capital_pd_df_for_strategy(self, strategy_name: str) -> pd.DataFrame:
        try:
            pd_df = self.parquet.read_data_given_data_type_and_identifier(
                data_type=CAPITAL_COLLECTION, identifier=strategy_name
            )
        except:
            raise missingData(
                "Unable to get capital data from parquet for strategy %s"
                % strategy_name
            )

        return pd_df

    def _delete_all_capital_for_strategy_no_checking(self, strategy_name: str):
        try:
            self.parquet.delete_data_given_data_type_and_identifier(
                data_type=CAPITAL_COLLECTION, identifier=strategy_name
            )
        except missingFile as mf:
            self.log.warning(
                f"Deleting old capital failed: {mf} - "
                f"this is ok if setting up capital for the first time"
            )

    def update_capital_pd_df_for_strategy(
        self, strategy_name: str, updated_capital_df: pd.DataFrame
    ):
        if len(updated_capital_df.columns) == 1:
            ## single strategy, need columns labelling
            updated_capital_df.columns = ["capital"]

        self.parquet.write_data_given_data_type_and_identifier(
            data_to_write=updated_capital_df,
            identifier=strategy_name,
            data_type=CAPITAL_COLLECTION,
        )
