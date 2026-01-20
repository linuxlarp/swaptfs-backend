from dataclasses import dataclass
from typing import Optional


@dataclass
class Flight:
    id: str
    from_: str          # "from" renamed (Python keyword)
    to: str
    aircraft: str
    departure: str
    seats: int
    booked: int = 0
    acftReg: str = ""
    deptGate: str = ""
    arrGate: str = ""

    codeshareIds: Optional[str] = None
    host: Optional[str] = None
    discordEventId: Optional[str] = None
    robloxPrivateServerLink: Optional[str] = None

@dataclass
class Session:
    user_id: str
    username: str
    discriminator: Optional[str] = None
    avatar: Optional[str] = None
    host: Optional[str] = None

    @classmethod
    def from_request(cls, request):
        user_data = request.session.get("user", {})
        return cls(
            user_id=user_data["id"],
            username=user_data["username"],
            discriminator=user_data.get("discriminator"),
            avatar=user_data.get("avatar"),
            host=user_data.get("user_ip", request.client.host)
        )


@dataclass
class Booking:
    userId: str
    username: str
    flightId: str
    confirmationNumber: str
    bookedAt: str
    boardingGroup: Optional[str] = None
    boardingPosition: Optional[str] = None
    checkedInAt: Optional[str] = None


@dataclass
class User:
    id: str
    username: str
    discriminator: str

    robloxId: Optional[str] = None
    avatar: Optional[str] = None
    points: int = 0
    apiToken: Optional[str] = None
    isAdmin: bool = False
    isBot: bool = False
    isStaff: bool = False
    isFlightStaff: bool = False
    rapidRwdStatus: str = "Base"
    hasEarlybird: bool = False
    flightsAttended: int = 0


@dataclass
class Airport:
    city: str
    state: str
    airport: str
    iata: str


@dataclass
class BannedUser:
    userId: str
    reason: Optional[str] = None
