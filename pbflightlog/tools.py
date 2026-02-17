"""Functions for CLI commands."""

# Standard imports
import os
import sys

# Third-party imports
import requests
import geopandas as gpd

# Project imports
from pbflightlog.aeroapi import AeroAPIWrapper
import pbflightlog.aeroapi as aero
from pbflightlog.boarding_pass import BoardingPass
import pbflightlog.flight_log as fl

def add_fa_flight_id(ident):
    """Gets flight info for an ident and saves flight(s) to log."""
    aw = AeroAPIWrapper()
    aw.add_flight(ident)

def add_flight_number(airline_code, flight_number):
    """Gets info for a flight number and logs the flight."""
    airline = fl.Airline.find_by_code(airline_code)
    # If airline is IATA, try to look up ICAO.
    if len(airline_code) == 2:
        if airline is not None and airline.icao_code is not None:
            airline_code = airline.icao_code
    ident = f"{airline_code}{flight_number}"
    print(f"Looking up {ident}:")
    fa_flights = aero.get_flights_ident(ident, "designator")
    if len(fa_flights) == 0:
        print("No matching flights found.")
        sys.exit(1)
    flights = [fl.Flight.from_aeroapi(f) for f in fa_flights]
    flight = fl.Flight.select_flight(flights)
    if flight.progress is None or flight.progress < 100:
        print(
            f"⚠️ Flight is not complete ({flight.progress}% complete). "
            "Flight was not added to log."
        )
        sys.exit(1)
    flight.fetch_aeroapi_track_geometry()
    flight.airline_fid = airline.fid
    flight.save()
    update_routes()


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
        print("ℹ️ Flight Historian provided zero recent flights.")
        sys.exit(0)
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
    if not bp.valid:
        print("⚠️ The boarding pass data is not valid.")
        sys.exit(1)
    flight_dates = bp.flight_dates
    for leg_index, leg in enumerate(bp.raw['legs']):
        airline_iata = leg['operating_carrier'].strip()
        flight_number = leg['flight_number'].strip()
        orig_iata = leg['from_airport'].strip()
        dest_iata = leg['to_airport'].strip()
        print(
            f"Leg {leg_index + 1}: {flight_dates[leg_index]} "
            f"{airline_iata} {flight_number} "
            f"{orig_iata} → {dest_iata}"
        )

def update_routes():
    """Refreshes the routes table."""
    fl.update_routes()
