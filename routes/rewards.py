from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from config import LOGS as logger
from core import crud
from core.crud import Users
from core.models import Session
from middleware.auth import is_authenticated
from middleware.multi_permission import is_bot_or_staff, is_bot_or_admin

router = APIRouter(prefix="/rewards", tags=["Rewards"])

def determine_rapid_status(points: int) -> str:
    """
    Determine the Rapid Rewards status tier from a points balance.

    Args:
        points (int): The user's total Rapid Rewards points.

    Returns:
        str: The status tier: "Base", "A-List", "A-List Preferred", or
            "Companion Pass".
    """

    if points >= 150000: return "Companion Pass"
    if points >= 60000: return "A-List Preferred"
    if points >= 40000: return "A-List"
    return "Base"

def calculate_points(userId: str, points: int, distance: int):
    user = Users.get_by_id(userId)
    points = (user.points or 0)

    


@router.get("/", dependencies=[Depends(is_authenticated)])
async def get_points(request: Request):
    """
    Get the current user's reward points and Rapid Rewards status.

    Reads the authenticated user's record and returns their points and status.

    Args:
        request (Request): The HTTP request containing session information.

    Returns:
        dict: The user's points and rapidRwdStatus.

    Raises:
        HTTPException:
            - 404: User not found.

    Logs:
        - When reward data is requested and successfully fetched.
    """


    session = Session.from_request(request)
    data = crud.Users.get_by_id(session.user_id)

    logger.info(f"GET /rewards/ - userId: {session.user_id}")

    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.success(f"Fetched points for {session.user_id}: {data.points}")
    return {"points": data.points, "rapidRwdStatus": data.rapidRwdStatus}


def award_points(user_id: str, points: int, increment_flights: bool = False):
    """
    Award points to a user and optionally increment attended flights.

    Updates the user's points, flightsAttended, and rapidRwdStatus based on
    the new total.

    Args:
        user_id (str): The ID of the user to update.
        points (int): The number of points to add.
        increment_flights (bool): Whether to increment flightsAttended.

    Returns:
        dict: Updated user ID, points, rapidRwdStatus, and flightsAttended.

    Raises:
        HTTPException:
            - 404: User not found.

    Logs:
        - Successful updates to user rewards.
    """

    user = crud.Users.get_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_points = (user.points or 0) + points
    new_flights = (user.points or 0) + (1 if increment_flights else 0)
    new_status = determine_rapid_status(new_points)

    crud.Users.update(user_id, {
        "points": new_points,
        "flightsAttended": new_flights,
        "rapidRwdStatus": new_status
    })

    logger.success(f"User {user_id} updated: {new_points} pts, {new_status}")
    return {"userId": user_id, "points": new_points, "rapidRwdStatus": new_status, "flightsAttended": new_flights}

def remove_points(user_id: str, points: int):
    """
    Remove points from a user and update their status.

    Subtracts points (not below zero) and recalculates rapidRwdStatus.

    Args:
        user_id (str): The ID of the user to update.
        points (int): The number of points to remove.

    Returns:
        dict: Updated user ID, points, and rapidRwdStatus.

    Raises:
        HTTPException:
            - 404: User not found.

    Logs:
        - Successful point removals and resulting status.
    """

    user = crud.Users.get_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_points = max(0, (user.points or 0) - points)
    new_status = determine_rapid_status(new_points)

    crud.Users.update(user_id, {"points": new_points, "rapidRwdStatus": new_status})
    logger.success(f"Removed {points} pts from {user_id}: {new_status}")
    return {"userId": user_id, "points": new_points, "rapidRwdStatus": new_status}

