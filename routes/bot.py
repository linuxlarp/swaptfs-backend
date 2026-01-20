from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from config import LOGS as logger
from core.crud import BannedUsers, Users
from core.models import BannedUser


router = APIRouter(prefix="/bot", tags=["Bot Communications"])

@router.post("/upload/banned")
async def update_banned_users(request: Request):
    """
    Update the banned users table from a validated JSON list.

    Validates Bearer token authorization, parses a JSON list into BannedUser
    objects, clears existing records, and replaces them with the new entries.

    Args:
        request (Request): The HTTP request containing authorization and JSON body.

    Returns:
        JSONResponse: A message indicating how many banned users were updated.

    Raises:
        HTTPException:
            - 400: Invalid body type or banned user format.
            - 403: Missing/invalid Authorization header or insufficient privileges.
            - 500: Server error while processing the update.

    Logs:
        - Upload attempts, table clearing, successful updates, and errors.
    """


    logger.info("POST /upload/banned")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Forbidden: Missing or invalid Authorization header")

    token = auth.split(" ", 1)[1].strip()
    user = Users.get_by_api_key(token)
    if not user or not (user.isBot or user.isAdmin):
        raise HTTPException(status_code=403, detail="Forbidden: Bot/Admin access required")
    

    try:
        data = await request.json()
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="Expected a list of banned user objects")

        banned_list: list[BannedUser] = []
        for entry in data:
            try:
                banned_list.append(BannedUser(**entry))
            except TypeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid banned user format: {e}")

        logger.info(f"Clearing banned_users table before update by {user.id}")
        BannedUsers.clear_all()

        for banned in banned_list:
            BannedUsers.add(banned)

        logger.success(f"{len(banned_list)} banned users updated by {user.id}")
        return JSONResponse(status_code=200, content={"message": f"Updated {len(banned_list)} banned users"})

    except Exception as e:
        logger.error(f"Error updating banned users: {e}")
        raise HTTPException(status_code=500, detail="Server error while updating banned users.")
