from dataclasses import dataclass

from sysdata.futures.futures_per_contract_prices import futuresContractPriceData
from sysobjects.futures_per_contract_prices import futuresContractPrices
from sysobjects.contracts import futuresContract, listOfFuturesContracts
from syslogging.logger import get_logger
from syscore.fileutils import (
    resolve_path_and_filename_for_package,
    files_with_extension_in_pathname,
)
from syscore.constants import arg_not_supplied
from syscore.dateutils import MIXED_FREQ, Frequency
from syscore.pandas.pdutils import pd_readcsv, DEFAULT_DATE_FORMAT_FOR_CSV


@dataclass
class ConfigCsvFuturesPrices:
    input_date_index_name: str = "DATETIME"
    input_date_format: str = DEFAULT_DATE_FORMAT_FOR_CSV
    input_column_mapping: dict = arg_not_supplied
    input_skiprows: int = 0
    input_skipfooter: int = 0
    apply_multiplier: float = 1.0
    apply_inverse: bool = False


class csvFuturesContractPriceData(futuresContractPriceData):
    """
        Class to read / write individual futures contract price data to and from csv files
    # no default datapath supplied as this is not normally used
    """

    def __init__(
        self,
        datapath=arg_not_supplied,
        log=get_logger("csvFuturesContractPriceData"),
        config: ConfigCsvFuturesPrices = arg_not_supplied,
    ):
        super().__init__(log=log)
        if datapath is arg_not_supplied:
            raise Exception("Need to pass datapath")
        self._datapath = datapath
        if config is arg_not_supplied:
            config = ConfigCsvFuturesPrices()

        self._config = config

    def __repr__(self):
        return "csvFuturesContractPricesData accessing %s" % self._datapath

    def _get_merged_prices_for_contract_object_no_checking(
        self, futures_contract_object: futuresContract
    ) -> futuresContractPrices:
        """
        Read back the prices for a given contract object

        :param futures_contract_object:  futuresContract
        :return: data
        """

        return self._get_prices_at_frequency_for_contract_object_no_checking(
            futures_contract_object=futures_contract_object, frequency=MIXED_FREQ
        )

    def _get_prices_at_frequency_for_contract_object_no_checking(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ) -> futuresContractPrices:
        keyname = self._keyname_given_contract_object_and_freq(
            futures_contract_object, frequency=frequency
        )
        filename = self._filename_given_key_name(keyname)
        config = self.config

        date_format = config.input_date_format
        date_time_column = config.input_date_index_name
        input_column_mapping = config.input_column_mapping
        skiprows = config.input_skiprows
        skipfooter = config.input_skipfooter
        multiplier = config.apply_multiplier
        inverse = config.apply_inverse

        try:
            instrpricedata = pd_readcsv(
                filename,
                date_index_name=date_time_column,
                date_format=date_format,
                input_column_mapping=input_column_mapping,
                skiprows=skiprows,
                skipfooter=skipfooter,
            )
        except OSError:
            self.log.warning(
                "Can't find adjusted price file %s" % filename,
                **futures_contract_object.log_attributes(),
                method="temp",
            )
            return futuresContractPrices.create_empty()

        instrpricedata = instrpricedata.groupby(level=0).last()
        for col_name in ["OPEN", "HIGH", "LOW", "FINAL"]:
            column_series = instrpricedata[col_name]
            if inverse:
                column_series = 1 / column_series
            column_series *= multiplier

        instrpricedata = futuresContractPrices(instrpricedata)

        return instrpricedata

    def _write_merged_prices_for_contract_object_no_checking(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
    ):
        """
        Write prices
        CHECK prices are overridden on second write

        :param futures_contract_object: futuresContract
        :param futures_price_data: futuresContractPriceData
        :return: None
        """
        self._write_prices_at_frequency_for_contract_object_no_checking(
            futures_contract_object=futures_contract_object,
            futures_price_data=futures_price_data,
            frequency=MIXED_FREQ,
        )

    def _write_prices_at_frequency_for_contract_object_no_checking(
        self,
        futures_contract_object: futuresContract,
        futures_price_data: futuresContractPrices,
        frequency: Frequency,
    ):
        keyname = self._keyname_given_contract_object_and_freq(
            futures_contract_object, frequency=frequency
        )
        filename = self._filename_given_key_name(keyname)
        futures_price_data.to_csv(
            filename, index_label=self.config.input_date_index_name
        )

    def _delete_merged_prices_for_contract_object_with_no_checks_be_careful(
        self, futures_contract_object: futuresContract
    ):
        raise NotImplementedError(
            "You can't delete futures prices stored as a csv - Add to overwrite existing data, or delete file manually"
        )

    def _delete_prices_at_frequency_for_contract_object_with_no_checks_be_careful(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ):
        raise NotImplementedError(
            "You can't delete futures prices stored as a csv - Add to overwrite existing data, or delete file manually"
        )

    def has_merged_price_data_for_contract(
        self, contract_object: futuresContract
    ) -> bool:
        return self.has_price_data_for_contract_at_frequency(
            contract_object, frequency=MIXED_FREQ
        )

    def has_price_data_for_contract_at_frequency(
        self, contract_object: futuresContract, frequency: Frequency
    ) -> bool:
        if (
            self._keyname_given_contract_object_and_freq(
                contract_object, frequency=frequency
            )
            in self._all_keynames_in_library()
        ):
            return True

    def get_contracts_with_merged_price_data(self) -> listOfFuturesContracts:
        """

        :return: list of contracts
        """

        return self.get_contracts_with_price_data_for_frequency(frequency=MIXED_FREQ)

    def get_contracts_with_price_data_for_frequency(
        self, frequency: Frequency
    ) -> listOfFuturesContracts:
        list_of_contract_and_freq_tuples = (
            self._get_contract_freq_tuples_with_price_data()
        )

        list_of_contracts = [
            futuresContract(contract_freq_tuple[1], contract_freq_tuple[2])
            for contract_freq_tuple in list_of_contract_and_freq_tuples
            if contract_freq_tuple[0] == frequency
        ]

        list_of_contracts = listOfFuturesContracts(list_of_contracts)

        return list_of_contracts

    def _get_contract_freq_tuples_with_price_data(self) -> list:
        """

        :return: list of futures contracts as tuples
        """

        all_keynames = self._all_keynames_in_library()
        list_of_contract_and_freq_tuples = [
            self._contract_tuple_and_freq_given_keyname(keyname)
            for keyname in all_keynames
        ]

        return list_of_contract_and_freq_tuples

    def _keyname_given_contract_object_and_freq(
        self, futures_contract_object: futuresContract, frequency: Frequency
    ) -> str:
        """
        We could do this using the .ident() method of instrument_object, but this way we keep control inside this class

        :param futures_contract_object: futuresContract
        :return: str
        """
        if frequency is MIXED_FREQ:
            frequency_str = ""
        else:
            frequency_str = frequency.name + "_"

        instrument_str = str(futures_contract_object.instrument)
        date_str = str(futures_contract_object.date_str)

        return "%s%s_%s" % (frequency_str, instrument_str, date_str)

    def _contract_tuple_and_freq_given_keyname(self, keyname: str) -> tuple:
        """
        Extract the two parts of a keyname

        We keep control of how we represent stuff inside the class

        :param keyname: str
        :return: tuple instrument_code, contract_date
        """
        if keyname.startswith("Day") or keyname.startswith("Hour"):
            ## has frequency
            index = keyname.find("_")
            frequency = Frequency[keyname[:index]]
            residual_keyname = keyname[index + 1 :]
        else:
            ## no frequency, mixed data
            frequency = MIXED_FREQ
            residual_keyname = keyname

        keyname_as_list = residual_keyname.split("_")

        if len(keyname_as_list) == 4:
            keyname_as_list = [
                "%s_%s_%s"
                % (keyname_as_list[0], keyname_as_list[1], keyname_as_list[2]),
                keyname_as_list[3],
            ]

        # It's possible to have GAS_US_20090700.csv, so we only take the second
        if len(keyname_as_list) == 3:
            keyname_as_list = [
                "%s_%s" % (keyname_as_list[0], keyname_as_list[1]),
                keyname_as_list[2],
            ]

        try:
            assert len(keyname_as_list) == 2
        except BaseException:
            self.log.error(
                "Keyname (filename) %s in wrong format should be instrument_contractid"
                % keyname
            )
        instrument_code, contract_date = tuple(keyname_as_list)

        return frequency, instrument_code, contract_date

    def _filename_given_key_name(self, keyname: str):
        return resolve_path_and_filename_for_package(
            self._datapath, "%s.csv" % (keyname)
        )

    def _all_keynames_in_library(self) -> list:
        return files_with_extension_in_pathname(self._datapath, ".csv")

    @property
    def config(self):
        return self._config

    @property
    def datapath(self):
        return self._datapath
