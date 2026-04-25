# Changelog

## [Unreleased]

## [0.4.0]

### Added

- `report milestones` command to show flights which cross cumulative distance milestones.

### Fixed

- Capitalization of table headers in `show airport` views.

## [0.3.0]

### Added

- `show airport` subcommand to show a flight table for a particular airport.
- CHANGELOG.
- Option to skip AeroAPI when selecting AeroAPI flight.

### Changed

- Rename `report airports` to `index airports`.
- Update environment variable prefixes from `FLIGHT_LOG_` to `PBFLIGHTLOG_` to match project name.
- Estimate trip section based on departure times with `add flights` subcommand.

## [0.2.0] - 2026-03-14

### Added

- `report airports` subcommand for listing airports by number of visits.

## [0.1.0] - 2026-03-09

### Added

- Initial release of PBFlightLog.
- `add flight` subcommand for importing flight data from [AeroAPI](https://www.flightaware.com/commercial/aeroapi/) based on boarding pass data or flight numbers.
- `refresh routes` subcommand for updating great circle route geometry based on the flights in the flight log.
- Initial documentation, including setup and usage.
- Initial [schema](docs/schema.md).