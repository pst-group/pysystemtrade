from pathlib import Path
import os
import sys
import socket
import logging.config
import syslogging
from syslogging.adapter import DynamicAttributeLogger
from syslogging.filters import IBFilter
from syslogging.pyyaml_env import parse_config
from syscore.fileutils import resolve_path_and_filename_for_package

CONFIG_ENV_VAR = "PYSYS_LOGGING_CONFIG"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def get_logger(name, attributes=None):
    """
    # set up a logger with a name
    log = get_logger("my_logger")

    # create a log message with a logging level
    log.debug("debug message")
    log.info("info message")
    log.warning("warning message")
    log.error("error message")
    log.critical("critical message")

    # parameterise the message
    log.info("Hello %s", "world")
    log.info("Goodbye %s %s", "cruel", "world")

    # setting attributes on initialisation
    log = get_logger("attributes", {"stage": "first"})

    # setting attributes on message creation
    log.info("logging call attributes", instrument_code="GOLD")

    # merging attributes: method 'overwrite' (default if no method supplied)
    overwrite = get_logger("Overwrite", {"type": "first"})
    overwrite.info("overwrite, type 'first'")
    overwrite.info(
        "overwrite, type 'second', stage 'one'",
        method="overwrite",
        type="second",
        stage="one",
    )

    # merging attributes: method 'preserve'
    preserve = get_logger("Preserve", {"type": "first"})
    preserve.info("preserve, type 'first'")
    preserve.info(
        "preserve, type 'first', stage 'one'", method="preserve", type="second", stage="one"
    )

    # merging attributes: method 'clear'
    clear = get_logger("Clear", {"type": "first", "stage": "one"})
    clear.info("clear, type 'first', stage 'one'")
    clear.info("clear, type 'second', no stage", method="clear", type="second")
    clear.info("clear, no attributes", method="clear")

    :param name: logger name
    :type name: str
    :param attributes: log attributes
    :type attributes: dict
    :return: logger instance
    :rtype: DynamicAttributeLogger
    """
    if not syslogging.logging_configured:
        _configure_logging()
    if not name:
        if attributes and "type" in attributes:
            name = attributes["type"]
    return DynamicAttributeLogger(logging.getLogger(name), attributes)


def _configure_logging():
    logging_config_path = os.getenv(CONFIG_ENV_VAR, None)
    if logging_config_path:
        _configure_prod(logging_config_path)
    else:
        _configure_sim()


def _configure_sim():
    print("Configuring sim logging")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(IBFilter())
    logging.getLogger("arctic").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.INFO)
    logging.basicConfig(
        handlers=[handler],
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )
    syslogging.logging_configured = True


def _configure_prod(logging_config_file):
    print(f"Attempting to configure prod logging from {logging_config_file}")
    config_path = resolve_path_and_filename_for_package(logging_config_file)
    if Path(config_path).exists():
        try:
            config = parse_config(path=config_path)
            try:
                host, port = _get_log_server_config(config)
            except KeyError:
                print("No log server configured")
            else:
                try:
                    _check_log_server(host, port)
                except BlockingIOError:
                    print(f"Log server detected OK at {host}:{port}")
                except (ConnectionResetError, ConnectionRefusedError):
                    print(
                        f"Cannot connect to log server at {host}:{port}, is it running?"
                    )
                    raise
            logging.config.dictConfig(config)
            syslogging.logging_configured = True
        except Exception as exc:
            print(f"ERROR: Problem configuring prod logging, reverting to sim: {exc}")
            _configure_sim()
    else:
        print(f"ERROR: prod logging config '{config_path}' not found, reverting to sim")
        _configure_sim()


def _get_log_server_config(config):
    handler = config["handlers"]["socket"]
    return handler["host"], handler["port"]


def _check_log_server(host, port):
    # https://stackoverflow.com/questions/48024720/python-how-to-check-if-socket-is-still-connected
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    # this will try to read bytes without blocking and also without removing them
    # from buffer (peek only). If a BlockingIOError is raised, we know the socket
    # is open
    data = sock.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
    if len(data) == 0:
        raise Exception("Unexpected data length")
