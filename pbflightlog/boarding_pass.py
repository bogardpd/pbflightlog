"""Tools for interacting with boarding passes."""

from datetime import datetime, date, timedelta

_BCBP_FIELDS = {
    "mandatory_unique": [
        # 1. Format Code
        {'key': 'format_code', 'length': 1},
        # 5. Number of Legs Encoded
        {'key': 'leg_count', 'length': 1},
        # 11. Passenger Name
        {'key': 'passenger_name', 'length': 20},
        # 253. Electronic Ticket Indicator
        {'key': 'electronic_ticket', 'length': 1},
    ],
    "mandatory_repeated": [
         # 7. Operating carrier PNR Code
        {'key': 'pnr', 'length': 7},
        # 26. From City Airport Code
        {'key': 'from_airport', 'length': 3},
        # 38. To City Airport Code
        {'key': 'to_airport', 'length': 3},
        # 42. Operating Carrier Designator
        {'key': 'operating_carrier', 'length': 3},
        # 43. Flight Number
        {'key': 'flight_number', 'length': 5},
        # 46. Date of Flight (Julian Date)
        {'key': 'flight_date', 'length': 3},
        # 71. Compartment Code
        {'key': 'compartment_code', 'length': 1},
        # 104. Seat Number
        {'key': 'seat_number', 'length': 4},
        # 107. Check-in Sequence Number
        {'key': 'check_in_sequence', 'length': 5},
        # 113. Passenger Status
        {'key': 'passenger_status', 'length': 1},
        # 6. Field size of variable size field (Conditional + Airline
        # item 4) in hexadecimal
        {'key': 'conditional_airline_length', 'length': 2},
    ],
    "conditional_unique": [
        # 8. Beginning of Version Number
        {'key': 'version_number_begin', 'length': 1},
        # 9. Version Number
        {'key': 'version_number', 'length': 1},
        # 10. Field Size of Following Structured Message - Unique
        {'key': 'following_unique_length', 'length': 2},
        # 15. Passenger Description
        {'key': 'passenger_description', 'length': 1},
        # 12. Source of Check-in
        {'key': 'check_in_source', 'length': 1},
        # 14. Source of Boarding Pass Issuance
        {'key': 'boarding_pass_source', 'length': 1},
        # 22. Date of Issue of Boarding Pass (Julian Date)
        {'key': 'boarding_pass_date', 'length': 4},
        # 16. Document type
        {'key': 'document_type', 'length': 1},
        # 21. Airline Designator of Boarding Pass Issuer
        {'key': 'boarding_pass_issuer_airline', 'length': 3},
        # 23. Baggage Tag License Plate Number
        {'key': 'baggage_tag_number', 'length': 13},
        # 31. 1st Non-Consecutive Baggage Tag License Plate
        # Number
        {'key': 'baggage_tag_number_nonconsecutive_1', 'length': 13},
        # 31. 2nd Non-Consecutive Baggage Tag License Plate
        # Number
        {'key': 'baggage_tag_number_nonconsecutive_2', 'length': 13},
    ],
    "conditional_repeated": [
        # 17. Field Size of Following Structured Message - Repeated
        {'key': 'following_repeated_length', 'length': 2},
        # 142. Airline Numeric Code
        {'key': 'airline_numeric_code', 'length': 3},
        # 143. Document Form/Serial Number
        {'key': 'document_form_serial_number', 'length': 10},
        # 18. Selectee Indicator
        {'key': 'selectee_indicator', 'length': 1},
        # 108. International Documentation Verification
        {'key': 'international_doc_verification', 'length': 1},
        # 19. Marketing Carrier Designator
        {'key': 'marketing_carrier', 'length': 3},
        # 20. Frequent Flier Airline Designator
        {'key': 'frequent_flier_airline', 'length': 3},
        # 236. Frequent Flier Number
        {'key': 'frequent_flier_number', 'length': 16},
        # 89. ID/AD Indicator
        {'key': 'id_ad', 'length': 1},
        # 118. Free Baggage Allowance
        {'key': 'free_baggage_allowance', 'length': 3},
        # 254. Fast Track
        {'key': 'fast_track', 'length': 1},
    ],
    "airline_repeated": [
        # 4. For Individual Airline Use (variable length)
        {'key': 'individual_airline_use', 'length': None},
    ],
    "security": [
        # 25. Beginning of Security Data
        {'key': 'security_data_begin', 'length': 1},
        # 28. Type of Security Data
        {'key': 'security_data_type', 'length': 1},
        # 29. Length of Security Data
        {'key': 'security_data_length', 'length': 2},
        # 30. Security Data (variable length)
        {'key': 'security_data', 'length': None}
    ]
}

