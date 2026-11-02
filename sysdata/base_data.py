from syslogging.logger import get_logger


class baseData(object):
    """
    Core data object - Base class

    simData objects are used to get data from a particular source, and give certain information about it

    The baseData class is highly generic

    Normally we'd inherit from this for specific implementations (eg simulation, production for different data types),
      specific asset classes (eg carry data for futures), and then for a
      specific source of data (eg csv files, databases, ...)

    The inheritance is:

    Base generic class: simData
    -> implementation specific eg simData for simulation
    -> asset class specific eg futuresdata.FuturesData
    -> source specific eg legacy.csvFuturesSimData

    """

    def __init__(self, log=get_logger("baseData")):
        """
        simData socket base class

        >>> data = baseData()
        >>> data
        simData object
        """

        self._log = log

    def __repr__(self):
        return "baseData object"

    @property
    def log(self):
        return self._log

    def __getitem__(self, keyname):
        """
         convenience method to get the price, make it look like a dict

        :param keyname: instrument to get prices for
        :type keyname: str

        :returns: pd.DataFrame
        """

        raise Exception(
            "__getitem__ not defined for baseData class: use a class where it has been overridden"
        )

    def keys(self):
        """
        list of things in this data set (futures contracts, instruments...)

        :returns: list of str

        >>> data=simData()
        >>> data.keys()
        []
        """

        raise Exception(
            "keys() not defined for baseData class: use a class where it has been overridden"
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
