This document is specifically about using pysystemtrade for *live production trading*.

This includes:

1. Getting prices
2. Generating desired trades
3. Executing trades
4. Getting accounting information

Related documents (which you should read before this one!):

- [Backtesting with pysystemtrade](/docs/backtesting.md)
- [Storing futures and spot FX data](/docs/data.md)
- [Connecting pysystemtrade to interactive brokers](/docs/IB.md)

And documents you should read after this one:

- [Instruments](/docs/instruments.md)
- [Dashboard and monitor](/docs/dashboard_and_monitor.md)
- [Production strategy changes](/docs/production_strategy_changes.md)

*IMPORTANT: Make sure you know what you are doing. All financial trading offers the possibility of loss. Leveraged trading, such as futures trading, may result in you losing all your money, and still owing more. Backtested results are no guarantee of future performance. No warranty is offered or implied for this software. I can take no responsibility for any losses caused by live trading using pysystemtrade. Use at your own risk.*


Table of Contents
=================

<!--ts-->
* [Table of Contents](#table-of-contents)
* [Quick start guide](#quick-start-guide)
* [Production system data flow](#production-system-data-flow)
* [Overview of a production system](#overview-of-a-production-system)
   * [Implementation options](#implementation-options)
      * [Automation options](#automation-options)
      * [Machines, containers and clouds](#machines-containers-and-clouds)
      * [Backup machine](#backup-machine)
      * [Multiple systems](#multiple-systems)
   * [Code and configuration management](#code-and-configuration-management)
      * [Managing your separate directories of code and configuration](#managing-your-separate-directories-of-code-and-configuration)
      * [Managing your private directory](#managing-your-private-directory)
      * [Custom private directory](#custom-private-directory)
   * [Finalise your backtest configuration](#finalise-your-backtest-configuration)
   * [Linking to a broker](#linking-to-a-broker)
   * [Other data sources](#other-data-sources)
   * [Data storage](#data-storage)
      * [Arctic](#arctic)
         * [Using Arctic in production instead of Parquet](#using-arctic-in-production-instead-of-parquet)
   * [Data backup](#data-backup)
      * [MongoDB data](#mongodb-data)
      * [Parquet data](#parquet-data)
      * [MongoDB / CSV data](#mongodb--csv-data)
   * [Echos, Logging, diagnostics and reporting](#echos-logging-diagnostics-and-reporting)
      * [Echos: stdout output](#echos-stdout-output)
         * [Cleaning old echo files](#cleaning-old-echo-files)
      * [Logging](#logging)
      * [socket](#socket)
         * [socket server as a service](#socket-server-as-a-service)
      * [console](#console)
      * [email](#email)
         * [Adding logging to your code](#adding-logging-to-your-code)
         * [Examples](#examples)
         * [Cleaning old logs](#cleaning-old-logs)
            * [Echos](#echos)
            * [Logs](#logs)
      * [psysystemtrade reports](#psysystemtrade-reports)
* [Positions and order levels](#positions-and-order-levels)
   * [Instrument level](#instrument-level)
   * [Contract level](#contract-level)
   * [Broker level](#broker-level)
* [The journey of an order](#the-journey-of-an-order)
   * [Optimal positions](#optimal-positions)
      * [Optimal position for roll orders](#optimal-position-for-roll-orders)
   * [Strategy order handling](#strategy-order-handling)
      * [Instrument orders in detail:](#instrument-orders-in-detail)
      * [Strategy order handling for roll orders](#strategy-order-handling-for-roll-orders)
      * [Overrides](#overrides)
   * [Stack handler](#stack-handler)
   * [Contract order creation](#contract-order-creation)
      * [Contract order creation - normal orders](#contract-order-creation---normal-orders)
      * [Contract order creation - passive roll status](#contract-order-creation---passive-roll-status)
      * [Instrument and contract order creation - active roll orders](#instrument-and-contract-order-creation---active-roll-orders)
   * [Manual trades](#manual-trades)
   * [Broker order creation and execution](#broker-order-creation-and-execution)
      * [Before an order is traded](#before-an-order-is-traded)
      * [Trading algos](#trading-algos)
      * [Pre-order preparation in the trading algo.](#pre-order-preparation-in-the-trading-algo)
      * [Broker order characteristics](#broker-order-characteristics)
      * [Order execution in the sysbroker code](#order-execution-in-the-sysbroker-code)
      * [Adding the broker trade to the database](#adding-the-broker-trade-to-the-database)
      * [Managing the trade](#managing-the-trade)
   * [After execution: fills and completions](#after-execution-fills-and-completions)
   * [Fills and completions](#fills-and-completions)
      * [Broker order fills](#broker-order-fills)
      * [An aside, what happens if fills happen later?](#an-aside-what-happens-if-fills-happen-later)
      * [Contract order fills and position updates](#contract-order-fills-and-position-updates)
      * [Instrument order fills and position updates](#instrument-order-fills-and-position-updates)
         * [Single contract order / single leg](#single-contract-order--single-leg)
         * [Single contract order / multiple legs (eg spread trade)](#single-contract-order--multiple-legs-eg-spread-trade)
         * [Multiple contract orders](#multiple-contract-orders)
      * [Order completions](#order-completions)
         * [Order deactivation](#order-deactivation)
         * [Adding to historic order databases](#adding-to-historic-order-databases)
   * [End of day stack shut down process](#end-of-day-stack-shut-down-process)
   * [Historic order tables and trade reporting](#historic-order-tables-and-trade-reporting)
* [Scripts](#scripts)
   * [Script calling](#script-calling)
   * [Script naming convention](#script-naming-convention)
   * [Run processes](#run-processes)
   * [Core production system components](#core-production-system-components)
      * [Get spot FX data from interactive brokers, write to Parquet (Daily)](#get-spot-fx-data-from-interactive-brokers-write-to-parquet-daily)
      * [Update sampled contracts (Daily)](#update-sampled-contracts-daily)
      * [Update futures contract historical price data (Daily)](#update-futures-contract-historical-price-data-daily)
         * [A note on market data subscriptions](#a-note-on-market-data-subscriptions)
         * [Set times when different regions download prices](#set-times-when-different-regions-download-prices)
      * [Update multiple and adjusted prices (Daily)](#update-multiple-and-adjusted-prices-daily)
      * [Update capital and P&amp;L by polling brokerage account](#update-capital-and-pl-by-polling-brokerage-account)
      * [Allocate capital to strategies](#allocate-capital-to-strategies)
      * [Run updated backtest systems for one or more strategies](#run-updated-backtest-systems-for-one-or-more-strategies)
      * [Generate orders for each strategy](#generate-orders-for-each-strategy)
      * [Execute orders](#execute-orders)
   * [Interactive scripts to modify data](#interactive-scripts-to-modify-data)
      * [Manual check of futures contract historical price data](#manual-check-of-futures-contract-historical-price-data)
      * [Manual check of FX price data](#manual-check-of-fx-price-data)
      * [Interactively modify capital values](#interactively-modify-capital-values)
      * [Interactively roll adjusted prices](#interactively-roll-adjusted-prices)
         * [Manually input instrument codes and manually decide when to roll](#manually-input-instrument-codes-and-manually-decide-when-to-roll)
         * [Cycle through instrument codes automatically, but manually decide when to roll](#cycle-through-instrument-codes-automatically-but-manually-decide-when-to-roll)
         * [Cycle through instrument codes automatically, auto decide when to roll, manually confirm rolls](#cycle-through-instrument-codes-automatically-auto-decide-when-to-roll-manually-confirm-rolls)
         * [Cycle through instrument codes automatically, auto decide when to roll, automatically roll](#cycle-through-instrument-codes-automatically-auto-decide-when-to-roll-automatically-roll)
   * [Menu driven interactive scripts](#menu-driven-interactive-scripts)
      * [Interactive controls](#interactive-controls)
         * [Trade limits](#trade-limits)
         * [Position limits](#position-limits)
         * [Trade control / override](#trade-control--override)
         * [Broker client IDs](#broker-client-ids)
         * [Process control &amp; monitoring](#process-control--monitoring)
            * [View processes](#view-processes)
            * [Change status of process](#change-status-of-process)
            * [Global status change](#global-status-change)
            * [Mark as close](#mark-as-close)
            * [Mark all dead processes as close](#mark-all-dead-processes-as-close)
            * [View process configuration](#view-process-configuration)
         * [Update configuration](#update-configuration)
      * [Interactive diagnostics](#interactive-diagnostics)
         * [Backtest objects](#backtest-objects)
            * [Output choice](#output-choice)
            * [Choice of strategy and backtest](#choice-of-strategy-and-backtest)
            * [Choose stage / method / arguments](#choose-stage--method--arguments)
            * [Alternative Python code](#alternative-python-code)
         * [Instrument configuration](#instrument-configuration)
            * [View instrument configuration data](#view-instrument-configuration-data)
            * [View contract configuration data](#view-contract-configuration-data)
            * [View trading hours for all instruments](#view-trading-hours-for-all-instruments)
         * [Emails](#emails)
            * [View stored emails](#view-stored-emails)
         * [View prices](#view-prices)
         * [View capital](#view-capital)
         * [Positions and orders](#positions-and-orders)
         * [Reports](#reports)
      * [Interactive order stack](#interactive-order-stack)
         * [View](#view)
         * [Create orders](#create-orders)
            * [Spawn contract orders from instrument orders](#spawn-contract-orders-from-instrument-orders)
            * [Create force roll contract orders](#create-force-roll-contract-orders)
            * [Create (and try to execute...) IB broker orders](#create-and-try-to-execute-ib-broker-orders)
            * [Balance trade: Create a series of trades and immediately fill them (not actually executed)](#balance-trade-create-a-series-of-trades-and-immediately-fill-them-not-actually-executed)
            * [Balance instrument trade: Create a trade just at the strategy level and fill (not actually executed)](#balance-instrument-trade-create-a-trade-just-at-the-strategy-level-and-fill-not-actually-executed)
            * [Manual trade: Create a series of trades to be executed](#manual-trade-create-a-series-of-trades-to-be-executed)
            * [Cash FX trade](#cash-fx-trade)
         * [Netting, cancellation and locks](#netting-cancellation-and-locks)
            * [Cancel broker order](#cancel-broker-order)
            * [Net instrument orders](#net-instrument-orders)
            * [Lock/unlock order](#lockunlock-order)
            * [Lock/unlock instrument code](#lockunlock-instrument-code)
            * [Unlock all instruments](#unlock-all-instruments)
            * [Remove Algo lock on contract order](#remove-algo-lock-on-contract-order)
         * [Delete and clean](#delete-and-clean)
            * [Delete entire stack (CAREFUL!)](#delete-entire-stack-careful)
            * [Delete specific order ID (CAREFUL!)](#delete-specific-order-id-careful)
            * [End of day process (cancel orders, mark all orders as complete, delete orders)](#end-of-day-process-cancel-orders-mark-all-orders-as-complete-delete-orders)
   * [Reporting, housekeeping and backup scripts](#reporting-housekeeping-and-backup-scripts)
      * [Run all reports](#run-all-reports)
      * [Delete old pickled backtest state objects](#delete-old-pickled-backtest-state-objects)
      * [Clean up old logs](#clean-up-old-logs)
      * [Truncate echo files](#truncate-echo-files)
      * [Backup DB to CSV files](#backup-db-to-csv-files)
      * [Backup state files](#backup-state-files)
      * [Backup MongoDB dump](#backup-mongodb-dump)
      * [Backup Parquet](#backup-parquet)
      * [Start up script](#start-up-script)
   * [Scripts under other (non-linux) operating systems](#scripts-under-other-non-linux-operating-systems)
* [Scheduling](#scheduling)
   * [Issues to consider when constructing the schedule](#issues-to-consider-when-constructing-the-schedule)
   * [Choice of scheduling systems](#choice-of-scheduling-systems)
      * [Linux cron](#linux-cron)
      * [Third party scheduler](#third-party-scheduler)
      * [Windows task scheduler](#windows-task-scheduler)
      * [Python](#python)
      * [Manual system](#manual-system)
      * [Hybrid of Python and cron](#hybrid-of-python-and-cron)
   * [Pysystemtrade scheduling](#pysystemtrade-scheduling)
      * [Configuring the scheduling](#configuring-the-scheduling)
         * [The crontab](#the-crontab)
         * [Process configuration](#process-configuration)
      * [System monitor and dashboard](#system-monitor-and-dashboard)
      * [Troubleshooting?](#troubleshooting)
* [Production system concepts](#production-system-concepts)
   * [Configuration files](#configuration-files)
      * [System defaults &amp; Private config](#system-defaults--private-config)
      * [System backtest YAML config file(s)](#system-backtest-yaml-config-files)
      * [Control config files](#control-config-files)
      * [Broker and data source specific configuration files](#broker-and-data-source-specific-configuration-files)
      * [Instrument and roll configuration](#instrument-and-roll-configuration)
      * [Set up configuration](#set-up-configuration)
      * [Trading hours configuration](#trading-hours-configuration)
   * [Capital](#capital)
      * [Large changes in capital](#large-changes-in-capital)
      * [Withdrawals and deposits of cash or stock](#withdrawals-and-deposits-of-cash-or-stock)
      * [Change in capital methodology or capital base](#change-in-capital-methodology-or-capital-base)
   * [Strategies](#strategies)
      * [Strategy capital](#strategy-capital)
         * [Risk target](#risk-target)
         * [Changing risk targets and/or capital](#changing-risk-targets-andor-capital)
      * [System runner](#system-runner)
      * [Strategy order generator](#strategy-order-generator)
      * [Load backtests](#load-backtests)
      * [Reporting code](#reporting-code)
* [Recovering from a crash - what you can save and how, and what you can't](#recovering-from-a-crash---what-you-can-save-and-how-and-what-you-cant)
   * [General advice](#general-advice)
   * [Data recovery](#data-recovery)
* [Reporting](#reporting)
   * [Dashboard](#dashboard)
      * [Roll report (Daily)](#roll-report-daily)
      * [P&amp;L report](#pl-report)
      * [Status report](#status-report)
      * [Trade report](#trade-report)
      * [Reconcile report](#reconcile-report)
      * [Strategy report](#strategy-report)
      * [Risk report](#risk-report)
      * [Liquidity report](#liquidity-report)
      * [Costs report](#costs-report)
      * [TODO add new reports](#todo-add-new-reports)
   * [Customize scheduled report generation](#customize-scheduled-report-generation)
<!--te-->

Created by [gh-md-toc](https://github.com/ekalinin/github-markdown-toc)

# Quick start guide

This 'quick' start guide assumes the following:

- you are running on a linux box with an appropriate distro (I use Mint). Windows / Mac people will have to do some things slightly differently
- you are using interactive brokers
- you are storing data using MongoDB
- you have a backtest that you are happy with
- you are happy to store your data and configuration in the /private directory of your pysystemtrade installation

You need to:

- Read this document very thoroughly!
- Prerequisites:
    - Install [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git), install or update [python3](https://docs.python-guide.org/starting/install3/linux/). You may also find a simple text editor (like emacs) is useful for fine-tuning, and if you are using a headless server then [x11vnc](http://www.karlrunge.com/x11vnc/) is helpful.
    - Add the following environment variables to your `~/.profile`: (feel free to use other directories):
        - MONGO_DATA=/home/user_name/data/mongodb/
        - PYSYS_CODE=/home/user_name/pysystemtrade
        - SCRIPT_PATH=/home/user_name/pysystemtrade/sysproduction/linux/scripts
        - ECHO_PATH=/home/user_name/echos
        - MONGO_BACKUP_PATH=/media/shared_network/drive/mongo_backup
    - Add the SCRIPT_PATH directory to your PATH
    - Create the following directories (again use other directories if you like, but you must modify the .profile above and specify the proper directories in `private_config.yaml`)
        - '/home/user_name/data/mongodb/'
        - '/home/user_name/data/parquet'
        - '/home/user_name/echos/'
        - '/home/user_name/data/mongo_dump'
        - '/home/user_name/data/backups_csv'
        - '/home/user_name/data/backtests'
        - '/home/user_name/data/reports'
    - Install the pysystemtrade package, and install or update, any dependencies in directory $PYSYS_CODE (it's possible to put it elsewhere, but you will need to modify the environment variables listed above). If using git clone from your home directory this should create the directory '/home/user_name/pysystemtrade/'
    - [Set up interactive brokers](/docs/IB.md), get a gateway running.
    - [Install MongoDB](https://docs.mongodb.com/manual/administration/install-on-linux/).
    - create a file `private_config.yaml` in the private directory of [pysystemtrade](/private), and optionally a [`private_control_config.yaml` file in the same directory](#process-configuration) See [here for more details](#system-defaults--private-config)
    - if you are located anywhere other than GMT, then you must adjust the trading hours for your timezone. See [here](#trading-hours-configuration)
    - Set `parquet_store` in 'private_config.yaml' to the Parquet directory you set up earlier 
    - [check a MongoDB server is running with the right data directory](/docs/data.md#mongodb) command line: `mongod --dbpath $MONGO_DATA`
    - launch an IB gateway (this could be done automatically depending on your security setup)
- FX data:
    - [Initialise the spot FX data from CSV files](/sysinit/futures/repocsv_spotfx_prices.py) (this will be out of date, but you will update it in a moment)
    - Update the FX price data using interactive brokers: command line:`. /home/your_user_name/pysystemtrade/sysproduction/linux/scripts/update_fx_prices`
- Instrument configuration:
    - Set up futures instrument spread costs using this script [repocsv_spread_costs.py](/sysinit/futures/repocsv_spread_costs.py).
- Futures contract prices:
    - [You must have a source of individual futures prices, then backfill them into Parquet](/docs/data.md#getting-historical-data-for-individual-futures-contracts).
- Roll calendars:
    - [Create roll calendars for each instrument you are trading](/docs/data.md#roll-calendars)
- [Ensure you are sampling all the contracts you want to sample](#update-sampled-contracts-daily)
- Adjusted futures prices:
    - [Create multiple prices in Parquet](/docs/data.md#creating-and-storing-multiple-prices).
    - [Create adjusted prices in Parquet](/docs/data.md#creating-and-storing-back-adjusted-prices)
- Use [interactive diagnostics](#interactive-diagnostics) to check all your prices are in place correctly
- Live production backtest:
    - Create a YAML config file to run the live production 'backtest'. For speed, I recommend you do not estimate parameters, but use fixed parameters, using the [yaml_config_with_estimated_parameters method of systemDiag](/systems/diagoutput.py) function to output these to a YAML file.
- Scheduling:
    - Initialise the [supplied crontab](/sysproduction/linux/crontab). Note if you have put your code or echos somewhere else you will need to modify the directory references at the top of the crontab.
    - All scripts executable by the crontab need to be executable, so do the following: `cd $SCRIPT_PATH` ; `sudo chmod +x *.*`
- Consider adding [position and trade limits](#interactive-controls)
- Review the [configuration options](#configuration-files) available


Before trading, and each time you restart the machine you should:

- [check a MongoDB server is running with the right data directory](/docs/data.md#mongodb) command line: `mongod --dbpath $MONGO_DATA` (the supplied crontab should do this)
- launch an IB gateway (this could [be done automatically](https://github.com/IbcAlpha/IBC) depending on your security setup)
- ensure all processes are [marked as 'close'](#mark-as-close)

Note that the system won't start trading until the next day, unless you manually launch the processes that would ordinarily have been started by the crontab or other [scheduler](#scheduling). [Linux screen](https://linuxize.com/post/how-to-use-linux-screen/) is helpful if you want to launch a process but not keep the window active (eg on a headless machine).

Also see [this](#recovering-from-a-crash---what-you-can-save-and-how-and-what-you-cant) on recovering from a crash (a system crash that is, not a market crash. You're on your own with the latter).

When trading you will need to do the following:

- Check [reports ](#reporting)
- [Roll instruments](#interactively-roll-adjusted-prices)
- Ad-hoc [diagnostics and controls](#menu-driven-interactive-scripts)
- [Manually check](#interactive-scripts-to-modify-data) large price changes


# Production system data flow

*[Update FX prices]()*
- Input: IB FX prices
- Output: Spot FX prices

*[Update roll adjusted prices](#get-spot-fx-data-from-interactive-brokers-write-to-parquet-daily)*
- Input: Manual decision, existing multiple price series
- Output: Current set of active contracts (price, carry, forward), Roll calendar (implicit in updated multiple price series)

*[Update sampled contracts](#update-sampled-contracts-daily)*
- Input: Current set of active contracts (price, carry, forward) implicit in multiple price series
- Output: Contracts to be sampled by historical data

*[Update historical prices](#update-futures-contract-historical-price-data-daily)*
- Input: Contracts to be sampled by historical data, IB futures prices
- Output: Futures prices per contract

*[Update multiple adjusted prices](#update-multiple-and-adjusted-prices-daily)*
- Input: Futures prices per contract, Existing multiple price series, Existing adjusted price series
- Output: Adjusted price series, Multiple price series

*[Update account values](#update-capital-and-pl-by-polling-brokerage-account)*
- Input: Brokerage account value from IB
- Output: Total capital. Account level P&L

*[Update strategy capital](#allocate-capital-to-strategies)*
- Input: Total capital
- Output: Capital allocated per strategy

*[Update system backtests](#run-updated-backtest-systems-for-one-or-more-strategies)*
- Input: Capital allocated per strategy, Adjusted futures prices, Multiple price series, Spot FX prices
- Output: Optimal positions and buffers per strategy, pickled backtest state

*[Update strategy orders](#generate-orders-for-each-strategy)*
- Input:  Optimal positions and buffers per strategy
- Output: Instrument orders

*[Run stack handler](#execute-orders)*
- Input: Instrument orders
- Output: Trades, historic order updates, position updates




# Overview of a production system

Here are the steps you need to follow to set up a production system. I assume you already have a backtested system in pysystemtrade, with appropriate Python libraries etc.

1. Consider your implementation options
2. Ensure you have a private area for your system code and configuration
3. Finalise and store your backtested system configuration
4. If you want to automatically execute, or get data from a broker, then set up a broker
5. Set up any other data sources you need.
6. Set up a database for storage, including a backup
7. Have a strategy for reporting, diagnostics, and logs
8. Write some scripts to kick off processes to: get data, get accounting information, calculate optimal positions, execute trades, run reports, and do backups and housekeeping.
9. Schedule your scripts to run regularly
10. Regularly monitor your system, and deal with any problems


## Implementation options

Standard implementation for pysystemtrade is a fully automated system running on a single local machine. In this section I briefly describe some alternatives you may wish to consider.

My own implementation runs on a Linux machine, and some of the implementation details in this document are Linux specific. Windows and Mac users are welcome to contribute with respect to any differences.

### Automation options

You can run pysystemtrade as a fully automated system, which does everything from getting prices through to executing orders.
If running fully automated, [IBC](https://github.com/IbcAlpha/IBC) is very useful. But other patterns make sense. In particular, you may wish to do your trading manually, after pulling in prices and generating optimal positions manually. It will also be possible to trade manually, but allow pysystemtrade to pick up your fills from the broker rather than entering them manually. For example, you might not trust the system (I wouldn't blame you), it gives you more control, you might think your execution is better than an algo, you might be doing some testing, or you simply want to use a broker that doesn't offer an API.

I suggest the following:

- From `run_stack_handler` process configuration in your `private_control_config.yaml` file, remove the method `create_broker_orders_from_contract_orders`
- Run `interactive_order_stack` to check what contract orders have been created.
- Do the trade
- Use 'manually fill broker or contract order' in `interactive_order_stack` to enter the fill details.

Everything else should be allowed to run as normal.


### Machines, containers and clouds

Pysystemtrade can be run locally in the normal way, on a single machine. But you may also want to consider containerisation (see [my blog post](https://qoppac.blogspot.com/2017/01/playing-with-docker-some-initial.html)), or even implementing on AWS or another cloud solution. You could also spread your implementation across several local machines.

If spreading your implementation across several machines bear in mind:

- Interactive brokers
   - interactive brokers Gateway will need to have the ip address of all relevant machines that connect to it in the whitelist
   - you will need to modify the `private_config.yaml` system configuration file, so it connects to a different IP address `ib_ipaddress: '192.168.0.10'`
- Mongodb
   - Add an ip address to the `bind_ip` line in the `/etc/mongod.conf` file to allow connections from other machines `eg bind_ip=localhost, 192.168.0.10`
   - You may need to change your firewall settings, either UFW (`sudo ufw enable`, `sudo ufw allow 27017 from 192.168.0.10`) or iptables
   - you will need to modify the `private_config.yaml` system configuration file, so it connects to a different IP address `mongo_host: 192.168.0.13`
   - you may want to enforce [further security protocol](https://docs.mongodb.com/manual/administration/security-checklist/)
- [Process configuration](#process-configuration); you will want to specify different machine names for each process in your private YAML config file.

### Backup machine

If you are running your implementation locally, or on a remote server that is not a cloud, then you should seriously consider a backup machine. The backup machine should have an up-to-date environment containing all the relevant applications, code and libraries, and on a regular basis you should update the local data stored on that machine (see [backup](#data-backup)). The backup machine doesn't need to be turned on at all times, unless you are trading in such a way that a one-hour period without trading would be critical (in my experience, one hour is the maximum time to get a backup machine online assuming the code is up-to-date, and the data is less than 24 hours stale). I also encourage you to perform a scheduled 'failover' on regular basis: stop the live machine running (best to do this at a weekend), copy across any data to the backup machine, start up the backup machine. The live machine then becomes the backup.

### Multiple systems

You may want to run multiple trading systems on a single machine. Common use cases are:

- You want to run relative value systems *
- You want different systems for different time frames (eg intraday and slower trading) *
- You want different systems for different asset classes eg stocks and ETFs, or futures
- You want to run the same system, but for different trading accounts (pysystemtrade can't handle multiple accounts natively)
- You want a paper trading and live trading system

*for these cases I plan to implement functionality in pysystemtrade so that it can handle them in the same system.

To handle this I suggest having multiple copies of the pysystemtrade environment. You will have a single crontab, but you will need multiple script, echos and other directories. You will need to change the private config file, so it points to different MongoDB database names. If you don't want multiple copies of certain data (eg prices) then you should hard code the database_name in the relevant files whenever a connection is made eg mongo_db = mongoDb(database_name='whatever'). See storing futures and spot FX data for more detail.

Finall, you should set the field `ib_idoffset` in the private config file `private/private_config.yaml` so that there is no chance of duplicate clientid connections; setting one system to have an id offset of 1, the next offset 1000, and so on should be sufficient.

## Code and configuration management

Your trading strategy will consist of pysystemtrade, plus some specific configuration files, plus possibly some bespoke code. You can either implement this as:

- separate environment, pulling in pysystemtrade as a 'yet another library'
- everything in pysystemtrade, with all specific code and configuration in the 'private' directory that is excluded from git uploads.

Personally I prefer the latter as it makes a neat self-contained unit, but this is up to you.

### Managing your separate directories of code and configuration

I strongly recommend that you use a code repo system or similar to manage your non pysystemtrade code and configuration. Since code and configuration will mostly be in text (or text like) YAML files a code repo system like git will work just fine. I do not recommend storing configuration in database files that will need to be backed up separately, because this makes it more complex to store old configuration data that can be archived and retrieved if required.

### Managing your private directory

Since the private directory is excluded from the git system (since you don't want it appearing on GitHub!), you need to ensure it is managed separately. I have a separate repo for my private stuff, for which I have a local clone in directory ~/private. Incidentally, GitHub are now offering free private repos, so that is another option.
I then use a bash script which I run in lieu of a normal git add/ commit / push cycle, to commit both private and public code:

```
# pass commit quote as an argument
# For example:
# mygitpush "this is a commit description string"
#
# copy the contents of the private directory to another, git controlled, directory
#
# we use rsync so we can exclude the git directory; which will screw things up as there is already one there
#
rsync -av ~/pysystemtrade/private/ ~/private --exclude .git
#
# git add/commit/push cycle on the main pysystemtrade directory
#
cd ~/pysystemtrade/
git add -A
git commit -m "$1"
git push
#
# git add/commit/push cycle on the copied private directory
#
cd ~/private/
git add -A
git commit -m "$1"
git push
```

A second script is run instead of a git pull:

```
# git pull within git controlled private directory copy
cd ~/private/
git pull
# copy the updated contents of the private directory to pysystemtrade private directory
# use rsync to avoid overwriting git metadata
rsync -av ~/private/ ~/pysystemtrade/private --exclude .git
# git pull from main pysystemtrade GitHub repo
cd ~/pysystemtrade/
git pull
```

### Custom private directory

If you prefer to keep your private config outside the *pysystemtrade* directory structure, this is possible too. Set
the environment variable `PYSYS_PRIVATE_CONFIG_DIR` with the full path to the custom directory:

```
PYSYS_PRIVATE_CONFIG_DIR=/home/user_name/private_custom_dir
```

or to set a custom config directory in the context of a single script

```
PYSYS_PRIVATE_CONFIG_DIR=/home/user_name/private_custom_dir python sysproduction/whatever.py
```


## Finalise your backtest configuration

You can just re-run a full daily backtest to generate your positions. This will probably mean that you end up refitting parameters like instrument weights and forecast scalars. This is pointless, slow, a waste of time, and potentially dangerous. Instead, I'd suggest using fixed values for all fitted parameters in a live trading system.

The following convenience function will take your backtested system, and create a dict which includes fixed values for all estimated parameters:

```python
# Assuming futures_system already contains a system which has estimated values
from systems.diagoutput import systemDiag

sysdiag = systemDiag(system)
sysdiag.yaml_config_with_estimated_parameters('someyamlfile.yaml',
                                              attr_names=['forecast_scalars',
                                                                  'forecast_weights',
                                                                  'forecast_div_multiplier',
                                                                  'forecast_mapping',
                                                                  'instrument_weights',
                                                                  'instrument_div_multiplier'])

```

Change the list of attr_names depending on what you want to output. You can then merge the resulting YAML file into your production backtest YAML file.

Don't forget to turn off the flags for `use_forecast_div_mult_estimates`, `use_forecast_scale_estimates`, `use_forecast_weight_estimates`, #`use_instrument_div_mult_estimates`, and `use_instrument_weight_estimates`.  You don't need to change flag for forecast mapping, since this isn't done by default.


## Linking to a broker

You are probably going to want to link your system to a broker, to do one or more of the following things:

- get prices
- get account value and profitability
- do trades
- get trade fills

... although one or more of these can also be done manually.

You should now read [connecting pysystemtrade to interactive brokers](/docs/IB.md). The fields `broker_account`,`ib_ipaddress`, `ib_port` and `ib_idoffset` should be set in the private config file.


## Other data sources

You might get all your data from your broker, but there are good reasons to get data from other sources as well:

- multiple sources can improve accuracy
- multiple sources can provide redundancy in case of feed issues
- you can't get the relevant data from your broker
- the relevant data is cheaper elsewhere

You should now read [getting and storing futures and spot FX data](/docs/data.md) for some hints on writing API layers for other data sources.


## Data storage

Various kinds of data files are used by the pysystemtrade production system. Broadly speaking they fall into the following categories:

- accounting (calculations of profit and loss)
- diagnostics
- prices (see [storing futures and spot FX data](/docs/data.md))
- positions
- other state and control information
- static configuration files

The default option is to store these all into a MongoDB database, except for configuration files which are stored as YAML and CSV files. Time series data is stored in [Parquet](https://parquet.apache.org/) files. Databases used will be named with the value of parameter `mongo_db` in private config. 

### Arctic

Early versions of this project used [Arctic](https://github.com/manahl/arctic) for storing time series data instead of Parquet, now deprecated. There is more detail in the [backtesting guide](/docs/backtesting.md#arctic)

#### Using Arctic in production instead of Parquet

It is still possible to use the older method. For production, modify the classes assigned in `sysproduction.data.production_data_objects.py` to point to the Arctic classes instead of Parquet:

```python
use_production_classes = {
    FX_DATA: arcticFxPricesData,
    ROLL_PARAMETERS_DATA: csvRollParametersData,
    FUTURES_INSTRUMENT_DATA: csvFuturesInstrumentData,
    FUTURES_CONTRACT_DATA: mongoFuturesContractData,
    STORED_SPREAD_DATA: mongoSpreadCostData,
    FUTURES_CONTRACT_PRICE_DATA: arcticFuturesContractPriceData,
    FUTURES_MULTIPLE_PRICE_DATA: arcticFuturesMultiplePricesData,
    FUTURES_ADJUSTED_PRICE_DATA: arcticFuturesAdjustedPricesData,
    CAPITAL_DATA: arcticCapitalData,
    CONTRACT_POSITION_DATA: arcticContractPositionData,
    STRATEGY_POSITION_DATA: arcticStrategyPositionData,
    OPTIMAL_POSITION_DATA: arcticOptimalPositionData,
    HISTORIC_SPREAD_DATA: arcticSpreadsForInstrumentData,
    STRATEGY_HISTORIC_ORDERS_DATA: mongoStrategyHistoricOrdersData,
    CONTRACT_HISTORIC_ORDERS_DATA: mongoContractHistoricOrdersData,
    BROKER_HISTORIC_ORDERS_DATA: mongoBrokerHistoricOrdersData,
    INSTRUMENT_ORDER_STACK_DATA: mongoInstrumentOrderStackData,
    CONTRACT_ORDER_STACK_DATA: mongoContractOrderStackData,
    BROKER_ORDER_STACK_DATA: mongoBrokerOrderStackData,
    ROLL_STATE_DATA: mongoRollStateData,
    PROCESS_CONTROL_DATA: mongoControlProcessData,
}
```

You would need to uncomment the Arctic imports too.

## Data backup

### MongoDB data

Assuming that you are using the default MongoDB for storing, then I recommend using [mongodump](https://docs.mongodb.com/manual/reference/program/mongodump/#bin.mongodump) on a daily basis to back up your files. Other more complicated alternatives are available (see the [official MongoDB man page](https://docs.mongodb.com/manual/core/backups/)). You may also want to do this if you're transferring your data to e.g. a new machine.

To avoid conflicts you should [schedule](#scheduling) your backup during the 'deadtime' for your system (see [scheduling](#scheduling)).


Linux:
```
# dumps everything into dump directory
# make sure a MongoDB instance is running with correct directory, but ideally without any load; command line: `mongod --dbpath $MONGO_DATA`
mongodump -o ~/dump/

# copy dump directory to another machine or drive. This will create a directory $MONGO_BACKUP_PATH/dump/
cp -rf ~/dump/* $MONGO_BACKUP_PATH
```

This is done by the scheduled backup process (see [scheduling](#scheduling)), and also by the script detailed [here](#backup-mongodb-dump)

Then to restore, from a linux command line:
```
cp -rf $MONGO_BACKUP_PATH/dump/ ~
# Now make sure a MongoDB instance is running with correct directory
# If required delete any existing instances of the databases. If you don't do this the results may be unpredictable...
mongo
# This starts a mongo client
> show dbs
admin              0.000GB
config             0.000GB
local              0.000GB
meta_db            0.000GB
production         0.000GB
# Most likely we want to remove 'production'
> use production
> db.dropDatabase()
> exit
# Now we run the restore (back on the linux command line)
mongorestore
```

### Parquet data

Time series data stored in Parquet files can be backed up like any other file, eg

```
rsync -chavzP --stats --progress --delete /home/user/data/parquet remote_machine:/home/user/backup_dir
```

This is done as part of the default scheduled back up process, see [here](#backup-parquet)



### MongoDB / CSV data

As I am super paranoid, I also like to output all my MongoDB data into CSV files, which I then regularly backup. This will allow a system recovery, should the MongoDB files be corrupted.

This currently supports: FX, individual futures contract prices, multiple prices, adjusted prices, position data, historical trades, capital, contract meta-data, spread costs, optimal positions. Some other state information relating to the control of trading and processes is also stored in the database and this will be lost, however this can be recovered with a little work: roll status, trade limits, position limits, and overrides. Log data will also be lost; but archived [echo files](#echos-stdout-output) could be searched if necessary.


Linux script:
```
. $SCRIPT_PATH/backup_db_to_csv
```

## Echos, Logging, diagnostics and reporting

We need to know what our system is doing, especially if it is fully automated. Here are the methods by which this should be done:

- Echos of stdout output from processes that are running
- Logging output in a file, tagged with keys to identify them
- Storage of diagnostics in a database, tagged with keys to identify them
- the option to run reports both scheduled and ad-hoc, which can optionally be automatically emailed

### Echos: stdout output

The [supplied crontab](/sysproduction/linux/crontab) contains lines like this:

```
SCRIPT_PATH="$HOME:/workspace3/psystemtrade/sysproduction/linux/scripts"
ECHO_PATH="$HOME:/echos"
#
0 6  * * 1-5 $SCRIPT_PATH/updatefxprices  >> $ECHO_PATH/updatefxprices.txt 2>&1
```

The above line will run the script `updatefxprices`, but instead of outputting the results to stdout they will go to `updatefxprices.txt`. These echo files are most useful when processes crash, in which case you may want to examine the stack trace. Usually however the log files will be more useful.

#### Cleaning old echo files

Over time echo files can get... large (my default position for logging is verbose). To avoid this there is a [daily cleaning process](#truncate-echo-files) which archives old echo files with a date suffix, and deletes anything more than a month old.

Note: the configuration variable echo_extension will need changing in `private_config.yaml` if you don't use .txt file extensions, otherwise cleaning won't work.

### Logging

pysystemtrade uses the [Python logging module](https://docs.python.org/3.10/library/logging.html). See the [user guide for more detail](/docs/backtesting.md#logging) about logging in sim. Python logging is powerful and flexible, and log messages can be [formatted as you like, and sent virtually anywhere](https://docs.python.org/3.10/howto/logging.html#logging-advanced-tutorial) by providing your own config. But this section describes the default provided production setup. 

In production, the requirements are more complex than in sim. As well as the context relevant attributes (that we have with sim), we also need
- ability to log to the same file from different processes
- output to console for echo files
- critical level messages to trigger an email

Configure the default production setup with:

```
PYSYS_LOGGING_CONFIG=syslogging.logging_prod.yaml
```

At the client side, (pysystemtrade) there are three handlers: socket, console, and email. There is a server (separate process) for the socket handler. More details on each below

### socket

Python doesn't support more than one process writing to a file at the same time. So, on the client side, log messages are serialised and sent over the wire. A simple TCP socket server receives, de-serialises, and writes them to disk. The socket server needs to be running first. The simplest way to start it:

```
python -u $PYSYS_CODE/syslogging/server.py
```

But that would write logs to the current working directory. Probably not what you want. Instead, pass the log file path 

```
python -u $PYSYS_CODE/syslogging/server.py --file /home/path/to/your/pysystemtrade.log
```

By default, the server accepts connections on port 6020. But if you want to use another

```
python -u $PYSYS_CODE/syslogging/server.py --port 6021 --file /home/path/to/your/pysystemtrade.log
```

The socket server also handles rotating the log files daily; the default setup rotates creates a new log at midnight each day, keeping the last 5 days' files. So after a week, the log directory file listing would look something like 

```
-rw-r--r--  1 user group 19944754 May  4 15:42 pysystemtrade.log
-rw-r--r--  1 user group 19030250 Apr 24 22:16 pysystemtrade.log.2023-04-24
-rw-r--r--  1 user group  6178163 Apr 25 22:16 pysystemtrade.log.2023-04-25
-rw-r--r--  1 user group  9465225 Apr 26 22:16 pysystemtrade.log.2023-04-26
-rw-r--r--  1 user group  4593885 Apr 27 16:53 pysystemtrade.log.2023-04-27
-rw-r--r--  1 user group  4414970 May  3 22:16 pysystemtrade.log.2023-05-03
```

The server needs to be running all the time. It needs to run in the background, start up on reboot, restart automatically in case of failure, etc. So a better way to do it would be to make it a service

#### socket server as a service

There is an example Linux systemd service file provided, see `examples/logging/logging_server.service`. And a setup guide [here](https://tecadmin.net/setup-autorun-python-script-using-systemd/). Basic setup for Debian/Ubuntu is:

- create a new file at `/etc/systemd/system/logging_server.service`
- paste the example file into it
- update the paths in `ExecStart`. If using a virtual environment, make sure to use the correct path to Python 
- update the `User` and `Group` values, so the log file is not owned by root
- update the path in `Environment`, if using a custom private config directory
- run the following commands to start/stop/restart etc

```
# reload daemon
sudo systemctl daemon-reload

# enable service (restart on boot)
sudo systemctl enable log_server.service

# view service status
sudo systemctl status log_server.service 

# start service
sudo systemctl start log_server.service

# stop service
sudo systemctl stop log_server.service

# restart
sudo systemctl restart log_server.service

# view service log (not pysystemtrade log)
sudo journalctl -e -u log_server.service
```

### console

All log messages also get sent to console, as with sim. The supplied `crontab` entries would therefore also pipe their output to the echo files

### email

There is a special SMTP handler, for CRITICAL log messages only. This handler uses the configured pysystemtrade email settings to send those messages as emails


#### Adding logging to your code

See the [logging docs](https://docs.python.org/3.10/library/logging.html) for usage examples. There are four ways to manage context attributes: 
* *overwrite* - passed attributes are merged with any existing, overwriting duplicates (the default)
* *preserve* - passed attributes are merged with any existing, preserving duplicates
* *clear* - existing attributes are cleared, passed ones added
* *temp* - passed attributes will only be used for one invocation

#### Examples

```python
# merging attributes: method 'overwrite' (default if no method supplied)
overwrite = get_logger("Overwrite", {"type": "first"})
overwrite.info("overwrite, type 'first'")
overwrite.info(
    "overwrite, type 'second', stage 'one'",
    method="overwrite",
    type="second",
    stage="one",
)

# merging attributes: method 'preserve'
preserve = get_logger("Preserve", {"type": "first"})
preserve.info("preserve, type 'first'")
preserve.info(
    "preserve, type 'first', stage 'one'", method="preserve", type="second", stage="one"
)

# merging attributes: method 'clear'
clear = get_logger("Clear", {"type": "first", "stage": "one"})
clear.info("clear, type 'first', stage 'one'")
clear.info("clear, type 'second', no stage", method="clear", type="second")
clear.info("clear, no attributes", method="clear")

# merging attributes: method 'temp'
temp = get_logger("temp", {"type": "first"})
temp.info("type should be 'first'")
temp.info(
    "type should be 'second' temporarily",
    method="temp",
    type="second",
)
temp.info("type should be back to 'first'")
```

#### Cleaning old logs

##### Echos

There is some code to clean up **echo** files. This code is run automatically from the [daily cleaning process](#clean-up-old-logs).

Python:

```python
from sysproduction.clean_truncate_log_files import clean_truncate_log_files
clean_truncate_log_files()
```

It defaults to deleting anything more than 30 days old.

##### Logs

With the provided production logging config, the cleaning of **log** files is managed by the Python logging server. Default config is to keep the last 5 days of production logs. To adjust this, see [syslogging/server.py](/syslogging/server.py) 


### psysystemtrade reports

Reports are run regularly to allow you to monitor the system and decide if any action should be taken. You can choose to have them emailed to you. To do this the email address, server and password *must* be set in `private_config.yaml`, as well as the address the email is being sent to (which can be the same as the sending email account):

```
email_address: "somebloke@anemailadress.com"
email_pwd: "h0Wm@nyLetter$ub$tiute$"
email_server: 'smtp.anemailadress.com'
email_to: "someotherbloke@anothermail.com"
```

Pysystemtrade will automatically try to negotiate TLS encryption when connecting to SMTP server and will resort to unencrypted communication only as a last resort.

Email reports are plain text by default. If your email client does not display
them in a fixed-width font, enable preformatted HTML in `private_config.yaml`:

```yaml
email_body_preformatted: True
```

This wraps plain-text message bodies in HTML `<pre>` tags, preserving spaces
and line breaks. HTML special characters in the original text are escaped.
The setting defaults to `False`, keeping existing plain-text email unchanged.
It applies to plain-text messages sent through `send_mail_msg`, including
reports and notifications; explicitly HTML messages and file/PDF emails are
unchanged. Restart processes that send emails after changing the configuration.

To use Google SMTP server without trusting the config file with your plain text password, you can create an 'App password' specifically for pysystemtrade:
- Go to [Manage my Google account](https://myaccount.google.com/security) and its 'Signing in to Google' subsection
- Ensure that '2-step verification' is On
- In 'App passwords' section generate a new one: Select app: Mail. Select device: Other, and name it 'pysystemtrade'. Click 'Generate' and copy the 16-character password (such as 'abcd efgh ijkl mnop').

For sending notifications via gmail to yourself, edit the config file as below:
```
email_address: "youraddress@gmail.com"
email_pwd: "abcdefghijklmnop"
email_server: 'smtp.gmail.com'
email_to: "youraddress@gmail.com"
```


Reports are run automatically every day by the [run reports](#run-all-reports) process, but you can also run ad-hoc reports in the [interactive diagnostics](#reports) tool. Ad hoc reports can be emailed or displayed on screen.

Full details of reports are given [here](#reporting).


# Positions and order levels

At this stage it's worth discussing the different kinds of positions and order levels. For abstraction and flexibility, positions and orders are at two /three levels:

- Instrument level (positions and orders)
- Contract level (positions and orders)
- Broker level (orders only)

You will see 'parent' and 'child' relationships discussed in the code: so the children of an instrument order are contract orders, and so on.

Each level has its own order 'stack' (not strictly a stack in computer science technology since there is no LIFO rule) on which active orders are held.

## Instrument level

Instrument specific orders for a particular strategy. These are generated by the process run_strategy_order_generator.

An instrument could be a general futures market, like GOLD or DAX. Importantly, no specific contract is specified (this will depend on the roll status). This level of abstraction is also used in backtesting. Hence, we create adjusted prices as the 'price' for an instrument. An instrument order could be explicit (i.e. no limit, just do this), conditional (do this if price goes to here) or include a limit (buy at this price or better). It can also come attached with execution preferences: trade as a market order (if urgent), as best you can using an algo, or as a limit order with a specific limit (which will be considered to be scaled to the adjusted price series).

We keep track of the positions allocated to each strategy and each instrument; these are updated when instrument orders are executed and filled.


## Contract level

An instrument order will be resolved into a contract order: an order for a specific contract (or intramarket contract spread, since this is also a 'tradeable instrument'). This is done by the process run_stack_handler. This could occur in a number of ways:

- For a normal single leg order, we trade the priced contract or the forward contract, or both; depending on whether we are passively rolling and whether our position is increasing or reducing (see [here](#interactively-roll-adjusted-prices) for more info about rolls)
- For a Force roll order, we create an intramarket spread between the priced and forward contract. This will also create a zero size instrument order.
- For a Force Outright roll order, we create two separate trades closing the priced and opening up in the forward. This will also create a zero size instrument order.

If an instrument order has a limit order, this is attached to the contract order, with an adjustment made if the contract traded is different from the contract used to generate the backadjusted price that the limit order will be scaled to (this will happen if you are currently passively rolling, and you trade the forward contract).

Contract orders are allocated to algorithms for execution, depending on what kind of instrument order was specified (limit, market, best-execution).

We keep track of the positions allocated to each instrument / contract combination; these are updated when instrument orders are executed and filled. They can also be compared directly to positions in the broker API.


## Broker level

A contract order will be resolved into a broker order when it is submitted to the broker. This is done by the process run_stack_handler. It's possible that a contract order will become multiple broker orders (since we might not choose to execute the whole lot, due to a lack of liquidity or a limit inside the algo that is used).

Broker orders are issued by execution algos (as allocated to the relevant contract order). They may be limit or market orders, depending on the operation of the relevant execution algo.

There are no positions at broker level, but we can compare broker level trades to trade information from the broker API.

Fills, once received from the broker API, are propagated upwards: broker orders are filled, then contract orders, and finally instrument orders.

Once all the child orders of an order are completed, then a parent order can also be completed. Completed orders are removed from the stack and put in historic order databases.

# The journey of an order


The most complex part of any trading system is the order management process. It is particularly complex in pysystemtrade, since it's designed to handle (in principle) some very complex types of trading strategy, and to trade multiple strategies. We also have the inherent complexity involved in trading futures. Let's look at the journey for a typical order. We'll consider the following:

- A normal order in a trading system. This could involve passively rolling from one contract to the next.
- A roll order which is a calendar spread (a Force roll)
- A roll order implemented as two separate trades (a Force Outright roll)


## Optimal positions

When a backtest is run (regularly by run_systems, or an ad-hoc basis by update_system_backtests) it will generate a set of *optimal position rules* for each strategy/instrument combination. There is no fixed structure for optimal positions, but some examples could be:

- A simple optimal position, eg trade until the position is +5 contracts. This used by the dynamic optimised trading system.
- A buffered optimal position, eg position should be between +10.87 and +13.32 contracts. This is what is used in the default provided backtest 'static' systems.
- A conditional optimal position, eg open a new buy if the price falls below this level, or close our current position if it goes above this level (which is what you'd use for mean reversion, with the addition of some stop orders). I plan to implement this kind of position management in a future trading system.

Optimal positions exist because it's generally expensive to run backtests even when parameters are fixed rather than being estimated, as I recommend for production systems (it's possible to generate backtests that only use a limited amount of data, which speeds things up somewhat, but this is unsatisfying).

An optimal position doesn't specify which contract or contracts the position is held in, that is determined later when a contract order is generated.

Optimal positions come with reference information attached. This is we can calculate the slippage caused by the delay between running the backtest and actually executing the order (normally in a backtest we assume this is one working day, but in production it will be less). We save:

- A reference price (basically the last price in the adjusted price series when the backtest was run)
- The contract that the price was snapshotted in (the current priced contract, which will give the same price as the adjusted price series). This is in case we trade a different contract than the price was referenced to (which we'll do if we're passively rolling, or if a roll occurred).
- A reference date/time, so we can calculate the delay in minutes between when the backtest thought we could execute, and when we actually execute.

Limit orders will also need to include a price, and a contract (in case the price that is referenced by the contract is wrong).


### Optimal position for roll orders

The concept of optimal positions doesn't exist for roll orders, since they are operating at the contract level, and optimal positions are at the instrument/strategy level.



## Strategy order handling

Either regularly (with run_strategy_order_generator) or ad-hoc (with update_strategy_orders) we generate instrument orders for each strategy. At the moment this is done daily, but for faster systems it may make sense to run it multiple times a day. The connection between the optimal positions and the orders generated depends on the type of strategy, but also what current positions are recorded in the database. 

For example:

- A simple optimal position would take the difference between the current recorded position and the required optimal position, and produce a trade (not implemented).
- A buffered optimal position, eg optimal position should be between +10.87 and +13.32 contracts. If the current position is above +13 contracts; sell down to +13 (rounded). If it's currently below +11 contracts, then buy up to +11 contracts. This is what is used in the default provided backtest systems.
- A conditional optimal position would depend on price levels as well as current recorded positions. Such a system will probably need to generate strategy orders multiple times a day.

Positions once generated are put on the instrument order stack, with the following behaviour:

- if one or more orders exists for the current instrument and strategy:
   - Sum up the unfilled part of the existing orders, then calculate what additional order would be needed to hit the optimal position
   - For example, if the optimal position is +10, and the current position is +8, the original order would be +2. However, there is an existing order of +4, of which +3 has been filled, leaving +1 unfilled. Thus, we adjust the original order to +1.
   - If the adjusted order is zero, which would be the case if the unfilled orders already came to the optimal position.
- if an order doesn't exist for the current instrument and strategy, then place the order (unless it is a zero order, which is what you'd get if the current required position was within the optimal buffer range)

Note that the above means it is vital that the recorded position and existing order fill data are updated and accessed at the same time (or at least that no fills are likely to occur while we're calculating them), and are as up-to-date as possible. 

Note also that it's quite possible that the sign of an adjusting order could change, depending on what unfilled orders are on the stack. We'd then quite possibly buy, and then sell, the same market which would be stupid and may even be illegal. To avoid this we need some kind of order netting (see below), which would also make trading across strategies more efficient.

These aren't serious issues when we generate orders once a day (at a time when the end of day process has cleared the instrument stack of any outstanding orders), but will be for intraday strategies.


### Instrument orders in detail:

Fields captured when an instrument order is created

- instrument/strategy
- order_id (assigned by the stack handling code)
- desired trade (always a scalar, since a spread instrument is treated like any other instrument at this stage)
- order type: Currently one of 'best' (execute at best possible price), 'market' (market order), 'limit' (limit order but not used), 'Zero-roll-order' used for roll orders, 'balance trade' (a balancing trade that isn't actually executed, generated by interactive_order_stack)
- limit price 
- limit contract 
- reference price
- reference datetime
- reference contract
- generated datetime
- manual trade (False unless it's generated by interactive_order_stack)
- roll order (False unless it's a roll order)
- active: True
- locked: False

The following fields are not yet used:

- fill, filled price, filled datetime
- parent (not used for instrument orders anyway)
- children 

### Strategy order handling for roll orders

Roll orders aren't generated here, but by the stack handler.



### Overrides

Overrides are applied before instrument orders are placed on the stack. They will take into account the desired trade, and the current position held.

See the [instruments documentation](/docs/instruments.md) to understand more about overrides.


## Stack handler

All the remaining operations in the active life of the order occur in the stack handler, either automatically with run_stack_handler, or ad-hoc with interactive_order_stack.

## Contract order creation

### Contract order creation - normal orders

If the roll status is 'not rolling', then contract orders are generated from instrument orders by spawn_children_from_new_instrument_orders in the stack handler.

For normal strategies when there is no rolling, there will just a single child contract order for each instrument order, trading in the current priced contract. Because it is a truth universally acknowledged that the contract order seeks to completely fulfill the required instrument order (this isn't true for broker and contract orders, of which more later).

Fields for a new contract order (once added to the database):

- instrument/strategy: strategy is _ROLL_PSEUDO_STRATEGY
- contract date (length 1 for a normal strategy that isn't rolling)
- desired trade (length 1)
- locked: False
- active: True
- order_id: assigned by stack handler
- parent: equal to the order_id of the parent instrument order
- order_type: Inherited from parent instrument order. Currently one of 'best' (execute at best possible price), 'market' (market order), 'limit' (limit order but not used), 'balance trade' (a balancing trade that isn't actually executed, generated by interactive_order_stack)
- limit_price: Will be identical to the instrument order limit price, assuming it is for the same contract, otherwise it will be adjusted to reflect the roll
- reference price: Will be identical to the instrument order limit price, assuming it is for the same contract, otherwise it will be adjusted to reflect the roll
- generated datetime: When this order, not the parent order, was generated
- roll_order: False
- inter_spread_order: False
- algo_to_use: the location of the algo that will be used to execute the order

The following are not used yet:

- fill, filled price, fill_datetime
- children
- reference of controlling algo
- split_order
- sibling_id_for_split_order

### Contract order creation - passive roll status

If the roll status is PASSIVE then we will issue closing orders in the current contract, and opening orders in the next forward contract. Theoretically, this means we could issue **two** contract orders for a given instrument order: a closing order for the current contract, and an opening order in the next contract.

The one or two contract orders will look much the same as above, except that the limit and reference prices will be adjusted for any orders that are in the forward contract.

Note that the roll_order flag will still be False: because these are trades we would do anyway, even if we weren't rolling.


### Instrument and contract order creation - active roll orders

If the roll status is Force or Force Outright then we generate instrument and contract orders together, with the method generate_force_roll_orders in the stack handler.

The instrument order will have the following characteristics:

- instrument/strategy: Strategy is _ROLL_PSEUDO_STRATEGY
- desired trade: 0 (roll orders are always flat in contract space and so don't affect the position in instrument space)
- order type: 'Zero-roll-order'
- limit price: N/A
- limit contract: N/A
- reference price,  reference datetime: a spread price taken from the last time when we have prices for both the current price and forward contracts
- reference contract: Not used since we don't need this to find the reference price for the contract orders
- generated datetime
- manual trade: False
- roll order: True
- active: True
- locked: False

If we are trading Force Outright, then we will also create two separate contract orders:

- instrument/strategy: Strategy is _ROLL_PSEUDO_STRATEGY
- contract date (length 1)
- desired trade: (length 1) to close the current contract, and open the same position in the next contract
- locked: False
- active: True
- order_id: assigned by stack handler
- parent: equal to the order_id of the parent instrument order
- order_type: 'best'
- limit_price: Not used
- reference price: For the priced contract leg will be identical to the instrument order limit price, assuming it is for the same contract, and for the forward contract will be adjusted to reflect the roll
- generated datetime: When this order was generated (will be a few seconds after the instrument order)
- roll_order: True
- inter_spread_order: False
- algo_to_use: the location of the algo that will be used to execute the order

If we are trading Force, we will create a single spread contract order:

- instrument/strategy: Strategy is _ROLL_PSEUDO_STRATEGY
- contract date (length 2)
- desired trade: (spread trade, length 2) to close the current contract, and open the same position in the next contract
- locked: False
- active: True
- order_id: assigned by stack handler
- parent: equal to the order_id of the parent instrument order
- order_type: 'best'
- limit_price: Not used
- reference price: Equal to the spread when both priced and forward contracts traded
- generated datetime: When this order was generated (will be a few seconds after the instrument order)
- roll_order: True
- inter_spread_order: False
- algo_to_use: the location of the algo that will be used to execute the order





## Manual trades

Using interactive_order_stack we can manually create instrument orders, and optionally contract orders. Manual trades have no reference data. 


## Broker order creation and execution

Broker orders are orders that are actually passed to the broker, although we also store them locally in a database. It's possible, and indeed likely, for there to be multiple broker orders for a given contract order (as my algos prefer to drip feed orders gradually into the market, one contract at a time).

Broker orders are created from contract orders by the method create_broker_order_for_contract_order in the stack handler.

Broker orders are unaffected by whether the contract order has been created as part of a roll, or for spread strategies. 

### Before an order is traded

Before a broker order is created we apply a number of steps to the contract order we retrieve from the database:

- Check to see if the contract order is fully filled already.
- Check that the current time falls within the trading hours for the instrument
- Check to see if an order is 'controlled' by an algo. This is in case we have multiple stack handlers running; we apply a pseudo lock when an algo issues a 
- Check to see if the instrument is locked. Locks are created when we have position mismatches, and cleared automatically when mismatches clear.
- Check to see if the contract is being traded (checks with broker)
- Resizes the order to comply with trade limits
- Resize the order depending on the current liquidity (level 1 volume at the top of the order book, checks with the broker. This is done on a leg-by-leg basis - not in the explicit spread market for multi-contract legs - and the most conservative size applied)

Note that the size changes do not impact the contract order saved to the database; only the order that is passed onwards in memory to become a broker order. Thus, it's possible that we have a buy of +10 contract order, but there is only enough liquidity for +3. A broker order of +3 will be created (unless the order is further reduced by the algo: see next step), subsequently the system will try and create a second broker order of +7. Or if we have a buy of +10, but the trade sizing only allows for +5, then a broker order of +5 will be created and once executed no more broker orders can be created from this contract order (at the end of the day it will be cleared from the order stack, and the next day assuming it was a daily limit that was the constraint more contracts can be executed).


### Trading algos

The next step is to send the order to a trading algo (an algo is allocated if one is not already attached to the contract order). Currently, there are two algos included, a market and a 'best execution' algo. Neither is designed to work with contract orders with a limit price, although the best execution algo uses limit orders tactically. Most orders are allocated to the 'best execution' unless there is less than an hour of market open time left, in which case they go to the market algo.

The contract order is marked 'algo controlled' to stop another thread or process trying to execute the same contract order (only possible right now accidentally through interactive_order_stack). 

### Pre-order preparation in the trading algo.

The Algo code will reduce the size of the contract trade further if required (both algos currently only trade single contracts by default). The next steps depend on the algo being used:

- The market algo will just use a market order
- The best execution algo will get a 'ticker object' for the contract. It will decide if it's viable to do a limit trade (basically it won't if the order book is unbalanced and a market order is more likely to get a better price). It will then submit either a market trade, or a limit trade which it will try and get executed passively

The code will then create a broker order of the same size as the cut down contract order (which remember, could be considerably smaller than the original contract order on the database!). 

### Broker order characteristics

The following attributes are set when a broker order is created:

- instrument/strategy: inherited from contract order
- contract date: inherited from contract order. Length 1 or length 2 for roll spread orders
- calendar_spread_order: False or True if a spread order
- locked: False
- parent: contract order id
- active: True
- order_type: Either market or limit order
- algo_used: the algo that created the order, so inherited from contract order
- limit_price: empty for market orders
- side_price: current offer for buys, current bid for sells ('current' when order created, not when it's submitted which will be a fraction of a second later); float even for spread orders
- mid_price: current mid price; float even for spread orders
- offside_price: current bid for sells, current offer for buys, float even for spread orders
- roll_order: inherited from contract order
- broker
- broker_account
- broker_clientid
- manual_fill: False

Note there are no reference information; when required later we get them from the parent contract order.

The following are not yet set:

- fill, filled price, filled datetime
- order_id: not set until saved to database
- children: not used as broker orders are at the bottom of the order pile
- algo_comment
- submit_datetime 
- broker_tempid
- broker_permid
- commission
- split_order
- sibling_id for split_order

The broker order is then sent to the sysbroker orders code, via the production data API sysproduction.data.broker (which also handles issues we've encountered earlier, like getting tick data, market opening hours, and available liquidity).

### Order execution in the sysbroker code

The following is correct for IB, which in any case is the only broker we can currently use in pysystemtrade.

Broker orders are passed to sysbrokers.IB.ib_orders.ibExecutionStackData.put_order_on_stack; after adding information needed to identify the contract to be traded accurately, it is subsequently sent to sysbrokers.IB.client.ib_orders_client.ibOrdersClient.

That translates the order into IB terms, and places the order. It returns a tradeWithContract object, which contains an ibcontractWithLegs object (containing the IB representation of the contract traded, plus any legs for a spread order), and the order object returned by the ib_async code. 

This is then turned into a ibOrderWithControls object. This further layer of abstraction contains both a broker order, plus the tradeWithContract 'control' object needed to manage the trade (clearly this would make it easier to use another broker). We then replace the submit_datetime with the order time (from the broker itself, to ensure consistency with the timestamp on price data as well as any fill times). We then store this orderWithControls object in a local cache. That will make it easier to access subsequently, and check for fills etc. The storage key is broker_tempid.

The ibOrderWithControls is then returned by the algo to the stack handler, with the following fields set for the order:

- submit_datetime: actual submission time from the broker 
- broker_tempid: Format is 'account_id/client_id/ib_order_id'. Used to match orders (see fills below)

### Adding the broker trade to the database

The broker order component of the ibOrderWithControls object is then added to the order stack database for broker orders as a new order (we don't save the 'control' part; this has implications for collecting fills). At this point the orderid will be set, and it will be added as a child to the parent contract order.

An important feature is that a broker order that does not successfully make it to the broker won't be saved in the database, or recorded in any way (except in log and echo files). The **broker** order database is for orders that have gone to the **broker**; even if they are subsequently cancelled. Also, if a broker order doesn't make it to the database we need to make sure we release the contract order from algo control.


### Managing the trade

Control then returns to the algo to manage the trade. For the market algo, it will just wait until the order is filled, been cancelled by the broker for some reason, or a timeout (10 minutes by default) has passed. If we run out of time the algo itself will try and cancel the order.

For the best execution algo if a market order has been issued it will behave like the market algo. If a limit order was issued, it will wait passively for a fill. If certain conditions are met it will switch to trading aggressively; which means it will change the limit price to buy at the offer, and sell at the bid. 

How do we poll for cancellations and fills, change limit prices, and request cancellations? This is all done via the 'control' objects buried inside ibOrderWithControls, which is the ib_async representation of the order and contract traded. A frequent pattern is to update that object, and then use it to update the *execution details* for the broker order. The following broker order fields are updated in this way:

- fill: length 1, or longer for spread orders
- filled price: float, even for spread orders (since IB fills are returned as a list for each leg, we have to calculate this)
- filled datetime: the datetime of the last fill if there are multiple fills in the order
- algo_comment: as the order is executed any messages received from the broker are appended to this string
- broker_permid: the reference attached to an order once it has begun executing
- commission

Note: At this stage none of this is in the database, only in the in memory representation of the order. 

Importantly trade management is blocking whilst orders are being executed; the stack handler can only manage the execution of one trade at a time. Multiple stack handlers could be employed to avoid this problem, and in theory the use of algo control settings should mostly avoid anything crazy happening... don't try it at home!


## After execution: fills and completions

Control then returns to the stack handler. At this point we *should* have an order object which is fully filled, or at least cancelled so no further fills are expected to be received. However, there are edge cases where this may not happen. The stack handler now:

- Updates the trade limits to reflect the size of the broker order
- Applies the broker order fill to the database (see next section)
- Releases the parent contract order from algo control



## Fills and completions

As we propagate orders down the stacks, from instrument, to contract, to broker orders; we also propagate fills back up; updating position tables as we go. Then when orders are completed they are removed from the active stack, and transferred to historic order databases. This can be done in the normal order flow, but there is a backup in that regular scheduled processes periodically check the order stacks to see if there are any orders with new fills. 

### Broker order fills

Once an order has executed, any fills will be applied to the broker order stored in the database. This is done by saving the broker order in memory to the stack, which now includes the execution details.

The code will then call code to fill the parent contract order.

IB sends commission reports separately from execution details. Until every
execution leg has a matching commission report, the broker order's commission is
`None` (unavailable), not zero. Fills and positions are updated immediately, but
normal order completion waits for the fee. The existing fill sweep continues
refreshing that order's commission without changing its recorded fill price,
quantity or time. A reported zero commission is valid and does not delay completion.

Explicit partial/zero completion, including end-of-day cleanup, remains available.
If it archives a filled order before the fee is available, it logs a warning and
preserves `None`; it does not invent a zero fee or automatically repair that
historical record later.

### An aside, what happens if fills happen later?

Suppose we have an edge case when perhaps an order is cancelled before the fill is received, but then later the order is filled by the broker. The stack handler has already forgotten about this broker order and carelessly deleted the all important control object which we use to find out about fills when managing the order. This will cause a mismatch between our position and fill records, and reality. How will we know about the fill?

Well the stack handler code regularly runs the method sysexecution/stack_handler/fills.stackHandlerForFills.pass_fills_from_broker_to_broker_stack. For each broker order on the stack (i.e. saved in the database, but remember without any control object), it will look for an order from the broker that matches. This matching is done as follows:

- first we look in the cached set of broker orders and control objects, that should include any orders made in this session (but that won't work if the order was done somewhere else, eg by interactive_order_stack). Remember that this was indexed by broker_tempid.
- if that fails then we get the orders and control objects actually from the broker. 
    - Again first we look for orders with the same broker_tempid (i.e. from the same account, clientid and with the same IB orderId). 
    - If that fails we look for an order with the same permid. This will work as long as the original broker order in the database got a permid before the stack handler had closed the original (failed?) execution process.
- if that fails we're buggered, and we need to enter the fill manually using interactive_order_stack. Most likely this will happen if more than 24 hours passes after the order was executed, since IB only returns recent orders from its API 


Once we have the order from the broker, which includes the control objects, we can update the following fields in the broker order, and save it to the database:

- fill, filled price, filled datetime
- algo_comment: as the order is executed any messages received from the broker are appended to this string
- broker_permid: the reference attached to an order once it has begun executing
- commission

We then call code to fill the parent contract order.

### Contract order fills and position updates

In the stack handler the method apply_broker_fills_to_contract_order will propagate fills upwards to contracts. This will be called either by (a) a completed order being handed off from the Algo, (b) a regular scheduled call of pass_fills_from_broker_to_broker_stack if the order wasn't fully filled, (c) a regular scheduled call of pass_fills_from_broker_up_to_contract, or (d) manually from interactive_order_stack.

Because we can have one:many relationships between contract and broker orders, we do this by getting all the fills from all the broker orders that are children of a given contract order. Note that the tradeable object (instrument/strategy/ and one or more contract dates) will be the same. We calculate the following:

- The *last* filled datetime
- The *total* filled quantity (which is specified for each leg of a multi-leg order)
- The *average* filled price (float)

We then change the saved contract order on the stack to reflect this new fill information. We modify:

- fill, filled price, fill_datetime

We then compare the in memory representation of the contract order (which does *not* have the fill) with the calculated total fills (which *does* have the fill), this allows us to identify if the fill quantity has changed (fills are cumulative remember). If the quantity has changed, then we update the stored position table for instrument/contract positions to reflect this (but not yet the instrument/strategy position table - so there will be a mismatch here). Now any check for mismatches between IB and our stored positions will pass with flying colours.

We then call code to apply the contract fill to the instrument order

### Instrument order fills and position updates

The stack handler uses apply_contract_fills_for_instrument_order to propagate fills upwards from contract orders. This will be called from (a) apply_broker_fills_to_contract_order (in the normal run of things this would happen after a broker order is filled), (b) a regular scheduled call of pass_fills_from_contract_up_to_instrument, or (c) manually from interactive_order_stack. 

Instrument orders can have one:many relationships with contract orders, so there are a few different cases.


#### Single contract order / single leg

This is trivial. We get from the contract order:

- The filled datetime
- The filled quantity
- The filled price 

We then compare the filled quantity with that of the original instrument order to see if it has changed. If so, we apply the position change to the instrument/strategy position table. Now both of our position tables are correct and consistent! 

Next we update the instrument order on the database stack to reflect the new fills. We now check to see if the order can be *completed*.

#### Single contract order / multiple legs (eg spread trade)

Two possible cases:

1. Flat spread where the instrument trade is zero (this would be a roll with FORCE status): This is trivial; as the instrument trade is a zero trade the instrument position isn't affected by the contract trade. We now try and *complete* the order.

2. Multiple leg trade where the instrument trade is non-zero



#### Multiple contract orders

Three cases:

1. Distributed orders (this can happen when we have PASSIVE rolls, and we get both a priced and forward contract trade): A distributed order is one where all the contract order trades are in the same direction, all the instrument codes are identical, and the total trades are equal to the total trade for the instrument. We calculate across contract orders:

   - The *last* filled datetime
   - The *total* filled quantity
   - The *average* filled price 

    We then compare the filled quantity with that of the original instrument order to see if it has changed. If so, we apply the position change to the instrument/strategy position table. Now both of our position tables are correct and consistent! 

    Next we update the instrument order on the database stack to reflect the new fills. We now check to see if the order can be completed.

2. Flat orders where the instrument order is a zero trade (this can happen when we have rolls with Force Outright status): This is trivial; as the instrument trade is a zero trade the instrument position isn't affected by the contract trade. We now try and *complete* the order.


### Order completions

The method handle_completed_instrument_order in the stack handler handles order completions. It can be called by (a) apply_contract_fills_for_instrument_order (which is the normal behaviour after a fill has been applied), (b) the regularly scheduled handle_completed_orders, (c) by the 'end of day' process that runs when the stack shuts down, or (d) manually by interactive_order_stack.

Orders are completed when the entire order 'family' (instrument order, child contract orders, and grandchild broker orders) are completely filled (there is an exception, when the completion is called by the end of day process it will also consider unfilled and partially filled orders to be complete, since completing is a pre-cursor to cleaning the stack up completely).

Completed orders then follow a two-step process:

- deactivation
- copy to historical orders database


#### Order deactivation

For all orders in the family we set:

- active: False

Deactivated orders are 'invisible'; they won't be seen by any calls to get lists of order IDs from the database, and thus stand no chance of being executed or filled. But they are still in the order stack (they are deleted by the end of day process).


#### Adding to historic order databases

For analysis, we want to keep records of the orders we've made. We save the family of orders to historic order databases. It's now safe to delete them from the order stack database tables (this is done by the end of day process).
 
Note that there is no guarantee that position and order databases will be consistent; although every effort is made to ensure this is the case. I usually assume that position data is correct, although I do use fill prices for mark to market purposes.


## End of day stack shut down process

Whenever the stack handler shuts down (usually the end of the day) we run a 'safe' shutdown process. This can also be triggered by interactive_order_stack. The goal is to ensure the stack is clean with no state; with all orders moved to historic storage, all pending orders cancelled and position tables updated. Then it's straightforward for new instrument orders to be generated, which for now happens on a daily basis once the stack has been closed and emptied.

- Attempt to cancel all broker orders
- Process fills
- Handle completed orders, including unfilled or partially filled (which will deactivate orders and move them to historic tables)
- Remove all deactivated orders


## Historic order tables and trade reporting


For TCA we compare (to get slippage):

- the reference price (set in the instrument order, adjusted in the contract order)
- the mid price  (for the broker order)
- the side price (for the broker order)
- the offside price (for the broker order)
- the limit price (for the broker order): note this will be the initial limit price
- the parent limit price (for the contract order: only relevant for algos that try and better a limit price)
- the fill price (for the broker order)

We also compare (to get time delays):

- the reference datetime (from the parent instrument order)
- the submitted datetime for the broker order
- the filled datetime for the broker order

We don't use:

- the datetime when the instrument order was generated
- the datetime when the contract order was generated
- any of the fill prices for instrument and contract orders (would be double counting)

The above is recovered from the historic order tables with a special method that augments the broker order information with data from the instrument and contract orders.



# Scripts

Scripts are used to run Python code which:

- runs different parts of the trading system, such as:
   - get price data
   - get FX data
   - calculate positions
   - execute trades
   - get accounting data
- fix any issues or basically interactively meddle with the system
- runs report and diagnostics, either regular or ad-hoc
- Do housekeeping duties, eg truncate log files and run backups

Script are then called by [schedulers](#scheduling), or on an ad-hoc basis from the command line.

## Script calling

I've created scripts that run under Linux, however these all just call simple python functions, so it ought to be easy to create your own scripts in another OS. See [here](#scripts-under-other-non-linux-operating-systems) for notes about a method to create cross-platform executable scripts.

So, for example, here is the [run reports script](/sysproduction/linux/scripts/run_reports):

```
#!/bin/bash
. ~/.profile
. p sysproduction.run_reports.run_reports
```

In plain english this will call the Python function `run_reports()`, located in `/sysproduction/run_reports.py` By convention all 'top level' Python functions should be located in this folder, and the file name, script name, and top level function name ought to be the same.

Scripts are run with the following linux convenience [script](/sysproduction/linux/scripts/p) that just calls run.py with the single argument in the script that is the code reference for the function:

```
python3 run.py $1
```

run.py is a little more complicated as it allows you to call Python functions that require arguments, such as [interactive_update_roll_status](/sysproduction/interactive_update_roll_status.py), and then ask the user for those arguments (with type hints).


## Script naming convention

The following prefixes are used for scripts:

- _backup: run a backup.
- _clean: run a housekeeping / cleaning process
- _interactive: run an interactive process to check or fix the system, avoiding diving into Python every time something goes wrong
- _update: update data in the system (basically do one of the stages in the system)
- startup: run when the machine starts
- _run: run a regularly scheduled process.

Normally it's possible to call a process directly (eg _backup_files) on an ad-hoc basis, or it will be called regularly through a 'run' process that may do other stuff as well  (eg run_backups, runs all backup processes). Run processes are a bit complicated, as I've foolishly written my own scheduling code, so see [this section](#pysystemtrade-scheduling) for more. Some exceptions are interactive scripts which only run when called, and run_stack_handler which does not have a separate script.

## Run processes

These are listed here for convenience, but more documentation is given below in the relevant section for each script

- run_backups: Runs [backup_db_to_csv](#backup-db-to-csv-files), [backup state files](#backup-state-files): [MongoDB dump backup](#backup-mongodb-dump)
- run_capital_updates: Runs [update_strategy_capital](#allocate-capital-to-strategies), [update_total_capital](#update-capital-and-pl-by-polling-brokerage-account): update capital
- run_cleaners: Runs [clean_truncate_backtest_states](#delete-old-pickled-backtest-state-objects), [clean_truncate_echo_files](#truncate-echo-files), [clean_truncate_log_files](#clean-up-old-logs): Clean up
- run_daily_price_updates: Runs [update_fx_prices](#get-spot-fx-data-from-interactive-brokers-write-to-parquet-daily), [update_sampled_contracts](#update-sampled-contracts-daily), [update_historical_prices](#update-futures-contract-historical-price-data-daily), [update_multiple_adjusted_prices](#update-multiple-and-adjusted-prices-daily): daily price and contract data updates
- run_daily_fx_and_contract_updates: Runs [update_fx_prices](#get-spot-fx-data-from-interactive-brokers-write-to-parquet-daily), [update_sampled_contracts](#update-sampled-contracts-daily).
- run_daily_update_multiple_adjusted_prices: Runs [update_multiple_adjusted_prices](#update-multiple-and-adjusted-prices-daily): daily price and contract data updates
- run_reports: Runs [all reports](#reporting)
- run_systems: Runs [update_system_backtests](#run-updated-backtest-systems-for-one-or-more-strategies): Runs a backtest to decide what optimal positions are required
- run_strategy_order_generator: Runs [update_strategy_orders](#generate-orders-for-each-strategy): Creates trades based on the output of run_systems
- [run_stack_handler](#execute-orders): Executes trades placed on the stack by run_strategy_order_generator


## Core production system components

These control the core functionality of the system.

### Get spot FX data from interactive brokers, write to Parquet (Daily)

Python:
```python
from sysproduction.update_fx_prices import update_fx_prices

update_fx_prices()
```

Linux script:
```
. $SCRIPT_PATH/update_fx_prices
```

Called by: `run_daily_fx_and_contract_updates`


This will check for 'spikes', unusually large movements in FX rates either when comparing new data to existing data, or within new data. If any spikes are found in data for a particular contract it will not be written. The system will attempt to email the user when a spike is detected. The user will then need to [manually check the data](#manual-check-of-fx-price-data).
.

The threshold for spikes is set in the `defaults.yaml` file, or overridden in the private config, using the parameter `max_price_spike`. Spikes are defined as a large multiple of the average absolute daily change. So for example if a price typically changes by 0.5 units a day, and `max_price_spike=6`, then a price change larger than 3 units will trigger a spike.


### Update sampled contracts (Daily)

This ensures that we are currently sampling active contracts, and updates contract expiry dates.

Python:
```python
from sysproduction.update_sampled_contracts import update_sampled_contracts
update_sampled_contracts()
```

Linux script:
```
. $SCRIPT_PATH/update_sampled_contracts
```

Called by: `run_daily_fx_and_contract_updates`


### Update futures contract historical price data (Daily)

This gets historical daily data from IB for all the futures contracts marked to sample in the MongoDB contracts database, and updates the futures prices in Parquet. If update sampled contracts has not yet run, it may not be getting data for all the contracts you need.

Python:
```python
from sysproduction.update_historical_prices import update_historical_prices
update_historical_prices()
```

Linux script:
```
. $SCRIPT_PATH/update_historical_prices
```

Called by: `run_daily_price_updates`

This will get daily closes, plus intraday data at the frequency specified by the parameter `intraday_frequency` in the `defaults.yaml` file (or overwritten in the private YAML config file). It defaults to 'H: hourly'. Prices are stored separately at Daily, Hourly and Merged frequencies.

It performs the following cleaning on data that it receives, depending on the YAML parameter values that are set (defaults are shown in brackets):

- if `ignore_future_prices` is True (default: True) we ignore any prices with time stamps in the future (assumes all prices are sampled back to local time). This prevents us from early filling of Asian time zone closing prices.
- if `ignore_prices_with_zero_volumes`  is True (default: True) we ignore any price in a bar with zero volume; this reduces the amount of bad data we get.
- if `ignore_zero_prices` is True  (default: True) we ignore prices that are exactly zero. A zero price is usually erroneous.
- if `ignore_negative_prices`  is True (default: False) we ignore negative prices. Because of the crude oil incident in March 2020 I prefer to allow negative prices, and if they are errors hope that the spike checker catches them.

This will also check for 'spikes', unusually large movements in price either when comparing new data to existing data, or within new data. If any spikes are found in data for a particular contract it will not be written. The system will attempt to email the user when a spike is detected. The user will then need to [manually check the data](#manual-check-of-futures-contract-historical-price-data).

The threshold for spikes is set in the `defaults.yaml` file, or overridden in the private config YAML file, using the parameter `max_price_spike`. Spikes are defined as a large multiple of the average absolute daily change. So for example if a price typically changes by 0.5 units a day, and `max_price_spike=8`, then a price change larger than 4 units will trigger a spike.

#### A note on market data subscriptions

- market data subscriptions used to be required for IB historical data. This changed in early 2023. There was no announcement of the change, and the IB API documentation still says a subscription is required, so things may change
- IB has different kinds of market data. There is the historical data, and there is also streaming data, which can be either live or delayed. Live streaming data requires a subscription, delayed streaming data does not
- pysystemtrade (by default) uses streaming data to manage trades. If you don't have live streaming data for an instrument, you will need to change your trade execution algo to one that doesn't rely on it. See the supported order types in `sysexecution.orders.broker_orders.py`. See the available trading algos in `sysexecution.algos`. Override `execution_algos` in your config to match your situation
- I detailed my own market data subscriptions on [my blog](https://qoppac.blogspot.com/2021/05/adding-new-instruments-or-how-i-learned.html), reproduced here:

|            Name             | Cost per month |
|:---------------------------:|:--------------:|
|          Cboe One           |    USD 1.00    |
|        CFE Enhanced         |    USD 4.50    | 
|         Eurex Core          |    EUR 8.75    | 
|     Eurex Retail Europe     |    EUR 2.00    | 
|    Euronext Data Bundle     |    EUR 3.00    | 
|    Korea Stock Exchange     |    USD 2.00    | 
|     Singapore Exchange      |    SGD 2.00    |
|       Osaka Exchange        |    JPY 200     |

More details and latest prices on the [Interactive Brokers site](https://www.interactivebrokers.com/en/index.php?f=14193)

#### Set times when different regions download prices

To maximise efficiency, rather than doing a big end of day download, you might prefer to download different regions throughout the day.

To achieve this, add code like the following to your `private_control_config.yaml` file:

```
arguments:
  run_daily_prices_updates:
    update_historical_prices: # everything in this block is passed as **kwargs to this method
      download_by_zone:
        ASIA: '07:00'
        EMEA: '18:00'
        US: '20:00'

```

This will download Asian regional instruments at 7am, local machine time; Europe Middle East Africa at 6pm, and US at 8pm. Regions are set in the instrument configuration (provided CSV file which is then written to the database using interactive_controls, options to update configuration). 

You should also ensure that `run_daily_price_updates` has a start time set in `private_control_config.yaml` earlier than 7am, and is started by the crontab or other scheduler before 7am.


### Update multiple and adjusted prices (Daily)

This will update both multiple and adjusted prices with new futures per contract price data.

It should be scheduled to run once the daily prices for individual contracts have been updated, although you can also schedule it to run without any dependencies if you don't want to be affected by a slow download of individual prices.

Python:
```python
from sysproduction.update_multiple_adjusted_prices import update_multiple_adjusted_prices
update_multiple_adjusted_prices()
```

Linux script:
```
. $SCRIPT_PATH/update_multiple_adjusted_prices
```

Called by: `run_daily_update_multiple_adjusted_prices`


Spike checks are not carried out on multiple and adjusted prices, since they should hopefully be clean if the underlying per contract prices are clean.


### Update capital and P&L by polling brokerage account


See [capital](#capital) to understand how capital works. On a daily basis we need to check how our brokerage account value has changed. This will be used to update our total available capital, and allocate that to individual strategies.

Python:
```python
from sysproduction.update_total_capital import update_total_capital
update_total_capital()
```

Linux script:
```
. $SCRIPT_PATH/update_total_capital
```

Called by: `run_capital_update`


If the brokers account value changes by more than 10% then capital will not be adjusted, and you will be sent an email. You will then need to run `modify_account_values`. This will repeat the poll of the brokerage account, and ask you to confirm if a large change is real. The next time `update_total_capital` is run there will be no error, and all adjustments will go ahead as normal.


### Allocate capital to strategies

Allocates total capital to individual strategies. See [strategy capital](#strategy-capital) for more details. Will not work if `update_total_capital` has not run at least once, or capital has been manually initialised by `update_capital_manual`.

Python:
```python
from sysproduction.update_strategy_capital import update_strategy_capital
update_strategy_capital()
```

Linux script:
```
. $SCRIPT_PATH/update_strategy_capital
```

Called by: `run_capital_update`


### Run updated backtest systems for one or more strategies
(Usually overnight)

The paradigm for pysystemtrade is that we run a new backtest nightly, which outputs some parameters that a trading engine uses the next day. For the basic system defined in the core code those parameters are a pair of position buffers for each instrument. The trading engine will trade if the current position lies outside those buffer values.

This can easily be adapted for different kinds of trading system. So for example, for a mean reversion system the nightly backtest could output the target prices for the range. For an intraday system it could output the target position sizes and entry  / exit points. This process reduces the amount of work the trading engine has to do during the day.


Python:
```python
from sysproduction.update_system_backtests import update_system_backtests
update_system_backtests()
```

Linux script:
```
. $SCRIPT_PATH/update_system_backtests
```

Called by: `run_systems`

The code to run each strategy's backtest is defined in the configuration parameter in the `control_config.yaml` file (or overridden in the `private_control_config.yaml` file): `process_configuration_methods/run_systems/strategy_name/`. For example:

```
process_configuration_methods:
  run_systems:
    example:
      max_executions: 1
      object: sysproduction.strategy_code.run_system_classic.runSystemClassic
      backtest_config_filename: systems.provided.futures_chapter15.futures_config.yaml

```


The sub-parameters do the following:

- `object` the class of the code that runs the system, eg `sysproduction.strategy_code.run_system_classic.runSystemClassic` This class **must** provide a method `run_backtest` that has no arguments.
- `backtest_config_filename` the location of the YAML configuration file to pass to the strategy runner eg `systems.provided.futures_chapter15.futures_config.yaml`

The following optional parameters are used only by `run_systems`:
- `max_executions` the number of times the backtest should be run on each iteration of run_systems. Normally 1, unless you have some whacky intraday system. Can be omitted.
- `frequency` how often, in minutes, the backtest is run. Normally 60 (but only relevant if max_executions>1). Can be omitted.

See [system runners](#system-runner) and scheduling processes(#process-configuration) for more details.

The backtest will use the most up-to-date prices and capital, so it makes sense to run this after these have updated.

### Generate orders for each strategy

Once each strategy knows what it wants to do, we generate orders. These will depend on the strategy; for the classic system we generate optimal positions that are then compared with current positions to see what trades are needed (or not). Other strategies may have specific limits ('buy but only at X or less'). Importantly these are *instrument orders*. These will then be mapped to actual [*contract level* orders](#positions-and-order-levels).

Python:
```python
from sysproduction.update_strategy_orders import update_strategy_orders
update_strategy_orders()
```

Linux script:
```
. $SCRIPT_PATH/update_strategy_orders
```

Called by: `run_strategy_order_generator`


The code to run each strategy's backtest is defined in the configuration parameter in the `control_config.yaml` file (or overridden in the `private_control_config.yaml` file): `process_configuration_methods/run_systems/strategy_name/`. For example:


```
  run_strategy_order_generator:
    example:
      object: sysexecution.strategies.classic_buffered_positions.orderGeneratorForBufferedPositions
      max_executions: 1
```

- `object` the class of the code that generates the orders, eg `sysexecution.strategies.classic_buffered_positions.orderGeneratorForBufferedPositions`. This must provide a method `get_and_place_orders` (which it will, as long as the class inherits from `orderGeneratorForStrategy`)

The following optional parameters are used only by `run_strategy_order_generator`:
- `max_executions` the number of times the generator should be run on each iteration of run_systems. Normally 1, unless you have some whacky intraday system. Can be omitted.
- `frequency` how often, in minutes, the generator is run. Normally 60 (but only relevant if max_executions>1). Can be omitted.

See [system order generator](#strategy-order-generator) and scheduling processes(#process-configuration) for more details.



### Execute orders

Once we have orders on the instrument stack (put there by the order generator), we need to execute them. This is done by the stack handler, which handles all three order stacks (instrument stack, contract stack and broker stack).

Python:
```python
from sysproduction.run_stack_handler import run_stack_handler
run_stack_handler()
```

Linux script:
```
. $SCRIPT_PATH/run_stack_handler
```

Notice that the stack handler only exists as a run process, as it's designed to run throughout the day.

The behaviour of the stack handler is extremely complex (and it's worth reading [this](#positions-and-order-levels) again, before reviewing this section). Here is the normal path an order takes:

- Instrument order created (by the strategy order generator)
- Spawn a contract order from an instrument order
- Create a broker order from a contract order and submit this to the broker
- Manage the execution of the order (technically done by execution algo code, but this is called by the stack handler), and note any fills that are returned
- Pass fills upwards; if a broker order is filled then the contract order should reflect that, and if a contract order is filled then an instrument order should reflect that
- Update position tables when fills are received
- Handle completed orders (which are fully filled) by deleting them from the stack after copying them to the historic order table

In addition the stack handler will:

- Check that the broker and database positions are aligned at contract level, if not then it will lock the instrument, so it can't be traded. Locks can be cleared automatically once positions reconcile again, or using [interactive_order_stack](#interactive-order-stack).
- Generate orders if a [roll status](#interactively-roll-adjusted-prices) is Force, Force Outright or Close
- Safely clear the order stacks at the end of the day or when the process is stopped by cancelling existing orders, and deleting them from the order stack.

That's quite a list, hence the use of the [interactive_order_stack](#interactive-order-stack) to keep it in check!

The stack handler will also periodically sample the bid/ask spread on all instruments. This is used to help with cost analysis (see the relevant [reports](#reporting) section).

## Interactive scripts to modify data

### Manual check of futures contract historical price data
(Whenever required)

You should run these if the normal price collection has identified a spike (for which you'd be sent an email, if you've set that up).

Python:
```python
from sysproduction.interactive_manual_check_historical_prices import interactive_manual_check_historical_prices
interactive_manual_check_historical_prices(instrument_code)
```

Linux script:
```
. $SCRIPT_PATH/interactive_manual_check_historical_prices
```

The script will pull in data from interactive brokers, and the existing data. It will behave in the same way as `update_historical_prices`, except you have the option to change the price filter configuration before you begin. The default config is: 

```yaml
priceFilterConfig(ignore_future_prices=True, ignore_prices_with_zero_volumes_daily=False, ignore_prices_with_zero_volumes_intraday=True, ignore_zero_prices=True, ignore_negative_prices=False, max_price_spike=8)
```

(Any of these values could be different if overridden in your own config)

Next it will check for spikes. If any spikes are found, then the user is interactively asked if they wish to (a) accept the spiked price, (b) use the previous time periods price instead, or (c) type a number in manually. You should check another data source to see if the spike is 'real', if so accept it, otherwise type in the correct value. Using the previous time periods value is only advisable if you are fairly sure that the price change wasn't real, and you don't have a source to check with.

If a new price is typed in then that is also spike checked, to avoid fat finger errors. So you may be asked to accept a price you have just typed in manually if that still results in a spike. Accepted or previous prices are not spike checked again.

Spikes are only checked on the FINAL price in each bar, and the user is only given the opportunity to correct the FINAL price. If the FINAL price is changed, then the OPEN, HIGH, and LOW prices are also modified; adding or subtracting the same adjustment that was made to the final price. The system does not currently use OHLC prices, but you should be aware of this creating potential inaccuracies. VOLUME figures are left unchanged if a price is corrected.

Once all spikes are checked for a given contract then the checked data is written to the database, and the system moves on to the next contract.


### Manual check of FX price data
(Whenever required)

You should run these if the normal price collection has identified a spike (for which you'd be sent an email, if you've set that up).


Python:
```python
from sysproduction.interactive_manual_check_fx_prices import interactive_manual_check_fx_prices
interactive_manual_check_fx_prices(fx_code)
```

Linux script:
```
. $SCRIPT_PATH/interactive_manual_check_fx_prices
```

See [manual check of futures contract prices](#manual-check-of-futures-contract-historical-price-data) for more detail. Note that as the FX data is a single series, no adjustment is required for other values.


### Interactively modify capital values

Python:
```python
from sysproduction.interactive_update_capital_manual import interactive_update_capital_manual
interactive_update_capital_manual()
```

Linux script:
```
. $SCRIPT_PATH/interactive_update_capital_manual
```

See [capital](#capital) to understand how capital works.
This function is used interactively to control total capital allocation in any of the following scenarios:

- You want to initialise the total capital available in the account. If this isn't done, it will be done automatically when `update_total_capital` runs with default values. The default values are brokerage account value = total capital available = maximum capital available (i.e. you start at HWM), with accumulated profits = 0. If you don't like any of these values then you can initialise them differently.
- You have made a withdrawal or deposit in your brokerage account, which would otherwise cause the apparent available capital available to drop, and needs to be ignored
- There has been a large change in the value of your brokerage account. A filter has caught this as a possible error, and you need to manually confirm it is ok.
- You want to delete capital entries for some recent period of time (perhaps because you missed a withdrawal, and it screwed up your capital)
- You want to delete all capital entries (and then probably reinitialise). This is useful if, for example, you've been running a test account and want to move to production.
- You want to make some other modification to one or more capital entries. Only do this if you know exactly what you are doing!




### Interactively roll adjusted prices
(Whenever required)

Allows you to change the roll state and roll from one priced contract to the next.

Python:
```python
from sysproduction.interactive_update_roll_status import interactive_update_roll_status
interactive_update_roll_status(instrument_code)
```

Linux script:
```
. $SCRIPT_PATH/interactive_update_roll_status
```

There are four different modes that this can be run in:

- Manually input instrument codes and manually decide when to roll
- Cycle through instrument codes automatically, but manually decide when to roll
- Cycle through instrument codes automatically, auto decide when to roll, manually confirm rolls
- Cycle through instrument codes automatically, auto decide when to roll, automatically roll

#### Manually input instrument codes and manually decide when to roll

You enter the instrument code you wish to think about rolling.

The first thing the process will do is create and print a roll report. See the [roll report](#roll-report-daily) for more information on how to interpret the information shown. You will then have the option of switching between roll modes. Not all modes will be allowed, depending on the current positions that you are holding and the current roll state.

The possible options are:

- No roll. Obvious.
- Passive. This will tactically reduce positions in the priced contract, and open new positions in the forward contract.
- Force. This will pause all normal trading in the relevant instrument, and the stack handler will create a calendar spread trade to roll from the priced to the forward contract.
- Force outright. This will pause all normal trading, and create two outright trades (closing the priced contract position, opening a forward position).
- Roll adjusted. This is only possible if you have no positions in the current price contract. It will create a new adjusted and multiple price series, hence the current forward contract will become the new priced contract (and everything else will shift accordingly). Adjusted price changes are manually confirmed before writing to the database.
- No open. No opening trades as we are near to expiry, but the forward contract is not liquid enough
- Close. Close position in near contract only

Once you've updated the roll status you have the option of choosing another instrument, or aborting.

NOTE: Adjusted price rolling will fail if the system can't find aligned prices for the current and forward contract. In this case you have the option of forward filling the prices - it will make the roll less accurate, but at least you can keep that instrument in your system.

#### Cycle through instrument codes automatically, but manually decide when to roll

This chooses a subset of instruments that are expiring soon. You will be prompted for the number of days ahead you want to look for expiries. This then behaves exactly like the manual option above, except it automatically cycles through the relevant subset of instruments.

#### Cycle through instrument codes automatically, auto decide when to roll, manually confirm rolls

Again this will first choose a subset of instruments that are expiring soon. The script then gives you the default auto rolls options, and offers the chance to adjust them. The default params are: 

```
auto_roll_if_relative_volume_higher_than: 1.0
min_relative_volume: 0.01
min_absolute_volume: 100
near_expiry_days: 10
default_roll_state_if_undecided: 'Ask'
auto_roll_expired: True
```

What happens next will depend on the parameters you have decided upon:

- If the volume in the forward contract is less than the required relative volume, we do nothing
- If the relative volume is fine, and you have no position in the priced contract, then we automatically decide to roll adjusted prices
- If the relative volume is fine, and you have a position in the priced contract, and you have asked to manually input the required state on a case by case basis: that's what will happen
- If the relative volume is fine, and you have a position in the priced contract, and you have NOT asked to manually input the required state, then the state will automatically be changed to one of passive, force, or force outright (as selected). I strongly recommend using Passive rolling here, and then manually changing individual instruments if required.

If a decision is made to roll adjusted prices, you will be asked to confirm you are happy with the prices changes before they are written to the database.

I recommend that you run a roll report after doing this to see what state things are in.

#### Cycle through instrument codes automatically, auto decide when to roll, automatically roll

This is exactly like the previous option, except that if a decision is made to roll adjusted prices, this will happen automatically without user confirmation.

## Menu driven interactive scripts

The remaining interactive scripts allow you to view and control a large array of things, and hence are menu-driven. There are three such scripts:

- interactive_controls: Trade limits, position limits, process control and monitoring
- interactive_diagnostics: View backtest objects, generate ad hoc reports, view logs/emails and errors; view prices, capital, positions & orders, and configuration.
- interactive_order_stack: View order stacks and positions, create orders, net/cancel orders, lock/unlock instruments, delete and clean up the order stack.

Menus are nested, and a common pattern is that *return* will go back a step, or exit.

### Interactive controls

Tools to control the system's behaviour, including operational risk controls.

Python:
```python
from sysproduction.interactive_controls import interactive_controls 
interactive_controls()
```

Linux script:
```
. $SCRIPT_PATH/interactive_controls
```

#### Trade limits

We can set limits for the maximum number of trades we will do over a given period, and for a specific instrument, or a specific instrument within a given strategy. Limits are applied within run_stack_handler whenever a broker order is about to be generated from a contract order. Options are as follows:

- View limits
- Change limits (instrument, instrument & strategy)
- Reset limits (instrument, instrument & strategy): helpful if you have reached your limit but want to keep trading, without increasing the limits upwards
- Autopopulate limits

Autopopulate uses current levels of risk to estimate the appropriate trade limit. So it will make limits smaller when risk is higher, and vice versa. It makes a lot of assumptions when setting limits: that all your strategies have the same risk limit (which you can set), and the same IDM (also can be modified), and that all instruments have the same instrument weight (which you can set), and trade at the same speed (again you can set the maximum proportion of typical position traded daily). It does not use actual instrument weights, and it only sets limits that are global for a particular instrument. It also assumes that trade sizes scale with the square root of time for periods greater than one day.

#### Position limits

We can set the maximum allowable position that can be held in a given instrument, or by a specific strategy for an instrument. An instrument trade that will result in a position which exceeds this limit will be rejected (this occurs when run_strategy_order_generator is run). We can:

- View limits
- Change limits (instrument, instrument & strategy)
- Autopopulate limits

Autopopulate uses current levels of risk to estimate the appropriate position limit. So it will make position limits smaller when risk is higher, and vice versa. It makes a lot of assumptions when setting limits: that all your strategies have the same risk limit (which you can set), and the same IDM (also can be modified), and that all instruments have the same instrument weight (which you can set). It does not use actual instrument weights, and it only sets limits that are global for a particular instrument.

The dynamic optimisation strategy will also use position limits in its optimisation in production (not in backtests, since fixed position limits make no sense for a historical backtest).

#### Trade control / override

Overrides allow us to reduce positions for a given strategy, for a given instrument (across all strategies), or for a given instrument & strategy combination. They are either:

- a multiplier, between 0 and 1, by which we multiply the desired . A multiplier of 1 is equal to 'normal', and 0 means 'close everything'
- a flag, allowing us only to submit trades which reduce our positions
- a flag, allowing no trading to occur in the given instrument.

Overrides are also set as a result of configured information about different instruments; see the [instruments documentation](/docs/instruments.md) for more detail.

Instrument trades will be modified to achieve any required override effect (this occurs when run_strategy_order_generator is run). We can:

- View overrides
- Update / add / remove override (for strategy, instrument, or instrument & strategy)

See the [instruments documentation](instruments.md) for more discussion on overrides.

#### Broker client IDs

Allows us to release any unused client IDs. Don't do this if any IB connections are active! Automatically called by the startup script.

#### Process control & monitoring

Allows us to control how processes behave.

See [scheduling](#pysystemtrade-scheduling).


##### View processes

Here's an example of the relevant output, start/end times, currently running, status, and PID (process ID).

```
run_capital_update            : Last started 2020-12-08 15:56:32.323000 Last ended status 2020-12-08 14:31:46.601000 GO      PID 63652.0    is running
run_daily_prices_updates      : Last started 2020-12-08 12:36:04.850000 Last ended status 2020-12-08 13:54:47.885000 GO      PID None       is not running
run_systems                   : Last started 2020-12-08 14:10:30.485000 Last ended status 2020-12-08 14:42:40.945000 GO      PID None       is not running
run_strategy_order_generator  : Last started 2020-12-08 14:46:28.013000 Last ended status 2020-12-08 14:49:44.081000 GO      PID None       is not running
run_stack_handler             : Last started 2020-12-08 13:43:53.628000 Last ended status 2020-12-08 14:22:55.388000 GO      PID None       is not running
run_reports                   : Last started 2020-12-08 15:48:55.595000 Last ended status 2020-12-07 23:43:13.476000 GO      PID 62388.0    is running
run_cleaners                  : Last started 2020-12-08 14:51:19.380000 Last ended status 2020-12-08 14:51:40.609000 GO      PID None       is not running
run_backups                   : Last started 2020-12-08 14:54:04.856000 Last ended status 2020-12-08 00:05:48.444000 GO      PID 61604.0    is running
```

You can use the PID to check using the Linux command line eg `ps aux | grep 86140` if a process really is running (in this case I'm checking if run_capital_update really is still going), or if it's abnormally aborted (in which case you will need to change it to 'not running' before relaunching - see below). This is also done automatically by the [system monitor and/or dashboard](/docs/dashboard_and_monitor.md), if running.

Note that processes that have launched but waiting to properly start (perhaps because it is not their scheduled start time, or because another process has not yet started) will be shown as not running and will have no PID registered. You can safely kill them.

#####  Change status of process

You can change the status of any process to STOP, GO or NO RUN. A process which is NO RUN will continue running, but won't start again. This is the correct way to stop processes that you want to kill, as it will properly update their process state and (importantly in the case of run stack handler) do a graceful exit. Stop processes will only stop once they have close running their current method, which means for run_systems and run_strategy_order_generator they will stop when the current strategy has close processing (which can take a while!).

If a process refuses to STOP, then as a last resort you can use `kill NNNN` at the command line where NNNN is the PID, but there may be data corruption, or weird behaviour (particularly if you do this with the stack handler), and you will definitely need to mark it as close (see below).

Marking a process as START won't actually launch it, you will have to do this manually or wait for the crontab to run it. Nor will the process run if it's preconditions aren't met (start and end time window, previous process).

##### Global status change

Sometimes you might want to mark all processes as STOP (emergency shut down?) or GO (post emergency restart).


#####  Mark as close

This will manually mark a process as close. This is done automatically when a process finishes normally, or is told to stop, but if it terminates unexpectedly then the status may well be set as 'running', which means a new version of the process can't be launched until this flag is cleared. Marking a process as close won't stop it if it is still running! Use 'change status' instead. Check the process PID isn't running using `ps aux | grep NNNNN` where NNNN is the PID, before marking it as close.

Note that the startup script will also mark all processes as close (as there should be no processes running on startup). Also, if you run the next option ('mark all dead processes as close') this will be automatic.

#####  Mark all dead processes as close

This will check to see if a process PID is active, and if not it will mark a process as close, assumed crashed. This is also done periodically by the [system monitor and/or dashboard](/docs/dashboard_and_monitor.md), if running.

#####  View process configuration

This allows you to see the configuration for each process, either from `control_config.yaml` or the `private_control_config.yaml` file. See [scheduling](#pysystemtrade-scheduling).

#### Update configuration

These options allow you to update, or suggest how to update, the instrument and roll configuration.

- Auto update spread cost configuration based on sampling and trades
- Safely modify roll parameters
- Check price multipliers are consistent with IB and configuration file


### Interactive diagnostics

Tools to view internal diagnostic information.

Python:
```python
from sysproduction.interactive_diagnostics import interactive_diagnostics
interactive_diagnostics()
```

Linux script:
```
. $SCRIPT_PATH/interactive_diagnostics
```

#### Backtest objects

It's often helpful to examine the backtest output of run_systems to understand where particular trades came from (above and beyond what the [strategy report](#strategy-report) gives you). These are saved as a combination of pickled cache and configuration YAML file, allowing you to see the calculations done when the system ran.

##### Output choice

First of all you can choose your output:

- Interactive Python. This loads the backtest, and effectively opens a small Python interpreter (actually it just runs eval on the input).
- Plot. This loads a menu allowing you to choose a data element in the backtest, which is then plotted (will obviously fail on headless servers)
- Print. This loads a menu allowing you to choose a data element in the backtest, which is then printed to screen.
- HTML. This loads a menu allowing you to choose a data element in the backtest, which is then output to an HTML file (outputs to ~/temp.html), which can easily be web browsed

##### Choice of strategy and backtest

Next you can choose your strategy, and the backtest you want to see - all backtests are saved with a timestamp (normally these are kept for a few days). The most recent backtest file is the default.

##### Choose stage / method / arguments

Unless you're working in 'interactive python' mode, you can then choose the stage and method for which you want to see output. Depending on exactly what you've asked for, you'll be asked for other parameters like the instrument code and possibly trading rule name. The time series of calling the relevant method will then be shown to you using your chosen output method.

##### Alternative Python code

If you prefer to do this exercise in your Python environment, then this will interactively allow you to choose a system and dated backtest, and returns the system object for you to do what you wish.

```python

from sysproduction.data.backtest import user_choose_backtest
backtest = user_choose_backtest()
system = backtest.system
```

#### Instrument configuration

##### View instrument configuration data

View the configuration data for a particular instrument, eg for DAX:

```{'Description': 'DAX 30 Index (Deutsche Aktien Xchange 30)', 'Pointsize': 1.0, 'Currency': 'EUR', 'AssetClass': 'Equity', 'PerBlock': 0.4, 'Percentage': 0.0, 'PerTrade': 0, 'Region': 'EMEA'}```

Note there may be further configuration stored in other places, eg broker specific.

#####  View contract configuration data

View the configuration for a particular contract, eg:

```
{'contract_date_dict': {'expiry_date': (2023, 6, 19), 'contract_date': '202306', 'approx_expiry_offset': 0}, 'instrument_dict': {'instrument_code': 'EDOLLAR'}, 'contract_params': {'currently_sampling': True}}
Rollcycle parameters hold_rollcycle:HMUZ, priced_rollcycle:HMUZ, roll_offset_day:-1100.0, carry_offset:-1.0, approx_expiry_offset:18.0
```

See [here](#interactively-roll-adjusted-prices) to understand roll parameters.

#####  View trading hours for all instruments

This function prints out the trading hours and session duration for the next three trading days, per instrument. For example:

```
AEX                 : 23/02 08:00 to 23/02 15:00 (7.0 hours) 24/02 08:00 to 24/02 15:00 (7.0 hours) 25/02 08:00 to 25/02 15:00 (7.0 hours)
ALUMINIUM           : 23/02 14:00 to 23/02 19:00 (5.0 hours) 24/02 14:00 to 24/02 19:00 (5.0 hours) 25/02 14:00 to 25/02 19:00 (5.0 hours)
AUDJPY              : 23/02 15:00 to 23/02 20:00 (5.0 hours) 24/02 15:00 to 24/02 20:00 (5.0 hours) 25/02 15:00 to 25/02 20:00 (5.0 hours)
AUD_micro           : 23/02 15:00 to 23/02 20:00 (5.0 hours) 24/02 15:00 to 24/02 20:00 (5.0 hours) 25/02 15:00 to 25/02 20:00 (5.0 hours)
BOBL                : 23/02 08:00 to 23/02 15:00 (7.0 hours) 24/02 08:00 to 24/02 15:00 (7.0 hours) 25/02 08:00 to 25/02 15:00 (7.0 hours)
...
V2X                 : 23/02 08:00 to 23/02 15:00 (7.0 hours) 24/02 08:00 to 24/02 15:00 (7.0 hours) 25/02 08:00 to 25/02 15:00 (7.0 hours)
VIX                 : 23/02 15:00 to 23/02 20:00 (5.0 hours) 24/02 15:00 to 24/02 20:00 (5.0 hours) 25/02 15:00 to 25/02 20:00 (5.0 hours)
WHEAT               : 23/02 15:30 to 23/02 18:20 (2.8 hours) 24/02 15:30 to 24/02 18:20 (2.8 hours) 25/02 15:30 to 25/02 18:20 (2.8 hours)
YENEUR              : 23/02 15:00 to 23/02 20:00 (5.0 hours) 24/02 15:00 to 24/02 20:00 (5.0 hours) 25/02 15:00 to 25/02 20:00 (5.0 hours)
ZAR                 : 23/02 15:00 to 23/02 20:00 (5.0 hours) 24/02 15:00 to 24/02 20:00 (5.0 hours) 25/02 15:00 to 25/02 20:00 (5.0 hours)
```

See [here](#trading-hours-configuration) for how to configure and customise trading hours.

#### Emails

##### View stored emails

The system sends emails quite a bit: when critical errors occur, when reports are sent, and when price spikes occur. To avoid spamming a user, it won't send an email with the same subject line as a previous email sent in the last 24 hours. Instead, these emails are stored, and if you view them here they will be printed and then deleted from the store. The most common case is if you get a large price move which affects many different contracts for the same instrument; the first spike email will be sent, and the rest stored.


#### View prices

View dataframes for historical prices. Options are:

- Individual futures contract prices
- Multiple prices
- Adjusted prices
- FX prices

#### View capital

View historical series of capital. See [here](#capital) for more details on how capital works. You can see the:

- Capital for a strategy
- Total capital (across all strategies): current capital
- Total capital: broker valuation
- Total capital: maximum capital
- Total capital: accumulated returns

#### Positions and orders

View historic series of positions and orders. Options are:

- Optimal position history (instruments for strategy)
- Actual position history (instruments for strategy)
- Actual position history (contracts for instrument)
- List of historic instrument level orders (for strategy)
- List of historic contract level orders (for strategy and instrument)
- List of historic broker level orders (for strategy and instrument)
- View full details of any individual order (of any type)

#### Reports

Allows you to run any of the [reports](#reporting) on an ad-hoc basis.


### Interactive order stack

Allows us to examine and control the [various order stacks](#positions-and-order-levels).

Python:
```python
from sysproduction.interactive_order_stack import interactive_order_stack
interactive_order_stack()
```

Linux script:
```
. $SCRIPT_PATH/interactive_order_stack
```

#### View

Options are:

- View specific order (on any stack)
- View instrument order stack
- View contract order stack
- View broker order stack (as stored in the local database)
- View broker order stack (will get all the active orders and completed trades from the broker API)
- View positions (optimal, instrument level, and contract level from the database; plus contract level from the broker API)

#### Create orders

Orders will normally be created by run_strategy_order_generator or by run_stack_handler, but sometimes it's useful to do these manually.

##### Spawn contract orders from instrument orders

If the stack handler is running it will periodically check for new instrument orders, and then create child contract orders. However, you can do this manually. Use case for this might be debugging, or if you don't trust the stack handler and want to do everything step by step, or if you're trading manually (in which case the stack handler won't be running).

##### Create force roll contract orders

If an instrument is in a Force or Force Outright roll status (see [rolling](#interactively-roll-adjusted-prices)), then the stack handler will, at the start of day, create new roll orders (consisting of a parent instrument order that is an intramarket spread, allocated to the phantom 'rolling' strategy, and a child contract order). However, you can do this manually. Use case for this might be debugging, or if you don't trust the stack handler and want to do everything step by step, or if you're trading manually (in which case the stack handler won't be running).


##### Create (and try to execute...) IB broker orders

If the stack handler is running it will periodically check for contract orders that aren't completely filled, and generate broker orders that it will submit to the broker and then pass to an algo to manage the execution. However, you can do this manually. Use case for this might be debugging, or if you don't trust the stack handler and want to do everything step by step.


##### Balance trade: Create a series of trades and immediately fill them (not actually executed)

Ordinarily the stack handler will pick up on any fills, and act accordingly. However, there are times when this might not happen. If a position is closed by IB because it is close to expiry, or you submit a manual trade on another platform, or if the stack handler crashes after submitting the order but executing the fill... the possibilities are endless. Anyway, this is a serious problem because the positions you actually have (in the brokers records) won't be reflected in the position database which will be reported in the [reconcile report](#reconcile-report) - a condition which, when detected, will lock the instrument, so it can't be traded until the problem is solved. Less seriously, you'll be missing the trade from your historic trade database.

To get round this you should submit a balance trade, which will ripple through the databases like a normal trade, but won't actually be sent to the broker for execution; thus replacing the missing trade.

##### Balance instrument trade: Create a trade just at the strategy level and fill (not actually executed)

Ordinarily the strategy level positions (for instruments, per strategy, summed across contracts) should match the contract level positions (for instruments and contracts, summed across strategies). However, if for some reason an order goes astray you will end up with a mismatch (which will be reported in the [reconcile report](#reconcile-report)). To solve this you can submit an order just at the strategy level (not allocated to a specific contract) which will solve the problem but isn't actually executed.


##### Manual trade: Create a series of trades to be executed

Normally run_strategy_order_generator creates all the trades you should need, but sometimes you might want to generate a manual trade. This could be for testing, because you urgently want to close a position (which you ought to do with an [override](#trade-control--override)), or because something has gone wrong with the roll process, and you're stuck in a contract that the system won't automatically close.

Manual trades are not the same as balance trades: they will actually go to the broker for execution!

Note, you can create a manual spread trade: enter the instrument position as zero, ask to create contract orders, then enter the number of legs you want.

##### Cash FX trade

Cash FX isn't the primary asset class traded in pysystemtrade, but we trade FX anyway without realising it (unless you only trade in your account currency). When you buy or sell a futures contract in another country, it will require margin. If you don't have margin in that currency, then IB will lend it to you. Borrowing money in foreign currencies incurs a spread, so it's better to do a spot FX trade, converting your domestic currency (which will probably be earning 0% interest anyway) into the margin currency. As a rule, I periodically optimise my currency holdings, so I have a diversified portfolio of currency. Others may prefer to 'sweep' all excess foreign currencies back to their home currency to reduce unwanted currency Beta. Or you could live dangerously, and try and maintain a larger balance in currencies with higher positive deposit rates (basically the carry trade).

First of all you see the balances in each currency. Note, these aren't excess or uncleared balances, so you will need to run an IB report to see what you really have spare or are short of. You can then create an FX trade. In specifying the pairing, don't forget there is a market convention so if you get the pairing the wrong way round your order will be rejected.

#### Netting, cancellation and locks


##### Cancel broker order

If you have an order that has been submitted, and you want to cancel it, here is where you come.

##### Net instrument orders

The complexity of the order stacks is there for a reason; it allows different kinds of strategies to submit trades at the same time. One advantage of this is that orders can be netted. Ordinarily the stack handler will do this netting, but you might want to trigger it manually.

##### Lock/unlock order

There is a 'lock' in the order database, basically an explicit flag preventing the order from being modified. Certain operations which span multiple data tables will impose locks first so the commit does not partially fail (I'm using noSQL so there is no explicit cross table commit available). If operations fail mid-lock they will usually try and fall back and remove locks, but this doesn't always work out. So it sometimes necessary to manually unlock orders, and for symmetry manually lock them.


##### Lock/unlock instrument code

If there is a mismatch between the brokers record of positions, and ours, then a lock will be placed on the instrument and no broker trades can be issued for it. This is done automatically by the stack handler. Once a mismatch clears, the stack handler will remove the lock. But you can also do these operations manually.

Note: if you want to avoid trading in an instrument for some other reason, use an [override](#trade-control--override) not a lock: a lock will be automatically cleared by the system, an override won't be.


##### Unlock all instruments

If the broker API has gone crazy or died for some reason then all instruments with active positions will be locked. This is a quick way of unlocking them.

##### Remove Algo lock on contract order

When an algo begins executing a contract order (in part or in full), it locks it. That lock is released when the order has close executing. If the stack handler crashes before that can happen, then no other algo can execute it. Although the order will be deleted in the normal end of day stack clean up, if you can't wait that long you can manually clear the problem.


#### Delete and clean

##### Delete entire stack (CAREFUL!)

You can delete all orders on any of the three stacks. I can't even begin to describe how bad an idea this is. If you want to stop trading urgently then I strongly advise using a [STOP command](#change-status-of-process) on run_stack_handler, or calling the end of day process manually (described below) - which will leave the stack handler running. Only use when debugging or testing, if you really know what you're doing.

##### Delete specific order ID (CAREFUL!)

You can delete a specific live order from the database. Again, this will most likely lead to all kinds of weird side effects. This won't cancel the order either; the broker will continue to try and execute it. Only use when debugging or testing, if you really know what you're doing.

##### End of day process (cancel orders, mark all orders as complete, delete orders)

When run_stack_handler has done it's work (either because it's time is up, or it has received a STOP command) it will run a cleanup process. First it will cancel any active orders. Then it will mark all orders as complete, which will update position databases, and move orders to historical data tables. Finally, it deletes every order from every stack; ensuring no state continues to the next day (which could lead to weird behaviour).

I strongly advise running this rather than deleting the stack, unless you know exactly what you're doing and have a very valid reason for doing it!


## Reporting, housekeeping and backup scripts

### Run all reports

Python:
```python
from sysproduction.run_reports import run_reports
run_reports()
```

Linux script:
```
. $SCRIPT_PATH/run_reports
```

See [reporting](#reporting) for details on individual reports.


### Delete old pickled backtest state objects

Python:
```python
from sysproduction.clean_truncate_backtest_states
clean_truncate_backtest_states()
```

Linux script:
```
. $SCRIPT_PATH/clean_truncate_backtest_states
```

Called by: `run_cleaners`

Every time run_systems runs it creates a pickled backtest and saves a copy of its configuration file. This makes it easier to use them for [diagnostic purposes](#backtest-objects).

However, these file are large! So we delete anything more than 5 days old.



### Clean up old logs


Python:
```python
from sysproduction.clean_truncate_log_files import clean_truncate_log_files
clean_truncate_log_files()
```

Linux command line:
```
cd $SCRIPT_PATH
. clean_truncate_log_files
```

Called by: `run_cleaners`

I love logging! Which does mean there are a lot of log entries. This deletes any that are more than a month old.

### Truncate echo files

Python:
```python
from sysproduction.clean_truncate_echo_files import clean_truncate_echo_files
clean_truncate_echo_files()
```

Linux command line:
```
cd $SCRIPT_PATH
. clean_truncate_echo_files
```

Called by: `run_cleaners`

Every day we generate echo files with extension .txt; this process renames ones from yesterday and before with a date suffix, and then deletes anything more than 30 days old.


### Backup DB to CSV files

Python:

```python
from sysproduction.backup_db_to_csv import backup_db_to_csv

backup_db_to_csv()
```

Linux script:
```
. $SCRIPT_PATH/backup_db_to_csv
```

Called by: `run_backups`

See [backups](#mongodb--csv-data).

- It copies data from MongoDB and Parquet into a temporary CSV directory
- It then copies the CSV files to the backup directory, "offsystem_backup_directory", subdirectory /csv



### Backup state files


Python:
```python
from sysproduction.backup_state_files import backup_state_files
backup_state_files()
```

Linux script:
```
. $SCRIPT_PATH/backup_files
```

Called by: `run_backups`

It copies backtest pickle and config files to the backup directory,  "offsystem_backup_directory", subdirectory /statefile

**Important**: the backed up files will contain any data you have added to your private config, some of which may be sensitive (e.g., IB account number, email address, email password). If you choose to store these files with a cloud storage provider or backup service, you should consider encrypting them first (some services may do this for you, but many do not).

### Backup MongoDB dump


Python:
```python
from sysproduction.backup_mongo_data_as_dump import *
backup_mongo_data_as_dump()
```

Linux script:
```
. $SCRIPT_PATH/backup_mongo_data_as_dump
```

Called by: `run_backups`

- Firstly it dumps the MongoDB databases to the local directory specified in the config parameter (`defaults.yaml` or private config YAML file) "mongo_dump_directory".
- Then it copies those dumps to the backup directory specified in the config parameter "offsystem_backup_directory", subdirectory `/mongo`


### Backup Parquet

Python:
```python
from sysproduction.backup_parquet_data_to_remote import *
backup_parquet_data_to_remote()
```

Linux script:
```
. $SCRIPT_PATH/backup_parquet_to_remote
```

Called by: `run_backups`

- Copies all parquet files to the backup directory specified in the config parameter "offsystem_backup_directory", subdirectory /parquet


### Start up script


Python:
```python
from sysproduction.startup import startup
startup()
```

Linux script:
```
. $SCRIPT_PATH/startup
```

There is some housekeeping to do when a machine starts up, primarily in case it crashed and did not close everything gracefully:

- Clear IB client IDs: Do this when the machine restarts and IB is definitely not running (or we'll eventually run out of IDs)
- Mark all running processes as close

## Scripts under other (non-linux) operating systems

There is a built-in Python mechanism for creating command line executables; it may make sense for those who want to have a production instance of pysystemtrade on macOS or Windows. Or for Linux users who would prefer to use the standard method than the supplied scripts. The mechanism is provided by the packaging tools, and configured in pyproject.toml. See the [docs here](https://setuptools.pypa.io/en/latest/userguide/entry_point.html). 

You add a new *entry_points* section to `pyproject.toml` file like:

```
...
[project.scripts]
interactive_controls = "sysproduction.interactive_controls:interactive_controls"
interactive_diagnostics = "sysproduction.interactive_diagnostics:interactive_diagnostics"
interactive_manual_check_fx_prices = "sysproduction.interactive_manual_check_fx_prices:interactive_manual_check_fx_prices"
interactive_manual_check_historical_prices = "sysproduction.interactive_manual_check_historical_prices:interactive_manual_check_historical_prices"
interactive_order_stack = "sysproduction.interactive_order_stack:interactive_order_stack"
interactive_update_capital_manual = "sysproduction.interactive_update_capital_manual:interactive_update_capital_manual"
interactive_update_roll_status = "sysproduction.interactive_update_roll_status:interactive_update_roll_status"
...
```

When the project is installed, the above config would generate executable *shims* for all the interactive scripts into the current Python path, which when run, would execute the configured function. There are several advantages to this method:
- no need for additional code or scripts
- cross-platform compatibility
- standard Python
- no need to manipulate PATH or other env variables
- name completion
- works with any virtualenv flavour


# Scheduling

Running a fully or partially automated trading system requires the use of scheduling software that can launch new scripts at regular intervals, for example:

- processes that kick off when a machine is switched on
- processes that kick off daily
- processes that kick off several times a day (eg regular reports or reconciliation)


## Issues to consider when constructing the schedule

Things to consider when constructing a schedule include:

- Machine load   (eg avoid running computationally intensive processes when also trading where latency could be important). This is less important if you are running multiple machines.
- Database thrashing (eg avoid running input intensive reporting processes on database tables that are being actively read / written to by more important live trading processes)
- File lock / integrity (eg avoid running backups whilst active writes are occurring)
- Robustness (eg it's probably better to have trading processes shutting down each night and then restarting in the morning, than trying to keep them running continuously)


## Choice of scheduling systems

You need some sort of scheduling system to kick off the various top level processes (all scripts that are prefixed with run_). Ideally this would allow us to monitor processes, record their activity, control them remotely, run them a certain number of times, wait for other processes to run first (conditionality) and so on.

### Linux cron

The linux crontab is a thing of beauty, but it can't (easily?) handle things like conditional processes, nor does it do monitoring.

### Third party scheduler

There are plenty of third party schedulers, particular if you are working with something like Docker / Puppet.

### Windows task scheduler

I have not used this product (I don't use Windows or Mac products for ideological reasons, also they're rubbish and overpriced respectively), but in theory it should do the job.

### Python

You can use Python itself as a scheduler, using something like [this](https://github.com/dbader/schedule), which gives you the advantage of being platform independent. However, you will still need to ensure there is a Python instance running all the time. You also need to be careful about whether you are spawning new threads or new processes, since only one connection to IB Gateway or TWS can be launched within a single process.

### Manual system

It's possible to run pysystemtrade without any scheduling, by manually starting the necessary processes as required. This option might make sense for traders who are not running a fully automated system (though [you may want to keep most of the scheduling running anyway](#automation-options)).

### Hybrid of Python and cron

This is the approach I use in pysystemtrade, and it's described in more detail below. It ought to be possible to replace the cron component with another scheduler.

## Pysystemtrade scheduling

The scheduler built into pysystemtrade does not launch processes (this is still be done by the cron on a daily basis), but it does everything else:

- Record when processes have started and stopped, if they are still running, and what their process ID is.
- Run only in a specified time window (start time, end time)
- Run only when another process has already close (i.e. do not run_systems until prices have been updated)
- Allow interactive_controls to STOP processes, or prevent them from starting.
- Call 'methods', which are effectively sub processes, multiple times (up to a specified limit) and at specified time intervals (if required).
- Provides a monitoring tool which can also be used from a remote machine

### Configuring the scheduling

#### The crontab

Processes still need to be launched every day, since the pysystemtrade scheduler doesn't do that. However, their start time isn't critical, since separate start times can be configured in YAML files (more of that below).

Because I use cron myself, there are is a [cron tab included in pysystemtrade](https://github.com/pst-group/pysystemtrade/blob/master/sysproduction/linux/crontab).

Useful things to note about the crontab:

- We start the stack handler and capital update processes. These run 'all day' (you can envisage a situation in which other processes also run all day, if you are running certain kinds of intraday system). They will actually start and then stop when the process configuration (in YAML) tells them to.
- We then start a bunch of 'once a day' processes: `run_daily_price_updates`, `run_systems`, `run_strategy_order_generator`, `run_cleaners`, `run_backups`, `run_reports`. They are started in the sequence they will run, but their behaviour will actually be governed by the process configuration in YAML (below)
- On startup, we start a MongoDB instance, and run the [startup script](#start-up-script)

#### Process configuration

Process configuration is governed by the following config parameters (in [/syscontrol/control_config.yaml](/syscontrol/control_config.yaml), or these will be overridden by `/private/private_control_config.yaml`):

-  `process_configuration_start_time`: when the process starts (default 00:01)
- `process_configuration_stop_time`: when the process ends, regardless of any method configuration (default 23:50)
- `process_configuration_previous_process`: a process that has to have run in the previous 24 hours for the process to start (default: none)

Each of these is a dict, with process names as keys. All values are strings; start and stop times are in 24-hour format eg '23:05'. If a value is missing for any process, then we use the default. Here's the default YAML values, with some comments:

```
process_configuration_start_time:
  default: '00:01'
  run_stack_handler: '00:01'
  run_capital_update: '01:00'
  run_daily_prices_updates: '20:00' # we start these off at 5 minute intervals, although the previous process will govern how they actually run
  run_systems: '20:05'
  run_strategy_order_generator: '20:10'
  run_backups: '20:15'
  run_cleaners: '20:20'
  run_reports: '20:25'
process_configuration_stop_time:
  default: '23:50'
  run_strategy_order_generator: '19:30' # this in case we're running it throughout the day
  run_stack_handler: '19:45' # I stop trading late in the US afternoon session to give myself a few hours for daily processes to run
  run_capital_update: '19:50'
  run_daily_prices_updates: '23:50' # these are all nominal stop times
  run_systems: '23:50'
  run_backups: '23:50'
  run_cleaners: '23:50'
  run_reports: '23:50'
process_configuration_previous_process:
  run_systems: 'run_daily_prices_updates' # no point running a backtest with stale prices.
  run_strategy_order_generator: 'run_systems' # will be no orders to generate until backtest system has run
  run_cleaners: 'run_strategy_order_generator' # wait until the main 'big 3' daily processes have run before tidying up
  run_backups: 'run_cleaners' # this can take a while, will be less stuff to back up if we've already cleaned
  run_reports: 'run_strategy_order_generator' # will be more interesting reports if we run after other stuff has close

```

The configuration of methods that run from within each process are governed by the config parameter `process_configuration_methods`. That in turn contains a dict for each relevant process, which in turn has a dict for each method, and these have the following possible values:

- `frequency`: How many minutes pass before we run a method again (default: 0, no waiting time)
- `max_executions`: How many times to run the method (default: -1, which means there is no maximum)
- `run_on_completion_only`: Don't run until the process is stopping

(Why isn't there a 'run on start only' option? Well setting max_executions will do this; and if this method has to come before any others then just list it first in the configuration)

Note for `run_systems` and `run_strategy_order_generator` the methods are actually strategy names, and there are additional parameters that are specific to these processes.

Here is the full default control config with comments:

```
process_configuration_methods:
  run_capital_update:
    update_total_capital: # every 2 hours throughout the day; in a crisis I like to keep an eye on my account value
      frequency: 120
      max_executions: 10 # nominal figure, since uptime is a little less than 20 hours
    strategy_allocation:
      max_executions: 1 # don't bother updating more often than we run backtests
  run_daily_prices_updates: # all this stuff happens once. the order matters.
    update_fx_prices:
      max_executions: 1
    update_sampled_contracts:
      max_executions: 1
    update_historical_prices:
      max_executions: 1
    update_multiple_adjusted_prices:
      max_executions: 1
  run_stack_handler: # frequency 0 and max_executions -1 means we just keep doing them over and over again until the process stops...
    refresh_additional_sampling_all_instruments:
      frequency: 60
      max_executions: -1
    check_external_position_break:
      frequency: 0
      max_executions: -1
    spawn_children_from_new_instrument_orders:
      frequency: 0
      max_executions: -1
    generate_force_roll_orders:
      frequency: 0
      max_executions: 1
    create_broker_orders_from_contract_orders:
      frequency: 0
      max_executions: -1
    process_fills_stack:
      frequency: 0
      max_executions: -1
    handle_completed_orders:
      frequency: 0
      max_executions: -1
    safe_stack_removal:
      run_on_completion_only: True   # only run this once we're done
  run_reports:  # all this stuff happens once.
    costs_report:
      max_executions: 1
    liquidity_report:
      max_executions: 1
    status_report:
      max_executions: 1
    roll_report:
      max_executions: 1
    daily_pandl_report:
      max_executions: 1
    reconcile_report:
      max_executions: 1
    trade_report:
      max_executions: 1
  run_backups:
    backup_db_to_csv:
      max_executions: 1
    backup_files:
      max_executions: 1
    backup_mongo_data_as_dump:
      max_executions: 1
  run_cleaners:  # all this stuff happens once.
    clean_backtest_states:
      max_executions: 1
    clean_echo_files:
      max_executions: 1
    clean_log_files:
      max_executions: 1
```

You can override any of these in `/private/private_control_config.yaml`, but you *must* also include the following sections in your private control config file (add more if you have more strategies), or these run processes won't work:

```
process_configuration_methods:
  run_systems:
    example:  # strategy name
      max_executions: 1
      object: sysproduction.strategy_code.run_system_classic.runSystemClassic # additional parameter
      backtest_config_filename: systems.provided.futures_chapter15.futures_config.yaml #additional parameter
  run_strategy_order_generator:
    example: # strategy_name
      object: sysexecution.strategies.classic_buffered_positions.orderGeneratorForBufferedPositions # additional parameter passed
      max_executions: 1
```

Finally, you can optionally include arguments, which will be passed to certain methods within a process (or to all methods that are run on completion for a given process). For example:

```
arguments:
  run_daily_prices_updates:# name of process
    update_historical_prices: # everything in this block is passed as **kwargs to this method
      download_by_zone:
        ASIA: '07:00'
        EMEA: '18:00'
        US: '20:00'
    _methods_on_completion: # and this block is passed to all methods that run on completion only - make sure you use **kwargs to trap if required
        a: 'test'

```


### System monitor and dashboard

There is a crude monitoring tool, and a more sophisticated fancy dashboard, which you can use to monitor what the system is up to. [Read the doc file here.](/docs/dashboard_and_monitor.md)


### Troubleshooting?

Use status report and interactive_controls to investigate.

Why won't my process run?

- is it launching in the cron or equivalent scheduler?
- is it set to STOP or NO-RUN? Fix with interactive_controls
- is it before the start_time? Change the start time, or wait
- is it after the end_time? Change the end time, or wait until tomorrow
- has the previous process close? Wait, or remove dependency
- is it already running, or at least thinks it is already running because a previous iteration didn't fail? Mark the process as close with interactive_controls

Why has my process stopped?

- is it set to STOP?
- is it after the end_time?
- have all the methods close running, because they have exceeded their `max_executions`?

Why won't my method run?

- has it run out of `max_executions`?
- is it set to `run_on_completion_only`?


# Production system concepts

## Configuration files

Configuration for the system is spread across a few different places:

- System defaults
- Private config (which overrides the system defaults)
- Backtest config (which overrides the system defaults and the private config)
- Control configs: private and default
- Broker and data source specific config
- Instrument and roll configuration


### System defaults & Private config

Most configuration is stored in [/sysdata/config/defaults.yaml](/sysdata/config/defaults.yaml), with the possibility of overriding in the private configuration file `/private/private_config.yaml`, an example of which is here [/examples/production/private_config_example.yaml](/examples/production/private_config_example.yaml). Anything included in the private config will override the `defaults.yaml` file.

Exceptionally, the following are configuration options that are not in `defaults.yaml` and *must* be in `private_config.yaml`:

- `broker_account`: IB account id, str
- `offsystem_backup_directory`: if you're using off site backup (if not set it to a local drive or modify the backup scripts)

[Strategy configuration](#strategies)
- `strategy_list` (dict, keys are strategy names)
   - `strategy_name`
      - `load_backtests`
         - `object` class to create system instance, eg sysproduction.strategy_code.run_system_classic.runSystemClassic
         - `function` method in class to create system instance eg system_method
      - `reporting_code`
         - `function` to produce strategy reporting code eg sysproduction.strategy_code.report_system_classic.report_system_classic
- `strategy_capital_allocation` see [capital](#capital)
   - `function` to produce allocations eg sysproduction.strategy_code.strategy_allocation.weighted_strategy_allocation
   - `strategy_weights` dict of strategy names
      - `strategy_name` weight as float


The following are configuration options that are not in `defaults.yaml` and *may* be in `private_config.yaml`:

- `quandl_key`: if using quandl data
- `barchart_key`: if using barchart data
- `email_address`: if you want to get emailed errors and reports
- `email_pwd`
- `email_server`: this is the outgoing server


The following are configuration options that are in `defaults.yaml` and can be overridden in `private_config.yaml`:

[Email formatting](#psysystemtrade-reports)

- `email_body_preformatted`: `False`; set to `True` to send plain-text message bodies as escaped HTML inside `<pre>` tags.

[Backup paths](#data-backup)
- `backtest_store_directory` parent directory, backtests are stored under strategy_name subdirectory
- `csv_backup_directory`
- `mongo_dump_directory`
- `echo_directory`

[Broker](#linking-to-a-broker)
- `ib_ipaddress`: 127.0.0.1
- `ib_port`: 4001
- `ib_idoffset`: 100

[Database](#data-storage)
- `mongo_host`: 127.0.0.1
- `mongo_db`: 'production'
- `parquet_store`: '/home/me/data/parquet'  # location of parquet files 

[Price collection](#update-futures-contract-historical-price-data-daily)
- `max_price_spike`: 8
- `intraday_frequency`: H

[Capital calculation](#capital)
- `production_capital_method`: 'full'
- `base_currency` (also used by backtesting, but clearly more important here)




### System backtest YAML config file(s)

See the [user guide for backtesting](/docs/backtesting.md).

The interaction of system, private, and backtest configs can be a bit confusing. Inside a backtest (which can either be in production or sim mode), configuration options will be pulled in the following priority (1) specific backtest YAML configuration, (2) `private_config.yaml`, (3) `defaults.yaml` file. 

Outside of the backtest code, in production configuration options are pulled in the following priority order: (1) `private_config.yaml`, (2) `defaults.yaml` file. *The production code can't see inside your backtest configuration files - it is not specific to a strategy so doesn't know which configuration to look for*. 


### Control config files

As discussed above, these are used purely for control and monitoring purposes in [/syscontrol/control_config.yaml](/syscontrol/control_config.yaml), overridden by `/private/private_control_config.yaml`).

### Broker and data source specific configuration files

The following are configurations mainly for mapping from our codes to broker codes:

- [/sysbrokers/IB/ib_config_futures.csv](/sysbrokers/IB/config/ib_config_futures.csv)
- [/sysbrokers/IB/ib_config_spot_FX.csv](/sysbrokers/IB/config/ib_config_spot_FX.csv)


### Instrument and roll configuration

The following are CSV configurations used in both production and sim:

- [/data/futures/csvconfig/instrumentconfig.csv](/data/futures/csvconfig/instrumentconfig.csv) 
- [/data/futures/csvconfig/rollconfig.csv](/data/futures/csvconfig/rollconfig.csv) 


### Set up configuration


The following are used when initialising the database with its initial configuration, but will also be used in the simulation environment:

- [/data/futures/csvconfig/spreadcosts.csv](/data/futures/csvconfig/spreadcosts.csv) 

### Trading hours configuration

The default trading hours config for IB is specified at: [sysbrokers/IB/ib_config_trading_hours.yaml](https://github.com/pst-group/pysystemtrade/blob/develop/sysbrokers/IB/ib_config_trading_hours.yaml). The default config assumes GMT. Anyone living anywhere else must do both of the following for production trading:
- Update `GMT_offset_hours` in private config to your local timezone
- Copy the trading hours config into a new private config file at `private/private_config_trading_hours.yaml`, or if using a [custom private directory](#custom-private-directory), then `$PYSYS_PRIVATE_CONFIG_DIR/private_config_trading_hours.yaml`
- Update the per-timezone trading hours. The simplest way to do that is to add (or subtract) your GMT offset from the default times. Keep in mind that the start time always has to be before the end time, which means in some cases you might want two sessions per day if the trading hours would span midnight. See the instrument-specific examples for how to configure multiple sessions per day.

## Capital

*Capital* is how much we have 'at risk' in our trading account. This total capital is then allocated to trading strategies; see [strategy-capital](#strategy-capital) on a [daily basis](#update-capital-and-pl-by-polling-brokerage-account).

The simplest possible case is that your capital at risk is equal to what is in your trading account. If you do nothing else, that is how the system will behave. For all other cases, the behaviour of capital will depend on the interaction between stored capital values and the parameter value `production_capital_method` (defaults to *full* unless set in private YAML config). If you want to do things differently, you should consider modifying that parameter and/or using the [interactive tool](#interactively-modify-capital-values) to modify or initialise capital.

On initialising capital you can choose what the following values are:

- Brokerage account value (defaults to value from brokerage API). You might want to change this if you have stitched in some capital from another system, otherwise usually leave as the default
- Current capital allocated (defaults to brokerage account value).
- Maximum capital allocated (defaults to current capital). This is only used if `production_capital_method='half'`. It's effectively the 'high-water mark' for your strategy. You might want to set this higher than current capital if for example you have already been running the strategy elsewhere, and it's accumulated losses. Although you can set it lower than current capital, there is no logical reason for doing that.
- Accumulated profits and losses (defaults to zero). Doesn't affect capital calculations, but is nice to know. You may want to set this if you've already been running the strategy elsewhere.

If you don't initialise capital deliberately, then the first time that is run it will populate the fields with the defaults (which will effectively mean your capital will be equal to your current trading account value).

After initialising the capital is updated [daily](#update-capital-and-pl-by-polling-brokerage-account). First the valuation of the brokerage account is captured, and compared to the previous valuation. The difference between the valuations is your profit (or loss) since the capital was last checked, and this is written to the P&L accumulation account.

What will happen next will depend on `production_capital_method`. Read [this first](https://qoppac.blogspot.com/2016/06/capital-correction-pysystemtrade.html):

- if *full*, then your profit or loss is added to capital employed. For tidiness, maximum capital is set to be equal to current capital employed. This will result in your returns being compounded. This is the default.
- if *half* then your profit or loss is added to capital employed, until your capital is equal to the maximum capital employed. After that no further profits accrue to your capital. This is 'Kelly compatible' because losses reduce capital, but your returns will not be compounded. It's the method I use myself.
- if *fixed* then no change is made to capital. For tidiness, maximum capital is set to be equal to current capital employed. This isn't recommended as it isn't 'Kelly compatible', and if you lose money you will make exponentially increasing losses as a % of your account value. It could plausibly make sense in a small test account where you want to maintain a minimum position size.

Capital is mostly 'fire and forget', with a few exceptions which require the [interactive tool](#interactively-modify-capital-values).

### Large changes in capital

If brokerage account value has changed by more than 10% no further action is taken as it's likely this is an erroneous figure. An email is sent, and you are invited to run the [interactive tool](#interactively-modify-capital-values) choosing option 'Update capital from IB account value'. The system will get the valuation again, and if the change is still larger than 10% you will have the option of accepting this (having checked it yourself of course!).


### Withdrawals and deposits of cash or stock

The method above is neat in that it 'self recovers'; if you don't collect capital for a while it will adjust correctly when restarted. However, this does mean that if you withdraw cash or securities from your brokerage account, it will look like you've made a loss and your capital will reduce. The reverse will happen if you make a deposit. This may not bother you (you actually want this to happen and aren't using the account level P&L figures), but if it does, you can run the [interactive tool](#interactively-modify-capital-values) and select 'Adjust account value for withdrawal or deposit'. Make sure you are using the base currency of the account.

If you forget to do this, you should select 'Delete values of capital since time T' in the interactive tool. You can then delete the erroneous rows of capital, account for the withdrawal, and finally 'Update capital from IB account value' to make sure it has worked properly.

If you want the P&L to be correct, but do want your capital to reduce (increase), then you should use option 'Modify any/all values' after accounting for the withdrawal. Decrease (increase) the total capital figure accordingly. If you are using half compounding you also need to increase the maximum capital figure if it is lower than the new total capital figure.


### Change in capital methodology or capital base

In the [interactive tool](#interactively-modify-capital-values), option 'Modify any/all values'. Note that it's possible to change the method for capital calculation, the maximum capital or anything you wish even after you have started trading, and there may be good reasons for doing so. It's recommended that you don't delete previous capital values if you want to be able to consistently calculate your 'account level' percentage profit and loss; but the option is there to do so ('Delete everything and start again' in the interactive tool).

- Changing the capital method: this is fine, and indeed I've done it myself. The system doesn't record historic values of this parameter, but you can usually infer it from the behaviour of historic capital values.
- Changing the total capital: this is also fine and can often make sense. For example, you might want to start a new system off with a limited amount of capital and gradually increase it, even if the full amount is already in the brokerage account. Or temporarily reduce it because you're a scaredy-cat. If using half compounding then think about your maximum capital.
- Changing your maximum capital (only affects half compounding): this might make sense but think about behaviour. If you reduce it below current total capital, then total capital will immediately reduce to that level. If you increase it above current total capital, then you will be able to accumulate profits until you reach the new maximum.

You can also change other values in the interactive tool, but be careful and make sure you know what you are doing and why!


## Strategies

Each strategy is defined in the config parameter `strategy_list`, found either in the `defaults.yaml` file or overridden in private YAML configuration. The following shows the parameters for an example strategy, named (appropriately enough) `example`.

```
strategy_list:
  example:
    load_backtests:
      object: sysproduction.strategy_code.run_system_classic.runSystemClassic
      function: system_method
    reporting_code:
      function: sysproduction.strategy_code.report_system_classic.report_system_classic
```

### Strategy capital

Strategy capital is allocated from [total capital](#capital). This is done by the scripted function, [update strategy capital](#allocate-capital-to-strategies). It is controlled by the configuration element below (in the `defaults.yaml` file, or overridden in `private_config.yaml`).

```
strategy_capital_allocation:
  function: sysproduction.strategy_code.strategy_allocation.weighted_strategy_allocation
  strategy_weights:
    example: 100.0
```

The allocation calls the function specified, with any other parameters passed as keywords. This default function is very simple, and just carves out the capital proportionally across all the strategies listed in `strategy_weights`. If you wish to use it you will just need to change the `strategy_weights` dict element. Alternatively, you can write your own capital allocation function.


#### Risk target

The actual risk a strategy will take depends on both it's capital, and it's risk target. The risk target is set in the configuration option, `percentage_vol_target`, in the backtest configuration YAML file for the relevant strategy (if not supplied, the `defaults.yaml` value is used; this is *not* overridden by `private_config.yaml`). Risk targets can be different across strategies.

#### Changing risk targets and/or capital

Strategy capital can be changed at any time, and indeed will usually change daily since it depends on the total capital allocated. You can also change the weight a strategy across the total strategy. A history of a strategies capital is stored, so any changes can be seen historically. Weights are not stored, but can be backed out from the total capital and strategy capital.

We do not store a history of the risk target of a strategy, so if you change the risk target this will make it difficult to compare across time. I do not advise doing this.


### System runner

System runners run overnight backtests for each of the strategies you are running (see [here](#run-updated-backtest-systems-for-one-or-more-strategies) for more details.)

The following shows the parameters for an example strategy, named (appropriately enough) `example` stored in [syscontrol/control_config.yaml](/syscontrol/control_config.yaml) (remember you must specify your own personal strategy configuration in `private_control_config.yaml`).

```
process_configuration_methods:
  run_systems:
    example:
      max_executions: 1
      object: sysproduction.strategy_code.run_system_classic.runSystemClassic
      backtest_config_filename: systems.provided.futures_chapter15.futures_config.yaml
```

Note the generic process parameters max_executions and frequency, both are optional, but it is strongly reccomended that you set max_executions to 1 unless you want the backtest to run multiple times throughout the day (in which case you should also set frequency, which is the gap between runs in minutes).

A system usually does the following:

- get the amount of capital currently in your trading account. See [strategy-capital](#strategy-capital).
- run a backtest using that amount of capital
- get the position buffer limits, and save these down (for the classic system, other systems may save different values down)
- store the backtest state (pickled cache) in the directory specified by the parameter csv_backup_directory (set in your private config file, or the system defaults file), subdirectory strategy name, filename date and time generated. It also copies the config file used to generate this backtest with a similar naming pattern.

As an example [here](/sysproduction/strategy_code/run_system_classic.py) is the provided 'classic' run systems function.

### Strategy order generator

Once a backtest has been run it will generate a list of desired optimal positions (for the classic buffered positions, these will include buffers). From those, and our actual current positions, we need to calculate what trades are required for execution by the run_stack_handler process.

The following shows the parameters for an example strategy, named (appropriately enough) `example` stored in [syscontrol/control_config.yaml](/syscontrol/control_config.yaml) (remember you must specify your own personal strategy configuration in `private_control_config.yaml`)

```
process_configuration_methods:
  run_strategy_order_generator:
    example:
      object: sysexecution.strategies.classic_buffered_positions.orderGeneratorForBufferedPositions
      max_executions: 1
```

Example of an order generator, [here](/sysexecution/strategies/classic_buffered_positions.py). Different order generators would be required for eg strategies that used limit orders, or conditional orders, or did not use buffering.


### Load backtests

It's often useful for diagnostic purposes to reload the backtest (eg for strategy reporting, discussed below). This configuration specifies the object class that is used, and the relevant method (in this case it's the same as the run_systems class, but with a different method):


```
strategy_list:
  example:
    load_backtests:
      object: sysproduction.strategy_code.run_system_classic.runSystemClassic
      function: system_method

```


### Reporting code

Reports are run that are specific for each strategy, to achieve this we need to configure which function will do the reporting:

```
strategy_list:
  example:
    reporting_code:
      function: sysproduction.strategy_code.report_system_classic.report_system_classic
```

Example [here](/sysproduction/strategy_code/report_system_classic.py).


# Recovering from a crash - what you can save and how, and what you can't

## General advice

Here's some general advice about recovering from a crash:

- If you're not using IBC restart the IB Gateway; and if you are check it has started ok
- Temporarily turn off the crontab to stop processes from spawning before you are ready
- Check you have a MongoDB instance running okay
- Run a full set of reports, and carefully check them, especially the status and reconcile reports, to see that all is well.
- If necessary take steps to recover data (see next section). 
- If this goes well you will have an empty order stack. Run update_strategy_orders to repopulate it.
- You should turn the crontab back on when everything is working fine
- Processes are started by the scheduler, eg Cron, you will need to start them manually if their normal start time has passed (I find [linux screen](https://linuxize.com/post/how-to-use-linux-screen/) helpful for this on my headless server). Everything should work normally the following day.



## Data recovery

Let's first consider an awful case where your MongoDB is corrupted, and the backups are also corrupted. In this case you can use the backed up CSV database dump files to recover the following: FX, individual futures contract prices, multiple prices, adjusted prices, position data, historical trades, capital, contract meta-data, instrument data, optimal positions. Note that scripts don't necessarily exist to do all this automatically yet FIX ME TO DO.

Some other state information relating to the control of trading and processes is also stored in the database and this will be lost, however this can be recovered with a little work: roll status, trade limits, position limits, and overrides. Log data will also be lost; but archived [echo files](#echos-stdout-output) could be searched if necessary.

The better case is when the MongoDB is fine. In this case (once you've [restored](#mongodb-data) it) you will have only lost everything from your last nightly backup onwards. Here is what you do to get it back (if possible)

- As the database isn't SQL it's possible for inconsistencies to creep in, so it's generally better to revert to the last good full backup even if some data appears to be up-to-date
- Any changes made to trade limits, position limits and overrides will be lost and will need to be redone.
- You may want to copy across the backtest state files.
- IMPORTANT:Any changes made to roll status will be lost; any back adjusted price rolls will have reverted. Do this before any trading takes place, or you may confuse the system!
- IMPORTANT: The stack handler may contain incomplete orders. Run interactive_order_stack and run the end of day process. Do this before any trading takes place, or you may confuse the system!
- IMPORTANT:Even after finishing the stack handler, position data and historical data will be missing the effect of any trades, including orders that were subsequently filled but for which the fill was lost. Run interactive_order_stack and check to see if view positions. If any breaks come up, you will need to enter create either a balance trade (contract level break between broker and database) or balance instrument trade (instrument level break between strategy and contract positions) using interactive_order_stack. Get the fill prices from your brokerage website. Do this before any trading takes place or the system will lock and won't trade the instruments with breaks.
- FX, individual futures contract prices, multiple prices, adjusted prices: data will be backfilled once run_daily_price_updates has run.
- Capital: any intraday P&L data will be lost, but once run_capital_update has run the current capital will be correct.
- Optimal positions: will be correct once run_systems has run.
- You can use update_*  processes to run skipped processes before the normal scheduled process will do so. Don't forget to run them in the correct order: update_fx_prices (has to be before run_systems), update_sampled_contracts, update_historical_prices, update_multiple_adjusted_prices, update_strategy_backtests
- IMPORTANT: State information about processes running may be wrong; you may need to manually FINISH processes using interactive_controls otherwise processes won't run for fear of conflict (but the startup script should do this for you)



# Reporting

## Dashboard

A lot of the information in the reports described below can also be found in the [Web Dashboard](/docs/dashboard_and_monitor.md)

### Roll report (Daily)

The roll report can be run for all markets (default for the email), or for a single individual market (if run on an ad hoc basis). It will also be run when you run the interactive [update roll status](#menu-driven-interactive-scripts) process for the relevant market. Here's an example of a roll report, which I've annotated with comments (marked with quotes ""):

```
********************************************************************************
           Roll status report produced on 2020-10-19 17:10:13.280422            
********************************************************************************

"The roll report gives you all the information you need to decide when to roll from one futures contract to the next"


============================================================================================================================================
                                                      Status and time to roll in days                                                       
============================================================================================================================================

                        status roll_expiry price_expiry carry_expiry contract_priced contract_fwd position_priced volume_priced   volume_fwd
EDOLLAR                Passive        -143          957          866        20240600     20240900               2             1     0.853933
GAS_US_mini            No_Roll         -14           21           55        20211200     20220100              -2             1    0.0949909
BRENT-LAST             Passive         -13           27           -5        20220100     20220200               1             1    0.0907098

Roll_exp is days until preferred roll set by roll parameters. Prc_exp is days until price contract expires, Crry_exp is days until carry contract expires

"When should you roll? Certainly before the current priced contract (what we're currently trading) expires
(note for some contracts, eg fixed income, you should roll before the first notice date).
If the carry contract is younger (as here) then you will probably want to roll before that expires,
assuming that there is enough liquidity, or carry calculations will become stale.
Suggested times to roll before an expiry are shown, and these are used in the backtest to generate
historical roll dates, but you do not need to treat these as gospel in live trading"

"contract priced/contract forward This shows the contracts we're currently primarily trading (price), and will trade next (forward)"

"The position we have in the priced contract"

Contract volumes over recent days, normalised so largest volume is 1.0

"You can't roll until there is sufficient volume in the forward contract. Often a sign that
volume is falling in the price relative to the forward is a sign you should hurry up and roll!
Volumes are shown in relative terms to make interpretation easier."

********************************************************************************
                               END OF ROLL REPORT                               
********************************************************************************

```

### P&L report
    
The P&L report shows you profit and loss (duh!).  On a daily basis it is run for the previous 24 hours. On an ad hoc basis, it can be run for any time period (recent or in the past).

Here is an example, with annotations added in quotes (""):

```

********************************************************************************
P&L report produced on 2020-10-20 09:50:44.037739 from 2020-06-01 00:00:00 to 2020-10-20 09:17:16.470039
********************************************************************************

"Total P&L is what you'd expect. This comes from comparing broker valuations from the two relevant snapshot times. "

Total p&l is -2.746%


"P&L by instrument as a % of total capital. Calculated from database prices and trades.
 There is a bug in my live cattle price somewhere!"

====================================
P&L by instrument for all strategies
====================================

      codes  pandl
0   LIVECOW -18.10
1   SOYBEAN  -4.08
2      CORN  -1.34
3   EUROSTX  -0.81

".... truncated"

19      OAT   2.29
20      BTP   3.88
21    WHEAT   5.03

"If we add up our futures P&L and compare to the total P&L, we get a residual.
This could be because of a bug (as here), but also fees and interest charges,
or non futures instruments which aren't captured by the instrument P&L,
or because of a difference in timing between the broker account valuation and the relevant prices."

Total futures p&l is -12.916%
Residual p&l is 10.171%

===============================
        P&L by strategy        
===============================

"P&L versus total capital, not the capital for the specific strategy. So these should all add up to total P&L"

                   codes  pandl
0  medium_speed_TF_carry -13.42
1               ETFHedge  -0.63
2  _ROLL_PSEUDO_STRATEGY   0.00
0               residual  11.31


==================
P&L by asset class
==================

    codes  pandl
0     Ags -18.51
1  Equity  -0.81
2     Vol  -0.36
3  OilGas  -0.24
4    STIR  -0.11
5  Metals   0.16
6      FX   1.15
7    Bond   5.81


********************************************************************************
                               END OF P&L REPORT                                
********************************************************************************

```

### Status report

The status report monitors the status of processes and data acquisition, plus all control elements. It is run on a daily basis, but can also be run ad hoc. Here is an example report, with annotations in quotes(""):

```

********************************************************************************
              Status report produced on 2020-10-19 23:02:57.321674              
********************************************************************************

"A process is called by the scheduler, eg crontab. Processes have start/end times,
and can also have pre-requisite processes that need to have been run recently.
This provides a quick snapshot to show if the system is running normally"

===============================================================================================================================================================================================================================
                                                                                                     Status of processses                                                                                                      
===============================================================================================================================================================================================================================

name                 run_capital_update run_daily_prices_updates             run_stack_handler                   run_reports   run_backups                  run_cleaners               run_systems run_strategy_order_generator
running                           False                    False                         False                          True          True                         False                      True                        False
start                       10/19 01:00              10/19 20:05                   10/19 00:30                   10/19 23:00   10/19 22:20                   10/19 22:10               10/19 22:05                  10/19 21:55
end                         10/19 19:08              10/19 22:05                   10/19 19:30                   10/16 23:54   10/16 23:14                   10/19 22:10               10/16 22:55                  10/19 21:57
status                               GO                       GO                            GO                            GO            GO                            GO                        GO                           GO
finished_in_last_day               True                     True                          True                         False         False                          True                     False                         True
start_time                     01:00:00                 20:00:00                      00:01:00                      23:00:00      22:20:00                      22:10:00                  01:00:00                     01:00:00
end_time                       19:30:00                 23:00:00                      19:30:00                      23:59:00      23:59:00                      23:59:00                  23:00:00                     23:00:00
required_machine                   None                     None                          None                          None          None                          None                      None                         None
right_machine                      True                     True                          True                          True          True                          True                      True                         True
time_to_run                       False                    False                         False                          True          True                          True                     False                        False
previous_required                  None       run_capital_update  run_strategy_order_generator  run_strategy_order_generator  run_cleaners  run_strategy_order_generator  run_daily_prices_updates                  run_systems
previous_finished                  True                     True                          True                          True          True                          True                      True                        False
time_to_stop                       True                     True                          True                         False         False                         False                      True                         True


"Methods are called from within processes. We list the methods in reverse order
from when they last ran; older processes first. If something hasn't run for some
reason it will be at the top of this list. "

=============================================================================================
                                      Status of methods                                      
=============================================================================================

                                                           process_name last_run_or_heartbeat
method_or_strategy                                                                           
update_total_capital                                 run_capital_update           10/19 19:08
strategy_allocation                                  run_capital_update           10/19 19:08
handle_completed_orders                               run_stack_handler           10/19 19:26
process_fills_stack                                   run_stack_handler           10/19 19:26

"....truncated for space...."

status_report                                               run_reports           10/19 23:00
backup_db_to_csv                                            run_backups           10/19 23:00


"Here's a list of all adjusted prices we've generated and FX rates. Again, listed oldest first.
If a market closes or something goes wrong then the price would be stale. Notice the Asian markets
near the top for which we've had no price since this morning - not a surprise, and the
FX rates with timestamp 23:00 which means they're daily prices (I don't collect intraday FX prices). "

==============================================
Status of adjusted price / FX price collection
==============================================

                last_update
name                       
KOSPI   2020-10-19 08:00:00
KR3     2020-10-19 08:00:00
KR10    2020-10-19 08:00:00
OAT     2020-10-19 18:00:00
CAC     2020-10-19 19:00:00

"....truncated for space...."

US20    2020-10-19 21:00:00
JPYUSD  2020-10-19 23:00:00
AUDUSD  2020-10-19 23:00:00
CADUSD  2020-10-19 23:00:00
CHFUSD  2020-10-19 23:00:00
EURUSD  2020-10-19 23:00:00
GBPUSD  2020-10-19 23:00:00
HKDUSD  2020-10-19 23:00:00
KRWUSD  2020-10-19 23:00:00


"Optimal positions are generated by the backtest that runs daily; this hasn't
quite close yet hence these are from the previous friday."

=====================================================
        Status of optimal position generation        
=====================================================

                                          last_update
name                                                 
medium_speed_TF_carry/AEX     2020-10-16 22:54:20.386
medium_speed_TF_carry/AUD     2020-10-16 22:54:21.677
medium_speed_TF_carry/BOBL    2020-10-16 22:54:22.386
medium_speed_TF_carry/BTP     2020-10-16 22:54:22.999

"....truncated for space...."

medium_speed_TF_carry/V2X     2020-10-16 22:54:57.874
medium_speed_TF_carry/VIX     2020-10-16 22:54:58.551
medium_speed_TF_carry/WHEAT   2020-10-16 22:55:00.283


"This shows the status of any trade and position limits: I've just reset
 these so the numbers are pretty boring"

=========================================================================================================================================
                                                         Status of trade limits                                                          
=========================================================================================================================================

                      instrument_code  period_days  trade_limit  trades_since_last_reset  trade_capacity_remaining  time_since_last_reset
strategy_name                                                                                                                            
                                 US10            1            3                        0                         3 0 days 00:00:00.000015
medium_speed_TF_carry            US10            1            3                        0                         3 0 days 00:00:00.000011
                                  KR3            1           12                        0                        12 0 days 00:00:00.000011
                                  AEX            1            1                        0                         1 0 days 00:00:00.000010

"....truncated for space...."

                                  V2X            1            6                        0                         6 0 days 00:00:00.000010
                                  OAT            1            2                        0                         2 0 days 00:00:00.000010
                                  US5           30           35                        0                        35 3 days 06:04:32.129139
                              EUROSTX           30            8                        0                         8 3 days 06:03:49.437166

"....truncated for space...."

                               COPPER           30            3                        0                         3 3 days 05:56:49.324062
                                WHEAT           30            6                        0                         6 3 days 05:56:36.958089
                                  V2X           30           32                        0                        32 3 days 05:56:26.776116
                                  OAT           30           11                        0                        11 3 days 05:56:21.616143


"Notice where we have a position we report on the limit, even if none is set.
In this case I've set instrument level, but not strategy/instrument position limits"

=====================================================
              Status of position limits              
=====================================================

                             keys  position pos_limit
0    medium_speed_TF_carry/GAS_US      -1.0  no limit
1       medium_speed_TF_carry/AUD       1.0  no limit
2      medium_speed_TF_carry/BOBL       2.0  no limit

"....truncated for space...."

12      medium_speed_TF_carry/BTP       3.0  no limit
13      medium_speed_TF_carry/MXP       4.0  no limit
0                             V2X      -5.0        35
1                             BTP       3.0        10
2                         LEANHOG       0.0         8

"....truncated for space...."

34                           US10       0.0        16
35                        LIVECOW       0.0        11
36                        EDOLLAR      11.0        86
37                            US5       0.0        39


"Overrides allow us to reduce or eliminate positions temporarily in specific
instruments, but I'm not using these right now"

===================
Status of overrides
===================

Empty DataFrame
Columns: [override]
Index: []

"Finally we check for instruments that are locked due to a position mismatch:
 see the reconcile report for details"

Locked instruments (position mismatch): []

********************************************************************************
                              END OF STATUS REPORT                              
********************************************************************************
```


### Trade report

The trade report lists all trades recorded in the database, and allows you to analyse slippage in very fine detail.  On a daily basis it is run for the previous 24 hours. On an ad hoc basis, it can be run for any time period (recent or in the past).

Here is an example, with annotations added in quotes (""):

```

********************************************************************************
              Trades report produced on 2020-10-20 09:25:43.596580              
********************************************************************************

"Here is a list of trades with basic information. Note that due to an issue with the way
roll trades are displayed, they are shown with fill 0."

==================================================================================================================
                                                  Broker orders                                                   
==================================================================================================================

         instrument_code          strategy_name           contract_id       fill_datetime    fill     filled_price
order_id                                                                                                          
30365                V2X  medium_speed_TF_carry            [20201200] 2020-10-02 07:51:53    (-1)           (27.7)
30366                KR3  medium_speed_TF_carry            [20201200] 2020-10-05 01:01:00     (1)         (112.01)

"....truncated for space...."


30378            EDOLLAR  medium_speed_TF_carry            [20230900] 2020-10-14 13:50:32    (-1)          (99.61)
30380               CORN  _ROLL_PSEUDO_STRATEGY  [20201200, 20211200] 2020-10-15 09:25:54  (0, 0)  (397.75, 394.0)
30379                V2X  _ROLL_PSEUDO_STRATEGY  [20201100, 20201200] 2020-10-15 09:24:32  (0, 0)   (25.25, 24.25)
30383                V2X  _ROLL_PSEUDO_STRATEGY  [20201100, 20201200] 2020-10-15 09:43:30  (0, 0)     (25.5, 24.4)
30388               KR10  medium_speed_TF_carry            [20201200] 2020-10-20 02:00:21     (1)         (133.03)


================================================================================================================================================================
                                                                             Delays                                                                             
================================================================================================================================================================

"We now look at timing. When was the parent order generated (the order at instrument level
 that generated this specific order) versus when the order was submitted to the broker?
Normally this is the night before, when the backtest is run, but for roll orders there
are no parents, and also for manual orders. In our simulation we assume that orders
are generated with a one business day delay. Here we're mostly doing better than that.
Once submitted, how long did it take to fill the order? Issues with timestamps when I
ran this report mean that some orders that apparently got filled before they were submitted, we ignore these. "

         instrument_code          strategy_name parent_generated_datetime         submit_datetime       fill_datetime submit_minus_generated filled_minus_submit
order_id                                                                                                                                                        
30365                V2X  medium_speed_TF_carry   2020-10-01 21:56:29.669 2020-10-02 08:50:03.637 2020-10-02 07:51:53                  39214                 NaN
30366                KR3  medium_speed_TF_carry   2020-10-02 21:57:41.427 2020-10-05 02:00:07.262 2020-10-05 01:01:00                 187346                 NaN
30367            EDOLLAR  medium_speed_TF_carry                       NaT 2020-10-05 12:43:01.885 2020-10-05 11:48:02                    NaN                 NaN
30368            EDOLLAR  medium_speed_TF_carry   2020-10-06 21:58:12.765 2020-10-07 00:30:32.000 2020-10-06 23:35:32                9139.24                 NaN

"....truncated for space...."

30380               CORN  _ROLL_PSEUDO_STRATEGY                       NaT 2020-10-15 09:24:46.000 2020-10-15 09:25:54                    NaN                  68
30379                V2X  _ROLL_PSEUDO_STRATEGY                       NaT 2020-10-15 09:22:16.000 2020-10-15 09:24:32                    NaN                 136
30383                V2X  _ROLL_PSEUDO_STRATEGY                       NaT 2020-10-15 09:41:42.000 2020-10-15 09:43:30                    NaN                 108
30388               KR10  medium_speed_TF_carry   2020-10-16 22:54:38.166 2020-10-20 02:00:16.000 2020-10-20 02:00:21                 270338                   5


==========================================================================================================================================================================================================================================================
                                                                                                                 Slippage (ticks per lot)                                                                                                                 
==========================================================================================================================================================================================================================================================

"We can calculate slippage in many different units. We start with 'ticks', units of price
(not strictly ticks I do know that...). The reference price is the price when we generated
the parent order (usually the closing price from the day before). The mid price is the mid
 price when we submit. The side price is the price we would pay if we submitted a market order
 (the best bid if we're selling, best offer if we're buying). The limit price is whatever
 the algo submits the order for initially. Normally an algo will try and execute passively,
 so the limit price would normally be the best offer if we're selling, best bid if we're
buying. Alternatively, if the parent order has a limit (for strategies that try and
achieve particular prices) the algo should use that price. The filled price is self
explanatory. We can then measure our slippage in different ways: caused by delay (side
price versus reference price - delays tend to add a lot of variability, but usually net
out very close to zero in our backtest (checking actual delays over a long period of time
 should confirm this), caused by bid/ask spread (mid versus side price, which is what we
assume we pay in a backtest), and caused by execution (side price versus fill, if our algo
is doing it's thing this should offset some of our costs). We can also measure the quality
 of our execution (initial limit versus fill) and how we did versus the required limit order
 (if relevant). Negative numbers are bad (we paid), positive are good (we earned).
Take the first order as an example (V2X sell one contract) with no parent order limit
price, the market moved 0.225 points in our favour from 27.45 the night before to a mid
 of 27.675 (bid 27.65, offer 27.7). If we'd paid up we would have sold at 27.65 side
price (bid/ask cost -0.025). We submitted a limit order of 27.7 at the offer, and were
filled there. So our execution cost was positive 0.05. Our total trading cost was -0.025+0.05 = 0.025."

         instrument_code          strategy_name    trade parent_reference_price parent_limit_price calculated_mid_price calculated_side_price limit_price calculated_filled_price   delay bid_ask execution versus_limit versus_parent_limit total_trading
order_id                                                                                                                                                                                                                                                  
30365                V2X  medium_speed_TF_carry     (-1)                  27.45               None               27.675                 27.65        27.7                    27.7   0.225  -0.025      0.05           -0                 NaN         0.025
30366                KR3  medium_speed_TF_carry      (1)                 112.08               None              111.995                   112      111.99                  112.01   0.085  -0.005     -0.01        -0.02                 NaN        -0.015
30367            EDOLLAR  medium_speed_TF_carry     (-1)                    NaN               None              99.6725                 99.67      99.675                   99.67     NaN -0.0025        -0       -0.005                 NaN       -0.0025
30368            EDOLLAR  medium_speed_TF_carry     (-1)                 99.645               None              99.6425                 99.64      99.645                   99.64 -0.0025 -0.0025        -0       -0.005                 NaN       -0.0025

"....truncated for space...."

30380               CORN  _ROLL_PSEUDO_STRATEGY  (1, -1)                    2.5               None                    4                  4.25        3.75                    3.75    -1.5   -0.25       0.5            0                 NaN          0.25
30379                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)                   0.85               None                 1.05                  1.15           1                       1    -0.2    -0.1      0.15            0                 NaN          0.05
30383                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)                   0.85               None                 1.05                  1.15        0.95                     1.1    -0.2    -0.1      0.05        -0.15                 NaN         -0.05
30388               KR10  medium_speed_TF_carry      (1)                 132.45               None              133.035                133.04      133.03                  133.03  -0.585  -0.005      0.01            0                 NaN         0.005


=======================================================================================================================================================================
                                                         Slippage (normalised by annual vol, BP of annual SR)                                                          
=======================================================================================================================================================================

"Ticks are meaningless as it depends on how volatile an instrument is. We divide by the annual
vol of an instrument, in price terms, to get a normalised figure. This is  multiplied by 10000
to get a basis point figure. For example the V2X trade had bid/ask slippage of 0.025, and the
 annual vol is currently 11.585; that works out to 0.025 / 11.585 = 0.00216, or 21.6 basis
points. Note that ignoring holding costs using my 'speed limit' concept we'd be able to do
0.13 / 0.00216 = 60 trades a year in V2X (or 48 if you assume monthly rolls), to put it another
 way the cost budget is 1300 basis points."

         instrument_code          strategy_name    trade last_annual_vol delay_vol bid_ask_vol execution_vol versus_limit_vol versus_parent_limit_vol total_trading_vol
order_id                                                                                                                                                               
30365                V2X  medium_speed_TF_carry     (-1)         11.5805   194.292    -21.5879       43.1759               -0                     NaN           21.5879
30366                KR3  medium_speed_TF_carry      (1)        0.829709   1024.46    -60.2621      -120.524         -241.048                     NaN          -180.786
30367            EDOLLAR  medium_speed_TF_carry     (-1)        0.224771       NaN    -111.224            -0         -222.448                     NaN          -111.224
30368            EDOLLAR  medium_speed_TF_carry     (-1)        0.224771  -111.224    -111.224            -0         -222.448                     NaN          -111.224

"....truncated for space...."

30380               CORN  _ROLL_PSEUDO_STRATEGY  (1, -1)         71.6612  -209.318    -34.8864       69.7727                0                     NaN           34.8864
30379                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)         11.5805  -172.704    -86.3518       129.528                0                     NaN           43.1759
30383                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)         11.5805  -172.704    -86.3518       43.1759         -129.528                     NaN          -43.1759
30388               KR10  medium_speed_TF_carry      (1)         4.18168  -1398.96    -11.9569       23.9138                0                     NaN           11.9569


==================================================================================================================================================================================
                                                                           Slippage (In base currency)                                                                            
==================================================================================================================================================================================

"Finally we can work out the slippage in base currency, i.e. actual money cost by multiplying
 ticks by the value of a price point in base currency (GBP for me)"

         instrument_code          strategy_name    trade value_of_price_point delay_cash bid_ask_cash execution_cash versus_limit_cash versus_parent_limit_cash total_trading_cash
order_id                                                                                                                                                                          
30365                V2X  medium_speed_TF_carry     (-1)              90.8755     20.447     -2.27189        4.54377                -0                      NaN            2.27189
30366                KR3  medium_speed_TF_carry      (1)              677.198    57.5618     -3.38599       -6.77198           -13.544                      NaN            -10.158
30367            EDOLLAR  medium_speed_TF_carry     (-1)               1930.7        NaN     -4.82676             -0          -9.65352                      NaN           -4.82676
30368            EDOLLAR  medium_speed_TF_carry     (-1)               1930.7   -4.82676     -4.82676             -0          -9.65352                      NaN           -4.82676

"....truncated for space...."

30380               CORN  _ROLL_PSEUDO_STRATEGY  (1, -1)              38.6141   -57.9211     -9.65352         19.307                 0                      NaN            9.65352
30379                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)              90.8755   -18.1751     -9.08755        13.6313                 0                      NaN            4.54377
30383                V2X  _ROLL_PSEUDO_STRATEGY  (1, -1)              90.8755   -18.1751     -9.08755        4.54377          -13.6313                      NaN           -4.54377
30388               KR10  medium_speed_TF_carry      (1)              677.198   -396.161     -3.38599        6.77198                 0                      NaN            3.38599

"Then follows a very long section, which is only really useful for doing annual analysis of
trades (unless you trade a lot!). For each type of slippage (delay, bid/ask, execution,
versus limit, versus parent limit, total trading [execution + bid/ask]) we calculate
summary statistics for each instrument and strategy: the total, count, mean, lower and
upper range (+/- two standard deviations), in three ways: ticks, vol adjusted, and base currency cash."

```



### Reconcile report

The reconcile report checks the consistency of positions and trades stored in the database, and with the broker. It is run on a daily basis, but can also be run ad hoc. Here is an example, with annotations added in quotes (""):

```

********************************************************************************
            Reconcile report produced on 2020-10-19 23:31:23.329834             
********************************************************************************

"Optimal positions are set by the nightly backtest. For this strategy we set an upper and
lower buffer region, so two figures are shown for the optimal. A break occurs if the
position is outside the buffer region. For example you can see for BTP that the current
 position (long 3) is higher than the upper buffer(2.4, rounded to 2). This either means
 that the relevant market hasn't traded yet, or there is something wrong with the system
(check the status report to see if a process or method hasn't run)."

=============================================================
               Optimal versus actual positions               
=============================================================

                               current        optimal  breaks
medium_speed_TF_carry AEX          0.0   -0.029/0.029   False
medium_speed_TF_carry AUD          1.0    1.030/1.301   False
medium_speed_TF_carry BOBL         2.0    1.696/2.107   False
medium_speed_TF_carry BTP          3.0    2.211/2.432    True
medium_speed_TF_carry BUND         0.0   -0.069/0.069   False

"....truncated for space...."

medium_speed_TF_carry JPY          0.0   -0.177/0.177   False
medium_speed_TF_carry KOSPI        0.0   -0.028/0.028   False
medium_speed_TF_carry KR10         1.0    1.953/2.131    True
medium_speed_TF_carry KR3          8.0    8.655/9.567    True
medium_speed_TF_carry LEANHOG      0.0  -0.616/-0.316   False

"....truncated for space...."

medium_speed_TF_carry VIX          1.0    0.410/0.541   False
medium_speed_TF_carry WHEAT        0.0   -0.135/0.115   False

"We now look at positions at a contract level, and compare those in the database with
those that the broker has recorded"

==========================================
             Positions in DB              
==========================================

   instrument_code contract_date  position
7              AUD      20201200       1.0
4             BOBL      20201200       2.0
5              BTP      20201200       3.0

"....truncated for space...."

14             V2X      20201200      -5.0
12             VIX      20201200       1.0


==========================================
             Positions broker             
==========================================

   instrument_code contract_date  position
10             AUD      20201214       1.0
9             BOBL      20201208       2.0
5              BTP      20201208       3.0

"....truncated for space...."

11             V2X      20201216      -5.0
12             VIX      20201216       1.0

"We now check for position breaks. These are of three kinds: an instrument position
is out of line with the optimal, the instrument positions are out of line with the
aggregate across contract positions, or the broker and database disagree on what the
 contract level positions are. The first problem should be fixed automatically if the
system is running properly; the second or third may require the creation of manual trades:
see interactive_stack_handler script."

Breaks Optimal vs actual [medium_speed_TF_carry BTP, medium_speed_TF_carry KR10, medium_speed_TF_carry KR3]
 Breaks Instrument vs Contract []
 Breaks Broker vs Contract []

"We now compare the orders in the database for the last 24 hours with those the broker
 has on record. No automated check is done, but you can do this visually. No trades
were done for this report so I've pasted in trades from another day to illustrate what
it looks like. You can see the trades match up (ignore the fills shown as 0 this is
an artifact of the way trades are stored)."


=========================================================================================================
                                              Trades in DB                                               
=========================================================================================================

                         strategy_name           contract_id       fill_datetime    fill     filled_price
instrument_code                                                                                          
CORN             _ROLL_PSEUDO_STRATEGY  [20201200, 20211200] 2020-10-15 09:25:54  (0, 0)  (397.75, 394.0)
V2X              _ROLL_PSEUDO_STRATEGY  [20201100, 20201200] 2020-10-15 09:24:32  (0, 0)   (25.25, 24.25)
V2X              _ROLL_PSEUDO_STRATEGY  [20201100, 20201200] 2020-10-15 09:43:30  (0, 0)     (25.5, 24.4)


=================================================================================================
                                       Trades from broker                                        
=================================================================================================

                strategy_name           contract_id       fill_datetime     fill     filled_price
instrument_code                                                                                  
V2X                            [20201118, 20201216] 2020-10-15 09:24:32  (1, -1)   (25.25, 24.25)
CORN                           [20201214, 20211214] 2020-10-15 09:25:54  (1, -1)  (397.75, 394.0)
V2X                            [20201118, 20201216] 2020-10-15 09:43:30  (1, -1)     (25.5, 24.4)



********************************************************************************
                              END OF STATUS REPORT                              
********************************************************************************


```


### Strategy report

The strategy report is bespoke to a strategy; it will load the last backtest file generated and report diagnostics from it. On a daily basis it runs for all strategies. On an ad hoc basis, it can be run for all or a single strategy.

The strategy reporting is determined by the parameter `strategy_list/strategy_name/reporting_code/function` in `defaults.yaml` or overridden in the private config YAML file. The 'classic' reporting function is `sysproduction.strategy_code.report_system_classic.report_system_classic`

Here is an example, with annotations added in quotes (""):

```

********************************************************************************
Strategy report for medium_speed_TF_carry backtest timestamp 20201012_215827 produced at 2020-10-12 23:15:08.677151
********************************************************************************



================================================================================================================================================================================================================================================================================================================================================================================
                                                                                                                                                                              Unweighted forecasts                                                                                                                                                                              
================================================================================================================================================================================================================================================================================================================================================================================

"This is a matrix of all forecast values for each instrument, before weighting. Not shown for space reasons"


================================================================================================================================================================================================================================================================================================================================================================================
                                                                                                                                                                                Forecast weights                                                                                                                                                                                
================================================================================================================================================================================================================================================================================================================================================================================

"This is a matrix of all forecast weights for each instrument, before weighting. Not shown for space reasons"



================================================================================================================================================================================================================================================================================================================================================================================
                                                                                                                                                                               Weighted forecasts                                                                                                                                                                               
================================================================================================================================================================================================================================================================================================================================================================================

"This is a matrix of all forecast values for each instrument, after weighting. Not shown for space reasons"

"Here we calculate the vol target for the strategy"

Vol target calculation {'base_currency': 'GBP', 'percentage_vol_target': 25.0, 'notional_trading_capital': 345040.64, 'annual_cash_vol_target': 86260.16, 'daily_cash_vol_target': 5391.26}

"Now we see how the instrument vol is calculated. These figures are also calculated independently in the risk report"

================================================================
                        Vol calculation                         
================================================================

         Daily return vol       Price  Daily % vol  annual % vol
AEX                6.3238    573.2500       1.1031       17.6504
AUD                0.0045      0.7214       0.6267       10.0272

"... truncated for space"

VIX                0.7086     27.7000       2.5580       40.9277
WHEAT             10.7527    596.5000       1.8026       28.8420


=========================================================================================================================================
                                                           Subsystem position                                                            
=========================================================================================================================================

"Calculation of subsystem positions: the position we'd have on if the entire system
 was invested in a single instrument. Abbreviations won't make sense unless you've read my first book, 'Systematic Trading'"

         Block_Value  Daily price % vol         ICV    FX      IVV  Daily Cash Vol Tgt  Vol Scalar  Combined forecast  subsystem_position
AEX          1146.50               1.10     1264.76  0.91  1094.74             5391.26        4.92               0.00                0.00
AUD           721.40               0.63      452.10  0.77   352.52             5391.26       15.29               9.02               13.79

"... truncated for space"

V2X            23.90               3.29       78.57  0.91    68.01             5391.26       79.28             -10.36              -82.15
VIX           277.00               2.56      708.56  0.77   552.48             5391.26        9.76               8.80                8.59
WHEAT         298.25               1.80      537.63  0.77   419.21             5391.26       12.86               1.07                1.38


=================================================================
                       Portfolio positions                       
=================================================================


"Final notional positions"

         subsystem_position  instr weight  IDM  Notional position
AEX                   0.000         0.022  2.5              0.000
AUD                  13.792         0.033  2.5              1.149

"... truncated for space"

V2X                 -82.154         0.025  2.5             -5.135
VIX                   8.592         0.025  2.5              0.537
WHEAT                 1.379         0.033  2.5              0.115


===============================================================================================
                                     Positions vs buffers                                      
===============================================================================================

"Shows the calculation of buffers. The position at timestamp is the position when
 the backtest was run; the current position is what we have on now"

         Notional position  Lower buffer  Upper buffer  Position at timestamp  Current position
AEX                    0.0          -0.0           0.0                    0.0               0.0
AUD                    1.1           1.0           1.3                    1.0               1.0

"... truncated for space"

V2X                   -5.1          -5.6          -4.6                   -4.0              -4.0
VIX                    0.5           0.5           0.6                    1.0               1.0
WHEAT                  0.1           0.0           0.2                    0.0               0.0

End of report for medium_speed_TF_carry

```


### Risk report

The risk report.... you're smart people, you can guess. It is run on a daily basis, but can also be run ad hoc. Here is an example, with annotations added in quotes (""):

```

********************************************************************************
               Risk report produced on 2020-10-19 23:54:09.835241               
********************************************************************************

"Our expected annual standard deviation is 10.6% a year, across everything"

Total risk across all strategies, annualised percentage 10.6

========================================
Risk per strategy, annualised percentage
========================================

"We now break this down by strategy, taking into account the capital allocated to
each strategy. The 'roll pseduo strategy' is used to generate roll trades and should
 never have any risk on. ETFHedge is another nominal strategy"


                               risk
_ROLL_PSEUDO_STRATEGY  0
medium_speed_TF_carry  10.6
ETFHedge               0


============================================================================================================================================================================================================================================================
                                                                                                                      Instrument risk                                                                                                                       
============================================================================================================================================================================================================================================================

"Detailed risk calculations for each instrument. Most of these are, hopefully, self explanatory,
but in case they aren't, from left to right: daily standard deviation in price units,
annualised std. dev in price units, the price, daily standard deviation in % units (std dev
in price terms / price), annual % std. dev, the point size (the value of a 1 point price movement)
 expressed in the base currency (GBP for me), the contract exposure value in GBP (point size * price),
 daily risk standard deviation in GBP for owning one contract (daily % std dev * exposure value,
 or daily price std dev * point size), annual risk per contract (daily risk * 16), current position,
total capital at risk, exposure of position held as % of capital (contract exposure * position / capital),
 annual risk of position held as % of capital (annual risk per contract / capital)."

         daily_price_stdev  annual_price_stdev   price  daily_perc_stdev  annual_perc_stdev  point_size_base  contract_exposure  daily_risk_per_contract  annual_risk_per_contract  position   capital  exposure_held_perc_capital  annual_risk_perc_capital
GAS_US                 0.1                 1.5     3.3               2.9               46.6           7722.8            25423.5                    740.4                   11845.6      -1.0  353675.6                        -7.2                      -3.3
EUROSTX               36.4               582.0  3207.0               1.1               18.1              9.1            29143.8                    330.5                    5288.6      -2.0  353675.6                       -16.5                      -3.0
V2X                    0.7                11.6    24.9               2.9               46.5             90.9             2262.8                     65.8                    1052.4      -5.0  353675.6                        -3.2                      -1.5
"... truncated for space"PLAT                  22.7               363.9   855.5               2.7               42.5             38.6            33034.3                    878.1                   14050.1       1.0  353675.6                         9.3                       4.0
BTP                    0.3                 5.4   149.4               0.2                3.6            908.8           135777.1                    307.7                    4923.3       3.0  353675.6                       115.2                       4.2


============================================================================================================
                                                Correlations                                                
============================================================================================================

"Correlation of *instrument* returns - doesn't care about sign of position"

          V2X   OAT   BTP   KR3  SOYBEAN  KR10   AUD  GAS_US  PLAT   VIX  BOBL  EDOLLAR   MXP  EUROSTX  CORN
V2X      1.00  0.19 -0.14  0.12    -0.22  0.21 -0.56    0.01 -0.30  0.77  0.21     0.41 -0.48    -0.71 -0.08
OAT      0.19  1.00  0.46  0.22    -0.05  0.19 -0.09   -0.10 -0.12  0.09  0.60     0.39 -0.16    -0.13 -0.11
BTP     -0.14  0.46  1.00  0.08    -0.01  0.09  0.22   -0.10  0.04 -0.04  0.17     0.02 -0.13     0.06 -0.06

"... truncated for space"

MXP     -0.48 -0.16 -0.13 -0.15     0.29 -0.13  0.48   -0.09  0.32 -0.56 -0.14    -0.33  1.00     0.44  0.11
EUROSTX -0.71 -0.13  0.06 -0.08     0.17 -0.15  0.53    0.00  0.17 -0.54 -0.32    -0.43  0.44     1.00  0.02
CORN    -0.08 -0.11 -0.06 -0.06     0.68 -0.10  0.08    0.05  0.13 -0.10 -0.25    -0.15  0.11     0.02  1.00


********************************************************************************
                               END OF RISK REPORT                               
********************************************************************************


```

### Liquidity report


This allows us to check that markets are sufficiently liquid to trade. See this [blog post](https://qoppac.blogspot.com/2021/05/adding-new-instruments-or-how-i-learned.html) for more discussion.

I require minimum volume ($1.25 million per day in risk units, and 100 contracts per day). The report uses the last two weeks of trading to determine the relevant values (not configurable - be careful if using a report just after new years day when liquidity may have fallen).


Any instruments that don't meet these thresholds you should seriously consider removing from your portfolio.


```

********************************************************************************
            Liquidity report produced on 2021-07-08 14:58:39.926324             
********************************************************************************



================================================================
 Sorted by contracts: Less than 100 contracts a day is a problem
================================================================

                   contracts          risk
EU-FOOD           139.888889      0.364353
EU-RETAIL         177.444444      0.473291
MILK              210.250000      0.535316
EU-HEALTH         227.555556      0.958930
OATIES            266.750000      1.059968
RICE              322.250000      1.313220
EU-TRAVEL         455.777778      1.234303
EU-TECH           512.000000      1.891341
PALLAD            647.125000     53.219742
EU-UTILS          912.888889      2.733389
CHF              1101.250000      6.785555
EU-DIV30         1360.222222      2.717361
.... snip....

===================================================================
Sorted by risk: Less than $1.5 million of risk per day is a problem
===================================================================

                   contracts          risk
EU-FOOD           139.888889      0.364353
EU-RETAIL         177.444444      0.473291
MILK              210.250000      0.535316    <----- milk isn't liquid :-)'
EU-HEALTH         227.555556      0.958930
OATIES            266.750000      1.059968
EU-TRAVEL         455.777778      1.234303
RICE              322.250000      1.313220    <----- everything above this line might be too illiquid
EU-TECH           512.000000      1.891341
EU-DIV30         1360.222222      2.717361
EU-UTILS          912.888889      2.733389
USIRS5           1433.375000      2.873852
BITCOIN          1522.888889      3.181693
BBCOMM           3546.875000      3.637609
.... snip....
```


### Costs report

This allows us to check that the bid/ask spread costs set in the configuration file are sufficiently conservative. It will use three different sources, using data over the last 250 days (configurable):

- Half the bid/ask spread captured before an order is entered (first column below)
- The actual spread paid between the initial mid price and the price traded at (second column below). Positive numbers refer to a loss making spread (as normal), negative implies we managed to trade at better than mid (due to the execution algo)
- Half the bid/ask spread as periodically captured by the stack handler (3rd column)

We then calculate:

- The worst (highest) of the above values (fourth column below)
- The bid/ask spread cost configured in the instrument metadata database table (which in turn is normally initialised from ) (5th column)
- The % difference between the configured and worst cost, as a % of the configured cost. +1.00 is a 100% difference, eg the highest spread is twice what is currently configured (final column)

```

********************************************************************************
Costs report produced on 2021-07-08 14:58:53.991457 from 2020-10-31 14:58:50.220961 to 2021-07-08 14:58:50.220958
********************************************************************************



=================================================================================================
                                              Costs                                              
=================================================================================================

               bid_ask_trades  total_trades  bid_ask_sampled      Worst  Configured  % Difference
CRUDE_W_mini         0.037500     -0.006250         0.024006   0.037500    0.012500      2.000000  
         <---- bid/ask before trading is 200% higher: 3x higher than configured. Actual trades have negative costs
GAS_US_mini          0.002500      0.005000         0.006408   0.006408    0.002500      1.563158
PLAT                 0.350000      0.550000         0.275935   0.550000    0.240108      1.290640  
BBCOMM                    NaN           NaN         0.100000   0.100000    0.050000      1.000000  <---- we haven't done any actual trades here in last 250 days, only sampled'
EUROSTX              1.000000      0.500000         0.261483   1.000000    0.500000      1.000000  <---- configured is same as trades, but pre trade was double
SOYBEAN              0.250000      0.250000         0.201436   0.250000    0.125000      1.000000
GBP                  0.000100     -0.000000         0.000059   0.000100    0.000050      1.000000
......
OATIES                    NaN           NaN         0.750000   0.750000    0.625000      0.200000  <---- sampled spreads are 20% worse than configured
.....
BOBL                 0.005000      0.005000         0.005000   0.005000    0.005000      0.000000  <---- spot on!
EDOLLAR              0.002500      0.002500         0.002500   0.002500    0.002500      0.000000
SHATZ                     NaN           NaN         0.002500   0.002500    0.002500      0.000000
WHEAT                0.250000      0.187500         0.192896   0.250000    0.250000      0.000000
....
GOLD_micro           0.050000      0.050000         0.066546   0.066546    0.100000     -0.334545  <----- slippage about half or two thirds of configured value
GOLD                      NaN           NaN         0.058550   0.058550    0.088530     -0.338639
US-REALESTATE             NaN           NaN         0.066095   0.066095    0.100000     -0.339047
EU-TECH                   NaN           NaN         0.196570   0.196570    0.300000     -0.344765
COPPER                    NaN           NaN         0.000385   0.000385    0.000615     -0.374535
CRUDE_W                   NaN           NaN         0.008526   0.008526    0.014533     -0.413304
EUR                       NaN           NaN         0.000028   0.000028    0.000050     -0.439945
MXP                  0.000005      0.000005         0.000006   0.000006    0.000012     -0.443000
NZD                       NaN           NaN         0.000055   0.000055    0.000107     -0.483610
US2                       NaN           NaN         0.001953   0.001953    0.004000     -0.511719
EU-BASIC                  NaN           NaN         0.141791   0.141791    1.250000     -0.886568
ASX                       NaN           NaN              NaN        NaN         NaN           NaN   <----- instrument in configuration file but no costs included
.....
KOSPI                     NaN           NaN              NaN        NaN    0.025000           NaN   <--- slippage is configured, but no sampling or trading done
....
```

### TODO add new reports


## Customize scheduled report generation

It is possible to set up a custom report configuration. Say for example that you would like to push reports to a git repo [like this](https://github.com/robcarver17/reports). In that case you would need to change the default behaviour (sending reports via email), to saving the report as a file. Files would be stored according to what is defined as `reporting_directory` in `private_config.yaml`. Example of reporting customization is: 

```
 reports:
  slippage_report:
    title: "Slippage report"
    function: "sysproduction.reporting.slippage_report.slippage_report"
    calendar_days_back: 250
    output: "file"

  costs_report:
    title: "Costs report"
    function: "sysproduction.reporting.costs_report.costs_report"
    output: "file"
    calendar_days_back: 250

```
The available reports can be found by interrogating the `dataReports` object, e.g.:
```python
from sysproduction.data.reports import dataReports
print(dataReports().get_default_reporting_config_dict().keys())
```
