# Flight Log Data Schema

These scripts use a [GeoPackage file](https://www.geopackage.org/) containing flight log data for a single traveler.

## GeoPackage Layers

> [!NOTE]
> Columns use the data types specified in the GeoPackage Encoding Standards [Table 1. GeoPackage Data Types](https://www.geopackage.org/spec/#table_column_data_types), and geometry types specified in [Annex G: Geometry Types (Normative)](https://www.geopackage.org/spec/#geometry_types). Optional fields must be null when unused.

### airlines (No Geometry)

The `airlines` table contains records of airlines that `flights` have used as their marketing carrier, operator, or codeshare.

| Column | Data Type | Description |
|--------|-----------|-------------|
| `fid` | INT (64 bit) | Primary key for the airline record. |
| `name` | TEXT | The name of the airline. |
| `icao_code` | TEXT | ICAO code for the airline (e.g. `AAL`). |
| `iata_code` | TEXT | IATA code for the airline (e.g. `AA`). |
| `numeric_code` | TEXT | *Optional.* The three-digit numeric code for the airline (e.g. `001`) |
| `is_only_operator` | BOOLEAN | True if an airline only operates flights for other airlines, false if it operates flights as its own marketing carrier. (See [Airline Types](#airline-types).) |
| `is_defunct` | BOOLEAN | True if an airline is no longer in use, false otherwise. When looking up airlines, defunct airlines will be ignored. This is helpful in situations where current airlines use the same codes as an old airline (for example, the current PSA Airlines and the defunct Comair both use the IATA code `OH`.) |

#### Airline Types

The airlines table is used in multiple contexts - to represent marketing airlines, operating airline, codeshare airlines.

Not all flights are operated by the airline that sold the ticket. In some cases, mainline airlines will subcontract to a regional subsidiary to actually run the flight. For example, many American Airlines regional flights are actually operated by Envoy Air. In this case, the **marketing airline** would be American Airlines, and the **operating airline** would be Envoy Air.

(If you're on an American Airlines flight that they actually operate themselves, then *both* the marketing airline and operating airline would be American Airlines.)

Additionally, sometimes mainline airlines will sell tickets for connecting flights on other mainline airlines' flights, particularly if they're in the same airline alliance. This is common on international itineraries, but can happen domestically as well. As an example, I could buy an itinerary on American Airlines with a flight from Dayton to Chicago O'Hare, and then on to London Heathrow. If that Chicago to London flight is actually a British Airways flight with its own flight number, then the **marketing airline** is British Airways, and the **codeshare airline** is American Airlines.

It's technically possible to have a flight with all three airline types, if you buy an itinerary with a flight operated by another airline's regional subsidiary.

### airports (Point)

The `airports` table contains records of airports that `flights` have used.

| Column | Data Type | Description |
|--------|-----------|-------------|
| `fid` | INT (64 bit) | Primary key for the airport record. |
| `city` | TEXT | The primary city or region the airport serves (e.g. `Atlanta`, `Dallas/Fort Worth`). If this is ambiguous, include the airport name in parentheses (e.g. `Chicago (O’Hare)`, `Chicago (Midway)`). |
| `country` | TEXT | The country the airport is located in, in ISO 3166-1 alpha-2 format (e.g. `US`). |
| `icao_code` | TEXT | *Optional.* ICAO code for the airport (e.g. `KATL`). |
| `iata_code` | TEXT | *Optional.* IATA code for the airport (e.g. `ATL`). |
| `is_defunct` | BOOLEAN | True if an airport is no longer in use, false otherwise. When looking up airports, defunct airports will be ignored. This is helpful in situations where current airports use the same codes as an old airport (for example, the modern Denver airport and the old Denver Stapleton both use `KDEN`/`DEN`.) |

### flights (MultiLineStringZ)

The `flights` table contains records of individual flights.

Individual flights may or may not have geometry (e.g., older flights without known tracks). If altitudes are present, they should use meters as units.

| Column | Data Type | Description |
|--------|-----------|-------------|
| `fid`  | INT (64 bit) | Primary key for the flight record. |
| `departure_utc` | DATETIME | UTC departure time for the flight. Prefer gate out time over wheels off (up) time. Prefer actual time over estimated time over scheduled time. |
| `arrival_utc` | DATETIME | *Optional.* UTC arrival time for the flight. Prefer gate in time over wheels on (down) time. Prefer actual time over estimated time over scheduled time. |
| `airline_fid` | INT (64 bit) | Foreign key referencing the marketing airline on the `airlines` table. (See [Airline Types](#airline-types).) |
| `flight_number` | TEXT | The marketing airline's flight number for the flight. (See [Airline Types](#airline-types).) |
| `origin_airport_fid` | INT (64 bit) | Foreign key referencing the origin airport on the `airports` table.
| `destination_airport_fid` | INT (64 bit) | Foreign key referencing the destination airport on the `airports` table.
| `operator_fid` | INT (64 bit) | Foreign key referencing the marketing airline on the `airlines` table. May or may not be the same as the `airline_fid`. (See [Airline Types](#airline-types).) |
| `codeshare_airline_fid` | INT (64 bit) | *Optional.* Foreign key referencing the codeshare airline on the `airlines` table. (See [Airline Types](#airline-types).) |
| `codeshare_flight_number` | TEXT | *Optional.* The codeshare airline's flight number for the flight. (See [Airline Types](#airline-types).) |
| `fa_flight_id` | TEXT | *Optional.* FlightAware AeroAPI ID string. |
| `fh_id` | INT (64 bit) | *Optional.* Flight Historian flight record ID. |
| `fa_json` | TEXT | *Optional.* Response string from AeroAPI flight lookup, in JSON format.
| `geom_source` | TEXT | *Optional.* Source of geometry data for this flight (e.g. `FlightAware`, `GPS`).
| `distance_mi` | INT (64 bit) | Distance of the flight in miles. Includes taxiing (ground) distance when available.
| `comments` | TEXT | *Optional.* Comments about the flight. |
