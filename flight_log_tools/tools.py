"""Functions for CLI commands."""

import os
import requests

import geopandas as gpd

from flight_log_tools.aeroapi import AeroAPIWrapper
from flight_log_tools.boarding_pass import BoardingPass

def add_fa_flight_id(ident):
    """Gets flight info for an ident and saves flight(s) to log."""
    aw = AeroAPIWrapper()
    aw.add_flight(ident)

def import_boarding_passes():
    """Imports digital boarding passes."""
    print("Importing digital boarding passes...")

def import_recent():
    """Finds recent flights on Flight Historian API and imports them."""
    api_key_fh = os.getenv("FLIGHT_HISTORIAN_API_KEY")
    if api_key_fh is None:
        raise KeyError(
            "Environment variable FLIGHT_HISTORIAN_API_KEY is missing."
        )
    flight_log = os.getenv("FLIGHT_LOG_GEOPACKAGE_PATH")
    if flight_log is None:
        raise KeyError(
            "Environment variable FLIGHT_LOG_GEOPACKAGE_PATH is missing."
        )

    # Get recent flights.
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

    # Get list of Flight Historian IDs already in log.
    current_flights = gpd.read_file(flight_log, layer='flights')
    current_fh_ids = current_flights['fh_id'].unique().tolist()

    # Look up recent flights with AeroAPI.
    aw = AeroAPIWrapper()
    for flight in fh_recent_flights:
        print(f"Importing {flight}")
        if flight['fh_id'] in current_fh_ids:
            print("This flight is already in the log.")
            continue
        fields = {'fh_id': flight['fh_id']}
        aw.add_flight(flight['fa_flight_id'], fields=fields)

def parse_bcbp(bcbp_str):
    """Parses a Bar-Coded Boarding Pass string."""
    bp = BoardingPass(bcbp_str)
    print(bp)
