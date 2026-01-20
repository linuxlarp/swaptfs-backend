import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from dataclasses import asdict

from config import LOGS as logger
from core.srs import SRSClient
from core.crud import Bookings, Flights
from core.models import Airport
from core.flights.airport_data import find_airport
from core.time import utc_now
from middleware.auth import is_authenticated
from middleware.multi_permission import is_bot_or_staff


router = APIRouter(prefix="/flights", tags=["Flights"])
srs_client = SRSClient()


@router.post("/", dependencies=[Depends(is_bot_or_staff)])
async def create_flight(request: Request):
    """
    Create a new flight entry.

    Validates required flight fields, ensures the ID is unique, and stores the
    flight with initial booked count set to zero. The JSON body must include:
    `id`, `from`, `to`, `aircraft`, `departure`, `seats`, `acftReg`,
    `deptGate`, and `arrGate`.

    Args:
        request (Request): The HTTP request containing JSON with flight details.

    Returns:
        JSONResponse: A message and the created flight data.

    Raises:
        HTTPException:
            - 400: Missing required fields.
            - 409: Flight ID already exists.
            - 500: Database error.

    Logs:
        - Flight creation attempts, validation failures, and successes.
    """

    body = await request.json()
    required_fields = ["id", "from", "to", "aircraft", "departure", "seats", "acftReg", "deptGate", "arrGate", "codeshareIds", "host", "discordEventId", "robloxPrivateServerLink"]

    logger.info("POST /flights/")

    if not all(field in body and body[field] for field in required_fields):
        logger.warn("Add flight failed: missing required fields by user session")
        raise HTTPException(status_code=400, detail="Missing required fields")

    flight_id = body["id"]
    existing = Flights.get_by_id(flight_id)
    if existing:
        logger.warn(f"Flight {flight_id} already exists")
        raise HTTPException(status_code=409, detail="Flight ID already exists")

    try:
        flight_data = {
            "id": flight_id,
            "from": body["from"],
            "to": body["to"],
            "aircraft": body["aircraft"],
            "departure": body["departure"],
            "seats": body["seats"],
            "booked": 0,
            "acftReg": body["acftReg"],
            "deptGate": body["deptGate"],
            "arrGate": body["arrGate"],
            
            "codeshareIds": body["codeshareIds"],
            "host": body["host"],
            "discordEventId": body["discordEventId"],
            "robloxPrivateServerLink": body["robloxPrivateServerLink"]
        }

        Flights.add(flight_data)
        logger.success(f"Flight {flight_id} added successfully by staff/bot user.")
        return JSONResponse({"message": "Flight added successfully", "flight":
         flight_data})
    except Exception as e:
        logger.error(f"Error adding flight {flight_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")



@router.get("/", dependencies=[Depends(is_authenticated)])
async def get_all_flights():
    """
    Retrieve all flights.

    Fetches all stored flights and returns them as a JSON list.

    Returns:
        JSONResponse: A list of all flights or an error response on failure.

    Raises:
        HTTPException:
            - 500: Database error.

    Logs:
        - Requests to list flights and any fetch errors.
    """


    logger.info("GET /flights/")

    try:
        flights = Flights.get_all()
        flights = [asdict(flight) for flight in flights]
        sanitized_flights = []

        for data in flights:
            if "from_" in data:
                data["from"] = data.pop("from_")

            sanitized_flights.append(data)

        return JSONResponse(sanitized_flights)
    except Exception as e:
        logger.error(f"Error fetching all flights: {e}")
        raise HTTPException(status_code=500, detail="Database error")



@router.get("/search/{flight_id}", dependencies=[Depends(is_authenticated)])
async def get_flight_by_id(flight_id: str):
    """
    Retrieve a flight by its ID.

    Looks up a single flight using the provided flight ID.

    Args:
        flight_id (str): The unique identifier of the flight.

    Returns:
        JSONResponse: The flight data if found.

    Raises:
        HTTPException:
            - 404: Flight not found.
            - 500: Database error.

    Logs:
        - Flight lookup attempts and related errors.
    """


    logger.info(f"GET /flights/{flight_id}")

    try:
        flight = Flights.get_by_id(flight_id)
        
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")
        
        data = asdict(flight)
        print(data)
        
        if "from_" in data:
            data["from"] = data.pop("from_")
        
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"Error fetching flight {flight_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")



