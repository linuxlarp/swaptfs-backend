from fastapi import Request, HTTPException
from core.crud import Users
from config import LOGS as logger


async def _get_user_from_session(request: Request):
    """Extract user ID from session."""
    session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
    return session_user.get("id") if session_user else None


async def is_staff_or_admin(request: Request):
    """Allow access if user is staff or admin."""
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )
    try:
        user_id = await _get_user_from_session(request)
        if not user_id:
            logger.info(f"Staff/Admin access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Staff/Admin access required")

        user = Users.get_by_id(user_id)
        if user and (user.isStaff or user.isAdmin): 
            return True

        logger.info(f"Staff/Admin access denied for user id={user_id} ({ip})")
        raise HTTPException(status_code=403, detail="Forbidden: Staff/Admin access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking Staff/Admin access: {err} ({ip})")
        raise HTTPException(status_code=500, detail="Database error")


async def is_bot_or_staff(request: Request):
    """Allow access if user is bot or staff."""
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )
    try:
        user_id = await _get_user_from_session(request)
        if not user_id:
            logger.info(f"Bot/Staff access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Bot/Staff access required")

        user = Users.get_by_id(user_id)
        if user and (user.isBot or user.isStaff or user.isAdmin):
            return True

        logger.info(f"Bot/Staff access denied for user id={user_id} ({ip})")
        raise HTTPException(status_code=403, detail="Forbidden: Bot/Staff access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking Bot/Staff access: {err} ({ip})")
        raise HTTPException(status_code=500, detail="Database error")


async def is_staff_or_flight_staff(request: Request):
    """Allow access if user is staff or flight staff."""
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )
    try:
        user_id = await _get_user_from_session(request)
        if not user_id:
            logger.info(f"Staff/FlightStaff access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Staff/FlightStaff access required")

        user = Users.get_by_id(user_id)
        if user and (user.isStaff or user.isFlightStaff or user.isAdmin): 
            return True

        logger.info(f"Staff/FlightStaff access denied for user id={user_id} ({ip})")
        raise HTTPException(status_code=403, detail="Forbidden: Staff/FlightStaff access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking Staff/FlightStaff access: {err} ({ip})")
        raise HTTPException(status_code=500, detail="Database error")


async def is_bot_or_admin(request: Request):
    """Allow access if user is bot or admin."""
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )
    try:
        user_id = await _get_user_from_session(request)
        if not user_id:
            logger.info(f"Bot/Admin access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Bot/Admin access required")

        user = Users.get_by_id(user_id)
        if user and (user.isBot or user.isAdmin):
            return True

        logger.info(f"Bot/Admin access denied for user id={user_id} ({ip})")
        raise HTTPException(status_code=403, detail="Forbidden: Bot/Admin access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking Bot/Admin access: {err} ({ip})")
        raise HTTPException(status_code=500, detail="Database error")
