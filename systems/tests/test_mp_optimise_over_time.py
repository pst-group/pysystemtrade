"""
Created on 09 Jan 2022

@author: JLangle
"""

import unittest
from sysquant.optimisation.optimise_over_time import optimiseWeightsOverTime
from sysquant.returns import returnsForOptimisation
from sysdata.config.configdata import Config

import pandas as pd
import numpy as np
from time import time
import pickle as pkl


class Test(unittest.TestCase):
    def setUp(self):
        index = pd.bdate_range(start="1/1/2000", end="1/08/2020")
        data = np.random.normal(0, 1, (len(index), 20))
        net_returns_df = pd.DataFrame(index=index, data=data)

        self.net_returns = returnsForOptimisation(net_returns_df)

    def test_pickling(self):
        # multiprocessing needs to pickle; make sure the derived class attributes get set when unpickling

        # pickle
        net_returns_pkl_s = pkl.dumps(self.net_returns)

        # unpickle
        net_returns = pkl.loads(net_returns_pkl_s)

        # attributes after unpicking
        attrs_after = net_returns.__dict__.keys()

        self.assertTrue("_pooled_length" in attrs_after)
        self.assertTrue("_frequency" in attrs_after)

    def test_mp_optimisation(self):
        config = Config()

        weighting_params = config.default_config_dict["forecast_weight_estimate"]

        n_threads = 8
        weighting_params["n_threads"] = n_threads  # running from a Pool of threads

        start_time1 = time()
        weights1 = optimiseWeightsOverTime(
            self.net_returns, **weighting_params
        ).weights()
        stop_time1 = time()

        del weighting_params[
            "n_threads"
        ]  # running in main process, not separate process

        start_time2 = time()
        weights2 = optimiseWeightsOverTime(
            self.net_returns, **weighting_params
        ).weights()
        stop_time2 = time()

        print(f"Takes {stop_time1 - start_time1} seconds with {n_threads} processes")
        print(f"Takes {stop_time2 - start_time2} seconds running in main process")

        self.assertTrue(weights1.equals(weights2))


if __name__ == "__main__":
    unittest.main()
