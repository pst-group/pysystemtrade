# pysystemtrade

Systematic futures trading in python, using the systems developed by [Rob Carver](https://github.com/robcarver17/)

## Description

**pysystemtrade** is the open source version of Rob Carver's own backtesting and trading engine that implements systems according to the framework outlined in his book ["Systematic Trading"](https://www.systematicmoney.org/systematic-trading), which is further developed on [his blog](https://qoppac.blogspot.com) and in his [other books](https://www.systematicmoney.org/).

For a longer explanation of the motivation and point of this project see this [blog post.](https://qoppac.blogspot.com/2015/12/pysystemtrade.html)

Pysystemtrade is a....:
- Backtesting environment that Rob uses to test all the strategies in his various [books](https://www.systematicmoney.org)
- Which implements all the optimisation and system design principles in his books and on his blog.
- A fully automated system for futures trading (for interactive brokers)

pysystemtrade uses the [ib_async library](https://ib-api-reloaded.github.io/ib_async/api.html) to connect to interactive brokers.

## History

[Rob](https://github.com/robcarver17/) originally developed and open sourced the system in December 2015. In 2024 [Andy Geach](https://github.com/bug-or-feature) took over as primary maintainer of the project. In January 2026 Rob moved pysystemtrade to a new github "organisation", [pst-group](https://github.com/pst-group). The organisation is 'owned' by Andy and Rob. It is the intention that this organisation will always have at least two owners, which will ensure the project continues into the future in the event of Rob's demise or him losing his github token. 


## Use and documentation

[Introduction (start here)](docs/introduction.md)

[Backtesting user guide](docs/backtesting.md)

[Working with futures data](/docs/data.md)

[Connecting to interactive brokers](/docs/IB.md)

[Running as a production system](/docs/production.md)
 

## Dependencies

See the `project.dependencies` section in [pyproject.toml](pyproject.toml) for full details.


## Installation

This package isn't hosted on pypi.org. So to get the code the easiest way is to use git:

```
# clone the repo to your local filesystem
$ git clone https://github.com/pst-group/pysystemtrade.git

# navigate to the project directory
$ cd pysystemtrade

```

then install with `uv` (recommended)

```
# either install pysystemtrade only
$ uv sync --extra parquet

# or with development dependencies (editable mode by default) 
$ uv sync --extra parquet --extra dev
```

or with `pip`

```
# either install pysystemtrade only
$ python -m pip install '.[parquet]'

# or with development dependencies, in editable mode 
$ python -m pip install --editable '.[parquet, dev]'
```

There is a more complete installation guide [here](docs/installation.md)

### A note on support

This is an open source project, designed for people who are already comfortable using and writing python code, are capable of installing the dependencies, and who want a head start on implementing a system of their own.  If you need a higher level of support then you are better off with another project. If you have a question, or find a problem, read the [contribution guide](CONTRIBUTING.md) to understand the processes.

## Licensing and legal stuff

GNU v3
( See [LICENSE](LICENSE) )

Absolutely no warranty is implied with this product. Use at your own risk. No guarantee is provided that it will be profitable, or that it won't lose all your money very quickly, or delete every file on your computer (by the way: it's not *supposed* to do that. Just in case you thought it was). All financial trading offers the possibility of loss. Leveraged trading, such as futures trading, may result in you losing all your money, and still owing more. Backtested results are no guarantee of future performance. The owners of the project can take no responsibility for any losses caused by live trading using pysystemtrade. Use at your own risk. The owners of the project are not currently registered or authorised by any financial regulator. 


