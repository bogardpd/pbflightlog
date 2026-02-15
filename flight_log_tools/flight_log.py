"""Scripts for interacting with the flight log."""

# Standard imports
import json
import os
import sqlite3
from math import ceil
from datetime import datetime

# Third-party imports
import colorama
import geopandas as gpd
import pandas as pd
from dateutil.parser import isoparse
from pyproj import Geod
from shapely.geometry import Point, LineString, MultiLineString

METERS_PER_MILE = 1609.344
METERS_BETWEEN_GC_POINTS = 100000

CRS = "EPSG:4326" # WGS-84

colorama.init()

flight_log = os.getenv("FLIGHT_LOG_GEOPACKAGE_PATH")
if flight_log is None:
    raise KeyError(
        "Environment variable FLIGHT_LOG_GEOPACKAGE_PATH is missing."
    )

class Flight():
    """Represents a flight record."""
    def __init__(self):
        self.geometry: MultiLineString | None = None
        self.departure_utc: datetime | None = None
        self.arrival_utc: datetime | None = None
        self.airline_fid: int | None = None
        self.flight_number: str | None = None
        self.origin_airport_fid: int | None = None
        self.destination_airport_fid: int | None = None
        self.aircraft_type_fid: int | None = None
        self.operator_fid: int | None = None
        self.tail_number: str | None = None
        self.fa_flight_id: str | None = None
        self.fa_json: dict | None = None
        self.geom_source: str | None = None
        self.distance_mi: int | None = None

    def gdf(self) -> gpd.GeoDataFrame:
        """Returns a GeoDataFrame record for the flight."""
        record = {
            'geometry': self.geometry,
            'departure_utc': _format_time(self.departure_utc),
            'arrival_utc': _format_time(self.arrival_utc),
            'flight_number': self.flight_number,
            'origin_airport_fid': self.origin_airport_fid,
            'destination_airport_fid': self.destination_airport_fid,
            'aircraft_type_fid': self.aircraft_type_fid,
            'operator_fid': self.operator_fid,
            'tail_number': self.tail_number,
            'fa_flight_id': self.fa_flight_id,
            'fa_json': (
                None if self.fa_json is None else json.dumps(self.fa_json)
            ),
            'geom_source': self.geom_source,
            'distance_mi': self.distance_mi,
            'comments': None,
        }
        return gpd.GeoDataFrame([record], geometry='geometry', crs=CRS)

    def load_aeroapi(self, fa_json: dict) -> None:
        """Loads flight values from an AeroAPI response."""
        self.fa_json = fa_json
        self.departure_utc = Flight.dep_utc(fa_json)
        self.arrival_utc = Flight.arr_utc(fa_json)
        self.flight_number = fa_json['flight_number']
        self.origin_airport_fid = find_airport_fid(
            fa_json['origin']['code']
        )
        self.destination_airport_fid = find_airport_fid(
            fa_json['destination']['code']
        )
        self.aircraft_type_fid = find_aircraft_type_fid(
            fa_json['aircraft_type']
        )
        self.operator_fid = find_airline_fid(fa_json['operator'])
        self.tail_number = fa_json['registration']
        self.fa_flight_id = fa_json['fa_flight_id']

    @classmethod
    def arr_utc(cls, fa_json: dict) -> datetime | None:
        """Gets the actual arrival time of a flight."""
        if fa_json['actual_in'] is None:
            # Flights diverted to a different airport use estimated_in.
            if fa_json['progress_percent'] == 100:
                return fa_json['estimated_in']
            return None
        return isoparse(fa_json['actual_in'])

    @classmethod
    def dep_utc(cls, flight_json: dict) -> datetime | None:
        """Gets the actual departure time of a flight."""
        if flight_json['actual_out'] is None:
            return None
        return isoparse(flight_json['actual_out'])


def append_flights(record_gdf):
    """Appends a GeoDataFrame of records to flights."""
    layer = "flights"

    # Ensure columns match existing structure.
    existing = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        rows=0,
    )
    existing_cols = list(existing.columns)
    incoming_cols = list(record_gdf.columns)

    # Check that geometry column name matches.
    geom_col = record_gdf.geometry.name
    if geom_col not in existing_cols:
        raise ValueError(
            f"Geometry column '{geom_col}' not found in existing "
            "layer schema"
        )

    # Check for columns in new data not in current schema.
    extra_cols = set(incoming_cols) - set(existing_cols)
    if extra_cols:
        raise ValueError(
            "Incoming data has columns not present in layer "
            f"schema: {extra_cols}"
        )

    # Add missing columns from existing schema as null values.
    for col in existing_cols:
        if col not in record_gdf.columns:
            record_gdf[col] = None
            print(
                f"No value was provided for column '{col}'; setting "
                "its value to null."
            )

    # Reorder columns to match existing schema.
    gdf = record_gdf[existing_cols]

    # Append data to geopackage layer.
    gdf.to_file(
        flight_log,
        driver="GPKG",
        engine="pyogrio",
        layer=layer,
        mode="a",
    )
    print(
        f"Appended {len(record_gdf)} flights(s) to '{layer}' in {flight_log}."
    )
    update_routes()

