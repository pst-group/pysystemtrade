"""
Created on 14 Dec 2015

@author: rob
"""

import unittest
from systems.stage import SystemStage
from systems.basesystem import System
from sysdata.sim.sim_data import simData
from sysdata.config.configdata import Config


class Test(unittest.TestCase):
    def setUp(self):
        class testStage(SystemStage):
            @property
            def name(self):
                return "test"

        stage = testStage()
        data = simData()
        config = Config(dict(instruments=["another_code", "code"]))
        system = System([stage], data=data, config=config)
        self.system = system

    @unittest.SkipTest
    def test_quicktest(self):
        system = self.system
        instrument_list = system.get_instrument_list()
        self.assertEqual(instrument_list, ["another_code", "code"])

        # get instrument list lives in cache
        self.assertEqual(3, len(system.cache))
        self.assertEqual(system, system.test.parent)


if __name__ == "__main__":
    unittest.main()
