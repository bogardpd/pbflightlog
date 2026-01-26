"""Scripts for interacting with the flight log."""

import os

import colorama
import geopandas as gpd

colorama.init()

flight_log = os.getenv("FLIGHT_LOG_GEOPACKAGE_PATH")
if flight_log is None:
    raise KeyError(
        "Environment variable FLIGHT_LOG_GEOPACKAGE_PATH is missing."
    )

def append_flights(record_gdf):
    """Appends a GeoDataFrame of records to flights."""
    layer = "flights"

    # Ensure columns match existing structure.
    existing = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        rows=0,
    )
    existing_cols = list(existing.columns)
    incoming_cols = list(record_gdf.columns)

    # Check that geometry column name matches.
    geom_col = record_gdf.geometry.name
    if geom_col not in existing_cols:
        raise ValueError(
            f"Geometry column '{geom_col}' not found in existing "
            "layer schema"
        )

    # Check for columns in new data not in current schema.
    extra_cols = set(incoming_cols) - set(existing_cols)
    if extra_cols:
        raise ValueError(
            "Incoming data has columns not present in layer "
            f"schema: {extra_cols}"
        )

    # Add missing columns from existing schema as null values.
    for col in existing_cols:
        if col not in record_gdf.columns:
            record_gdf[col] = None
            print(
                f"No value was provided for column '{col}'; setting "
                "its value to null."
            )

    # Reorder columns to match existing schema.
    gdf = record_gdf[existing_cols]

    # Append data to geopackage layer.
    gdf.to_file(
        flight_log,
        driver="GPKG",
        engine="pyogrio",
        layer=layer,
        mode="a",
    )
    print(
        f"Appended {len(record_gdf)} flights(s) to '{layer}' in {flight_log}."
    )

def find_aircraft_type_fid(code):
    """Finds an aircraft_type fid by ICAO or IATA code."""
    layer = "aircraft_types"
    ac_types = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = ac_types[ac_types[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one aircraft type. Setting "
                + "value to null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any aircraft type. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None

def find_airline_fid(code):
    """Finds an airline fid by ICAO or IATA code."""
    layer = "airlines"
    airlines = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )
    # Filter out defunct airlines. This is helpful in situations where
    # current airlines use the same codes as an old airline (for
    # example, the current PSA airlines and the defunct Comair both use
    # the IATA code 'OH'.)
    airlines = airlines[~airlines['is_defunct']]

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = airlines[airlines[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one airline. Setting value to "
                + "null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any airline. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None

def find_airport_fid(code):
    """Finds an airport fid by ICAO or IATA code."""
    layer = "airports"
    airports = gpd.read_file(
        flight_log,
        layer=layer,
        engine="pyogrio",
        fid_as_index=True
    )
    # Filter out defunct airports. This is helpful in situations where
    # current airports use the same codes as an old airport (for
    # example, the modern Denver airport and the old Denver Stapleton
    # both use 'KDEN'/'DEN'.)
    airports = airports[~airports['is_defunct']]

    for code_type in ['icao_code', 'iata_code']:
        # Search for matching codes.
        matching_code = airports[airports[code_type] == code]
        if len(matching_code) == 1:
            return matching_code.index[0]
        if len(matching_code) > 1:
            print(
                colorama.Fore.YELLOW
                + f"'{code}' matches more than one airport. Setting value to "
                + "null."
                + colorama.Style.RESET_ALL,
            )
            return None

    # No matches were found.
    print(
        colorama.Fore.YELLOW
        + f"'{code}' did not match any airport. Setting value to null."
        + colorama.Style.RESET_ALL,
    )
    return None
