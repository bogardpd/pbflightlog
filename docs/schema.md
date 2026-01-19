# Flight Log Data Schema

These scripts use a [GeoPackage file](https://www.geopackage.org/) containing flight log data for a single traveler.

## GeoPackage Layers

> [!NOTE]
> Columns use the data types specified in the GeoPackage Encoding Standards [Table 1. GeoPackage Data Types](https://www.geopackage.org/spec/#table_column_data_types), and geometry types specified in [Annex G: Geometry Types (Normative)](https://www.geopackage.org/spec/#geometry_types). Optional fields must be null when unused.

### flights (MultiLineStringZ)

The `flights` table contains records of individual flights.

| Column | Data Type | Description |
|--------|-----------|-------------|
| `fid`  | INT (64 bit) | Primary key for the flight record. |
| `departure_utc` | DATETIME | UTC departure time for the flight. Prefer gate out time over wheels off (up) time. Prefer actual time over estimated time over scheduled time. |
| `arrival_utc` | DATETIME | *Optional.* UTC arrival time for the flight. Prefer gate in time over wheels on (down) time. Prefer actual time over estimated time over scheduled time. |
| `fa_flight_id` | TEXT | *Optional.* FlightAware AeroAPI ID string. |
| `identifier` | TEXT | *Optional.* Identifer string for the flight (e.g. `AAL1234`).
| `origin_icao` | TEXT | ICAO code for the origin airport. |
| `destination_icao` | TEXT | ICAO code for the destination airport. |
| `fh_id` | INT (64 bit) | *Optional.* Flight Historian flight record ID. |
| `fa_json` | TEXT | *Optional.* Response string from AeroAPI flight lookup, in JSON format.
| `geom_source` | TEXT | *Optional.* Source of geometry data for this flight (e.g. `FlightAware`, `GPS`).
| `origin_airport_fid` | INT (64 bit) | Foreign key referencing the origin airport on the `airports` table.
| `destination_airport_fid` | INT (64 bit) | Foreign key referencing the destination airport on the `airports` table.
| `comments` | TEXT | *Optional.* Comments about the flight. |

### airports (Point)

The `airports` table contains records of airports that `flights` have used.

| Column | Data Type | Description |
|--------|-----------|-------------|
| `fid` | INT (64 bit) | Primary key for the airport record. |
| `iata_code` | TEXT | IATA code for the airport (e.g. `ATL`). |
| `icao_code` | TEXT | ICAO code for the airport (e.g. `KATL`). |
| `city` | TEXT | The primary city or region the airport serves (e.g. `Atlanta`, `Dallas/Fort Worth`). If this is ambiguous, include the airport name in parentheses (e.g. `Chicago (O’Hare)`, `Chicago (Midway)`). |
| `country` | TEXT | The country the airport is located in, in ISO 3166-1 alpha-2 format (e.g. `US`) |
