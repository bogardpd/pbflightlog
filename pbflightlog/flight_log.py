"""Scripts for interacting with the flight log."""

# Standard imports
import json
import os
import sqlite3
import sys
from datetime import datetime
from math import ceil
from typing import Self
from zoneinfo import ZoneInfo

# Third-party imports
import geopandas as gpd
import pandas as pd
from dateutil.parser import isoparse
from pyproj import Geod
from shapely.geometry import Point, LineString, MultiLineString

# Project imports
import pbflightlog.aeroapi as aero

METERS_PER_MILE = 1609.344
METERS_PER_HUNDRED_FEET = 30.48
METERS_BETWEEN_GC_POINTS = 100000

CRS = "EPSG:4326" # WGS-84

flight_log = os.getenv("FLIGHT_LOG_GEOPACKAGE_PATH")
if flight_log is None:
    raise KeyError(
        "Environment variable FLIGHT_LOG_GEOPACKAGE_PATH is missing."
    )

class Record():
    """Represents a record from a flight log table."""
    LAYER = None
    FIND_BY_CODES = []
    DTYPES = {}

    @classmethod
    def pluck(cls, column) -> list(Self):
        """Returns a list of all values of a column."""
        records = gpd.read_file(
            flight_log,
            layer = cls.LAYER,
            engine="pyogrio",
            fid_as_index=True,
        ).astype(cls.DTYPES)
        return records[column].to_list()

    @classmethod
    def find_by_code(cls, code: str) -> Self | None:
        """Finds a record by searching through code fields."""
        if getattr(cls, 'FIND_BY_CODES', None) is None:
            return None
        if len(cls.FIND_BY_CODES) == 0:
            return None
        records = gpd.read_file(
            flight_log,
            layer = cls.LAYER,
            engine="pyogrio",
            fid_as_index=True,
        )

        # Filter out defunct records. This is helpful in situations
        # where current records use the same codes as an old record
        # (for example, the current PSA airlines and the defunct Comair
        # both use the IATA code 'OH'.)
        if 'is_defunct' in records.columns:
            records = records[~records['is_defunct']]
        for code_type in cls.FIND_BY_CODES:
            # Search for matching codes.
            matching_code = records[records[code_type] == code]
            if len(matching_code) == 1:
                record_dict = matching_code.iloc[0].to_dict()
                record_dict['fid'] = int(matching_code.index[0])
                record = cls()
                for key, value in record_dict.items():
                    setattr(record, key, value)
                return record
        print(f"⚠️ Could not find {cls.__name__} matching \"{code}\".")
        return None

class AircraftType(Record):
    """Represents an aircraft type record."""
    LAYER = "aircraft_types"
    FIND_BY_CODES = ['icao_code']
    DTYPES = {}

    def __init__(self):
        # Fields used in flight log database:
        self.fid: int | None = None
        self.manufacturer: str | None = None
        self.name: str | None = None
        self.icao_code: str | None = None
        self.iata_code: str | None = None
        self.family: str | None = None
        self.category: str | None = None

class Airline(Record):
    """Represents an airline record."""
    LAYER = "airlines"
    FIND_BY_CODES = ['icao_code', 'iata_code']
    DTYPES = {}

    def __init__(self):
        # Fields used in flight log database:
        self.fid: int | None = None
        self.name: str | None = None
        self.icao_code: str | None = None
        self.iata_code: str | None = None
        self.numeric_code: str | None = None
        self.is_only_operator: bool | None = None
        self.is_defunct: bool | None = None

class Airport(Record):
    """Represents an airline record."""
    LAYER = "airports"
    FIND_BY_CODES = ['icao_code', 'iata_code']
    DTYPES = {}

    def __init__(self):
        # Fields used in flight log database:
        self.fid: int | None = None
        self.geometry: Point | None = None
        self.name: str | None = None
        self.country: str | None = None
        self.icao_code: str | None = None
        self.iata_code: str | None = None
        self.faa_lid: str | None = None
        self.time_zone: str | None = None
        self.is_defunct: bool | None = None

