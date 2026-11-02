from syscore.exceptions import missingContract
from syslogging.logger import get_logger
from sysbrokers.IB.ib_futures_contracts_data import ibFuturesContractData
from sysdata.data_blob import dataBlob
from sysbrokers.IB.client.ib_positions_client import ibPositionsClient
from sysbrokers.IB.ib_instruments_data import ibFuturesInstrumentData
from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.broker_contract_position_data import brokerContractPositionData

from syscore.constants import arg_not_supplied

from sysobjects.production.positions import contractPosition, listOfContractPositions
from sysobjects.contracts import futuresContract


class ibContractPositionData(brokerContractPositionData):
    def __init__(
        self,
        ibconnection: connectionIB,
        data: dataBlob,
        log=get_logger("ibContractPositionData"),
    ):
        super().__init__(log=log, data=data)
        self._ibconnection = ibconnection

    @property
    def ibconnection(self) -> connectionIB:
        return self._ibconnection

    @property
    def ib_client(self) -> ibPositionsClient:
        client = getattr(self, "_ib_client", None)
        if client is None:
            client = self._ib_client = ibPositionsClient(
                ibconnection=self.ibconnection, log=self.log
            )

        return client

    def __repr__(self):
        return "IB Futures per contract position data %s" % str(self.ib_client)

    @property
    def futures_contract_data(self) -> ibFuturesContractData:
        return self.data.broker_futures_contract

    @property
    def futures_instrument_data(self) -> ibFuturesInstrumentData:
        return self.data.broker_futures_instrument

    def get_all_current_positions_as_list_with_contract_objects(
        self, account_id=arg_not_supplied
    ) -> listOfContractPositions:
        all_positions = self._get_all_futures_positions_as_raw_list(
            account_id=account_id
        )
        current_positions = []
        for position_entry in all_positions:
            try:
                contract_position_object = self._get_contract_position_for_raw_entry(
                    position_entry
                )
            except missingContract:
                continue
            else:
                current_positions.append(contract_position_object)

        list_of_contract_positions = listOfContractPositions(current_positions)

        list_of_contract_positions_no_duplicates = (
            list_of_contract_positions.sum_for_contract()
        )

        return list_of_contract_positions_no_duplicates

    def _get_contract_position_for_raw_entry(self, position_entry) -> contractPosition:
        position = position_entry["position"]
        if position == 0:
            raise missingContract

        expiry = position_entry["expiry"]
        instrument_code = self._get_instrument_code_from_ib_position_entry(
            position_entry
        )
        contract = futuresContract(instrument_code, expiry)

        contract_position_object = contractPosition(position, contract)

        return contract_position_object

    def _get_instrument_code_from_ib_position_entry(self, position_entry) -> str:
        ib_contract = position_entry["ib_contract"]
        instrument_code = self.futures_instrument_data.get_instrument_code_from_broker_contract_object(
            ib_contract
        )

        return instrument_code

    def _get_all_futures_positions_as_raw_list(
        self, account_id: str = arg_not_supplied
    ) -> list:
        self.ib_client.refresh()
        all_positions = self.ib_client.broker_get_positions(account_id=account_id)
        positions = all_positions.get("FUT", [])

        return positions

    def get_position_as_df_for_contract_object(self, *args, **kwargs):
        raise Exception("Only current position data available from IB")

    def update_position_for_contract_object(self, *args, **kwargs):
        raise Exception("IB position data is read only")

    def delete_last_position_for_contract_object(self, *args, **kwargs):
        raise Exception("IB position data is read only")

    def _get_series_for_args_dict(self, *args, **kwargs):
        raise Exception("Only current position data available from IB")

    def _update_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("IB position data is read only")

    def _delete_last_entry_for_args_dict(self, *args, **kwargs):
        raise Exception("IB position data is read only")

    def _get_list_of_args_dict(self) -> list:
        raise Exception("Args dict not used for IB")

    def get_list_of_instruments_with_any_position(self):
        raise Exception("Not implemented for IB")
