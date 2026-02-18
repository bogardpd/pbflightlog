"""Tools for interacting with FlightAware's AeroAPI."""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

import colorama
import requests
import geopandas as gpd
from shapely.geometry import MultiLineString, LineString, Point

import pbflightlog.flight_log as fl

# Load API key.
_API_KEY = os.getenv("AEROAPI_API_KEY")
if _API_KEY is None:
    raise KeyError("Environment variable AEROAPI_API_KEY is missing.")
# Server info.
SERVER = "https://aeroapi.flightaware.com/aeroapi"
_TIMEOUT = 10

colorama.init()

class AeroAPIRateLimiter:
    """Maintains state of wait time."""

    def __init__(self):
        # Set a wait time in seconds to avoid rate limiting on the
        # Personal tier. If your account has a higher rate limit, you
        # can set this to 0.
        self.wait_time = 8
        self.wait_until = datetime.now(timezone.utc)

    def wait(self):
        """Delays requests to avoid AeroAPI rate limits."""
        if self.wait_time == 0:
            return
        now = datetime.now(timezone.utc)

        # If we're early, wait.
        if now < self.wait_until:
            sleep_seconds = (self.wait_until - now).total_seconds()
            print(f"⏳ Waiting until {self.wait_until}")
            time.sleep(sleep_seconds)

        # Schedule the next wait.
        self.wait_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.wait_time
        )

_rate_limiter = AeroAPIRateLimiter()