@router.post("/award/points", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def award_points_user(request: Request):
    """
    Award points to a single user via the rewards API.

    Parses the JSON body, awards points (and a flight credit) to the target user,
    and returns the updated rewards data.

    Args:
        request (Request): The HTTP request containing JSON with userId and points.

    Returns:
        JSONResponse: A message plus updated user reward data.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not bot/staff).
            - 404: User not found (from award_points).

    Logs:
        - API calls to award user points and their outcomes.
    """

    body = await request.json()
    
    result = award_points(body["userId"], body["points"], True)
    logger.info(f"POST /rewards/award/points - recipentUserId: {body["userId"]}, points: {body["points"]}")

    return JSONResponse(status_code=200, content={"message": "Points awarded", **result})

@router.post("/remove/points", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def remove_points_user(request: Request):
    """
    Remove points from a single user via the rewards API.

    Parses the JSON body, removes points from the target user, and returns the
    updated rewards data.

    Args:
        request (Request): The HTTP request containing JSON with userId and points.

    Returns:
        JSONResponse: A message plus updated user reward data.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not bot/staff).
            - 404: User not found (from remove_points).

    Logs:
        - API calls to remove user points and their outcomes.
    """


    body = await request.json()
    result = remove_points(body["userId"], body["points"])

    logger.info(f"POST /rewards/remove/points - recipentUserId: {body["userId"]}, points: {body["points"]}")

    return JSONResponse(status_code=200, content={"message": "Points removed", **result})




@router.post("/award/points/flight", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def award_points_flight(request: Request):
    """
    Award points to all users booked on a specific flight.

    Fetches bookings for the flight, awards points and flight credit to each
    user, and returns the updated records.

    Args:
        request (Request): The HTTP request containing JSON with flightId and points.

    Returns:
        JSONResponse: A message and a list of updated user reward data.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not bot/staff).
            - 404: No users found on the flight.

    Logs:
        - Flight-wide point awards and number of users updated.
    """


    body = await request.json()
    flight_id, points = body["flightId"], body["points"]
    bookings = crud.Bookings.get_by_flight(flight_id)

    logger.info(f"POST /rewards/award/points/flights - flightId: {flight_id}, points: {body["points"]}")

    if not bookings:
        raise HTTPException(status_code=404, detail="No users found on this flight")

    updated = [award_points(b["userId"], points, True) for b in bookings]
    logger.success(f"Awarded {points} pts to {len(updated)} users on {flight_id}")
    return JSONResponse(status_code=200, content={"message": "Flight points awarded", "updatedUsers": updated})

@router.post("/remove/points/flight", dependencies=[Depends(is_authenticated), Depends(is_bot_or_staff)])
async def remove_points_flight(request: Request):
    """
    Remove points from all users booked on a specific flight.

    Fetches bookings for the flight, removes points from each user, and returns
    the updated records.

    Args:
        request (Request): The HTTP request containing JSON with flightId and points.

    Returns:
        JSONResponse: A message and a list of updated user reward data.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not bot/staff).
            - 404: No users found on the flight.

    Logs:
        - Flight-wide point removals and number of users updated.
    """


    body = await request.json()
    flight_id, points = body["flightId"], body["points"]
    bookings = crud.Bookings.get_by_flight(flight_id)

    logger.info(f"POST /rewards/remove/points/flights - flightId: {flight_id}, points: {body["points"]}")

    if not bookings:
        raise HTTPException(status_code=404, detail="No users found on this flight")

    updated = [remove_points(b["userId"], points) for b in bookings]
    logger.success(f"Removed {points} pts from {len(updated)} users on {flight_id}")

    return JSONResponse(status_code=200, content={"message": "Flight points removed", "updatedUsers": updated})    


@router.post("/refresh", dependencies=[Depends(is_authenticated), Depends(is_bot_or_admin)])
async def refresh_rewards():
    """
    Recalculate and refresh Rapid Rewards status for all users.

    Iterates over all users, recomputes rapidRwdStatus from current points,
    updates each record, and returns the updated list.

    Returns:
        JSONResponse: A message and list of users with refreshed status.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not bot/admin).
            - 404: No users found.

    Logs:
        - Rewards refresh requests and number of users updated.
    """


    users = crud.Users.get_all()
    logger.info("POST /rewards/refresh")

    if not users:
        raise HTTPException(status_code=404, detail="No users found")
    

    updated = []
    for u in users:
        new_status = determine_rapid_status(u.points or 0)
        crud.Users.update(u.id, {"rapidRwdStatus": new_status})
        updated.append({"userId": u.id, "points": u.points, "rapidRwdStatus": new_status})

    logger.success(f"Refreshed {len(updated)} user statuses")
    return JSONResponse(status_code=200, content={"message": "Refreshed all users awards", "updatedUsers": updated})   
