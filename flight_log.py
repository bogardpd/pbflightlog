"""Tools for interacting with a local GeoPackage flight log."""

import argparse

def import_boarding_passes():
    """Imports digital boarding passes."""
    print("Importing digital boarding passes...")

def import_recent():
    """Finds recent flights on Flight Historian API and imports them."""
    print("Importing Flight Historian recent flights...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tools for interacting with a local flight log."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # import-boarding-passes
    parser_import_boarding_passes = subparsers.add_parser(
        "import-boarding-passes",
        help="Import digital boarding passes from import folder"
    )

    # import-recent
    parser_import_recent = subparsers.add_parser(
        "import-recent",
        help="Import recent flights from Flight Historian"
    )

    # Parse arguments
    args = parser.parse_args()
    match args.command:
        case "import-boarding-passes":
            import_boarding_passes()
        case "import-recent":
            import_recent()
        case _:
            print("No command provided. See --help for commands.")
