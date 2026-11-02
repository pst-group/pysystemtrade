from syscore.objects import get_methods
from syslogging import STAGE_LOG_LABEL
from syslogging.logger import get_logger
from systems.basesystem import System


class SystemStage(object):
    """
    Default stage object:  we inherit from this, rather than use 'in the raw'

    Here is the standard header to use for stages:

    Create a SystemStage for doing something


    KEY INPUT: system.....method(args)
                found in self.method(args)

    KEY OUTPUT: system.stage_name.method(args)

    Name: stage_name
    """

    @property
    def name(self):
        return "Need to replace method when inheriting"

    def __repr__(self):
        return "SystemStage '%s' Try %s.methods()" % (
            self.name,
            self.name,
        )

    def methods(self):
        return get_methods(self)

    def system_init(self, system: System):
        # method called once we have a system
        self._parent = system

        # and a log
        self._log = get_logger("base_system", {STAGE_LOG_LABEL: self.name})

    @property
    def log(self):
        log = getattr(
            self, "_log", get_logger("base_system", {STAGE_LOG_LABEL: self.name})
        )
        return log

    @property
    def parent(self) -> System:
        parent = getattr(self, "_parent", None)
        return parent
