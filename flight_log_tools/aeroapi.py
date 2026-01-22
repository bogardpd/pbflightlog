"""Tools for interacting with FlightAware's AeroAPI."""

import os
import time
from datetime import datetime, timedelta, timezone

import requests

class AeroAPIWrapper:
    """Class for interacting with AeroAPI version 4."""
    def __init__(self):
        self.api_key = os.getenv("AEROAPI_API_KEY")
        if self.api_key is None:
            raise KeyError("Environment variable AEROAPI_API_KEY is missing.")
        self.server = "https://aeroapi.flightaware.com/aeroapi"
        self.timeout = 10

        # Set a wait time in seconds to avoid rate limiting on the
        # Personal tier. If your account has a higher rate limit,
        # you can set this to 0.
        self.wait_time = 8
        self.wait_until = None

    def get_flights(self, ident):
        """Gets flight info for an ident."""
        headers = {'x-apikey': self.api_key}
        url = f"{self.server}/flights/{ident}"
        self.wait()
        response = requests.get(url, headers=headers, timeout=self.timeout)
        print(f"🌐 GET {response.url}")
        response.raise_for_status()
        return response.json()

    def wait(self):
        """Delays requests to avoid AeroAPI rate limits."""
        if self.wait_time == 0:
            return
        now = datetime.now(timezone.utc)

        # On the first request, initialize and proceed.
        if self.wait_until is None:
            self.wait_until = now + timedelta(seconds=self.wait_time)
            return

        # If we're early, wait.
        if now < self.wait_until:
            sleep_seconds = (self.wait_until - now).total_seconds()
            print(f"⏳ Waiting until {self.wait_until}")
            time.sleep(sleep_seconds)

        # Schedule the next wait.
        self.wait_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.wait_time
        )
