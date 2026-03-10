"""Functions for CLI commands."""

# Standard imports
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project imports
import pbflightlog.aeroapi as aero
import pbflightlog.flight_log as fl
from pbflightlog.boarding_pass import BoardingPass, PKPass

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Tools for interacting with a local flight log."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    add_parser = subparsers.add_parser(
        "add",
        help="Add items to flight log",
    )
    add_subparsers = add_parser.add_subparsers(dest="entity", required=True)

    # add flight
    add_flight_parser = add_subparsers.add_parser(
        "flight",
    )
    add_flight_source_group = add_flight_parser.add_mutually_exclusive_group(
        required=True, # Set to false if we create GUI add flight option
    )
    add_flight_source_group.add_argument("--bcbp",
        help="Add flight(s) from a BCBP-coded text string",
        metavar="BCBP_TEXT",
        type=str,
    )
    add_flight_source_group.add_argument("--fa-flight-id",
        help="Add a flight from an FlightAware fa_flight_id",
        type=str,
    )
    add_flight_source_group.add_argument("--number",
        dest="flight_number",
        help=(
            "Add a flight from an airline code (ICAO preferred) and "
            "flight number"
        ),
        nargs=2,
        metavar=("AIRLINE_CODE", "FLIGHT_NUMBER"),
        type=str,
    )
    add_flight_source_group.add_argument("--pkpasses",
        action="store_true",
        help="Add flights from .pkpass files in the import folder"
    )

    # refresh
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Refresh flight log data",
    )
    refresh_parser_subparsers = refresh_parser.add_subparsers(
        dest="entity",
        required=True,
    )

    # refresh routes
    refresh_parser_subparsers.add_parser(
        "routes",
        help="Manually refresh routes layer",
    )

    # Parse arguments
    args = parser.parse_args()
    if args.command == "add":
        if args.entity == "flight":
            if args.bcbp is not None:
                add_flight_bcbp(args.bcbp)
            elif args.fa_flight_id is not None:
                add_flight_fa_flight_id(args.fa_flight_id)
            elif args.flight_number is not None:
                add_flight_number(*args.flight_number)
            elif args.pkpasses:
                add_flight_pkpasses()
    elif args.command == "refresh":
        if args.entity == "routes":
            refresh_routes()

def add_flight_bcbp(bcbp_str) -> None:
    """Parses a Bar-Coded Boarding Pass string."""
    bp = BoardingPass(bcbp_str)
    _add_bp_flights(bp)
    refresh_routes()

def add_flight_fa_flight_id(fa_flight_id: str) -> None:
    """Gets info for a fa_flight_id and saves flight to log."""
    fa_flights = aero.get_flights_ident(fa_flight_id, "fa_flight_id")
    _add_fa_flight_results(fa_flights)
    refresh_routes()

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
    refresh_routes()

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
    if len(pkpasses) == 0:
        print("⚠️ No .pkpass files found.")

    # Sort passes by relevant_date.
    pkpasses = dict(
        sorted(
            pkpasses.items(),
            key=lambda item: item[1].relevant_date or datetime.max.replace(
                tzinfo=timezone.utc
            )
        )
    )

    # Process passes.
    for pkpass_file, pkpass in pkpasses.items():
        print(pkpass.relevant_date)
        bp = pkpass.boarding_pass
        _add_bp_flights(bp)
        archive_file_path = archive_folder / pkpass.archive_filename
        pkpass_file.move(archive_file_path)
        print(f"Archived PKPass to \"{archive_file_path}\"")
    refresh_routes()

def refresh_routes() -> None:
    """Refreshes the routes table."""
    fl.refresh_routes()

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
        if trip is not None:
            flight.trip_fid = trip.fid
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
