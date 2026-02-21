"""Tools for interacting with FlightAware's AeroAPI."""

# Standard imports
import os
import time
from datetime import datetime, timedelta, timezone

# Third-party imports
import requests

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