class AeroAPIWrapper:
    """Class for interacting with AeroAPI version 4."""
    def __init__(self):
        self.api_key = os.getenv("AEROAPI_API_KEY")
        if self.api_key is None:
            raise KeyError("Environment variable AEROAPI_API_KEY is missing.")
        self.server = "https://aeroapi.flightaware.com/aeroapi"
        self.timeout = 10
        self.isoformat = "%Y-%m-%dT%H:%M:%SZ"

        # Set a wait time in seconds to avoid rate limiting on the
        # Personal tier. If your account has a higher rate limit,
        # you can set this to 0.
        self.wait_time = 8
        self.wait_until = None

    def add_flight(self, ident, fields=None):
        """Gets flight info for an ident and saves flight(s) to log."""
        headers = {'x-apikey': self.api_key}
        url = f"{self.server}/flights/{ident}"
        params = {'ident_type': "fa_flight_id"}
        self.wait()
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=self.timeout,
        )
        print(f"🌐 GET {response.url}")
        response.raise_for_status()
        json_response = response.json()
        flights = json_response['flights']
        if len(flights) == 0:
            print(
                colorama.Fore.YELLOW
                + f"AeroAPI returned 0 flights for {ident}."
                + colorama.Style.RESET_ALL
            )
            return

        # AeroAPI may return more than one flight for an fa_flight_id
        # if the flight was diverted. The flight without diverted status
        # is the actual flight as shown.
        flight = [f for f in flights if f['status'] != "Diverted"][0]

        # Check that flight is completed.
        progress = flight['progress_percent']
        if progress is None or progress != 100:
            print(
                colorama.Fore.YELLOW
                + f"{ident} is not 100% complete (complete: {progress}%). "
                + "Flight was not added to log."
                + colorama.Style.RESET_ALL
            )
            return

        # Get geometry:
        track_json = self.get_geometry(flight['fa_flight_id'])
        if track_json is None:
            print(
                colorama.Fore.YELLOW,
                f"No track found for {ident}",
                colorama.Style.RESET_ALL,
            )
            geom_mls = None
            track_dist_mi = None
        else:
            positions = track_json['positions']
            track_ls = LineString([Point(
                p['longitude'],
                p['latitude'],
                p['altitude']*30.48, # Convert 100s of feet to meters
            ) for p in positions])
            geom_mls = AeroAPIWrapper.split_antimeridian(track_ls)
            track_dist_mi = int(track_json['actual_distance'])

        # Create record.
        record = {
            'geometry': geom_mls,
            'departure_utc': self.dep_utc(flight),
            'arrival_utc': self.arr_utc(flight),
            'flight_number': flight['flight_number'],
            'origin_airport_fid': getattr(
                fl.Airport.find_by_code(flight['origin']['code']),
                'fid', None
            ),
            'destination_airport_fid': getattr(
                fl.Airport.find_by_code(flight['destination']['code']),
                'fid', None
            ),
            'aircraft_type_fid': getattr(
                fl.AircraftType.find_by_code(flight['aircraft_type']),
                'fid', None
            ),
            'operator_fid': getattr(
                fl.Airline.find_by_code(flight['operator']), 'fid', None
            ),
            'tail_number': flight['registration'],
            'fa_flight_id': flight['fa_flight_id'],
            'fa_json': json.dumps(flight),
            'geom_source': "FlightAware",
            'distance_mi': track_dist_mi,
            'comments': None,
        }

        # Add supplied field values.
        if fields is not None:
            for k, v in fields.items():
                record[k] = v

        # Append flight.
        gdf = gpd.GeoDataFrame([record], geometry='geometry', crs="EPSG:4326")
        fl.append_flights(gdf)

    def format_time(self, time_val):
        """Format time as ISO 8601."""
        if time_val is None:
            return None
        return time_val.strftime(self.isoformat)

    def get_geometry(self, ident):
        """Gets the track for a specific flight."""
        url = f"{self.server}/flights/{ident}/track"
        headers = {'x-apikey': self.api_key}
        params = {
            'include_estimated_positions': "true",
            'include_surface_positions': "true",
        }
        self.wait()
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=self.timeout,
        )
        print(f"🌐 GET {response.url}")
        response.raise_for_status()
        track_json = response.json()
        if track_json is None:
            print(
                colorama.Fore.YELLOW,
                f"No track found for {ident}",
                colorama.Style.RESET_ALL,
            )
        return track_json

    def wait(self):
        """Delays requests to avoid AeroAPI rate limits."""
        if self.wait_time == 0:
            return
        now = datetime.now(timezone.utc)

        # On the first request, initialize and proceed.
        if self.wait_until is None:
            self.wait_until = now + timedelta(seconds=self.wait_time)
            return

        # If we're early, wait.
        if now < self.wait_until:
            sleep_seconds = (self.wait_until - now).total_seconds()
            print(f"⏳ Waiting until {self.wait_until}")
            time.sleep(sleep_seconds)

        # Schedule the next wait.
        self.wait_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.wait_time
        )

    def arr_utc(self, flight_dict):
        """Gets the actual arrival time of a flight."""
        if flight_dict['actual_in'] is None:
            # Flights diverted to a different airport use estimated_in.
            if flight_dict['progress_percent'] == 100:
                return flight_dict['estimated_in']
            else:
                return None
        return self.format_time(isoparse(flight_dict['actual_in']))

    def dep_utc(self, flight_dict):
        """Gets the actual departure time of a flight."""
        if flight_dict['actual_out'] is None:
            return None
        return self.format_time(isoparse(flight_dict['actual_out']))


    @staticmethod
    def split_antimeridian(track_ls: LineString):
        """Split a LineString at the antimeridian."""
        crossings = [
            i + 1 for i, (p1, p2)
            in enumerate(zip(track_ls.coords[:-1], track_ls.coords[1:]))
            if (p1[0] < 0 and p2[0] >= 0) or (p1[0] >= 0 and p2[0] < 0)
        ]

        # Split the track at the indices.
        if len(crossings) == 0:
            geom = MultiLineString([track_ls])
        else:
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
                    p_cross = AeroAPIWrapper.__crossing_point(p1, p2)
                    if p_cross is not None:
                        track.insert(0, p_cross)
                if i < len(crossings):
                    p1 = track[-1]
                    p2 = tracks[i+1][0]
                    p_cross = AeroAPIWrapper.__crossing_point(p1, p2)
                    if p_cross is not None:
                        track.append(p_cross)

            # Filter out tracks with only one point.
            tracks = [track for track in tracks if len(track) > 1]

            geom = MultiLineString(tracks)
        return geom

    @staticmethod
    def __crossing_point(p1, p2):
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

def get_flights_ident(ident, ident_type=None):
    """Gets flights matching an ident."""
    url = f"{SERVER}/flights/{ident}"
    headers = {'x-apikey': _API_KEY}
    params = {'ident_type': ident_type}
    _rate_limiter.wait()
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=_TIMEOUT,
    )
    print(f"🌐 GET {response.url}")
    response.raise_for_status()
    fa_json = response.json()
    return fa_json['flights']

def get_flights_ident_track(ident):
    """Gets the track for a specific flight."""
    url = f"{SERVER}/flights/{ident}/track"
    headers = {'x-apikey': _API_KEY}
    params = {
        'include_estimated_positions': "true",
        'include_surface_positions': "true",
    }
    _rate_limiter.wait()
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=_TIMEOUT,
    )
    print(f"🌐 GET {response.url}")
    response.raise_for_status()
    fa_json = response.json()
    return fa_json
