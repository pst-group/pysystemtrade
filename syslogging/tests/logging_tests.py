import pytest
import logging
from syslogging import CURRENCY_CODE_LOG_LABEL
from syslogging.logger import get_logger
from sysobjects.contracts import futuresContract


class TestLogging:
    def test_name(self, caplog):
        logger = get_logger("my_type")
        assert logger.name == "my_type"
        assert logger.getEffectiveLevel() == logging.DEBUG

        logger.info("foo %s", "bar")
        assert caplog.record_tuples == [("my_type", logging.INFO, "foo bar")]

    def test_attributes_good(self, caplog):
        logger = get_logger("my_type", {"stage": "bar"})
        logger.warning("foo %s", "bar")
        assert caplog.record_tuples == [
            ("my_type", logging.WARNING, "{'stage': 'bar'} foo bar")
        ]

    def test_attributes_bad(self):
        with pytest.raises(Exception):
            get_logger("my_type", {"foo": "bar"})

    def test_no_name_no_attributes(self, caplog):
        logger = get_logger("")
        logger.warning("foo")
        assert caplog.record_tuples == [("root", logging.WARNING, "foo")]

    def test_attributes_clear(self, caplog):
        clear = get_logger("Clear", {"stage": "first", "type": "one"})
        clear.info("Clearing attributes", method="clear")
        assert caplog.record_tuples == [("Clear", logging.INFO, "Clearing attributes")]
        caplog.clear()
        clear.info("Clearing attributes", method="clear", stage="second")
        assert caplog.record_tuples == [
            ("Clear", logging.INFO, "{'stage': 'second'} Clearing attributes")
        ]

    def test_attributes_reset(self, caplog):
        reset = get_logger("reset")
        reset.info("Updating log attributes", **{"instrument_code": "GOLD"})
        assert caplog.record_tuples[0] == (
            "reset",
            logging.INFO,
            "{'instrument_code': 'GOLD'} Updating log attributes",
        )
        reset.info("Log attributes reset", **{"method": "clear"})
        assert caplog.record_tuples[1] == (
            "reset",
            logging.INFO,
            "Log attributes reset",
        )

    def test_attributes_preserve(self, caplog):
        preserve = get_logger("Preserve", {"stage": "first"})
        preserve.info(
            "Preserving attributes", method="preserve", type="one", stage="second"
        )
        assert caplog.record_tuples == [
            (
                "Preserve",
                logging.INFO,
                "{'type': 'one', 'stage': 'first'} Preserving attributes",
            )
        ]

    def test_attributes_overwrite(self, caplog):
        overwrite = get_logger("Overwrite", {"stage": "first"})
        overwrite.info(
            "Overwriting attributes", method="overwrite", type="one", stage="second"
        )
        assert caplog.record_tuples == [
            (
                "Overwrite",
                logging.INFO,
                "{'stage': 'second', 'type': 'one'} Overwriting attributes",
            )
        ]

    def test_attributes_temp(self, caplog):
        temp = get_logger("temp", {"stage": "first"})
        temp.info("setting temp 'type' attribute", method="temp", type="one")
        assert caplog.record_tuples[0] == (
            "temp",
            logging.INFO,
            "{'stage': 'first', 'type': 'one'} setting temp 'type' attribute",
        )
        temp.info("no type attribute")
        assert caplog.record_tuples[1] == (
            "temp",
            logging.INFO,
            "{'stage': 'first'} no type attribute",
        )

    def test_contract_log_attributes(self, caplog):
        contract_logger = get_logger("contract")
        contract = futuresContract(
            instrument_object="AUD", contract_date_object="20231200"
        )
        log_attrs = contract.log_attributes()
        contract_logger.info(
            "setting temp contract attributes", **log_attrs, method="temp"
        )
        assert caplog.record_tuples[0] == (
            "contract",
            logging.INFO,
            "{'instrument_code': 'AUD', 'contract_date': '20231200'} setting temp "
            "contract attributes",
        )
        contract_logger.info("no contract attributes")
        assert caplog.record_tuples[1] == (
            "contract",
            logging.INFO,
            "no contract attributes",
        )

    def test_contract_log_attributes_inline(self, caplog):
        contract_inline = get_logger("contract_inline")
        contract = futuresContract(
            instrument_object="AUD", contract_date_object="20231200"
        )
        contract_inline.info(
            "setting temp contract attributes inline",
            **contract.log_attributes(),
            method="temp",
        )
        assert caplog.record_tuples[0] == (
            "contract_inline",
            logging.INFO,
            "{'instrument_code': 'AUD', 'contract_date': '20231200'} setting temp "
            "contract attributes inline",
        )
        contract_inline.info("no contract attributes")
        assert caplog.record_tuples[1] == (
            "contract_inline",
            logging.INFO,
            "no contract attributes",
        )

    def test_fx_log_attributes(self, caplog):
        fx = get_logger("fx")
        fx.info(
            "setting temp fx attributes inline",
            **{CURRENCY_CODE_LOG_LABEL: "USDAUD", "method": "temp"},
        )
        assert caplog.record_tuples[0] == (
            "fx",
            logging.INFO,
            "{'currency_code': 'USDAUD'} setting temp fx attributes inline",
        )
        fx.info("no contract attributes")
        assert caplog.record_tuples[1] == (
            "fx",
            logging.INFO,
            "no contract attributes",
        )
