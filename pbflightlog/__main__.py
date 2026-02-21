"""Tools for interacting with a local GeoPackage flight log."""

# Standard imports
import argparse

# Project imports
import pbflightlog.tools as flt

if __name__ == "__main__":
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
        help="Add a flight from a BCBP-coded text string",
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
    add_flight_source_group.add_argument("--recent",
        action="store_true",
        help="Add recent flights from Flight Historian"
    )

    # update-routes
    parser_update_routes = subparsers.add_parser(
        "update-routes",
        help="Manually refresh routes layer",
    )

    # Parse arguments
    args = parser.parse_args()
    if args.command == "add":
        if args.entity == "flight":
            if args.bcbp is not None:
                flt.add_flight_bcbp(args.bcbp)
            elif args.fa_flight_id is not None:
                flt.add_flight_fa_flight_id(args.fa_flight_id)
            elif args.flight_number is not None:
                flt.add_flight_number(*args.flight_number)
            elif args.pkpasses:
                flt.add_flight_pkpasses()
            elif args.recent:
                flt.add_flight_fh_recent()
    elif args.command == "update-routes":
        flt.update_routes()
