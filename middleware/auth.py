from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from core.crud import Users, BannedUsers
from urllib.parse import quote
from config import LOGS as logger
from dataclasses import asdict

async def is_authenticated(request: Request):
    """
    Middleware/Dependency to check user authentication.

    - Verifies session or Bearer token in headers.
    - Loads user info into request.state.user.
    - Rejects banned users.
    - Raises 401 or redirects if unauthorized/banned.
    """
    user = None

    # Determine IP for logging
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0]
        or request.client.host
    )

    try:
        session_user = getattr(request, "session", {}).get("user") if hasattr(request, "session") else None
        
        if session_user:
            user = session_user
        else:
            auth_header = request.headers.get("authorization")
            logger.auth(f"Checking authentication status for {session_user.get('id') if session_user else 'unknown'} ({ip})")

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                db_user = Users.get_by_api_key(token)

                if db_user:
                    user = {
                        "id": db_user.id,
                        "username": db_user.id,
                        "discriminator": db_user.discriminator,
                        "avatar": db_user.avatar,
                    }
                    if hasattr(request, "session"):
                        request.session["user"] = user
                    logger.auth(f"Authentication check completed for {user['id']} ({ip})")

        if not user:
            logger.auth(f"Unauthorized access attempt ({ip})")
            raise HTTPException(
                status_code=401,
                detail="Unauthorized. Please log in via Discord or provide a valid API token."
            )

        banned = BannedUsers.get_by_id(user["id"])

        if banned:
            reason = banned.reason or "No reason provided"
            reason_q = quote(reason)
            logger.warn(f"Banned user {banned.userId} attempted to access protected endpoint: {request.method} {request.url} ({ip}, ban reason: {reason})")

            return RedirectResponse(url=f"https://southwestptfs.com/error/banned?reason={reason_q}")
        else:
            pass

        request.state.user = user
        return True

    except HTTPException:
        raise
    except Exception as err:
        logger.error(f"Error during authentication: {err}")
        raise HTTPException(status_code=500, detail="Database error during authentication")
