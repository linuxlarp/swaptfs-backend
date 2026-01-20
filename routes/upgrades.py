from fastapi import APIRouter, Depends, HTTPException, Request

from config import EARLYBIRD_PRICE, LOGS
from core import crud
from core.models import Session
from database import get_all_query, get_one_query, run_query
from middleware.auth import is_authenticated
from middleware.permisions import is_admin


router = APIRouter(prefix="/upgrades", tags=["Upgrades"])
logger = LOGS

@router.get("/earlybird", dependencies=[Depends(is_authenticated)])
async def get_earlybird_status(request: Request):
    """
    Get the current user's Early Bird Check-In status.

    Looks up the authenticated user's record and returns whether they have purchased EarlyBird Checkin.

    Args:
        request (Request): The HTTP request containing session information.

    Returns:
        dict: {"hasEarlyBird": bool} indicating Early Bird status.

    Raises:
        HTTPException:
            - 404: User not found.

    Logs:
        - Early Bird status checks with user ID and flag.
    """


    session = Session.from_request(request)
    user = crud.Users.get_by_id(session.user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"GET /upgrades/earlybird - userId: {session.user_id}, hasEarlyBird: {user.hasEarlybird}")
    
    return {"hasEarlyBird": user.hasEarlybird}

@router.get("/earlybird/list", dependencies=[Depends(is_admin)])
async def get_earlybird_list():
    """
    Get a list of all users with Early Bird Check-In.

    Returns basic user info for every user who has Early Bird enabled.

    Returns:
        list[dict]: A list of {"id": str, "username": str} for Early Bird users.

    Raises:
        HTTPException:
            - 403: Authenticated but not allowed (not admin).

    Logs:
        - Requests for the Early Bird user list.
    """

    logger.info("GET /upgrades/earlybird/list")

    users = get_all_query("SELECT id, username FROM users WHERE hasEarlyBird = 1")
    return [{"id": u["id"], "username": u.get("username", "Unknown")} for u in users]

@router.post("/purchase/earlybird", dependencies=[Depends(is_authenticated)])
async def purchase_earlybird(request: Request):
    """
    Purchase Early Bird Check-In for the current user.

    Verifies the user exists, has not already purchased Early Bird, and has
    enough points, then deducts points and enables Early Bird.

    Args:
        request (Request): The HTTP request containing session information.

    Returns:
        dict: A success message on completed purchase.

    Raises:
        HTTPException:
            - 400: Already purchased or insufficient points.
            - 403: Authenticated but not allowed if auth fails upstream.
            - 404: User not found.
            - 500: Database error.

    Logs:
        - Purchase attempts, successes, and errors for Early Bird.
    """

    session = Session.from_request(request)
    user = crud.Users.get_by_id(session.user_id)

    logger.info(f"POST /upgrades/purchase/earlybird - userId: {session.user_id}")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.hasEarlybird is True:
        raise HTTPException(status_code=400, detail="Early Bird Check-In already purchased")
    if user.points < EARLYBIRD_PRICE:
        raise HTTPException(status_code=400, detail="Insufficient points")

    try:
        crud.Users.update(session.user_id, {
            "points": user.points - EARLYBIRD_PRICE,
            "hasEarlyBird": True
        })

        logger.success(f"User {session.user_id} purchased EarlyBird Check-In")
        return {"message": "Early Bird Check-In purchased successfully"}
    except Exception as e:
        logger.error(f"Error purchasing EarlyBird for user {session.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
