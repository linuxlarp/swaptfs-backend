from datetime import datetime, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from config import LOGS as logger
from core.flights.boarding_pass import generate_boarding_pass_image
from core.flights.booking_utils import assign_boarding_position
from core.models import Session
from core import crud
from core.srs import SRSClient
from core.time import utc_now
from database import get_one_query, run_query
from middleware.auth import is_authenticated
from middleware.permisions import is_flight_staff

router = APIRouter(prefix="/checkin", tags=["Check-in"])
srs_client = SRSClient()
DEVMODE = os.getenv("DEV_MODE", "false").lower() == "true"


@router.post("/start", dependencies=[Depends(is_authenticated)])
async def start_checkin(request: Request):
    """
    Start self-service check-in and generate a boarding pass image.

    Validates the confirmation number and user, enforces the check-in window,
    assigns a boarding position if needed, updates check-in time, generates a
    PNG boarding pass image, and optionally sends it via SRS.

    Args:
        request (Request): The HTTP request containing JSON with a confirmation
            number.

    Returns:
        Response: A PNG image of the generated boarding pass.

    Raises:
        HTTPException:
            - 400: Missing confirmation, too-early check-in, or other bad request.
            - 404: Booking or user not found.
            - 500: Flight data or image generation errors.

    Logs:
        - Check-in attempts, time window checks, boarding assignment,
        image generation, and SRS delivery results.
    """

    session = Session.from_request(request)
    body = await request.json()
    confirmation_number = body.get("confirmationNumber")

    if not confirmation_number:
        raise HTTPException(status_code=400, detail="Confirmation number is required")

    logger.info(f"POST /checkin/start - userId: {session.user_id}, confirmationNumber: {confirmation_number}")
    
    booking = get_one_query("SELECT * FROM bookings WHERE confirmationNumber = ?", (confirmation_number,))
    if not booking:
        logger.warn(f"Booking not found for confirmationNumber: {confirmation_number}")
        raise HTTPException(status_code=404, detail="Confirmation number not found")

    flight = get_one_query("SELECT * FROM flights WHERE id = ?", (booking["flightId"],))
    if not flight:
        logger.error(f"Flight data missing for flightId: {booking['flightId']}")
        raise HTTPException(status_code=500, detail="Flight data not found")

    user_data = get_one_query("SELECT hasEarlyBird FROM users WHERE id = ?", (session.user_id,))
    if not user_data:
        logger.warn(f"User not found for id: {session.user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    is_early_bird = user_data["hasEarlyBird"] == 1
    if user_data["hasEarlyBird"] is None:
        logger.warn(f"hasEarlyBird is NULL for user {session.user_id}, treating as non-Early Bird")

    checkin_window_hours = 36 if is_early_bird else 24
    logger.info(f"User {session.user_id} EarlyBird={is_early_bird}, Check-in window={checkin_window_hours}h")

    if not DEVMODE:
        now = datetime.now(timezone.utc)
        departure_time = datetime.fromisoformat(flight["departure"])
        time_difference = (departure_time - now).total_seconds() / 3600

        logger.info(f"Flight departure in {time_difference:.2f}h for flight {flight['id']}")

        if time_difference > checkin_window_hours:
            logger.warn(f"Attempted check-in too early. Flight {flight['id']}, user {session.user_id}, timeDifference={time_difference:.2f}")
            raise HTTPException(
                status_code=400,
                detail=f"Check-in is only allowed within {checkin_window_hours} hours before departure",
            )
    else:
        logger.warn("DEV_MODE is enabled (vice-versa for testing.). Please disable this to enforce check-in time restrictions.")
        logger.info("Skipping check-in time restriction.")

    if not booking["boardingPosition"]:
        logger.info(f"Assigning boarding position for booking {confirmation_number}")
        position = assign_boarding_position(flight["id"])
        group = position[0]

        run_query(
            "UPDATE bookings SET boardingGroup = ?, boardingPosition = ? WHERE confirmationNumber = ?",
            (group, position, confirmation_number),
        )
        booking["boardingGroup"] = group
        booking["boardingPosition"] = position
        logger.success(f"Boarding position assigned: {group}{position} for booking {confirmation_number}")
    else:
        logger.info(f"Booking {confirmation_number} already has boarding position {booking['boardingGroup']}{booking['boardingPosition']}")

    username = session.username if session.username is not None else "Guest"

    boarding_pass = {
        "confirmationNumber": booking["confirmationNumber"],
        "flightId": flight["id"],
        "from": flight["from"],
        "to": flight["to"],
        "aircraft": flight["aircraft"],
        "departure": flight["departure"],
        "passenger": f"{username}",
        "boardingGroup": booking["boardingGroup"],
        "boardingPosition": booking["boardingPosition"],
        "gate": flight.get("deptGate"),
        "checkedInAt": utc_now()
    }

    logger.info(f"Updating checkedInAt for booking {confirmation_number}")
    run_query("UPDATE bookings SET checkedInAt = ? WHERE confirmationNumber = ?", (boarding_pass["checkedInAt"], confirmation_number))

    # Generate and send the boarding pass image
    logger.info(f"Generating boarding pass image for {confirmation_number}")
    try:
        buffer = generate_boarding_pass_image(confirmation_number, cache_only=False)
        logger.success(f"Boarding pass generated for {confirmation_number}")

        try:
            logger.info(f"Sending boarding pass for {confirmation_number} via SRS")
            
            await srs_client.send_checkin(booking, flight, buffer, user_data)
            logger.success(f"SRS boarding pass sent for {confirmation_number}")
        except Exception as e:
            logger.error(f"Failed to send SRS boarding pass for {confirmation_number}: {e}")
            pass

        return Response(content=buffer, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to generate boarding pass image: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate boarding pass image")

@router.get("/printed/{confirmationCode}", dependencies=[Depends(is_authenticated)])
async def get_printed_boarding_pass(confirmationCode: str, request: Request):
    """
    Retrieve a previously generated boarding pass image.

    Args:
        confirmationCode (str): The confirmation number of the booking.
        request (Request): The HTTP request.

    Returns:
        Response: A PNG image of the boarding pass.

    Raises:
        HTTPException:
            - 404: If the boarding pass image is not found.

    Logs:
        - Boarding pass retrieval attempts and results.
    """

    session = Session.from_request(request)
    logger.info(f"GET /checkin/printed/{confirmationCode} - userId: {session.user_id}")

    if not confirmationCode:
        raise HTTPException(status_code=400, detail="Confirmation code is required")
    
    booking = crud.Bookings.get_by_confirmation(confirmationCode)

    if booking.userId != session.user_id:
        logger.warn(f"User {session.user_id} attempted to access boarding pass for booking {confirmationCode} owned by user {booking.userId}")
        raise HTTPException(status_code=404, detail="Boarding pass not found")
    
    if booking.checkedInAt is None:
        logger.warn(f"Booking {confirmationCode} has not been checked in yet.")
        raise HTTPException(status_code=404, detail="Not checked in yet")
    
    try:
        buffer = generate_boarding_pass_image(confirmationCode, cache_only=True) ## instead of generation, we just want to get the cached image
        logger.info(f"Buffer response: {buffer}")

        if buffer is None:
            logger.warn(f"No cached boarding pass image found for confirmation code {confirmationCode}")
            raise HTTPException(status_code=404, detail="Boarding pass not found")
        
        logger.success(f"Boarding pass retrieved for {confirmationCode}")
        return Response(content=buffer, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to retrieve boarding pass image for {confirmationCode}: {e}")
        raise HTTPException(status_code=404, detail="Boarding pass not found")

@router.post("/staff/start", dependencies=[Depends(is_authenticated), Depends(is_flight_staff)])
async def staff_checkin(request: Request):
    """
    Start staff-initiated check-in and return boarding position details.

    Allows flight staff to check in a target user, validates booking and user,
    enforces the appropriate check-in window, assigns a boarding position, updates
    check-in time, generates a boarding pass image, and sends it via SRS.

    Args:
        request (Request): The HTTP request containing JSON with 'confirmNumber': str and 'targetUser': id

    Returns:
        JSONResponse: The assigned boarding group and position for the booking.

    Raises:
        HTTPException:
            - 400: Missing confirmation or too-early check-in.
            - 404: Booking, flight, or user not found.
            - 500: Errors generating the boarding pass image.

    Logs:
        - Staff check-in attempts, time window checks, boarding assignment,
        image generation, and SRS delivery results.
    """


    session = Session.from_request(request)
    body = await request.json()
    confirmation_number = body.get("confirmationNumber")
    target_user = body.get("targetUser")

    if not confirmation_number:
        raise HTTPException(status_code=400, detail="Confirmation number is required")

    logger.info(f"POST /checkin/staff/start - staffId: {session.user_id}, userId (target): {target_user}, confirmationNumber: {confirmation_number}")
    
    booking = get_one_query("SELECT * FROM bookings WHERE confirmationNumber = ?", (confirmation_number,))
    
    if not booking:
        logger.warn(f"Booking not found for confirmationNumber: {confirmation_number}, userId (target): {target_user}")
        raise HTTPException(status_code=404, detail="Confirmation number not found")

    flight = get_one_query("SELECT * FROM flights WHERE id = ?", (booking["flightId"],))
    if not flight:
        logger.error(f"Flight data missing for flightId: {booking['flightId']}")
        raise HTTPException(status_code=500, detail="Flight data not found")

    user_data = get_one_query("SELECT hasEarlyBird FROM users WHERE id = ?", (target_user,))
    if not user_data:
        logger.warn(f"User not found for id: {target_user}")
        raise HTTPException(status_code=404, detail="User not found")

    is_early_bird = user_data["hasEarlyBird"] == 1
    if user_data["hasEarlyBird"] is None:
        logger.warn(f"hasEarlyBird is NULL for user {target_user }, treating as non-Early Bird")

    checkin_window_hours = 36 if is_early_bird else 24
    logger.info(f"User {target_user} EarlyBird={is_early_bird}, Check-in window={checkin_window_hours}h")

    if not DEVMODE:
        now = datetime.now(timezone.utc)
        departure_time = datetime.fromisoformat(flight["departure"])
        time_difference = (departure_time - now).total_seconds() / 3600

        logger.info(f"Flight departure in {time_difference:.2f}h for flight {flight['id']}")

        if time_difference > checkin_window_hours:
            logger.warn(f"Attempted check-in too early. Flight {flight['id']}, user {target_user}, timeDifference={time_difference:.2f}")
            raise HTTPException(
                status_code=400,
                detail=f"Check-in is only allowed within {checkin_window_hours} hours before departure",
            )
    else:
        logger.warn("DEV_MODE is enabled (vice-versa for testing.). Please disable this to enforce check-in time restrictions.")
        logger.info("Skipping check-in time restriction.")

    if not booking["boardingPosition"]:
        logger.info(f"Assigning boarding position for booking {confirmation_number}")
        position = assign_boarding_position(flight["id"])
        group = position[0]

        run_query(
            "UPDATE bookings SET boardingGroup = ?, boardingPosition = ? WHERE confirmationNumber = ?",
            (group, position, confirmation_number),
        )
        booking["boardingGroup"] = group
        booking["boardingPosition"] = position
        logger.success(f"Boarding position assigned: {group}{position} for booking {confirmation_number}")
    else:
        logger.info(f"Booking {confirmation_number} already has boarding position {booking['boardingGroup']}{booking['boardingPosition']}")

    username = session.username if session.username is not None else "Guest"

    boarding_pass = {
        "confirmationNumber": booking["confirmationNumber"],
        "flightId": flight["id"],
        "from": flight["from"],
        "to": flight["to"],
        "aircraft": flight["aircraft"],
        "departure": flight["departure"],
        "passenger": f"{username}",
        "boardingGroup": booking["boardingGroup"],
        "boardingPosition": booking["boardingPosition"],
        "gate": flight.get("deptGate"),
        "checkedInAt": utc_now()
    }

    logger.info(f"Updating checkedInAt for booking {confirmation_number}")
    run_query("UPDATE bookings SET checkedInAt = ? WHERE confirmationNumber = ?", (boarding_pass["checkedInAt"], confirmation_number))

    logger.info(f"Generating boarding pass image for {confirmation_number}")
    try:
        buffer = generate_boarding_pass_image(confirmation_number)
        logger.success(f"Boarding pass generated for {confirmation_number}")

        try:
            logger.info(f"Sending boarding pass for {confirmation_number} via SRS")
            result = await srs_client.send_checkin(booking, flight, buffer, user_data)
            logger.debug(result)
            logger.success(f"SRS boarding pass sent for {confirmation_number}")
        except Exception as e:
            logger.error(f"Failed to send SRS boarding pass for {confirmation_number}: {e}")
            pass

        return JSONResponse(status_code=200, content={"boardingGroup": boarding_pass.get("boardingGroup"), "boardingPosition": boarding_pass.get("boardingPosition")})
    except Exception as e:
        logger.error(f"Failed to generate boarding pass image: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate boarding pass image")
