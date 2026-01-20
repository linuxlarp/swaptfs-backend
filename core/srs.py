import os
import base64
import httpx
from datetime import datetime

from config import LOGS as logger
from core.flights.airport_data import find_airport
from core.models import Booking, Flight, User, Airport

class SRSPayloadBuilder():
    def __init__(self):
        pass

    @staticmethod
    def build_create(booking: Booking, flight: Flight) -> dict:
        from_airport: Airport  = find_airport(flight.from_)
        to_airport: Airport = find_airport(flight.to)

        return {
            "passengerId": str(booking.userId),
            "flight": flight.id,
            "departing": (
                f"{flight.from_}, {from_airport.state} ({from_airport.iata})"
                if from_airport else flight.from_
            ),
            "arriving": (
                f"{flight.to}, {to_airport.state} ({to_airport.iata})"
                if to_airport else flight.to
            ),
            "aircraft": flight.aircraft or "Unknown",
            "confirmation": booking.confirmationNumber,
            "checkInTime": (
                flight.departure.isoformat()
                if isinstance(flight.departure, datetime)
                else str(flight.departure)
            ),
        }
    
    @staticmethod
    def build_cancel(booking: Booking, flight: Flight, manual: bool) -> dict:
        from_airport: Airport = find_airport(flight.from_)
        to_airport: Airport = find_airport(flight.to)

        return {
            "passengerId": str(booking.userId),
            "flight": flight.id,
            "departing": (
                f"{flight.from_}, {from_airport.state} ({from_airport.iata})"
                if from_airport else flight.from_
            ),
            "arriving": (
                f"{flight.to}, {to_airport.state} ({to_airport.iata})"
                if to_airport else flight.to
            ),
            "confirmation": booking.confirmationNumber,
            "manual": manual,
        }
    
    @staticmethod
    def build_checkin(booking: Booking, flight: Flight, user: User, image_bytes: bytes) -> dict:
        """Construct SRS check-in payload with base64 encoded boarding pass image."""
        boarding_pass_image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "passengerId": str(booking["userId"]),
            "flight": flight["id"],
            "bytes": boarding_pass_image_b64,
        }

        return payload


class SRSClient():
    """Client for communicating with the SRS system. Sending, booking, cancellation and check-in data to SRS."""

    def __init__(self, base_url: str | None = None, password: str | None = None):
        self.base_url = base_url or os.getenv("SRS_URL")
        self.password = password or os.getenv("SRS_PASSWORD")
        pass

    async def _post(self, endpoint: str, payload: dict, label: str) -> bool:
        if not self.base_url or not self.password:
            logger.error(f"SRS {label} skipped: SRS_URL (base_url) or SRS_PASSWORD (password) missing.")
            return
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{self.base_url}/{endpoint}",
                    headers={
                        "Authorization": f"Bearer {self.password}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
            
            if r.status_code == 200:
                logger.booking(
                    f"SRS {label} success for {payload.get("confirmation")}",
                    f"statusCode: {r.status_code}"
                )
                return True
            
            logger.error(
                f"SRS {label} failed for {payload.get('confirmation')}", r.text,
            )
        except Exception as e:
            logger.error(f"SRS {label} exception:", e)
            return False

    async def send_booking(self, booking: Booking, flight: Flight) -> bool:
        payload = SRSPayloadBuilder.build_create(booking, flight)
        return await self._post("booking/create", payload, "booking")

    async def send_cancel(self, booking: Booking, flight: Flight, manual: bool = True) -> bool:
        payload = SRSPayloadBuilder.build_cancel(booking, flight, manual)
        return await self._post("booking/cancel", payload, "booking")
    
    async def send_checkin(self, booking: Booking, flight: Flight, image_bytes: bytes, user: User) -> bool:
        payload = SRSPayloadBuilder.build_checkin(booking, flight, user, image_bytes)
        return await self._post("checkin", payload, "check-in")

