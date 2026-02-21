"""Functions for CLI commands."""

# Standard imports
import os
import sys

# Third-party imports
import requests
import pandas as pd

# Project imports
import pbflightlog.aeroapi as aero
import pbflightlog.flight_log as fl
from pbflightlog.boarding_pass import BoardingPass

def add_flight_bcbp(bcbp_str) -> None:
    """Parses a Bar-Coded Boarding Pass string."""
    bp = BoardingPass(bcbp_str)
    if not bp.valid:
        print("⚠️ The boarding pass data is not valid.")
        sys.exit(1)
    flight_dates = bp.flight_dates
    legs = [
        {
            'airline_iata': leg.get('operating_carrier').strip(),
            'flight_number': leg.get('flight_number').strip(),
            'orig_iata': leg.get('from_airport').strip(),
            'dest_iata': leg.get('to_airport').strip(),
            'flight_date': flight_dates[i],
        } for i, leg in enumerate(bp.raw['legs'])
    ]
    if len(legs) == 1:
        selected_leg = legs[0]
    else:
        # Select a leg.
        selected_leg = None
        for i, leg in enumerate(legs):
            print(
                f"Leg {i + 1}: {leg.get('flight_date')} "
                f"{leg.get('airline_iata')} {leg.get('flight_number')} "
                f"{leg.get('orig_iata')} → {leg.get('dest_iata')}"
            )
        while selected_leg is None:
            choice = input("Select a leg number (or Q to quit): ")
            if choice.upper() == "Q":
                sys.exit(0)
            try:
                row_index = int(choice) - 1
                if row_index < 0:
                    print("Invalid leg number.")
                    continue
                selected_leg = legs[row_index]
            except IndexError, ValueError:
                print("Invalid leg number.")

    airline = fl.Airline.find_by_code(selected_leg.get('airline_iata'))
    if airline is not None and airline.icao_code is not None:
        airline_code = airline.icao_code
    else:
        airline_code = selected_leg.get('airline_iata')
    flight_number = selected_leg.get('flight_number').lstrip("0") or "0"
    ident = f"{airline_code}{flight_number}"
    print(f"Looking up {ident}...")
    fa_flights = aero.get_flights_ident(ident, "designator")
    _add_fa_flight_results(fa_flights, {
        'airline_fid': airline.fid,
        'boarding_pass_data': bcbp_str,
    })
    update_routes()

def add_flight_fa_flight_id(fa_flight_id: str) -> None:
    """Gets info for a fa_flight_id and saves flight to log."""
    print(f"Looking up {fa_flight_id}...")
    fa_flights = aero.get_flights_ident(fa_flight_id, "fa_flight_id")
    _add_fa_flight_results(fa_flights)
    update_routes()

def add_flight_fh_recent() -> None:
    """Finds recent flights on Flight Historian API and imports them."""
    api_key_fh = os.getenv("FLIGHT_HISTORIAN_API_KEY")
    if api_key_fh is None:
        raise KeyError(
            "Environment variable FLIGHT_HISTORIAN_API_KEY is missing."
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
    current_fh_ids = [
        f for f in fl.Flight.pluck('fh_id') if not pd.isna(f)
    ]

    # Look up recent flights on AeroAPI.
    update_flag = False # Track if we need to update routes
    for flight in fh_recent_flights:
        print(f"Importing {flight}")
        if flight['fh_id'] in current_fh_ids:
            print("This flight is already in the log.")
            continue
        fa_flights = aero.get_flights_ident(
            flight.get('fa_flight_id'), "fa_flight_id"
        )
        _add_fa_flight_results(fa_flights, {'fh_id': flight.get('fh_id')})
        update_flag = True
    if update_flag:
        update_routes()

def add_flight_number(airline_code: str, flight_number: str) -> None:
    """Gets info for a flight number and logs the flight."""
    airline = fl.Airline.find_by_code(airline_code)
    # If airline is IATA, try to look up ICAO.
    if len(airline_code) == 2:
        if airline is not None and airline.icao_code is not None:
            airline_code = airline.icao_code
    flight_number = flight_number.lstrip("0") or "0"
    ident = f"{airline_code}{flight_number}"
    print(f"Looking up {ident}...")
    fa_flights = aero.get_flights_ident(ident, "designator")
    _add_fa_flight_results(fa_flights, {'airline_fid': airline.fid})
    update_routes()

def add_flight_pkpasses() -> None:
    """Imports digital boarding passes."""
    print("Importing digital boarding passes...")

def update_routes() -> None:
    """Refreshes the routes table."""
    fl.update_routes()

def _add_fa_flight_results(fa_flights: dict, fields: dict = None) -> None:
    """Processes the results of an AeroAPI flights request."""
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

    # Set provided fields
    if fields is not None:
        for key, value in fields.items():
            setattr(flight, key, value)

    flight.save()
