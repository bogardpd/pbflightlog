"""Functions for CLI commands."""

import os
import sys
from zoneinfo import ZoneInfo

import requests
import geopandas as gpd
from dateutil import parser
from tabulate import tabulate

from flight_log_tools.aeroapi import AeroAPIWrapper
from flight_log_tools.boarding_pass import BoardingPass
import flight_log_tools.flight_log as fl

def add_fa_flight_id(ident):
    """Gets flight info for an ident and saves flight(s) to log."""
    aw = AeroAPIWrapper()
    aw.add_flight(ident)

def add_flight_number(airline, flight_number):
    """Gets info for a flight number and logs the flight."""
    # If airline is IATA, try to look up ICAO.
    if len(airline) == 2:
        record = fl.find_airline_by_code(airline)
        if record is not None and record['icao_code'] is not None:
            airline = record['icao_code']
    ident = f"{airline}{flight_number}"
    print(f"Looking up {ident}:")
    aw = AeroAPIWrapper()
    flights = aw.get_flights_ident(ident, "designator")
    if len(flights) == 0:
        print("No matching flights found.")
        sys.exit(0)
    flights = sorted(flights, key=lambda f: f['scheduled_out'], reverse=True)
    table = [
        [
            i + 1,
            f['ident'],
            _dt_str_tz(f['scheduled_out'], f['origin']['timezone']),
            f['origin']['code_iata'] or f['origin']['code'],
            f['destination']['code_iata'] or f['destination']['code'],
            f['progress_percent'],
        ]
        for i, f in enumerate(flights)
    ]
    print(tabulate(table,
        headers=["Row", "Ident", "Departure", "Orig", "Dest", "Progress %"],

    ))
    selected_flight = None
    while selected_flight is None:
        row = input("Select a row number (or Q to quit): ")
        if row.upper() == "Q":
            sys.exit(0)
        try:
            row_index = int(row) - 1
            if row_index < 0:
                print("Invalid row selection.")
                continue
            selected_flight = flights[row_index]
        except IndexError, ValueError:
            print("Invalid row selection.")

    flight = fl.Flight.from_aeroapi(selected_flight)
    print(flight.gdf().iloc[0])


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
    if not bp.valid:
        print("The boarding pass data is not valid.")
        quit()
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

def _dt_str_tz(dt_str, tz):
    """Converts a datetime string into local time."""
    dt = parser.isoparse(dt_str)
    dt_tz = dt.astimezone(ZoneInfo(tz))
    return dt_tz.strftime("%a %d %b %Y %H:%M %Z")
