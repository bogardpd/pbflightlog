"""Tools for interacting with a local GeoPackage flight log."""

import argparse
import flight_log_tools.tools as flt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tools for interacting with a local flight log."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add-fa-flight-id
    parser_add_fa_flight_id = subparsers.add_parser(
        "add-fa-flight-id",
        help="Look up a flight by fa_flight_id and add it to the log"
    )
    parser_add_fa_flight_id.add_argument(
        "fa_flight_id",
        metavar="fa-flight-id",
        help="AeroAPI fa_flight_id",
        type=str,
    )

    # import-boarding-passes
    parser_import_boarding_passes = subparsers.add_parser(
        "import-boarding-passes",
        help="Import digital boarding passes from import folder",
    )

    # import-recent
    parser_import_recent = subparsers.add_parser(
        "import-recent",
        help="Import recent flights from Flight Historian",
    )

    # parse-bcbp
    parser_parse_bcbp = subparsers.add_parser(
        "parse-bcbp",
        help="Import Bar-Coded Boarding Pass text string",
    )
    parser_parse_bcbp.add_argument(
        "bcbp_text",
        metavar="bcbp-text",
        help="BCBP text string",
        type=str,
    )

    # Parse arguments
    args = parser.parse_args()
    match args.command:
        case "add-fa-flight-id":
            flt.add_fa_flight_id(args.fa_flight_id)
        case "import-boarding-passes":
            flt.import_boarding_passes()
        case "import-recent":
            flt.import_recent()
        case "parse-bcbp":
            flt.parse_bcbp(args.bcbp_text)
        case _:
            print("No command provided. See --help for commands.")
