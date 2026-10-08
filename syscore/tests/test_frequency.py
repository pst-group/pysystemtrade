import unittest

import numpy as np
import pandas as pd

from syscore.pandas.frequency import merge_data_with_different_freq


class TestMergeDataWithDifferentFreq(unittest.TestCase):
    def test_later_item_wins_on_shared_timestamp(self):
        # large enough that an unstable sort reorders tied timestamps
        hourly = pd.DataFrame(
            dict(FINAL=1.0),
            index=pd.date_range("2026-01-01", periods=24 * 60, freq="h"),
        )
        daily = pd.DataFrame(
            dict(FINAL=2.0),
            index=pd.date_range("2026-01-01 23:00", periods=60, freq="D"),
        )

        merged = merge_data_with_different_freq([hourly, daily])

        self.assertTrue(merged.index.is_unique)
        self.assertTrue(merged.index.is_monotonic_increasing)
        self.assertTrue((merged.loc[daily.index, "FINAL"] == 2.0).all())
        self.assertEqual(len(merged), len(hourly.index.union(daily.index)))

    def test_whole_row_wins_not_last_non_null_value(self):
        when = pd.Timestamp("2026-01-01 23:00")
        hourly = pd.DataFrame(dict(FINAL=[1.0], VOLUME=[10.0]), index=[when])
        daily = pd.DataFrame(dict(FINAL=[2.0], VOLUME=[np.nan]), index=[when])

        merged = merge_data_with_different_freq([hourly, daily])

        self.assertEqual(merged.loc[when, "FINAL"], 2.0)
        self.assertTrue(np.isnan(merged.loc[when, "VOLUME"]))


if __name__ == "__main__":
    unittest.main()
