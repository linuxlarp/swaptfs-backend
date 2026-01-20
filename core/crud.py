from database import get_query, get_one_query, run_query
from typing import List, Dict, Any, Optional, Union, Type, TypeVar
from dataclasses import is_dataclass, asdict
from core.models import Flight, User,  BannedUser, Booking
from config import LOGS as logger

T = TypeVar("T")

def _normalize_model(data: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Converts dataclass or dict to proper DB-ready dict, fixing column names."""
    if is_dataclass(data):
        data = asdict(data)
    elif not isinstance(data, dict):
        raise TypeError("Expected dataclass or dict")

    if "from_" in data:
        data["from"] = data.pop("from_")
    return data

def _row_to_model(model_cls: Type[T], row: Optional[Dict[str, Any]]) -> Optional[T]:
    if row is None:
        return None

    if "from_" in model_cls.__dataclass_fields__ and "from" in row:
        row = dict(row)
        row["from_"] = row.pop("from")

    field_names = set(model_cls.__dataclass_fields__.keys())
    filtered_data = {k: v for k, v in row.items() if k in field_names}
    return model_cls(**filtered_data)


class Flights:
    """CRUD operations for flights table."""

    @staticmethod
    def get_all():
        row = get_query("SELECT * FROM flights")
        return [_row_to_model(Flight, r) for r in row]

    @staticmethod
    def get_by_id(flight_id: str):
        row = get_one_query("SELECT * FROM flights WHERE id = ?", (flight_id,))
        return _row_to_model(Flight, row)

    @staticmethod
    def add(data: Union[Dict[str, Any], Any]) -> Dict[str, int]:
        data = _normalize_model(data)
        return run_query(
            """INSERT INTO flights 
               (id, "from", "to", aircraft, departure, seats, booked, acftReg, deptGate, arrGate, codeshareIds, host, discordEventId, robloxPrivateServerLink)
               VALUES (:id, :from, :to, :aircraft, :departure, :seats, :booked, :acftReg, :deptGate, :arrGate, :codeshareIds, :host, :discordEventId, :robloxPrivateServerLink)""",
            data,
        )
    
    @staticmethod
    def update(flight_id: str, data: Dict[str, Any]) -> Dict[str, int]:
        """Update an existing flight with new data."""
        fields = ", ".join(f'"{key}" = :{key}' for key in data.keys())
        data["id"] = flight_id
        query = f"UPDATE flights SET {fields} WHERE id = :id"
        return run_query(query, data)

    
    @staticmethod
    def change_seats(flight_id: str, seats: int, operation: str = "add"):
        """Increment or decrement total seats."""
        
        op = "+" if operation == "add" else "-"
        return run_query(
            f"UPDATE flights SET seats = seats {op} ? WHERE id = ?",
            (seats, flight_id),
        )

    @staticmethod
    def change_bookings(flight_id: str, count: int = 1, operation: str = "add"):
        """Increment or decrement booked seats."""

        op = "+" if operation == "add" else "-"
        return run_query(
            f"UPDATE flights SET booked = booked {op} ? WHERE id = ?",
            (count, flight_id),
        )

    
    @staticmethod
    def update_seats(flight_id: str, seats: int):
        return run_query("UPDATE flights SET seats =  ? WHERE id = ?", (seats, flight_id))
    
    @staticmethod
    def verify_seats(flight_id: str):
        """Ensure flight seat counts are valid. Reset if negatives or overbooked."""
        flight = get_one_query("SELECT seats, booked FROM flights WHERE id = ?", (flight_id,))
        if not flight:
            raise ValueError(f"Flight {flight_id} not found")

        seats, booked = flight["seats"], flight["booked"]

        # Fix negatives or overbooking
        if booked < 0 or seats < 0 or booked > seats:
            logger.warn(f"Seat data invalid for {flight_id}: seats={seats}, booked={booked}. Resetting values.")
            total = max(seats, booked, 0)
            run_query("UPDATE flights SET seats = ?, booked = ? WHERE id = ?", (total, 0, flight_id))
            return {"corrected": True, "seats": total, "booked": 0}

        return {"corrected": False, "seats": seats, "booked": booked}



    @staticmethod
    def delete(flight_id: str) -> int:
        return run_query("DELETE FROM flights WHERE id = ?", (flight_id,))


class Users:
    """CRUD operations for users table."""

    @staticmethod
    def get_all():
        row = get_query("SELECT * FROM users")
        return [_row_to_model(User, r) for r in row]

    @staticmethod
    def get_by_id(user_id: str):
        row = get_one_query("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_model(User, row)
    
    @staticmethod
    def get_by_api_key(api_key: str):
        row = get_one_query("SELECT * FROM users WHERE apiToken = ?", (api_key, ))
        return _row_to_model(User, row)

    @staticmethod
    def add(data: Union[Dict[str, Any], Any]):
        data = _normalize_model(data)
        return run_query(
            """INSERT OR IGNORE INTO users 
               (id, username, discriminator, avatar, points, apiToken, isAdmin, isBot, isStaff, isFlightStaff, rapidRwdStatus, flightsAttended)
               VALUES (:id, :username, :discriminator, :avatar, :points, :apiToken, :isAdmin, :isBot, :isStaff, :isFlightStaff, :rapidRwdStatus, :flightsAttended)""",
            data,
        )
    
    @staticmethod
    def update(user_id: str, data: Dict[str, Any]):
        """Update user record by ID."""
        data = _normalize_model(data)
        data["id"] = user_id
        fields = ", ".join(f'"{key}" = :{key}' for key in data.keys())
        query = f"UPDATE users SET {fields} WHERE id = :id"
        return run_query(query, data)


    @staticmethod
    def update_points(user_id: str, points: int):
        return run_query("UPDATE users SET points = ? WHERE id = ?", (points, user_id))

    @staticmethod
    def delete(user_id: str):
        return run_query("DELETE FROM users WHERE id = ?", (user_id,))


class Bookings:
    """CRUD operations for bookings table."""

    @staticmethod
    def get_all():
        row = get_query("SELECT * FROM bookings")
        return [_row_to_model(Booking, r) for r in row]
    
    @staticmethod
    def get_all_by_user(user_id: str):
        row = get_query("SELECT * FROM bookings WHERE userId = ?", (user_id, ))
        return [_row_to_model(Booking, r) for r in row]

    @staticmethod
    def get_by_confirmation(confirmation: str):
        row = get_one_query("SELECT * FROM bookings WHERE confirmationNumber = ?", (confirmation,))
        return _row_to_model(Booking, row)
    

    @staticmethod
    def add(data: Union[Dict[str, Any], Any]):
        data = _normalize_model(data)
        return run_query(
            """INSERT INTO bookings 
               (userId, username, flightId, confirmationNumber, bookedAt, boardingGroup, boardingPosition, checkedInAt)
               VALUES (:userId, :username, :flightId, :confirmationNumber, :bookedAt, :boardingGroup, :boardingPosition, :checkedInAt)""",
            data,
        )
    
    @staticmethod
    def delete(confirmation: str):
        return run_query("DELETE FROM bookings WHERE confirmationNumber = ?", (confirmation,))
    
    @staticmethod
    def delete_by_flight_id(flight: str):
        return run_query("DELETE FROM bookings WHERE flightId = ?", (flight,))
    
    @staticmethod
    def delete_by_confirmation(confirmation: str):
        return run_query("DELETE FROM bookings WHERE confirmationNumber = ?", (confirmation,))



class BannedUsers:
    """CRUD operations for banned_users table."""

    @staticmethod
    def get_all():
        row = get_query("SELECT * FROM banned_users")
        return [_row_to_model(BannedUser, r) for r in row]
    
    @staticmethod
    def get_by_id(user_id: str):
        row = get_one_query("SELECT * FROM banned_users WHERE userId = ?", (user_id,))
        return _row_to_model(BannedUser, row)

    @staticmethod
    def add(data: Union[str, Dict[str, Any], Any], reason: Optional[str] = None):
        if is_dataclass(data):
            data = asdict(data)
        elif isinstance(data, str):
            data = {"userId": data, "reason": reason}
        elif not isinstance(data, dict):
            raise TypeError("Expected userId (str), dict, or dataclass")

        return run_query(
            "INSERT OR REPLACE INTO banned_users (userId, reason) VALUES (:userId, :reason)",
            data,
        )

    @staticmethod
    def delete(user_id: str):
        return run_query("DELETE FROM banned_users WHERE userId = ?", (user_id,))
    
    @staticmethod
    def clear_all():
        return run_query("DELETE FROM banned_users")

