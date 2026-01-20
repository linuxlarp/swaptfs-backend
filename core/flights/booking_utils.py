import re
import secrets
import string
from core import crud
from config import LOGS as logger
from database import get_one_query

def generate_confirmation_number(length: int = 6) -> str:
    """Generate a random alphanumeric confirmation number."""
    characters = string.ascii_uppercase + string.digits
    
    while True:
        code = ''.join(secrets.choice(characters) for _ in range(length))
        existing = get_one_query("SELECT confirmationNumber FROM bookings WHERE confirmationNumber = ?", (code, ))

        if not existing:
            return generate_confirmation_number(length)
    


def assign_boarding_position(flight_id: str) -> str:
    """
    Assigns the next available boarding position for a given flight
    using data from the bookings table via CRUD.
    Returns a string like 'A1', 'B32', etc.
    """
    try:
        # Pull all bookings for this flight that already have boarding positions
        bookings = crud.get_query(
            "SELECT boardingGroup, boardingPosition FROM bookings WHERE flightId = ?",
            (flight_id,)
        ) ## We dont converts these to dataclasses for simplicity.

        positions_taken = []
        for b in bookings:
            group = b.get("boardingGroup")
            match = re.search(r"\d+", str(b.get("boardingPosition")))
            pos = int(match.group()) if match else None
            if group and pos is not None:
                positions_taken.append({"group": group, "pos": pos})

        # Group and seat order same as Southwest logic (they're removing this soon though)
        groups = ["A", "B", "C"]
        for group in groups:
            for pos in range(1, 61):
                if not any(p["group"] == group and p["pos"] == pos for p in positions_taken):
                    return f"{group}{pos}"

        return "C60"

    except Exception as e:
        logger.error(f"Error assigning boarding position: {e}")
        return "C60"
