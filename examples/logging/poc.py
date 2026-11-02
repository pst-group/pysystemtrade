import logging
from syslogging.logger import get_logger

# default LoggerAdapter functionality
first = get_logger("Foo")
second = get_logger("Foo")
assert first is not second
assert first.logger is second.logger

# params
param_logger = get_logger("Params")
param_logger.warning("Hello %s", "world")
param_logger.info("Goodbye %s %s", "cruel", "world")

# exc_info
err_logger = get_logger("Err")
my_dict = dict()
try:
    var = my_dict["foo"]
except KeyError:
    err_logger.error("Oops, logging exception", exc_info=True)

# stack_info
stack_logger = get_logger("Stack")
try:
    var = my_dict["foo"]
except KeyError:
    err_logger.error("Oops, logging stack", stack_info=True)

# exc_info and stack_info
both_logger = get_logger("Both")
try:
    var = my_dict["foo"]
except KeyError:
    err_logger.error("Oops, logging both", exc_info=True, stack_info=True)

# now DynamicAttributeLogger stuff

# simple, no attributes
no_attrs_logger = get_logger("No_Attributes")
no_attrs_logger.info("No attributes")

# with attributes
attrs_logger = get_logger("Attributes", {"type": "attrs"})
attrs_logger.info("initialisation attributes")
attrs_logger.info("logging call attributes", instrument_code="GOLD")

# merging attributes: method 'clear'
clear = get_logger("Clear", {"type": "first", "stage": "one"})
clear.info("clear, type 'first', stage 'one'")
clear.info("clear, type 'second', no stage", method="clear", type="second")
clear.info("clear, no attributes", method="clear")

# merging attributes: method 'preserve'
preserve = get_logger("Preserve", {"type": "first"})
preserve.info("preserve, type 'first'")
preserve.info(
    "preserve, type 'first', stage 'one'", method="preserve", type="second", stage="one"
)

# merging attributes: method 'overwrite'
overwrite = get_logger("Overwrite", {"type": "first"})
overwrite.info("overwrite, type 'first'")
overwrite.info(
    "overwrite, type 'second', stage 'one'",
    method="overwrite",
    type="second",
    stage="one",
)

# merging attributes: method 'temp'
temp = get_logger("temp", {"type": "first"})
temp.info("type should be 'first'")
temp.info(
    "type should be 'second' temporarily",
    method="temp",
    type="second",
)
temp.info("type should be back to 'first'")

# levels
level = get_logger("Level")
level.setLevel(logging.WARNING)
level.info("does not print")
level.warning("does print")

# replacing log.label() - we want to update the log attributes permanently - same as
# overwrite
label = get_logger("label", {"stage": "whatever"})
label.info("Should have 'stage' of 'whatever'")
label.info("Updating log attributes", instrument_code="GOLD")
label.info("Should have 'stage' of 'whatever', and 'instrument_code' 'GOLD'")


# critical mail
# level.critical("sends mail")
