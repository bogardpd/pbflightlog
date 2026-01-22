# Flight Log Tools

> [!IMPORTANT]
> This module is still pre-release and may be incomplete.

A small collection of command-line tools for working with a personal flight log stored in a GeoPackage.

## Setup

### Editable Installation

If you want to install this module locally and access it from any folder, while still allowing the scripts to be edited after install, perform a pip editable installation:

```bash
cd path/to/module
python -m pip install -e .
```

### Environment Variables

This script interacts with a GeoPackage flight log database as described in the [schema](docs/schema.md). The path to this file must be set as an environment variable:

```FLIGHT_LOG_GEOPACKAGE_PATH=/path/to/flight_log.gpkg```

Many of these scripts interact with [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) to get flight data. You will need to get an AeroAPI API key and set it as an environment variable:

```AEROAPI_API_KEY=yourkey```

> [!IMPORTANT]
> When these scripts call AeroAPI with your API key, you will incur AeroAPI per-query fees as appropriate for your AeroAPI account.

The [`import-recent`](#import-recent) script also requires a [Flight Historian](https://www.flighthistorian.com) API key to be set as an environment variable:

`FLIGHT_HISTORIAN_API_KEY=yourkey`

## Basic usage

> [!NOTE]
> Throughout this documentation, `python` refers to the Python 3 interpreter. Different operating systems may require different commands such as `py` or `python3`.

```bash
python -m flight_log_tools <command> [options]
```

To see available commands:

```bash
python -m flight_log_tools --help
```

To see help for a specific command:

```bash
python -m flight_log_tools <command> --help
```

## Commands

### `import-boarding-passes`

Imports flight records by parsing airline boarding pass files and creating corresponding entries in the flight log GeoPackage.

Typical use cases:

* Processing saved Apple Wallet .pkpass boarding passes

Example:

```bash
python -m flight_log_tools import-boarding-passes
```

### `import-recent`

Retrieves recent flights from the Flight Historian API and creates corresponding records in the local flight log.

This command is intended to:

* Pull newly completed flights
* Avoid re-importing flights that already exist in the log

Example:

```bash
python -m flight_log_tools import-recent
```
