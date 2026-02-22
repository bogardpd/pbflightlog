"""Tools for interacting with FlightAware's AeroAPI."""

# Standard imports
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Third-party imports
import requests
from dateutil.parser import isoparse
from tabulate import tabulate

# Load API key.
_API_KEY = os.getenv("AEROAPI_API_KEY")
if _API_KEY is None:
    raise KeyError("Environment variable AEROAPI_API_KEY is missing.")
# Server info.
SERVER = "https://aeroapi.flightaware.com/aeroapi"
_TIMEOUT = 10

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

def get_flights_ident(ident, ident_type=None):
    """Gets flights matching an ident."""
    print(f"Looking up \"{ident}\" on AeroAPI")
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

def select_flight_info(flight_info_flights: list(dict)) -> dict | None:
    """
    Asks user to select flight info from a list of flight info.
    """
    if len(flight_info_flights) == 0:
        return None
    if len(flight_info_flights) == 1:
        return flight_info_flights[0]
    flight_info_flights = sorted(flight_info_flights, key=lambda f: (
        f.get('scheduled_out') is None, f.get('scheduled_out')
    ), reverse=True)
    table = [
        [
            i + 1,
            f.get('ident'),
            _dt_str_tz((
                f.get('actual_out')
                or f.get('estimated_out')
                or f.get('scheduled_out')
            ), f.get('origin', {}).get('timezone')),
            (
                f.get('origin', {}).get('code_iata')
                or f.get('origin', {}).get('code')
            ),
            (
                f.get('destination', {}).get('code_iata')
                or f.get('destination', {}).get('code')
            ),
            f.get('progress_percent'),
        ]
        for i, f in enumerate(flight_info_flights)
    ]
    print(tabulate(table,
        headers=["Row", "Ident", "Departure", "Orig", "Dest", "Progress %"],

    ))
    selected_flight_info = None
    while selected_flight_info is None:
        row = input("Select a row number (or Q to quit): ")
        if row.upper() == "Q":
            sys.exit(0)
        try:
            row_index = int(row) - 1
            if row_index < 0:
                print("Invalid row selection.")
                continue
            selected_flight_info = flight_info_flights[row_index]
        except IndexError, ValueError:
            print("Invalid row selection.")
    return selected_flight_info

def _dt_str_tz(dt_str, tz):
    """Converts a datetime into local time."""
    if dt_str is None or tz is None:
        return None
    try:
        dt = isoparse(dt_str)
        dt_tz = dt.astimezone(ZoneInfo(tz))
    except ValueError:
        return None
    return dt_tz.strftime("%a %d %b %Y %H:%M %Z")
