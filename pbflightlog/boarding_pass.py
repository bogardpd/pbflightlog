"""Tools for interacting with boarding passes."""

# Standard imports
import calendar
import json
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from zipfile import ZipFile

# Third-party imports
from dateutil.parser import isoparse

class BoardingPass():
    """
    Represents a Bar-Coded Boarding Pass (BCBP).

    This class only encodes data that the flight log uses. Many IATA
    BCBP fields are intentionally excluded.
    """
    def __init__(self, bcbp_str: str, pass_dt:datetime=None):
        self.bcbp_str: str = bcbp_str
        self.valid: bool = True
        self.pass_dt: datetime | None = pass_dt
        self._data_len: int = len(self.bcbp_str)
        self._leg_count: int = 0
        self._blocks: dict | None = None
        self._calculate_blocks()
        self.legs: list(Leg) = self._legs()

    def __str__(self):
        return self.bcbp_str.replace(" ", "·")

    def _calculate_blocks(self) -> None:
        """
        Calculates block locations in the BCBP text.

        Sets self._blocks to a dict with values containing slices of the
        start and stop character indexes in the BCBP text for each
        block. Blocks that are not present store a value of None instead
        of a slice.
        """
        if len(self.bcbp_str) < 60:
            self.valid = False
            return None
        # Get number of legs.
        try:
            self._leg_count = int(self.bcbp_str[1:2])
            if self._leg_count < 1 or self._leg_count > 4:
                self.valid = False
                return None
        except ValueError:
            self.valid = False
            return None

        # Initialize blocks.
        self._blocks = {
            'unique': {
                'mandatory': slice(0, 23), # Always here
                'conditional': None,
                'security': None,
            },
            'repeated': []
        }

        # Loop through legs.
        for leg_index in range(self._leg_count):
            self._blocks['repeated'].append({
                'mandatory': None,
                'conditional': None,
                'airline': None,
            })

            # Mandatory Repeated block
            mand_rept_start = self._prev_leg_stop(leg_index)
            mand_rept_stop = mand_rept_start + 37 # Always 37 characters
            if mand_rept_stop > self._data_len:
                self.valid = False
                return
            self._blocks['repeated'][leg_index]['mandatory'] = slice(
                mand_rept_start, mand_rept_stop
            )
            cond_airline_size = _parse_hex(
                self.bcbp_str[mand_rept_stop - 2:mand_rept_stop])
            if cond_airline_size is None:
                self.valid = False
                return
            if cond_airline_size == 0:
                # No conditional or airline items.
                continue
            leg_stop = mand_rept_stop + cond_airline_size
            if leg_stop > self._data_len:
                self.valid = False
                return

            # Conditional Unique block (first leg only)
            if leg_index == 0:
                if cond_airline_size < 4:
                    # Conditional Unique not big enough to contain size
                    # field
                    self._blocks['unique']['conditional'] = slice(
                        mand_rept_stop, mand_rept_start + cond_airline_size
                    )
                    continue
                cond_uniq_size = _parse_hex(
                    self.bcbp_str[mand_rept_stop + 2:mand_rept_stop + 4]
                )
                if cond_uniq_size is None:
                    self.valid = False
                    return
                cond_rept_start = mand_rept_stop + 4 + cond_uniq_size
                if cond_rept_start > self._data_len:
                    self.valid = False
                    return
                self._blocks['unique']['conditional'] = slice(
                    mand_rept_stop, cond_rept_start
                )
            else:
                cond_rept_start = mand_rept_stop

            # Conditional Repeated block
            if cond_rept_start == leg_stop:
                # No more data.
                continue
            if cond_rept_start + 2 > leg_stop:
                # Conditional not big enough to contain Conditional
                # Repeated size field.
                self._blocks['repeated'][leg_index]['conditional'] = slice(
                    cond_rept_start, leg_stop
                )
            cond_rept_size = _parse_hex(
                self.bcbp_str[cond_rept_start:cond_rept_start + 2]
            )
            if cond_rept_size is None:
                self.valid = False
                return
            cond_rept_stop = cond_rept_start + 2 + cond_rept_size
            if cond_rept_stop > self._data_len:
                self.valid = False
                return
            self._blocks['repeated'][leg_index]['conditional'] = slice(
                cond_rept_start, cond_rept_stop
            )

            # Airline Repeated block
            if cond_rept_stop == leg_stop:
                # No more data.
                continue
            self._blocks['repeated'][leg_index]['airline'] = slice(
                cond_rept_stop, leg_stop
            )

        # Security block
        security_start = self._prev_leg_stop(self._leg_count)
        if security_start < self._data_len:
            self._blocks['unique']['security'] = slice(
                security_start, self._data_len
            )

    def _legs(self) -> list(Leg):
        """Returns Leg objects for each leg."""
        return [
            Leg(self.bcbp_str, self._blocks['repeated'][i], self.pass_dt)
            for i in range(self._leg_count)
        ]

    def _prev_leg_stop(self, leg_index):
        """Gets the index of the stop of the previous leg."""
        if leg_index == 0:
            # Use end of mandatory unique block.
            return self._blocks['unique']['mandatory'].stop
        prev_leg = self._blocks['repeated'][leg_index - 1]
        if prev_leg['airline'] is not None:
            return prev_leg['airline'].stop
        if prev_leg['conditional'] is not None:
            return prev_leg['conditional'].stop
        if leg_index == 1:
            # Second leg might start at end of Unique Conditional.
            if self._blocks['unique']['conditional'] is not None:
                return self._blocks['unique']['conditional'].stop
        return prev_leg['mandatory'].stop


