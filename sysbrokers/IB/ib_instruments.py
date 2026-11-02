from dataclasses import dataclass
from typing import Union
from ib_async import Future

from sysobjects.instruments import futuresInstrument


def ib_futures_instrument_just_symbol(symbol):
    ibcontract = Future(symbol=symbol)
    return ibcontract


NOT_REQUIRED_FOR_IB = ""


@dataclass
class ibInstrumentConfigData:
    symbol: str
    exchange: str
    currency: str = NOT_REQUIRED_FOR_IB
    ibMultiplier: float = NOT_REQUIRED_FOR_IB
    priceMagnifier: float = 1.0
    ignoreWeekly: bool = False

    @property
    def effective_multiplier(self):
        # A blank IBMultiplier means the product has no single multiplier (it
        # varies by delivery month), so there is no effective one either
        if self.ibMultiplier is NOT_REQUIRED_FOR_IB:
            return NOT_REQUIRED_FOR_IB
        return self.ibMultiplier / self.priceMagnifier

    def __repr__(self):
        return (
            "symbol='%s', exchange='%s', currency='%s', ibMultiplier='%s', priceMagnifier='%.2f', "
            "ignoreWeekly='%s', effective_multiplier='%s'"
            % (
                self.symbol,
                self.exchange,
                self.currency,
                self.ibMultiplier,
                self.priceMagnifier,
                self.ignoreWeekly,
                _format_effective_multiplier(self.effective_multiplier),
            )
        )

    def as_dict(self):
        return dict(
            symbol=self.symbol,
            exchange=self.exchange,
            currency=self.currency,
            ibMultiplier=self.ibMultiplier,
            priceMagnifier=self.priceMagnifier,
            ignoreWeekly=self.ignoreWeekly,
            effective_multiplier=self.effective_multiplier,
        )


@dataclass
class futuresInstrumentWithIBConfigData(object):
    instrument: futuresInstrument
    ib_data: ibInstrumentConfigData

    @property
    def instrument_code(self):
        return self.instrument.instrument_code

    @property
    def broker_symbol(self):
        return self.ib_data.symbol

    @property
    ## FIXME make it look like a standard instrument, but we don't officially inherit... not sure why?
    def meta_data(self):
        return self.ib_data


def ib_futures_instrument(
    futures_instrument_with_ib_data: futuresInstrumentWithIBConfigData,
) -> Future:
    """
    Get an IB contract which is NOT specific to a contract date
    Used for getting expiry chains

    :param futures_instrument_with_ib_data: instrument with .metadata suitable for IB
    :return: IBcontract
    """

    ib_data = futures_instrument_with_ib_data.ib_data

    ibcontract = Future(ib_data.symbol, exchange=ib_data.exchange)

    if ib_data.ibMultiplier is NOT_REQUIRED_FOR_IB:
        pass
    else:
        ibcontract.multiplier = _resolve_multiplier(ib_data.ibMultiplier)

    if ib_data.currency is NOT_REQUIRED_FOR_IB:
        pass
    else:
        ibcontract.currency = ib_data.currency

    return ibcontract


def _format_effective_multiplier(effective_multiplier: Union[float, str]) -> str:
    if effective_multiplier is NOT_REQUIRED_FOR_IB:
        return effective_multiplier
    return "%.2f" % effective_multiplier


def _resolve_multiplier(multiplier_passed):
    multiplier = float(multiplier_passed)
    multiplier_is_round_number = round(multiplier) == multiplier
    if multiplier_is_round_number:
        multiplier = str(int(multiplier_passed))
    else:
        multiplier = str(multiplier_passed)

    return multiplier