def find_aircraft_type_fid(code):
    """Finds an aircraft_type fid by ICAO or IATA code."""
    layer = "aircraft_types"
    ac_types = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = ac_types[ac_types[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one aircraft type. Setting "
                + "value to null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any aircraft type. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None

def find_airline_by_code(code):
    """Finds an airline fid by ICAO or IATA code."""
    layer = "airlines"
    airlines = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )
    # Filter out defunct airlines. This is helpful in situations where
    # current airlines use the same codes as an old airline (for
    # example, the current PSA airlines and the defunct Comair both use
    # the IATA code 'OH'.)
    airlines = airlines[~airlines['is_defunct']]

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = airlines[airlines[code_type] == code]
        if len(matching_code) == 1:
            airline = matching_code.iloc[0].to_dict()
            airline['fid'] = int(matching_code.index[0])
            return airline
    return None

def find_airline_fid(code):
    """Finds an airline fid by ICAO or IATA code."""
    layer = "airlines"
    airlines = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )
    # Filter out defunct airlines. This is helpful in situations where
    # current airlines use the same codes as an old airline (for
    # example, the current PSA airlines and the defunct Comair both use
    # the IATA code 'OH'.)
    airlines = airlines[~airlines['is_defunct']]

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = airlines[airlines[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one airline. Setting value to "
                + "null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any airline. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None

def find_airport_fid(code):
    """Finds an airport fid by ICAO or IATA code."""
    layer = "airports"
    airports = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )
    # Filter out defunct airports. This is helpful in situations where
    # current airports use the same codes as an old airport (for
    # example, the modern Denver airport and the old Denver Stapleton
    # both use 'KDEN'/'DEN'.)
    airports = airports[~airports['is_defunct']]

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = airports[airports[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one airport. Setting value to "
                + "null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any airport. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None

def update_routes():
    """Updates the routes layer based on logged flights."""
    con = sqlite3.connect(flight_log)
    flights_sql = """
        SELECT origin_airport_fid, destination_airport_fid,
            COUNT(*) as flight_count
        FROM flights
        GROUP BY origin_airport_fid, destination_airport_fid
        ORDER BY origin_airport_fid, destination_airport_fid
    """
    flights_df = pd.read_sql(flights_sql, con)
    con.close()

    airports = gpd.read_file(
        flight_log,
        layer='airports',
        engine='pyogrio',
        fid_as_index=True,
    )

    flights_df[['distance_mi', 'geometry']] = flights_df.apply(lambda f:
        _great_circle_route(
            airports.loc[f.origin_airport_fid, 'geometry'],
            airports.loc[f.destination_airport_fid, 'geometry'],
        ),
        axis = 1,
    )
    flights_df['distance_mi'] = flights_df['distance_mi'].astype(int)

    routes_gdf = gpd.GeoDataFrame(
        flights_df,
        geometry='geometry',
        crs="EPSG:4326", # WGS-84
    )

    routes_gdf.to_file(
        flight_log,
        driver='GPKG',
        engine='pyogrio',
        layer='routes',
        mode='w',
    )
    print(
        f"Updated all routes in {flight_log}."
    )

def _format_time(time_val):
    """Format time as ISO 8601 with Z."""
    if time_val is None:
        return None
    return time_val.strftime("%Y-%m-%dT%H:%M:%SZ")

def _great_circle_route(point1, point2) -> pd.Series:
    """
    Creates a great circle line between points.

    Returns a Pandas series with distance in integer miles and a
    MultiLineString geometry.
    """
    if point1 == point2:
        # Returned to same airport. Return zero great circle distance
        # and no geometry.
        return pd.Series([0, None])
    geod = Geod(ellps="WGS84")
    _, _, dist_m = geod.inv(point1.x, point1.y, point2.x, point2.y)
    dist_mi = int(round(dist_m / METERS_PER_MILE))

    # Create a great circle LineString.
    num_points = ceil(dist_m / METERS_BETWEEN_GC_POINTS) + 1
    midpoints = geod.npts(
        point1.x, point1.y,
        point2.x, point2.y,
        num_points - 2,
    )
    geom = _split_at_antimeridian(
        LineString([point1, *midpoints, point2])
    )

    return pd.Series([dist_mi, geom])

def _split_at_antimeridian(linestring) -> MultiLineString:
    """Splits a linestring at the antimeridian (180 degrees)."""
    points = [Point(x, y) for x, y in linestring.coords]
    if len(points) < 2:
        return MultiLineString(linestring)
    crossing_index = None
    crossing_lat = None
    crossing_lon = [None, None]
    for i, (p1, p2) in enumerate(zip(points[:-1],points[1:])):
        if abs(p1.x - p2.x) > 180:
            crossing_index = i + 1
            # Calculate crossing points at -180 and +180 longitude.
            if p1.x > p2.x:
                dist_to_crossing = 180 - p1.x
                total_dist = (180 - p1.x) + (180 + p2.x)
                crossing_lon = [180, -180]
            else:
                dist_to_crossing = p1.x - (-180)
                total_dist = (p1.x - (-180)) + (180 - p2.x)
                crossing_lon = [-180, 180]
            if total_dist == 0:
                crossing_lat = p1.y
            else:
                frac_dist = dist_to_crossing / total_dist
                crossing_lat = p1.y + frac_dist * (p2.y - p1.y)
            break
    if crossing_index is None:
        # No crossing was found. Return a single part MultiLineString.
        return MultiLineString([linestring])

    # Add crossing point to both parts of the split LineString.
    parts = [
        LineString([
            *points[:crossing_index],
            Point(crossing_lon[0], crossing_lat),
        ]),
        LineString([
            Point(crossing_lon[1], crossing_lat),
            *points[crossing_index:],
        ]),
    ]
    return MultiLineString(parts)
