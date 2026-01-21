"""Functions for CLI commands."""

import os
import requests
from dotenv import load_dotenv

def import_boarding_passes():
    """Imports digital boarding passes."""
    print("Importing digital boarding passes...")

def import_recent():
    """Finds recent flights on Flight Historian API and imports them."""
    print("Importing Flight Historian recent flights...")
    load_dotenv()
    api_key_fh = os.getenv("API_KEY_FLIGHT_HISTORIAN")
    if api_key_fh is None:
        raise KeyError(
            "Environment variable API_KEY_FLIGHT_HISTORIAN is missing."
        )
    headers = {"api-key": api_key_fh}
    url = "https://www.flighthistorian.com/api/recent_flights"
    print(f"🌐 Requesting {url}")
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    json_data = response.json()
    if len(json_data) == 0:
        print("Flight Historian provided zero recent flights.")
        quit()
    for flight in json_data:
        print(flight)
