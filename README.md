# PBFlightLog

PBFlightLog is a Python command-line interface (CLI) tool for managing a personal flight log stored in a GeoPackage file.

## Setup

### Installation

Navigate to the module's folder and install it with pip:

```bash
cd path/to/module
python -m pip install .
```

If you want to allow the scripts to be editable after install, perform a pip editable installation instead:

```bash
cd path/to/module
python -m pip install -e .
```

After installation, the `pbflightlog` command is available on the command line.

### Environment Variables

This package interacts with a GeoPackage flight log database as described in the [schema](docs/schema.md). The path to this file must be set as an environment variable:

```FLIGHT_LOG_GEOPACKAGE_PATH=/path/to/flight_log.gpkg```

This package has the ability to import files from a predefined import folder. The path to this folder must be set as an environment variable:

```FLIGHT_LOG_IMPORT_PATH=/path/to/import/folder```

Many of these scripts interact with [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) to get flight data. You will need to get an AeroAPI API key and set it as an environment variable:

```AEROAPI_API_KEY=yourkey```

> [!IMPORTANT]
> When these scripts call AeroAPI with your API key, you will incur AeroAPI per-query fees as appropriate for your AeroAPI account.

## Basic usage

```bash
pbflightlog <command> [options]
```

To see available commands:

```bash
pbflightlog --help
```

To see help for a specific command:

```bash
pbflightlog <command> --help
```

## Commands

### `add flight`

Create a new flight (or new flights) in the flight log.

> [!IMPORTANT]
> Flight data is pulled from [AeroAPI](https://www.flightaware.com/commercial/aeroapi/), so an API key must be set in [environment variables](#environment-variables).

#### Options (mutually exclusive)

- `--bcbp <bcbp_text>`: Parse a string coded in the IATA Bar-Coded Boarding Pass (BCBP) format, and add the flight(s) it represents to the log.

    You can get this string by scanning the 2-D barcode on a boarding pass with a barcode reader app.

    **Example**
    ```bash
    pbflightlog add flight --bcbp "M1DOE/JOHN            EABC123 BOSJFKB6 0717 345P014C0010 147>3180 M6344BB6              29279          0 B6 B6 1234567890          ^108abcdefgh"
    ```

    Since BCBP data contains spaces, be sure to place the BCBP string in quotes. Do not trim trailing spaces from the string, as spaces have meaning in the BCBP format.

- `--fa-flight-id <fa_flight_id>`: Look up a flight on [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) by `fa_flight_id` and add it to the flight log.

    **Example**
    ```bash
    pbflightlog add flight --fa-flight-id UAL1234-1234567890-airline-0123
    ```

- `--number <airline_code> <flight_number>`: Look up an airline and flight number on [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) and add it to the flight log.

  To reduce ambiguity, ICAO airline codes (three letter codes, like `AAL`) are preferred. However, this will attempt to look up IATA airline codes (two character codes, like `AA`).

  **Example**
    ```bash
    pbflightlog add flight --number AAL 1234
    ```

- `--pkpasses`: Fetch all PKPass (Apple Wallet) files from the [import folder](#environment-variables) and add them to the flight log.

    **Example**
    ```bash
    pbflightlog add flight --pkpasses
    ```

### `refresh routes`

Regenerates the routes table based on all origin and destination airport pairs present in the flights table. Generates great circle geometry for these routes.

> [!WARNING]
> This will overwrite the routes table, including removing routes that no longer have flights. Do not manually edit the routes table, as any edits will be lost when routes are refreshed.

**Example:**
```bash
pbflightlog refresh routes
```

### `report airports`

Generates a report of airports visited. ([Layovers count as a single visit.](https://paulbogard.net/flight-historian/counting-visits-to-airports-the-significance-of-trip-sections/))

#### Options

- `--year <year>` (`-y <year>`): Filter the flights that airport visits are calculated from to those whose UTC departure is in the provided year. If this option is not used, airport visits will be calculated on all flights.

- `--output <file>` (`-o <file>`): Save the report in CSV format to the provided filename.

#### Examples

Show 2015 airport visits:

```bash
pbflightlog report airports --year 2015
```

```
 rank                    name iata_code icao_code faa_lid  visits
    1                  Dayton       DAY      KDAY     DAY      42
    2        Chicago (O’Hare)       ORD      KORD     ORD      16
    3 Orlando (International)       MCO      KMCO     MCO      12
    4       Dallas/Fort Worth       DFW      KDFW     DFW      10
    4                   Tulsa       TUL      KTUL     TUL      10
    6               Baltimore       BWI      KBWI     BWI       5
    6               Charlotte       CLT      KCLT     CLT       5
    6            Columbus, OH       CMH      KCMH     CMH       5
    9          Seattle/Tacoma       SEA      KSEA     SEA       4
    9               St. Louis       STL      KSTL     STL       4
10 airport(s) visited
```
Save 2015 airport visits to airports.csv:

```bash
pbflightlog report airports --year 2015 --output airports.csv
```