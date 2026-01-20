from fastapi import Request, HTTPException
from core.crud import Users
from config import LOGS as logger

async def is_flight_staff(request: Request):
    """
    Dependency / middleware to check if the current user is an auhtorized flight staff member.
    Raises HTTPException(403) if not authorized.
    """
    
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )

    try:
        session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
        user_id = session_user.get("id") if session_user else None

        if not user_id:
            logger.auth(f"Flight Staff access denied: no user in session ({ip}, user_id={user_id})")
            raise HTTPException(status_code=403, detail="Forbidden: Flight Staff access required")

        user = Users.get_by_id(user_id)
        if user and user.isFlightStaff or user.isStaff or user.isAdmin or user.isBot:
            return True

        logger.auth(f"Flight Staff access denied for user id=%s ({ip})", user_id)
        raise HTTPException(status_code=403, detail="Forbidden: Flight Staff access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error("Error checking admin status: %s", err)
        raise HTTPException(status_code=500, detail="Database error")


async def is_staff(request: Request):
    """
    Dependency / middleware to check if the current user is an auhtorized staff member.
    Raises HTTPException(403) if not authorized.
    """

    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )

    try:
        session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
        user_id = session_user.get("id") if session_user else None

        if not user_id:
            logger.auth(f"Staff access denied: no user in session ({ip}, user_id={user_id})")
            raise HTTPException(status_code=403, detail="Forbidden: Staff access required")

        user = Users.get_by_id(user_id)

        if user and user.isStaff or user.isAdmin or user.isBot:
            return True
        
        logger.auth(f"Staff access denied for user id=%s ({ip})", user_id)
        raise HTTPException(status_code=403, detail="Forbidden: Staff access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking admin status: %s ({ip}, user_id={user_id})", err)
        raise HTTPException(status_code=500, detail="Database error")


async def is_admin(request: Request):
    """
    Dependency / middleware to check if the current user is an admin.
    Raises HTTPException(403) if not authorized.
    """
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )

    try:
        session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
        user_id = session_user.get("id") if session_user else None

        if not user_id:
            logger.info(f"Admin access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Admin access required")

        user = Users.get_by_id(user_id)
        if user and user.isAdmin:
            return True

        logger.info(f"Admin access denied for user id=%s ({ip})", user_id)
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking admin status: %s, ({ip})", err)
        raise HTTPException(status_code=500, detail="Database error")


async def is_bot(request: Request):
    """
    Dependency / middleware to check if the current user is marked as a BOT.
    Raises HTTPException(403) if not authorized.
    """
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )

    try:
        session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
        user_id = session_user.get("id") if session_user else None

        if not user_id:
            logger.info(f"Bot access denied: no user in session ({ip})")
            raise HTTPException(status_code=403, detail="Forbidden: Bot access required")

        user = Users.get_by_id(user_id)
        if user and user.get("isBot"):
            return True

        logger.info(f"Bot access denied for user id=%s ({ip})", user_id)
        raise HTTPException(status_code=403, detail="Forbidden: Bot access required")

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error checking bot status: %s ({ip})", err)
        raise HTTPException(status_code=500, detail="Database error")