class Flight(Record):
    """Represents a flight record."""
    LAYER = "flights"
    FIND_BY_CODES = []
    DTYPES = {'fh_id': "Int64"}

    def __init__(self):
        # Fields used in flight log database:
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
        self.boarding_pass_data: str | None = None
        self.fh_id: int | None = None
        self.fa_flight_id: str | None = None
        self.fa_json: dict | None = None
        self.geom_source: str | None = None
        self.distance_mi: int | None = None

        # Other fields from AeroAPI:
        self.scheduled_out: datetime | None = None
        self.estimated_out: datetime | None = None
        self.actual_out: datetime | None = None
        self.scheduled_in: datetime | None = None
        self.estimated_in: datetime | None = None
        self.actual_in: datetime | None = None
        self.ident: str | None = None
        self.origin_code: str | None = None
        self.origin_tz: str | None = None
        self.destination_code: str | None = None
        self.destination_tz: str | None = None
        self.progress: int | None = None

    def fetch_aeroapi_track_geometry(self) -> None:
        """Gets flight track from AeroAPI"""
        if self.progress is None or self.progress < 100:
            print(
                "⚠️ Cannot get track: flight is not complete "
                f"({self.progress}% complete)."
            )
            return
        if self.fa_flight_id is None:
            print("⚠️ Cannot get track: fa_flight_id is not set.")
            return
        fa_json = aero.get_flights_ident_track(self.fa_flight_id)
        if fa_json is None:
            print(f"⚠️ No track found for {self.fa_flight_id}.")
            return
        positions = fa_json.get('positions')
        if len(positions) == 0:
            print(f"⚠️ No positions found for {self.fa_flight_id}.")
            return
        track_ls = LineString([Point(
            p.get('longitude'),
            p.get('latitude'),
            p.get('altitude') * METERS_PER_HUNDRED_FEET,
        ) for p in positions])
        self.geometry = split_at_antimeridian(track_ls)
        self.geom_source = "FlightAware"
        try:
            self.distance_mi = int(fa_json.get('actual_distance'))
        except TypeError, ValueError:
            print(f"⚠️ No distance found for {self.fa_flight_id}.")

    def exit_if_not_complete(self) -> None:
        """Exits if this flight is not complete."""
        if self.progress is None or self.progress < 100:
            print(
                f"⚠️ Flight is not complete ({self.progress}% complete). "
                "Flight was not added to log."
            )
            sys.exit(1)

    def gdf(self) -> gpd.GeoDataFrame:
        """Returns a GeoDataFrame record for the flight."""
        record = {
            'geometry': self.geometry,
            'departure_utc': _format_time(self.departure_utc),
            'arrival_utc': _format_time(self.arrival_utc),
            'airline_fid': self.airline_fid,
            'flight_number': self.flight_number,
            'origin_airport_fid': self.origin_airport_fid,
            'destination_airport_fid': self.destination_airport_fid,
            'aircraft_type_fid': self.aircraft_type_fid,
            'operator_fid': self.operator_fid,
            'tail_number': self.tail_number,
            'boarding_pass_data': self.boarding_pass_data,
            'fh_id': self.fh_id,
            'fa_flight_id': self.fa_flight_id,
            'fa_json': (
                None if self.fa_json is None else json.dumps(self.fa_json)
            ),
            'geom_source': self.geom_source,
            'distance_mi': self.distance_mi,
            'comments': None,
        }
        return gpd.GeoDataFrame([record], geometry='geometry', crs=CRS)

    def save(self) -> None:
        """Appends a flight to the geopackage file."""
        record_gdf = self.gdf()
        existing = gpd.read_file(
            flight_log,
            layer=Flight.LAYER,
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
        gdf.to_file(
            flight_log,
            driver="GPKG",
            engine="pyogrio",
            layer=Flight.LAYER,
            mode="a",
        )
        print(f"Appended flight to {flight_log}.")


    def _arr_utc(self) -> datetime | None:
        """Gets the actual arrival time of a flight."""
        if self.actual_in is None:
            # Flights diverted to a different airport use estimated_in.
            if self.progress == 100:
                return self.estimated_in
            return None
        return self.actual_in

    def _dep_utc(self) -> datetime | None:
        """Gets the actual departure time of a flight."""
        return self.actual_out or None

    @classmethod
    def from_aeroapi(cls, fa_json: dict) -> Self:
        """Loads flight values from an AeroAPI response."""
        flight = cls()
        try:
            flight.progress = int(fa_json.get('progress_percent'))
        except TypeError, ValueError:
            pass
        flight.fa_json = fa_json
        flight.ident = fa_json.get('ident')
        flight.scheduled_out = cls.parse_dt(fa_json.get('scheduled_out'))
        flight.estimated_out = cls.parse_dt(fa_json.get('estimated_out'))
        flight.actual_out = cls.parse_dt(fa_json.get('actual_out'))
        flight.scheduled_in = cls.parse_dt(fa_json.get('scheduled_in'))
        flight.estimated_in = cls.parse_dt(fa_json.get('estimated_in'))
        flight.actual_in = cls.parse_dt(fa_json.get('actual_in'))
        flight.departure_utc = flight._dep_utc()
        flight.arrival_utc = flight._arr_utc()
        flight.flight_number = fa_json.get('flight_number')

        origin = fa_json.get('origin', {})
        flight.origin_airport_fid = getattr(
            Airport.find_by_code(origin.get('code')), 'fid', None
        )
        flight.origin_code = origin.get('code_iata') or origin.get('code')
        flight.origin_tz = origin.get('timezone')

        destination = fa_json.get('destination', {})
        flight.destination_airport_fid = getattr(
            Airport.find_by_code(destination.get('code')), 'fid', None
        )
        flight.destination_code = destination.get('code_iata') \
            or destination.get('code')
        flight.destination_tz = destination.get('timezone')

        flight.aircraft_type_fid = getattr(
            AircraftType.find_by_code(fa_json.get('aircraft_type')),
            'fid', None
        )
        flight.operator_fid = getattr(
            Airline.find_by_code(fa_json.get('operator')), 'fid', None
        )
        flight.tail_number = fa_json.get('registration')
        flight.fa_flight_id = fa_json.get('fa_flight_id')
        return flight

    @staticmethod
    def parse_dt(dt_str) -> datetime | None:
        """Parses a datetime string."""
        if dt_str is None:
            return None
        return isoparse(dt_str)


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
        _great_circle_airport_lookup(f, airports),
        axis = 1,
    )
    flights_df['distance_mi'] = flights_df['distance_mi'].astype("Int64")

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

