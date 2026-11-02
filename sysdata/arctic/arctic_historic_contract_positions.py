import pandas as pd

from sysobjects.contracts import futuresContract, listOfFuturesContracts
from sysdata.arctic.arctic_connection import arcticData
from sysdata.production.historic_contract_positions import contractPositionData

from syscore.exceptions import missingData

from syslogging.logger import get_logger

CONTRACT_POSITION_COLLECTION = "contract_positions"


class arcticContractPositionData(contractPositionData):
    def __init__(self, mongo_db=None, log=get_logger("arcticContractPositionData")):
        super().__init__(log=log)

        self._arctic = arcticData(CONTRACT_POSITION_COLLECTION, mongo_db=mongo_db)

    def __repr__(self):
        return repr(self._arctic)

    @property
    def arctic(self):
        return self._arctic

    def _write_updated_position_series_for_contract_object(
        self, contract_object: futuresContract, updated_series: pd.Series
    ):
        ## overwrites what is there without checking
        ident = contract_object.key
        updated_data_as_df = pd.DataFrame(updated_series)
        updated_data_as_df.columns = ["position"]

        self.arctic.write(ident=ident, data=updated_data_as_df)

    def _delete_position_series_for_contract_object_without_checking(
        self, contract_object: futuresContract
    ):
        ident = contract_object.key
        self.arctic.delete(ident)

    def get_position_as_series_for_contract_object(
        self, contract_object: futuresContract
    ) -> pd.Series:
        keyname = contract_object.key
        try:
            pd_df = self.arctic.read(keyname)
        except:
            raise missingData

        return pd_df.iloc[:, 0]

    def get_list_of_contracts(self) -> listOfFuturesContracts:
        ## doesn't remove zero positions
        list_of_keys = self.arctic.get_keynames()
        list_of_futures_contract = [
            futuresContract.from_key(key) for key in list_of_keys
        ]

        return listOfFuturesContracts(list_of_futures_contract)
