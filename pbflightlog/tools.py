"""Functions for CLI commands."""

# Standard imports
import os
import sys
from pathlib import Path

# Third-party imports
import requests
import pandas as pd

# Project imports
import pbflightlog.aeroapi as aero
import pbflightlog.flight_log as fl
from pbflightlog.boarding_pass import BoardingPass, PKPass

def add_flight_bcbp(bcbp_str) -> None:
    """Parses a Bar-Coded Boarding Pass string."""
    bp = BoardingPass(bcbp_str)
    _add_bp_flights(bp)
    update_routes()

def add_flight_fa_flight_id(fa_flight_id: str) -> None:
    """Gets info for a fa_flight_id and saves flight to log."""
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
    fa_flights = aero.get_flights_ident(ident, "designator")
    _add_fa_flight_results(fa_flights, {'airline_fid': airline.fid})
    update_routes()

def add_flight_pkpasses() -> None:
    """Imports digital boarding passes."""

    import_folder_env = os.getenv("FLIGHT_LOG_IMPORT_PATH")
    if import_folder_env is None:
        raise KeyError(
            "Environment variable FLIGHT_LOG_IMPORT_PATH is missing."
        )
    import_folder = Path(import_folder_env)
    if not import_folder.is_dir():
        raise KeyError(
            "Environment variable FLIGHT_LOG_IMPORT_PATH is not a directory."
        )
    archive_folder_env = os.getenv("FLIGHT_LOG_PKPASS_ARCHIVE_PATH")
    if archive_folder_env is None:
        raise KeyError(
            "Environment variable FLIGHT_LOG_PKPASS_ARCHIVE_PATH is missing."
        )
    archive_folder = Path(archive_folder_env)
    if not archive_folder.is_dir():
        raise KeyError(
            "Environment variable FLIGHT_LOG_PKPASS_ARCHIVE_PATH is not a directory."
        )

    print(f"Importing digital boarding passes from \"{import_folder}\"")
    pkpasses = {
        f: PKPass(f) for f in import_folder.glob("*.pkpass")
        if f.is_file()
    }
    for pkpass_file, pkpass in pkpasses.items():
        bp = pkpass.boarding_pass
        _add_bp_flights(bp)
        archive_file_path = archive_folder / pkpass.archive_filename
        pkpass_file.move(archive_file_path)
        print(f"Archived PKPass to \"{archive_file_path}\"")
    update_routes()

def update_routes() -> None:
    """Refreshes the routes table."""
    fl.update_routes()

def _add_bp_flights(bp: BoardingPass) -> None:
    """Builds Flights from a BoardingPass, and saves them."""
    if not bp.valid or len(bp.legs) == 0:
        print("⚠️ The boarding pass data is not valid.")
        sys.exit(1)

    # Build list of boarding pass flights.
    bp_flights: list(fl.Flight) = []
    for leg in bp.legs:
        print(f"Processing leg \"{leg}\"")
        airline = fl.Airline.find_by_code(leg.airline_iata)
        if airline is not None and airline.icao_code is not None:
            airline_code = airline.icao_code
        else:
            airline_code = leg.airline_iata
        ident = f"{airline_code}{leg.flight_number}"
        aero_results = aero.get_flights_ident(ident, "designator")
        flight = _flight_from_aeroapi_results(aero_results)
        flight.airline_fid = airline.fid
        flight.boarding_pass_data = leg.bcbp_str
        trip = fl.Trip.select_by_date(leg.flight_date)
        print(trip, trip.fid)
        if trip is not None:
            flight.trip_fid = trip.fid
        print(flight.trip_fid)
        bp_flights.append(flight)

    # Save flights.
    for flight in bp_flights:
        flight.save()

def _add_fa_flight_results(aero_results: dict, fields: dict = None) -> None:
    """Processes the results of an AeroAPI flights request."""
    flight = _flight_from_aeroapi_results(aero_results)

    # Set provided fields
    if fields is not None:
        for key, value in fields.items():
            setattr(flight, key, value)

    flight.save()

def _flight_from_aeroapi_results(aero_results) -> fl.Flight:
    """Has user select flight from AeroAPI results and gets geometry."""
    if len(aero_results) == 0:
        print("No matching flights found.")
        sys.exit(1)
    aero_flight_info = aero.select_flight_info(aero_results)
    flight = fl.Flight.from_aeroapi(aero_flight_info)
    flight.exit_if_not_complete()
    flight.fetch_aeroapi_track_geometry()
    return flight
