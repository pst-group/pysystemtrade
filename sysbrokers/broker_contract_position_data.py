from syslogging.logger import get_logger

from syscore.constants import arg_not_supplied

from sysdata.production.historic_contract_positions import contractPositionData
from sysdata.data_blob import dataBlob
from sysobjects.production.positions import listOfContractPositions


class brokerContractPositionData(contractPositionData):
    def __init__(
        self, data: dataBlob, log=get_logger("brokerFuturesContractPriceData")
    ):
        super().__init__(log=log)
        self._data = data

    def get_all_current_positions_as_list_with_contract_objects(
        self, account_id=arg_not_supplied
    ) -> listOfContractPositions:
        raise NotImplementedError

    def get_position_as_df_for_contract_object(self, *args, **kwargs):
        raise Exception("Only current position data available from broker")

    def update_position_for_contract_object(self, *args, **kwargs):
        raise Exception("Broker position data is read only")

    def delete_last_position_for_contract_object(self, *args, **kwargs):
        raise Exception("Broker position data is read only")

    def _get_series_for_args_dict(self, *args, **kwargs):
        raise Exception("Only current position data available from broker")

    def _update_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("Broker position data is read only")

    def _delete_last_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("Broker position data is read only")

    def _get_list_of_args_dict(self) -> list:
        raise Exception("Args dict not used for broker")

    def get_list_of_instruments_with_any_position(self):
        raise Exception("Not implemented for broker")

    @property
    def data(self):
        return self._data