class BoardingPass():
    """Represents a Bar-Coded Boarding Pass (BCBP)."""
    def __init__(self, bcbp_str):
        self.bcbp_str = bcbp_str
        self.data_len = len(self.bcbp_str)
        self.raw = {}
        self.valid = True
        self.version_number = None
        self.__parse()

    def __str__(self):
        return self.bcbp_str.replace(" ", "·")

    @property
    def flight_dates(self) -> list[date]:
        """Gets a list of flight dates for all legs."""
        leg_dates = []
        for leg in self.raw['legs']:
            try:
                date_ordinal = int(leg['flight_date'])
                if date_ordinal > 366 or date_ordinal < 1:
                    leg_dates.append(None)
                    continue
            except ValueError:
                leg_dates.append(None)
                continue
            # Assume flight is up to 3 days in the future, or else the
            # most recent date matching this ordinal in the past.
            latest_dt = datetime.now() + timedelta(days=3)
            latest_dt_year = latest_dt.timetuple().tm_year
            latest_date = latest_dt.date()
            # Loop through years in reverse trying to find a good date.
            # Searches 8 years since leap years can be up to 8 years
            # apart.
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
                leg_dates.append(test_date)
                break
            else: # Loop did not break.
                # No valid date was found.
                leg_dates.append(None)

        return leg_dates

    def __parse(self):
        """Parses a boarding pass and returns a dict."""
        # Keep track of start of current block throughout parsing.
        cursor = 0

        # MANDATORY UNIQUE
        mand_u_len = self.__parse_mand_u()
        try:
            self.leg_count = int(self.raw['leg_count'])
        except ValueError:
            self.valid = False
            return
        # Set offset to end of mand_u block.
        cursor = mand_u_len

        legs = []
        self.raw['legs'] = []
        for leg_index in range(self.leg_count):
            self.raw['legs'].append({})
            leg_data = {}
            # MANDATORY REPEATED
            mand_r_len = self.__parse_mand_r(cursor, leg_index)

            try:
                cond_air_len = int(
                    self.raw['legs'][leg_index]['conditional_airline_length'],
                    16,
                )
            except ValueError:
                self.valid = False
                return
            # Set cursor to end of this leg's mand_r block.
            cursor += mand_r_len
            leg_end = cursor + cond_air_len

            if cond_air_len == 0:
                # No conditional or airline items
                continue

            if leg_index == 0:
                # CONDITIONAL UNIQUE
                cond_u_len = self.__parse_cond_u(cursor)
                if cond_u_len is None:
                    return
                try:
                    self.version_number = int(self.raw['version_number'])
                except ValueError:
                    self.valid = False
                cursor += cond_u_len
                if cond_air_len == cond_u_len:
                    # No repeated conditional or airline items
                    continue

            # CONDITIONAL REPEAT
            cond_r_len = self.__parse_cond_r(cursor, leg_index)
            if cond_r_len is None:
                return
            # Set cursor to end of this leg's cond_r block:
            cursor += cond_r_len

            if cursor > leg_end:
                # Boarding pass data had invalid lengths.
                return
            if cursor < leg_end:
                # Airline data exists.
                self.__parse_airline(cursor, leg_end, leg_index)

            # Set cursor to leg end and save leg data.
            cursor = leg_end
            legs.append(leg_data)

        if cursor > self.data_len:
            # Boarding pass data had invalid lengths.
            self.valid = False
            return None

        # SECURITY
        if self.version_number is not None and self.version_number >= 3:
            if cursor < self.data_len:
                security_len = self.__parse_security(cursor)
                if security_len is None:
                    return None
                # Set cursor to end of security.
                cursor += security_len

        # LEFTOVER UNKNOWN DATA
        if cursor < self.data_len:
            self.raw['unknown'] = self.bcbp_str[cursor:self.data_len]

        return

    def __parse_mand_u(self):
        """
        Parses the mandatory unique block.

        Returns the length of the block.
        """
        raw = self.bcbp_str
        fields = _BCBP_FIELDS['mandatory_unique']
        lengths = [v['length'] for v in fields]
        for i, f in enumerate(fields):
            start = sum(lengths[0:i])
            stop = start + f['length']
            self.raw[f['key']] = raw[start:stop]
        return sum(lengths)

    def __parse_mand_r(self, offset, leg_index):
        """
        Parses a mandatory repeat block starting at the offset.

        Returns the length of the block.
        """
        raw = self.bcbp_str
        fields = _BCBP_FIELDS['mandatory_repeated']
        lengths = [v['length'] for v in fields]
        for i, f in enumerate(fields):
            start = offset + sum(lengths[0:i])
            stop = start + f['length']
            self.raw['legs'][leg_index][f['key']] = raw[start:stop]
        return sum(lengths)

    def __parse_cond_u(self, offset):
        """Parses a conditional unique block starting at offset."""
        return self.__parse_cond(
            offset,
            None, # Store unique outside of a leg
            _BCBP_FIELDS['conditional_unique'],
            'following_unique_length',
        )

    def __parse_cond_r(self, offset, leg_index):
        """Parses a conditional repeat block starting at offset."""
        return self.__parse_cond(
            offset,
            leg_index,
            _BCBP_FIELDS['conditional_repeated'],
            'following_repeated_length',
        )

    def __parse_cond(self, offset, leg_index, fields, following_length_key):
        """
        Parses a conditional block.

        Conditional blocks have a field (identified by
        following_length_key) indicating the length of the block after
        it. Fields are populated in order until the length is reached.

        Returns the length of the block.
        """
        raw = self.bcbp_str
        cond = {}
        lengths = [v['length'] for v in fields]
        fol_offset = None # Start of "following" block
        fol_len = None # Length of "following" block
        for i, f in enumerate(fields):
            start = offset + sum(lengths[0:i])
            stop = start + f['length']
            if fol_len is not None:
                remaining_size = fol_offset + fol_len - start
                if remaining_size <= 0:
                    # No size remains.
                    break
                if remaining_size < f['length']:
                    # Field is longer than remaining size; truncate.
                    stop = start + remaining_size
            value_str = raw[start:stop]
            cond[f['key']] = value_str
            if leg_index is None:
                self.raw[f['key']] = value_str
            else:
                self.raw['legs'][leg_index][f['key']] = value_str
            if f['key'] == following_length_key:
                # Parse the following field size.
                try:
                    fol_len = int(value_str, 16)
                    fol_offset = stop
                except ValueError:
                    self.valid = False
                    return None
        if fol_offset is None:
            self.valid = False
            return None
        return fol_offset + fol_len - offset # Length

    def __parse_airline(self, offset_start, offset_end, leg_index):
        """Parses airline data."""
        raw = self.bcbp_str
        key = _BCBP_FIELDS['airline_repeated'][0]['key']
        self.raw['legs'][leg_index][key] = raw[offset_start:offset_end]
        return

    def __parse_security(self, offset):
        """Parses security data."""
        raw = self.bcbp_str
        fields = _BCBP_FIELDS['security']
        if raw[offset:offset+1] == "^":
            # Properly formatted security data.
            lengths = [v['length'] for v in fields if v['length'] is not None]
            for i, f in enumerate(fields[0:3]):
                start = offset + sum(lengths[0:i])
                stop = start + f['length']
                self.raw[f['key']] = raw[start:stop]
            # Get security data length from field 29.
            try:
                sec_data_len = int(self.raw['security_data_length'], 16)
            except ValueError:
                self.valid = False
                return None
            sec_offset = offset + sum(lengths)
            if sec_offset + sec_data_len > self.data_len:
                sec_data_len = self.data_len - sec_offset
            self.raw[fields[-1]['key']] = raw[
                sec_offset:sec_offset+sec_data_len
            ]
            length = (sec_offset - offset) + sec_data_len
        else:
            # Improperly formatted security data. Treat the rest of the
            # boarding pass as security data.
            self.raw[fields[-1]['key']] = raw[offset:self.data_len]
            length = self.data_len - offset
        return length
