"""
Created on 2 Dec 2015

@author: rob
"""

import unittest
import pandas as pd
import numpy as np


class Test(unittest.TestCase):
    @unittest.SkipTest
    def test_divide_df_single_column(self):
        x = pd.DataFrame(
            dict(a=[2.0, 7.0, -7.0, -7.00, 3.5]),
            pd.date_range(pd.datetime(2015, 1, 1), periods=5),
        )
        y = pd.DataFrame(
            dict(b=[2.0, 3.5, 2.0, -3.5, -3.5]),
            pd.date_range(pd.datetime(2015, 1, 1), periods=5),
        )
        ans = list(divide_df_single_column(x, y).iloc[:, 0])
        self.assertEqual(ans, [1.0, 2.0, -3.5, 2.0, -1.0])

        x = pd.DataFrame(
            dict(a=[2.0, np.nan, -7.0, np.nan, 3.5]),
            pd.date_range(pd.datetime(2015, 1, 1), periods=5),
        )
        y = pd.DataFrame(
            dict(b=[2.0, 3.5, np.nan, np.nan, -3.5]),
            pd.date_range(pd.datetime(2015, 1, 2), periods=5),
        )

        ans = list(divide_df_single_column(x, y).iloc[:, 0])

        self.assertTrue(np.isnan(ans[0]))
        self.assertTrue(np.isnan(ans[1]))
        self.assertTrue(np.isnan(ans[3]))

        self.assertEqual(ans[2], -2.0)

        ans = list(divide_df_single_column(x, y, ffill=(True, False)).iloc[:, 0])
        self.assertEqual(ans[1], 1.0)

        ans = list(divide_df_single_column(x, y, ffill=(False, True)).iloc[:, 0])
        self.assertEqual(ans[4], 1.0)

        ans = list(divide_df_single_column(x, y, ffill=(True, True)).iloc[:, 0])
        self.assertEqual(list(ans)[1:], [1.0, -2.0, -2.0, 1.0, -1.0])

    def multiply_df_single_column(self):
        pass

    def multiply_df(self):
        pass


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