class Leg():
    """Represents one flight leg of a boarding pass."""

    def __init__(self,
        bcbp_text: str, leg_blocks: dict, pass_dt: datetime | None = None
    ):
        self._bcbp_text = bcbp_text
        self._blocks = leg_blocks
        self._pass_dt = pass_dt
        self.flight_date: date | None = self._parse_flight_date()
        self.airline_iata: str | None = self._parse_airline_iata()
        self.flight_number: str | None = self._parse_flight_number()
        self.origin_iata: str | None = self._parse_airport_orig_iata()
        self.destination_iata: str | None = self._parse_airport_dest_iata()

    def __repr__(self):
        return (
            f"Leg({self.flight_date} {self.airline_iata} {self.flight_number} "
            f"{self.origin_iata} → {self.destination_iata})"
        )

    def __str__(self):
        return (
            f"{self.flight_date} {self.airline_iata} {self.flight_number} "
            f"{self.origin_iata} → {self.destination_iata}"
        )

    def _parse_airline_iata(self) -> str | None:
        """Parses airline IATA code."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(13, 16)
        )
        if raw is None:
            return None
        return raw.strip()

    def _parse_airport_dest_iata(self) -> str | None:
        """Parses destination airport IATA code."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(10, 13)
        )
        if raw is None:
            return None
        return raw.strip()

    def _parse_airport_orig_iata(self) -> str | None:
        """Parses origin airport IATA code."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(7, 10)
        )
        if raw is None:
            return None
        return raw.strip()

    def _parse_flight_date(self) -> date | None:
        """Parses flight date."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(21, 24)
        )
        try:
            day_of_year: int = int(raw)
            if day_of_year > 366 or day_of_year < 1:
                return None
        except TypeError, ValueError:
            return None
        if self._pass_dt is None:
            # Assume flight is up to 3 days in the future, or else the
            # most recent date matching this ordinal in the past.
            latest_dt = datetime.now() + timedelta(days=3)
            latest_dt_year = latest_dt.timetuple().tm_year
            latest_date = latest_dt.date()
            # Loop through years in reverse trying to find a good date.
            # Searches 8 years since leap years can be up to 8 years apart.
            for year in range(latest_dt_year, latest_dt_year-8, -1):
                test_date = _ordinal_date(year, day_of_year)
                if test_date is None or test_date.year != year:
                    # The ordinal was larger than the number of days
                    # this year, probably due to no leap year.
                    continue
                if test_date > latest_date:
                    # The date this year is more than three days in the
                    # future.
                    continue
                # This is the most recent date that works.
                return test_date
            return None

        # Use pass_dt to figure out the year.
        # Because the timezone of the departure airport is not known,
        # the departure date in the local time of the departure airport
        # could potentially be the year before or after the UTC
        # pass_dt's year. Look at all three years and see which date is
        # closest to pass_dt.
        utc_year = self._pass_dt.year
        years = [utc_year - 1, utc_year, utc_year + 1]
        if day_of_year == 366:
            # Eliminate non-leap-years.
            years = [y for y in years if calendar.isleap(y)]
            if len(years) == 0:
                # No adjacent year is a leap year.
                return None
        # Create dates to check.
        dates = [_ordinal_date(y, day_of_year) for y in years]
        # Create a dictionary of date indexes and their differences from
        # the pass date.
        date_diffs = {
            i: abs(d - self._pass_dt.date())
            for i, d in enumerate(dates)
        }
        # Get date with smallest difference.
        return dates[min(date_diffs, key=date_diffs.get)]

    def _parse_flight_number(self) -> str | None:
        """Parses flight number."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(16, 21)
        )
        if raw is None:
            return None
        return raw.strip().lstrip("0") or "0"


class PKPass():
    """Represents an Apple Wallet PKPass boarding pass."""
    PASS_FILE = "pass.json"

    def __init__(self, path: Path):
        self.pass_json = self._load_pass_json(path)
        self.relevant_date = self._parse_relevant_date()
        self.message = self.pass_json.get('barcode', {}).get('message')
        self.boarding_pass = self._boarding_pass()

    @property
    def archive_filename(self) -> str:
        """Creates an archive filename."""
        fields = []
        if self.relevant_date is None:
            if self.boarding_pass is not None:
                date_str = self.boarding_pass.legs[0].flight_date or "NODATE"
            date_str = "NODATE"
        else:
            date_str = self.relevant_date.strftime("%Y%m%dT%H%MZ")
        fields.append(date_str)
        if self.boarding_pass is not None:
            leg = self.boarding_pass.legs[0]
            fields.append(leg.airline_iata)
            fields.append(leg.flight_number)
            fields.append("-".join([leg.origin_iata, leg.destination_iata]))
            if len(self.boarding_pass.legs) > 1:
                fields.append(f"{len(self.boarding_pass.legs)}LEGS")
        fields = [f for f in fields if f is not None]
        return "_".join(fields) + ".pkpass"

    def _boarding_pass(self) -> BoardingPass:
        if self.message is None:
            return None
        return BoardingPass(self.message, self.relevant_date)

    def _load_pass_json(self, path) -> dict:
        """Gets boarding pass JSON."""
        with ZipFile(path, 'r') as zf:
            if PKPass.PASS_FILE not in zf.namelist():
                print(f"{PKPass.PASS_FILE} not found in {path}.")
                return {}
            with zf.open(PKPass.PASS_FILE) as pf:
                return json.loads(pf.read().decode('utf-8'))

    def _parse_relevant_date(self) -> datetime | None:
        """Gets the PKPass date."""
        try:
            pass_date = isoparse(self.pass_json.get('relevantDate'))
            return pass_date.astimezone(ZoneInfo("UTC"))
        except TypeError, ValueError:
            return None

def _get_raw(bcbp_str, block_slice, field_slice):
    """Gets raw values for a field."""
    if block_slice is None:
        return None
    chars = slice(
        block_slice.start + field_slice.start,
        block_slice.start + field_slice.stop,
    )
    if chars.stop > block_slice.stop:
        return None
    return bcbp_str[chars]

def _ordinal_date(year: int, day_of_year: int):
    """Creates a date from a year and day of year."""
    if day_of_year < 1 or day_of_year > 366:
        return None
    if day_of_year == 366 and not calendar.isleap(year):
        return None
    return date(year, 1, 1) + timedelta(days=day_of_year-1)

def _parse_hex(hex_str) -> int | None:
    """Parses a hexadecimal string."""
    try:
        return int(hex_str, 16)
    except ValueError:
        return None
