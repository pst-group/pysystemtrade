import pandas as pd

from sysobjects.contracts import futuresContract, listOfFuturesContracts
from sysdata.parquet.parquet_access import ParquetAccess

from sysdata.production.historic_contract_positions import contractPositionData

from syscore.exceptions import missingData

from syslogging.logger import get_logger

CONTRACT_POSITION_COLLECTION = "contract_positions"


class parquetContractPositionData(contractPositionData):
    def __init__(
        self,
        parquet_access: ParquetAccess,
        log=get_logger("parquetContractPositionData"),
    ):
        super().__init__(log=log)

        self._parquet = parquet_access

    def __repr__(self):
        return "parquetContractPositionData"

    @property
    def parquet(self):
        return self._parquet

    def _write_updated_position_series_for_contract_object(
        self, contract_object: futuresContract, updated_series: pd.Series
    ):
        ## overwrites what is there without checking
        ident = from_contract_to_key(contract_object)
        updated_data_as_df = pd.DataFrame(updated_series)
        updated_data_as_df.columns = ["position"]

        self.parquet.write_data_given_data_type_and_identifier(
            data_to_write=updated_data_as_df,
            identifier=ident,
            data_type=CONTRACT_POSITION_COLLECTION,
        )

    def _delete_position_series_for_contract_object_without_checking(
        self, contract_object: futuresContract
    ):
        ident = from_contract_to_key(contract_object)
        self.parquet.delete_data_given_data_type_and_identifier(
            data_type=CONTRACT_POSITION_COLLECTION, identifier=ident
        )

    def get_position_as_series_for_contract_object(
        self, contract_object: futuresContract
    ) -> pd.Series:
        keyname = from_contract_to_key(contract_object)
        try:
            pd_df = self.parquet.read_data_given_data_type_and_identifier(
                data_type=CONTRACT_POSITION_COLLECTION, identifier=keyname
            )
        except:
            raise missingData

        return pd_df.iloc[:, 0]

    def get_list_of_contracts(self) -> listOfFuturesContracts:
        ## doesn't remove zero positions
        list_of_keys = self.parquet.get_all_identifiers_with_data_type(
            data_type=CONTRACT_POSITION_COLLECTION
        )
        list_of_futures_contract = [from_key_to_contract(key) for key in list_of_keys]

        return listOfFuturesContracts(list_of_futures_contract)


def from_contract_to_key(contract: futuresContract) -> str:
    return str(contract.instrument_code) + "#" + str(contract.contract_date)


def from_key_to_contract(key: str) -> futuresContract:
    [instrument_code, contract_date] = key.split("#")
    return futuresContract(instrument_code, contract_date)
