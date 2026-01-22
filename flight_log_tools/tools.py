"""Functions for CLI commands."""

import os
import requests

from flight_log_tools import aeroapi

def import_boarding_passes():
    """Imports digital boarding passes."""
    print("Importing digital boarding passes...")

def import_recent():
    """Finds recent flights on Flight Historian API and imports them."""
    aw = aeroapi.AeroAPIWrapper()
    api_key_fh = os.getenv("FLIGHT_HISTORIAN_API_KEY")
    if api_key_fh is None:
        raise KeyError(
            "Environment variable FLIGHT_HISTORIAN_API_KEY is missing."
        )
    headers = {"api-key": api_key_fh}
    url = "https://www.flighthistorian.com/api/recent_flights"
    response = requests.get(url, headers=headers, timeout=10)
    print(f"🌐 GET {response.url}")
    response.raise_for_status()
    fh_recent_flights = response.json()
    if len(fh_recent_flights) == 0:
        print("Flight Historian provided zero recent flights.")
        quit()
    print(f"{len(fh_recent_flights)} recent flight(s) found.")
    for flight in fh_recent_flights:
        result = aw.get_flights(flight['fa_flight_id'])
        print(result)
