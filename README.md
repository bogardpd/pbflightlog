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

This package interacts with a GeoPackage flight log database as described in the [schema](docs/schema.md). The path to this file must be set as an environment variable:

```FLIGHT_LOG_GEOPACKAGE_PATH=/path/to/flight_log.gpkg```

This package has the ability to import files from a predefined import folder. The path to this folder must be set as an environment variable:

```FLIGHT_LOG_IMPORT_PATH=/path/to/import/folder```

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
python -m pbflightlog <command> [options]
```

To see available commands:

```bash
python -m pbflightlog --help
```

To see help for a specific command:

```bash
python -m pbflightlog <command> --help
```

## Commands

### `add flight`

Create a new flight (or new flights) in the flight log.

> [!IMPORTANT]
> Flight data is pulled from [AeroAPI](https://www.flightaware.com/commercial/aeroapi/), so an API key must be set in [environment variables](#environment-variables).

#### Options (mutually exclusive)

- `--bcbp <bcbp_text>`: Parse a string coded in the IATA Bar-Coded Boarding Pass (BCBP) format, and add the flight(s) it represents to the log.

    You can get this string by scanning the 2-D barcode on a boarding pass with a barcode reader app.

    **Example:**
    ```bash
    python -m pbflightlog add flight --bcbp "M1DOE/JOHN            EABC123 BOSJFKB6 0717 345P014C0010 147>3180 M6344BB6              29279          0 B6 B6 1234567890          ^108abcdefgh"
    ```

    Since BCBP data contains spaces, be sure to place the BCBP string in quotes. Do not trim trailing spaces from the string, as spaces have meaning in the BCBP format.

- `--fa-flight-id <fa_flight_id>`: Look up a flight on [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) by `fa_flight_id` and add it to the flight log.

    **Example:**
    ```bash
    python -m pbflightlog add flight --fa-flight-id UAL1234-1234567890-airline-0123
    ```

- `--number <airline_code> <flight_number>`: Look up an airline and flight number on [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) and add it to the flight log.

  To reduce ambiguity, ICAO airline codes (three letter codes, like `AAL`) are preferred. However, this will attempt to look up IATA airline codes (two character codes, like `AA`).

  **Example:**
    ```bash
    python -m pbflightlog add flight --number AAL 1234
    ```

- `--pkpasses`: Fetch all PKPass (Apple Wallet) files from the [import folder](#environment-variables) and add them to the flight log.

    **Example:**
    ```bash
    python -m pbflightlog add flight --pkpasses
    ```

- `--recent`: Add recent flights from [Flight Historian](https://www.flighthistorian.com).

    This looks up all flights from Flight Historian within the last 10 days, and adds them if they have not already been added.

    **Example:**
    ```bash
    python -m pbflightlog add flight --recent
    ```

### `update-routes`

Updates the routes table based on all routes present in the flights table. Generates great circle geometry for these routes.

> [!WARNING]
> This will overwrite the routes table, including removing routes that no longer have flights. Do not manually edit the routes table, as any edits will be lost when routes are updated.

**Example:**
```bash
python -m pbflightlog update-routes
```