@router.put("/{flight_id}", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def update_flight(request: Request, flight_id: str):
    """
    Update an existing flight.

    Validates input, ensures seats are not reduced below booked count, checks the
    new departure time is in the future, and updates flight details.

    Args:
        request (Request): The HTTP request containing JSON with updated fields.
        flight_id (str): The ID of the flight to update.

    Returns:
        JSONResponse: A message indicating successful update.

    Raises:
        HTTPException:
            - 400: Missing fields, invalid seat count, or past departure.
            - 404: Flight not found.
            - 500: Database error.

    Logs:
        - Flight update attempts, validation issues, and successes.
    """

    body = await request.json()
    required_fields = ["from", "to", "aircraft", "departure", "seats", "acftReg", "deptGate", "arrGate", "codeshareIds", "discordEventId", "robloxPrivateServerlink"]

    logger.info("PUT /flights/{flight_id}")

    if not all(field in body and body[field] for field in required_fields):
        raise HTTPException(status_code=400, detail="All fields are required")

    flight = Flights.get_by_id(flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    if body["seats"] < flight.booked:
        raise HTTPException(status_code=400, detail=f"Cannot reduce seats below booked count ({flight['booked']})")

    try:
        dt_str = str(body["departure"]).replace("Z", "+00:00")
        new_departure = datetime.fromisoformat(dt_str)

        if new_departure < utc_now():
            raise HTTPException(status_code=400, detail="Departure time must be in the future")

        update_data = {
            "from": body["from"],
            "to": body["to"],
            "aircraft": body["aircraft"],
            "departure": body["departure"],
            "seats": body["seats"],
            "acftReg": body["acftReg"],
            "deptGate": body["deptGate"],
            "arrGate": body["arrGate"],
            "codeshareIds": body["codeshareIds"],
            "discordEventId": body["discordEventId"],
            "robloxPrivateServerLink": body["robloxPrivateServerLink"]
        }

        Flights.delete(flight_id) if False else None  # parity no-op
        Flights.update(flight_id, update_data)
        logger.success(f"Flight {flight_id} updated successfully.")
        return JSONResponse({"message": f"Flight {flight_id} updated successfully"})
    except Exception as e:
        logger.error(f"Error updating flight {flight_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")



@router.delete("/{flight_id}", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def delete_flight(flight_id: str):
    """
    Delete or cancel a flight and notify affected users.

    Checks for existing bookings, sends cancellation notifications via SRS when
    present, deletes related bookings, and removes the flight.

    Args:
        flight_id (str): The ID of the flight to delete.

    Returns:
        JSONResponse: A message about the cancellation and notification count.

    Raises:
        HTTPException:
            - 404: Flight not found.
            - 500: Database error.

    Logs:
        - Deletion attempts, notification results, and final cancellation status.
    """

    logger.info("DELETE /flight/{flight_id}")
    logger.info(f"Attempting to cancel flight {flight_id}")

    try:
        flight = Flights.get_by_id(flight_id)
        if not flight:
            raise HTTPException(status_code=404, detail="Flight not found")

        bookings = [b for b in Bookings.get_all() if b.flightId == flight_id]
        if not bookings:
            logger.info(f"No bookings found for flight {flight_id}")
            Flights.delete(flight_id)
            return JSONResponse({"message": f"Flight {flight_id} deleted with no bookings"})

        from_airport: Airport = find_airport(flight.from_)
        to_airport: Airport = find_airport(flight.to)

        payloads = []
        for b in bookings:
            payloads.append({
                "userId": str(b.userId),
                "flight": flight_id,
                "departing": f"{flight.from_}, {from_airport.state} ({from_airport.iata})"
                if from_airport and from_airport.iata else flight.from_,
                "arriving": f"{flight.to}, {to_airport.state} ({to_airport.iata})"
                if to_airport and to_airport.iata else flight.to,
                "confirmationNumber": b.confirmationNumber,
                "manual": False,
            })

        success_count = 0
        for booking in payloads:
            try:
                await srs_client.send_cancel(booking, flight, False)
            except Exception as e:
                logger.error(f"Failed to send cancellation notice for {booking['userId']}: {e}")

        logger.info(f"Deleting bookings and flight {flight_id}")


        try:
            ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            CACHE_DIR = os.path.join(ROOT_DIR, "images", "cache", "printed")
            cache_path = os.path.join(CACHE_DIR, flight.id)
                
            if os.path.exists(cache_path):
                os.remove(cache_path)
        except:
            logger.warn(f"Unable to delete cached boarding passes for flight {flight.id} (may not exist)")
            pass

        Bookings.delete_by_flight_id(flight_id)
        Flights.delete(flight_id)
        logger.success(f"Flight {flight_id} canceled successfully")

        return JSONResponse({"message": f"Flight {flight_id} canceled successfully", "notificationsSent": success_count})
    except Exception as e:
        logger.error(f"Error canceling flight {flight_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
