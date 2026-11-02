"""
Created on 27 Nov 2015

@author: rob
"""

import unittest as ut
import pandas as pd


class Test(ut.TestCase):
    def test_data(self):
        x = pd.DataFrame(
            dict(
                CARRY_CONTRACT=[
                    "",
                    "201501",
                    "",
                    "201501",
                    "20150101",
                    "20150101",
                    "201501",
                ],
                PRICE_CONTRACT=[
                    "",
                    "",
                    "201504",
                    "201504",
                    "201504",
                    "20150115",
                    "201406",
                ],
            )
        )

        assert len(x) == 7


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.test_robust_vol_calc']
    ut.main()
