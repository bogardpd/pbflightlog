"""Tools for interacting with boarding passes."""

# Standard imports
from datetime import datetime, date, timedelta

class BoardingPass():
    """
    Represents a Bar-Coded Boarding Pass (BCBP).

    This class only encodes data that the flight log uses. Many IATA
    BCBP fields are intentionally excluded.
    """
    def __init__(self, bcbp_str):
        self.bcbp_str = bcbp_str
        self.valid = True
        self._data_len = len(self.bcbp_str)
        self._leg_count = None
        self._blocks = None
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
            Leg(self.bcbp_str, self._blocks['repeated'][i])
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

    def __init__(self, bcbp_text: str, leg_blocks: dict):
        self._bcbp_text = bcbp_text
        self._blocks = leg_blocks
        self.flight_date: date | None = self._parse_flight_date()
        self.airline_iata: str | None = self._parse_airline_iata()
        self.flight_number: str | None = self._parse_flight_number()
        self.origin_iata: str | None = self._parse_airport_orig_iata()
        self.destination_iata: str | None = self._parse_airport_dest_iata()

    def __repr__(self):
        return (
            f"{self.flight_date} {self.airline_iata} {self.flight_number} "
            f"{self.origin_iata}-{self.destination_iata}"
        )

    def __str__(self):
        return (
            f"{self.flight_date} {self.airline_iata} {self.flight_number} "
            f"{self.origin_iata}-{self.destination_iata}"
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
            date_ordinal: int = int(raw)
            if date_ordinal > 366 or date_ordinal < 1:
                return None
        except TypeError, ValueError:
            return None
        # Assume flight is up to 3 days in the future, or else the
        # most recent date matching this ordinal in the past.
        latest_dt = datetime.now() + timedelta(days=3)
        latest_dt_year = latest_dt.timetuple().tm_year
        latest_date = latest_dt.date()
        # Loop through years in reverse trying to find a good date.
        # Searches 8 years since leap years can be up to 8 years apart.
        for year in range(latest_dt_year, latest_dt_year-8, -1):
            test_date = date(year, 1, 1) + timedelta(days=date_ordinal-1)
            if test_date.year != year:
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

    def _parse_flight_number(self) -> str | None:
        """Parses flight number."""
        raw = _get_raw(
            self._bcbp_text, self._blocks['mandatory'], slice(16, 21)
        )
        if raw is None:
            return None
        return raw.strip().lstrip("0") or "0"

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

def _parse_hex(hex_str) -> int | None:
    """Parses a hexadecimal string."""
    try:
        return int(hex_str, 16)
    except ValueError:
        return None
