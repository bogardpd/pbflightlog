"""Tools for interacting with boarding passes."""

class BoardingPass():
    """Represents a Bar-Coded Boarding Pass (BCBP)."""
    def __init__(self, bcbp_str):
        self.bcbp_str = bcbp_str

    def __str__(self):
        return self.bcbp_str.replace(" ", "·")
