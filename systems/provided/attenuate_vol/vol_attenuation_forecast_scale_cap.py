import numpy as np
import pandas as pd

from syscore.pandas.strategy_functions import quantile_of_points_in_data_series
from syscore.pandas.pdutils import from_scalar_values_to_ts
from systems.forecast_scale_cap import ForecastScaleCap
from systems.system_cache import input, diagnostic


class volAttenForecastScaleCap(ForecastScaleCap):
    @diagnostic()
    def get_vol_quantile_points(self, instrument_code):
        ## More properly this would go in raw data perhaps
        self.log.debug("Calculating vol quantile for %s" % instrument_code)
        daily_vol = self.parent.rawdata.get_daily_percentage_volatility(instrument_code)
        ten_year_vol = daily_vol.rolling(2500, min_periods=10).mean()
        normalised_vol = daily_vol / ten_year_vol

        normalised_vol_q = quantile_of_points_in_data_series(normalised_vol)

        return normalised_vol_q

    @diagnostic()
    def get_vol_attenuation(self, instrument_code):
        normalised_vol_q = self.get_vol_quantile_points(instrument_code)
        vol_attenuation = normalised_vol_q.apply(multiplier_function)

        smoothed_vol_attenuation = vol_attenuation.ewm(span=10).mean()

        return smoothed_vol_attenuation

    @input
    def get_raw_forecast_before_attenuation(self, instrument_code, rule_variation_name):
        ## original code for get_raw_forecast
        raw_forecast = self.parent.rules.get_raw_forecast(
            instrument_code, rule_variation_name
        )

        return raw_forecast

    @diagnostic()
    def get_raw_forecast(self, instrument_code, rule_variation_name):
        ## overridden method this will be called downstream so don't change name
        raw_forecast_before_atten = self.get_raw_forecast_before_attenuation(
            instrument_code, rule_variation_name
        )
        vol_attenutation_reindex = (
            self.get_attenuation_for_rule_and_instrument_indexed_to_forecast(
                instrument_code=instrument_code, rule_variation_name=rule_variation_name
            )
        )

        attenuated_forecast = raw_forecast_before_atten * vol_attenutation_reindex

        return attenuated_forecast

    @diagnostic()
    def get_attenuation_for_rule_and_instrument_indexed_to_forecast(
        self, instrument_code, rule_variation_name
    ) -> pd.Series:
        raw_forecast_before_atten = self.get_raw_forecast_before_attenuation(
            instrument_code, rule_variation_name
        )

        use_attenuation = self.config.get_element_or_default("use_attenuation", [])

        if rule_variation_name not in use_attenuation:
            forecast_ts = raw_forecast_before_atten.index
            return from_scalar_values_to_ts(1.0, forecast_ts)

        vol_attenutation = self.get_vol_attenuation(instrument_code)
        vol_attenutation_reindex = vol_attenutation.reindex(
            raw_forecast_before_atten.index, method="ffill"
        )

        return vol_attenutation_reindex


# this is a little slow so suggestions for speeding up are welcome


def multiplier_function(vol_quantile):
    if np.isnan(vol_quantile):
        return 1.0

    return 2 - 1.5 * vol_quantile
