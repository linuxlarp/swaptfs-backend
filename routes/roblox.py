import httpx
import config

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from config import LOGS as logger
from dataclasses import asdict
from core.models import Session
from core.crud import Users
from middleware.auth import is_authenticated


router = APIRouter(prefix="/roblox", tags=["Pull in data from bloxlink"])


@router.get("/me", dependencies=[Depends(is_authenticated)])
async def get_my_roblox_info(request: Request):
    """
    Get the authenticated user's linked Roblox ID via Bloxlink.

    Uses the current Discord user ID to query the Bloxlink API and returns the
    associated Roblox user ID if found.

    Args:
        request (Request): The HTTP request containing session data.

    Returns:
        JSONResponse: The linked Roblox ID as {"robloxId": "<id>"}.

    Raises:
        HTTPException:
            - 404: Roblox account not linked or Roblox ID missing.
            - 500: Failed to authenticate with Bloxlink.

    Logs:
        - Requests for Roblox info and Bloxlink auth failures.
    """

    session = Session.from_request(request)

    logger.info(f"GET /roblox/me - userId: {session.user_id}")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.blox.link/v4/public/guilds/{config.DISCORD_SERVER_ID}/discord-to-roblox/{session.user_id}",
            headers={
                "Authorization": config.BLOXLINK_API_KEY
            },
        )

        data = r.json()

        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Roblox not linked")

        if r.status_code == 401:
            logger.warn("Failed to pass authentication to Bloxlink")
            raise HTTPException(status_code=500, detail="Server error")


    if not data.get("robloxID"):
        raise HTTPException(status_code=404, detail="Roblox not found")

    return JSONResponse({"robloxId": data.get("robloxID")})

    
@router.get("/info/{discordId}", dependencies=[Depends(is_authenticated)])
async def get_roblox_info_by_userid(request: Request, discordId: str):
    """
    Get a user's linked Roblox ID from their Discord ID.

    Queries the Bloxlink API with the provided Discord ID and returns the
    associated Roblox user ID if found.

    Args:
        request (Request): The HTTP request containing session data.
        discordId (str): The target user's Discord ID.

    Returns:
        JSONResponse: The linked Roblox ID as {"robloxId": "<id>"}.

    Raises:
        HTTPException:
            - 404: Roblox account not linked or Roblox ID missing.
            - 500: Failed to authenticate with Bloxlink.

    Logs:
        - Roblox lookup requests by Discord ID and Bloxlink auth failures.
    """


    session = Session.from_request(request)
    user = Users.get_by_id(discordId)
    logger.info(f"GET /roblox/info/{discordId} - requestFrom: {session.user_id}")

    if user.robloxId and user.robloxId != "":
        logger.info(f"Returning cached Roblox ID for user {discordId}")
        return JSONResponse({"robloxId": user.robloxId})

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.blox.link/v4/public/guilds/{config.DISCORD_SERVER_ID}/discord-to-roblox/{discordId}",
            headers={
                "Authorization": config.BLOXLINK_API_KEY
            },
        )

        data = r.json()

        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Roblox not linked")

        if r.status_code == 401:
            logger.warn("Failed to pass authentication to Bloxlink")
            raise HTTPException(status_code=500, detail="Server error")


    if not data.get("robloxID"):
        raise HTTPException(status_code=404, detail="Roblox not found")
    

    try:
        user['robloxId'] = data.get("robloxID")
        Users.update(discordId, user)
    except Exception:
        logger.warn("Failed to cache Roblox info from Bloxlink")

    return JSONResponse({"robloxId": data.get("robloxID")})


@router.get("/details/{robloxId}", dependencies=[Depends(is_authenticated)])
async def get_roblox_details(request: Request, robloxId: str):
    """
    Get Roblox profile details and avatar URL for a Roblox user ID.

    Fetches basic user info and avatar thumbnail from the Roblox APIs and
    returns display name, username, ID, and avatar URL.

    Args:
        request (Request): The HTTP request containing session data.
        robloxId (str): The Roblox user ID to look up.

    Returns:
        JSONResponse: Roblox user details including displayName, username,
            userId, and avatarURL.

    Raises:
        HTTPException:
            - 404: Roblox user not found or API error.

    Logs:
        - Roblox detail lookup requests and any failures.
    """


    session = Session.from_request(request)
    logger.info(f"GET /roblox/details/{robloxId} - requestFrom: {session.user_id}")
    
    async with httpx.AsyncClient(timeout=10) as client:
        user_response = await client.get(f"https://users.roblox.com/v1/users/{robloxId}")
        avatar_response = await client.get(
            f"https://thumbnails.roblox.com/v1/users/avatar-bust?userIds={robloxId}&size=420x420&format=Png&isCircular=false"
        )
        
        if user_response.status_code != 200 or avatar_response.status_code != 200:
            raise HTTPException(status_code=404, detail="Roblox user not found")
        
        user_data = user_response.json()
        avatar_data = avatar_response.json()

        if avatar_data is None:
            avatar_data = f"https://cdn.discordapp.com/embed/avatars/{session.avatar}.png?size=128"
        
        return JSONResponse({
            "displayName": user_data.get("displayName"),
            "username": user_data.get("name"),
            "userId": robloxId,
            "avatarURL": avatar_data.get("data", [{}])[0].get("imageUrl", "")
        })