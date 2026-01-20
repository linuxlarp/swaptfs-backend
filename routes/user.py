from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from config import LOGS as logger
from core.crud import Users
from dataclasses import asdict
from core.models import Session
from database import run_query
from middleware.auth import is_authenticated

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/self", dependencies=[Depends(is_authenticated)])
async def get_self_info(request: Request):
    """
    Get the authenticated user's own account data.

    Uses the current session to look up the user in the database and returns
    their full stored record.

    Args:
        request (Request): The HTTP request containing session information.

    Returns:
        JSONResponse: {"success": True, "user": <user_record>} if found.

    Raises:
        HTTPException:
            - 404: User not found.
            - 403: If upstream authentication permissions fail.

    Logs:
        - Self-info requests, missing users, and successful responses.
    """

    session = Session.from_request(request)
    logger.info(f"GET /users/ - userId: {session.user_id} ({session.host})")

    db_user = Users.get_by_id(session.user_id)
    if not db_user:
        logger.warn(f"Self-info not found for {session.user_id} ({session.host})")
        raise HTTPException(status_code=404, detail="User not found")

    logger.success(f"User data returned for self-info {session.user_id} ({session.host})")
    return JSONResponse(status_code=200, content={"success": True, "user": asdict(db_user)})

@router.get("/{discord_id}")
async def get_user_info(discord_id: str, request: Request, user=Depends(is_authenticated)):
    """
    Get user data by Discord ID with role-based access control.

    Normal users may only access their own record, while bots, admins, staff,
    and flight staff can access any user. Flight staff without higher roles
    receive user data with apiToken stripped.

    Args:
        discord_id (str): The Discord user ID to fetch.
        request (Request): The HTTP request containing session information.
        user: Injected dependency ensuring the caller is authenticated.

    Returns:
        JSONResponse: {"success": True, "user": <user_record>} if found.

    Raises:
        HTTPException:
            - 401: Authenticated user not present in the database.
            - 403: Forbidden when a non-elevated user requests another user.
            - 404: Target user not found.

    Logs:
        - Access attempts, elevation checks, and successful lookups.
    """

    session = Session.from_request(request)
    authenticated_user_id = session.user_id
    logger.info(f"GET /users/{discord_id} - userId: {authenticated_user_id}")
    
    auth_user_record = Users.get_by_id(authenticated_user_id)
    
    if not auth_user_record:
        raise HTTPException(status_code=401, detail="Authenticated user not found in database")
    
    is_elevated = bool(
        auth_user_record.isBot or 
        auth_user_record.isAdmin or 
        auth_user_record.isStaff or 
        auth_user_record.isFlightStaff
    )
    
    should_strip_api_token = bool(
        auth_user_record.isFlightStaff and 
        not (auth_user_record.isBot or 
             auth_user_record.isAdmin or 
             auth_user_record.isStaff)
    )
    
    if not is_elevated and str(authenticated_user_id) != str(discord_id):
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Cannot access other users' data"
        )
    
    if is_elevated:
        logger.info(f"Elevated user {authenticated_user_id} requested user data for {discord_id}")
    else:
        logger.info(f"User {authenticated_user_id} requested their own data")
    
    db_user = Users.get_by_id(discord_id)
    if not db_user:
        logger.warn(f"User not found for Discord ID {discord_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    if should_strip_api_token and "apiToken" in db_user:
        db_user.apiToken = None
    
    logger.success(f"User data returned for {discord_id}")
    return JSONResponse(status_code=200, content={"success": True, "user": asdict(db_user)})


@router.patch("/{user_id}")
async def update_user(request: Request, user_id: str):
    """
    Update staff/admin/flight-staff flags for a target user.

    Validates a Bearer API token, ensures the requester is an admin, then
    updates the target user's role flags in the database.

    Args:
        request (Request): The HTTP request containing JSON with role flags.
        user_id (str): The ID of the user whose roles are being updated.

    Returns:
        JSONResponse: A message confirming the update and status 200.

    Raises:
        HTTPException:
            - 401: Missing/invalid Bearer token.
            - 403: Requester is not an admin.
            - 404: Target user not found.

    Logs:
        - Role update attempts, authorization failures, and successful updates.
    """

    body = await request.json()
    is_staff = 1 if body.get("isStaff") else 0
    is_admin = 1 if body.get("isAdmin") else 0
    is_flight_staff = 1 if body.get("isFlightStaff") else 0

    logger.info(f"PATCH /users/{user_id} - userId: {user_id}, isFlightStaff: {bool(is_flight_staff)}, isStaff: {bool(is_staff)}, isAdmin: {bool(is_admin)}")

    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized. API token required.")

    token = auth_header.split(" ")[1]
    requesting_user = Users.get_by_api_key(token)

    if not requesting_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not requesting_user.isAdmin:
        raise HTTPException(status_code=403, detail="Forbidden: Admins/Bot only")

    target_user = Users.get_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    run_query(
        "UPDATE users SET isStaff = ?, isAdmin = ?, isFlightStaff = ? WHERE id = ?",
        (is_staff, is_admin, is_flight_staff, user_id),
    )

    updated = Users.get_by_id(user_id)
    logger.info(f"Updated user: {updated.id}, isFlightStaff: {updated.isFlightStaff}, isStaff: {updated.isStaff}, isAdmin: {updated.isAdmin}")
    return JSONResponse(status_code=200, content={"message": "User updated successfully"})