def great_circle_route(point1, point2) -> pd.Series:
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
    geom = split_at_antimeridian(
        LineString([point1, *midpoints, point2])
    )

    return pd.Series([dist_mi, geom])

def split_at_antimeridian(track_ls: LineString) -> MultiLineString:
    """Split a LineString at the antimeridian."""
    # Find all points where the track crosses the antimeridian.
    crossings = [
        i + 1 for i, (p1, p2)
        in enumerate(zip(track_ls.coords[:-1], track_ls.coords[1:]))
        if abs(p1[0] - p2[0]) > 180
    ]
    if len(crossings) == 0:
        return MultiLineString([track_ls])

    # Split the track at the indices.
    tracks = []
    starts = [0, *crossings]
    ends = [*crossings, len(track_ls.coords)-1]
    tracks = [
        track_ls.coords[start:end] for start, end in zip(starts, ends)
    ]
    for i, track in enumerate(tracks):
        if i > 0:
            p1 = track[0]
            p2 = tracks[i-1][-1]
            p_cross = _crossing_point(p1, p2)
            if p_cross is not None:
                track.insert(0, p_cross)
        if i < len(crossings):
            p1 = track[-1]
            p2 = tracks[i+1][0]
            p_cross = _crossing_point(p1, p2)
            if p_cross is not None:
                track.append(p_cross)

    # Filter out tracks with only one point.
    tracks = [track for track in tracks if len(track) > 1]
    return MultiLineString(tracks)

def _crossing_point(p1, p2):
    """Return the point where a track crosses the antemeridian.
    Returns None if p1 is already on the antemeridian.

    p1 : tuple(float)
        The point on the current track
    p2 : tuple(float)
        The point on the adjacent track.
    """
    p2 = list(p2)
    if -180 < p1[0] < 0:
        lon = -180
        p2[0] = p2[0] - 360
    elif 0 < p1[0] < 180:
        lon = 180
        p2[0] = p2[0] + 360
    else:
        return None
    x_frac = (lon - p1[0]) / (p2[0] - p1[0])
    return tuple([c1 + (x_frac * (c2 - c1)) for c1, c2 in zip(p1, p2)])

def _format_time(time_val):
    """Format time as ISO 8601 with Z."""
    if time_val is None:
        return None
    return time_val.strftime("%Y-%m-%dT%H:%M:%SZ")

def _great_circle_airport_lookup(row, airports):
    """Runs great_circle_route with a GeoDataFrame row."""
    try:
        return great_circle_route(
            airports.loc[row.origin_airport_fid, 'geometry'],
            airports.loc[row.destination_airport_fid, 'geometry'],
        )
    except KeyError:
        return pd.Series([None, None])

def _dt_str_tz(dt, tz):
    """Converts a datetime into local time."""
    if dt is None or tz is None:
        return None
    dt_tz = dt.astimezone(ZoneInfo(tz))
    return dt_tz.strftime("%a %d %b %Y %H:%M %Z")
