"""Tools for interacting with boarding passes."""

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
        self.raw = self.__parse()

    def __str__(self):
        return self.bcbp_str.replace(" ", "·")

    def __parse(self):
        """Parses a boarding pass and returns a dict."""
        # Keep track of start of current block throughout parsing.
        cursor = 0

        # MANDATORY UNIQUE
        mand_u_parse = self.__parse_mand_u()
        mand_u = mand_u_parse['data']
        try:
            self.leg_count = int(mand_u['leg_count'])
        except ValueError:
            return None
        # Set offset to end of mand_u block.
        cursor = mand_u_parse['length']

        cond_u = None
        legs = []
        for leg in range(self.leg_count):
            leg_data = {}
            # MANDATORY REPEATED
            mand_r_parse = self.__parse_mand_r(cursor)
            if mand_r_parse is None:
                return None
            mand_r = mand_r_parse['data']
            leg_data['mandatory'] = mand_r
            try:
                cond_air_len = int(
                    mand_r['conditional_airline_length'], 16
                )
            except ValueError:
                return None
            # Set cursor to end of this leg's mand_r block.
            cursor += mand_r_parse['length']
            leg_end = cursor + cond_air_len

            if cond_air_len == 0:
                # No conditional or airline items
                continue

            if leg == 0:
                # CONDITIONAL UNIQUE
                cond_u_parse = self.__parse_cond_u(cursor)
                if cond_u_parse is None:
                    return None
                cond_u = cond_u_parse['data']
                cursor += cond_u_parse['length']
                if cond_air_len == cond_u_parse['length']:
                    # No repeated conditional or airline items
                    continue

            # CONDITIONAL REPEAT
            cond_r_parse = self.__parse_cond_r(cursor)
            if cond_r_parse is None:
                return None
            cond_r = cond_r_parse['data']
            leg_data['conditional'] = cond_r
            # Set cursor to end of this leg's cond_r block:
            cursor += cond_r_parse['length']

            if cursor > leg_end:
                # Boarding pass data had invalid lengths.
                return None
            if cursor < leg_end:
                # Airline data exists.
                leg_data['airline'] = self.__parse_airline(cursor, leg_end)

            # Set cursor to leg end and save leg data.
            cursor = leg_end
            legs.append(leg_data)

        # SECURITY
        security = None
        if cursor > self.data_len:
            # Boarding pass data had invalid lengths.
            return None
        if cursor < self.data_len:
            security_parse = self.__parse_security(cursor)
            if security_parse is None:
                return None
            security = security_parse['data']
            # Set cursor to end of security.
            cursor += security_parse['length']

        # LEFTOVER UNKNOWN DATA
        unknown = None
        if cursor < self.data_len:
            unknown = {0: self.bcbp_str[cursor:self.data_len]}

        # Build fields dict.
        fields = {}
        fields['mandatory'] = mand_u
        if cond_u is not None:
            fields['conditional'] = cond_u
        fields['legs'] = legs
        if security is not None:
            fields['security'] = security
        if unknown is not None:
            fields['unknown'] = unknown
        return fields

    def __parse_mand_u(self):
        """Parses the mandatory unique block."""
        raw = self.bcbp_str
        mand_u = {}
        fields = _BCBP_FIELDS['mandatory_unique']
        lengths = [v['length'] for v in fields]
        for i, f in enumerate(fields):
            start = sum(lengths[0:i])
            stop = start + f['length']
            mand_u[f['key']] = raw[start:stop]
        return {'length': sum(lengths), 'data': mand_u}

    def __parse_mand_r(self, offset):
        """Parses a mandatory repeat block starting at the offset."""
        raw = self.bcbp_str
        mand_r = {}
        fields = _BCBP_FIELDS['mandatory_repeated']
        lengths = [v['length'] for v in fields]
        for i, f in enumerate(fields):
            start = offset + sum(lengths[0:i])
            stop = start + f['length']
            mand_r[f['key']] = raw[start:stop]
        return {'length': sum(lengths), 'data': mand_r}

    def __parse_cond_u(self, offset):
        """Parses a conditional unique block starting at offset."""
        return self.__parse_cond(
            offset,
            _BCBP_FIELDS['conditional_unique'],
            'following_unique_length',
        )

    def __parse_cond_r(self, offset):
        """Parses a conditional repeat block starting at offset."""
        return self.__parse_cond(
            offset,
            _BCBP_FIELDS['conditional_repeated'],
            'following_repeated_length',
        )

    def __parse_cond(self, offset, fields, following_length_field_id):
        """
        Parses a conditional block.

        Conditional blocks have a field (identified by
        following_length_field_id) indicating the length of the block
        after it. Fields are populated in order until the length is
        reached.
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
            if f['key'] == following_length_field_id:
                # Parse the following field size.
                try:
                    fol_len = int(value_str, 16)
                    fol_offset = stop
                except ValueError:
                    return None
        if fol_offset is None:
            return None
        return {'length': (fol_offset - offset) + fol_len, 'data': cond}

    def __parse_airline(self, offset_start, offset_end):
        """Parses airline data."""
        raw = self.bcbp_str
        field_id = _BCBP_FIELDS['airline_repeated'][0]['key']
        return {field_id: raw[offset_start:offset_end]}

    def __parse_security(self, offset):
        """Parses security data."""
        raw = self.bcbp_str
        security = {}
        fields = _BCBP_FIELDS['security']
        if raw[offset:offset+1] == "^":
            # Properly formatted security data.
            lengths = [v['length'] for v in fields if v['length'] is not None]
            for i, f in enumerate(fields[0:3]):
                start = offset + sum(lengths[0:i])
                stop = start + f['length']
                security[f['key']] = raw[start:stop]
            # Get security data length from field 29.
            try:
                sec_data_len = int(security['security_data_length'], 16)
            except ValueError:
                return None
            sec_offset = offset + sum(lengths)
            if sec_offset + sec_data_len > self.data_len:
                sec_data_len = self.data_len - sec_offset
            security[fields[-1]['key']] = raw[
                sec_offset:sec_offset+sec_data_len
            ]
            length = (sec_offset - offset) + sec_data_len
        else:
            # Improperly formatted security data. Treat the rest of the
            # boarding pass as security data.
            security[fields[-1]['key']] = raw[offset:self.data_len]
            length = self.data_len - offset
        return {'length': length, 'data': security}
