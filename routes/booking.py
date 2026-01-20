from datetime import timedelta
import secrets
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from dataclasses import asdict

from config import LOGS as logger
from core.crud import Bookings, Flights, Users
from core.models import Session
from core.srs import SRSClient
from core.time import parse_datetime, parse_iso, utc_now
from middleware.auth import is_authenticated
from middleware.multi_permission import is_staff_or_flight_staff


router = APIRouter(prefix="/bookings", tags=["Bookings"])
srs_client = SRSClient()

def _generate_confirmation() -> str:
    """
    Generate a random 6-character alphanumeric confirmation code.

    Returns:
        str: A randomly generated confirmation code consisting of uppercase
            letters and digits.
    """

    return "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(6))


@router.post("/", dependencies=[Depends(is_authenticated)])
async def create_booking(request: Request):
    """
    Create a new booking for the authenticated user.

    Validates flight data, checks availability and duplicate bookings, then creates
    a booking, updates seats and user points, and triggers booking notifications.

    Args:
        request (Request): The HTTP request containing JSON booking details.

    Returns:
        JSONResponse: A response with a success message and booking data.

    Raises:
        HTTPException:
            - 400: Missing flight ID, departed flight, or no seats available.
            - 404: Flight not found.
            - 500: Database or booking creation error.

    Logs:
        - Booking attempts, rejections, and successful booking creation.
    """

    session = Session.from_request(request)
    body = await request.json()

    flight_id = body.get("flightId")
    dep = body.get("departure")

    if not flight_id:
        raise HTTPException(status_code=400, detail="Flight ID is required")
    

    logger.booking(f"POST /bookings - flightId: {flight_id}, userId: {session.user_id}")

    dep = parse_datetime(dep)
    if dep and dep + timedelta(minutes=45) < utc_now():
        logger.info(f"Booking rejected: Flight has already deprated, + 45 minute pading for user {session.user_id} flight {flight_id}")
        raise HTTPException(status_code=400, detail="Flight already departed")

    flight = Flights.get_by_id(flight_id)

    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    if flight.booked >= flight.seats:
        raise HTTPException(status_code=400, detail="No seats available")

    bookings = Bookings.get_all()

    existing = next(
        (b for b in bookings if b.userId == session.user_id and b.flightId == flight_id),
        None
    )

    logger.info("Checking existing: Checking if a duplicate booking already exists")

    if existing:
        logger.info(f"Booking rejected: duplicate booking for user {session.user_id} flight {flight_id}")
        raise HTTPException(status_code=400, detail="User already has a booking for this flight")

    confirmation = _generate_confirmation()
    booking_data = {
        "userId": session.user_id,
        "username": session.username,
        "flightId": flight_id,
        "confirmationNumber": confirmation,
        "bookedAt": utc_now().isoformat(),
        "boardingGroup": None,
        "boardingPosition": None,
        "checkedInAt": None,
    }

    try:
        if flight.seats <= 0: ## while the website denies booking, we'll confirm here too and add response
            raise HTTPException(status_code=400, detail="No seats available")

        Bookings.add(booking_data)

        booking = Bookings.get_by_confirmation(confirmation)
        Flights.change_bookings(flight.id, 1, operation="add")
        Flights.verify_seats(flight.id)

    
        Flights.delete(flight_id) if False else None
        logger.booking(f"Created booking {confirmation} for user {session.user_id}")

        try:
            await srs_client.send_booking(booking, flight)
        except Exception as e:
            logger.error(f"Failed to send SRS booking notification for booking {confirmation}", e)
            pass

        logger.success(f"Sucessfully booked flight {flight_id} for user {session.user_id} with confirmation {confirmation}")
        return JSONResponse({"message": "Flight booked successfully", "booking": booking_data})
    except Exception as e:
        logger.error(f"Error creating booking: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@router.get("/search/{flightId}", dependencies=[Depends(is_staff_or_flight_staff)])
async def get_bookings_by_flight(request: Request, flightId: str):
    session = Session.from_request(request)
    logger.info(f"GET /bookings/search/{flightId} - userId: {session.user_id}")

    all_bookings = Bookings.get_all()

    bookings = [b for b in all_bookings if b.flightId == flightId]

    if not bookings:
        return JSONResponse({"message": "No bookings found for this flight", "bookings": []})

    flight = Flights.get_by_id(flightId)
    status = "Unknown"

    if flight and flight.departure:
        dep = parse_iso(flight.departure)
        status = "Flight has departed" if dep < utc_now() else "Upcoming"

    flight_data = asdict(flight) if flight else {}
    if "from_" in flight_data:
        flight_data["from"] = flight_data.pop("from_")

    result = []
    for b in bookings:
        data = asdict(b)

        if "from_" in data:
            data["from"] = data.pop("from_")

        result.append({
            **data,
            "flight": flight_data or {},
            "status": status
        })

    return JSONResponse(result)

@router.get("/me", dependencies=[Depends(is_authenticated)])
async def get_user_bookings(request: Request):
    """
    Fetch all bookings for a specific flight.

    Retrieves all bookings, attaches flight data and computed status, and returns
    a list for staff or flight staff users.

    Args:
        request (Request): The HTTP request with session info.
        flightId (str): The ID of the flight to fetch bookings for.

    Returns:
        JSONResponse: A list of bookings with flight info and status, or a message
            if none exist.

    Logs:
        - Requests for flight bookings and any empty results.
    """

    session = Session.from_request(request)
    logger.info(f"GET /bookings - userId: {session.user_id}")

    bookings = Bookings.get_all_by_user(session.user_id)

    if not bookings:
        return JSONResponse({"message": "No bookings found", "bookings": []})
        
    result = []
    for b in bookings:
        flight = Flights.get_by_id(b.flightId)
        status = "Unknown"
        if flight and flight.departure:
            dep = parse_iso(flight.departure)
            status = "Flight has departed" if dep < utc_now() else "Upcoming"

    data = asdict(b)
    if "from_" in data:
        data["from"] = data.pop("from_")

    flight_data = asdict(flight) if flight else {}
    if "from_" in flight_data:
        flight_data["from"] = flight_data.pop("from_")

    result.append({
        **data,
        "flight": flight_data,
        "status": status
    })

    return JSONResponse(result)

@router.get("/{confirmationNumber}", dependencies=[Depends(is_authenticated)])
async def get_booking_by_confirmation(request: Request, confirmationNumber: str):
    """
    Retrieve booking details by confirmation number for the current user.

    Looks up a booking by confirmation code, ensures ownership, fetches flight
    details, and returns booking, flight, and status.

    Args:
        request (Request): The HTTP request containing session data.
        confirmationNumber (str): The booking confirmation code.

    Returns:
        JSONResponse: Booking and flight details plus computed status.

    Raises:
        HTTPException:
            - 404: Booking or flight not found.

    Logs:
        - Access to booking by confirmation number and related errors.
    """

    session = Session.from_request(request)
    logger.booking(f"GET /bookings/{confirmationNumber} - userId: {session.user_id}")

    if confirmationNumber is None:
        raise HTTPException(status_code=400, detail="Confirmation number is required")

    all_bookings = Bookings.get_all()
    booking = next((b for b in all_bookings if b.confirmationNumber == confirmationNumber and b.userId == session.user_id), None)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    flight = Flights.get_by_id(booking.flightId)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found for this booking")
    
    flight_data = asdict(flight) if flight else {}
    if "from_" in flight_data:
        flight_data["from"] = flight_data.pop("from_")

    status = "Upcoming"
    dep = parse_iso(flight.departure)
    if dep and dep < utc_now():
        status = "Flight has departed"
    else:
        status = "Upcoming"

    booking_data = asdict(booking)

    if "from_" in booking_data:
        booking_data["from"] = booking_data.pop("from_")


    return JSONResponse({
        "booking": booking_data,
        "flight": flight_data,
        "status": status
    })

@router.get("/attended", dependencies=[Depends(is_authenticated)])
async def get_attended_count(request: Request):
    """
    Return the number of attended flights for the current user.

    Retrieves the user's record and returns their attended flights count.

    Args:
        request (Request): The HTTP request containing session data.

    Returns:
        JSONResponse: The count of attended flights for the user.

    Raises:
        HTTPException:
            - 401: User not found.

    Logs:
        - Requests for attended flight counts.
    """

    session = Session.from_request(request)
    u = Users.get_by_id(session.user_id)

    if not u:
        raise HTTPException(status_code=401, detail="User not found")

    return JSONResponse({"attendedCount": u.get("flightsAttended", 0)})

@router.post("/cancel", dependencies=[Depends(is_authenticated)])
async def cancel_booking(request: Request):
    """
    Cancel a booking for the authenticated user.

    Validates ownership and departure time, deletes the booking, updates flight
    bookings and user points, and sends a cancellation notification.

    Args:
        request (Request): The HTTP request containing JSON with a confirmationCode.

    Returns:
        JSONResponse: A message indicating successful cancellation or issues.

    Raises:
        HTTPException:
            - 400: Missing booking ID or flight already departed.
            - 403: Not authorized or booking not found.
            - 500: Database or cancellation error.

    Logs:
        - Cancellation attempts, successes, and errors.
    """

    
    session = Session.from_request(request)
    body = await request.json()
    confirmationCode = body.get("confirmationNumber")

    if not confirmationCode:
        raise HTTPException(status_code=400, detail="Booking ID required")

    logger.booking(f"POST /bookings/cancel - bookingId: {confirmationCode}, userId: {session.user_id}")

    booking = Bookings.get_by_confirmation(confirmationCode)
    if not booking or booking.userId != session.user_id:
        raise HTTPException(status_code=403, detail="Not authorized or booking not found")

    flight = Flights.get_by_id(booking.flightId)
    if not flight:
        Bookings.delete(confirmationCode)
        return JSONResponse({"message": "Booking canceled (flight missing)"})

    dep = parse_datetime(flight.departure)
    if dep and dep + timedelta(minutes=45) < utc_now(): ## Add 45 minutes of padding
        raise HTTPException(status_code=400, detail="Flight already departed")
    

    ## attempt to delete any cached boarding pass (if there was any to begin with)
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CACHE_DIR = os.path.join(ROOT_DIR, "images", "cache", "printed")

    try:
        cache_path = os.path.join(f"{CACHE_DIR}/{flight.id}", f"{booking.confirmationNumber}.png")

        if os.path.exists(cache_path):
            os.remove(cache_path)
            logger.info(f"Deleted cached boarding pass for confirmation code {confirmationCode}")
    except Exception as e:
        logger.warn("Unable to delete cached boarding pass (may not exist)", e)
        pass

    try:
        Bookings.delete(confirmationCode)

        Flights.change_bookings(flight.id, 1, operation="sub")
        Flights.verify_seats(flight.id)
        
        await srs_client.send_cancel(booking, flight, True)

        logger.booking(f"Canceled booking #{confirmationCode} successfully for user {session.user_id}")
        return JSONResponse(status_code=200, content={"message": "Booking canceled successfully"})
    except Exception as e:
        logger.error(f"Error canceling booking: {e}")
        raise HTTPException(status_code=500, detail="Database error")
