# Flight Log Tools

> [!IMPORTANT]
> These scripts are still pre-release and may be incomplete.

A small collection of command-line tools for working with a personal flight log stored in a GeoPackage.

## Basic usage

> [!NOTE]
> Throughout this documentation, `python` refers to the Python 3 interpreter. Different operating systems may require different commands such as `py` or `python3`.

```bash
python flight_log.py <command> [options]
```

To see available commands:

```bash
python flight_log.py --help
```

To see help for a specific command:

```bash
python flight_log.py <command> --help
```

---

## Commands

### `import-boarding-passes`

Imports flight records by parsing airline boarding pass files and creating corresponding entries in the flight log GeoPackage.

Typical use cases:

* Processing saved Apple Wallet .pkpass boarding passes

Example:

```bash
python flight_log.py import-boarding-passes
```

---

### `import-recent`

Retrieves recent flights from the Flight Historian API and creates corresponding records in the local flight log.

This command is intended to:

* Pull newly completed flights
* Avoid re-importing flights that already exist in the log

Example:

```bash
python flight_log.py import-recent
```

---

## Data model notes

* The flight log is stored as a GeoPackage, as described in the [schema](docs/schema.md).
* Individual flights may or may not have geometry (e.g., older flights without known tracks).
