import os
import time
import json
import base64
import secrets
import urllib.parse
import requests # pyright: ignore[reportMissingModuleSource]

from fastapi import APIRouter, Request, Depends, HTTPException, status
from starlette.responses import RedirectResponse, JSONResponse
from config import (
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    DISCORD_REDIRECT_URI,
    DISCORD_SCOPE,
)

from database import get_one_query
from config import LOGS as logger
from middleware.auth import is_authenticated
from core.crud import Users, BannedUsers
from core.models import User, Session

router = APIRouter(prefix="/auth")
linking_codes = {} ## saved in memory

async def save_user(user_data: dict):
    """
    Create or update a user record and return a new API token.

    Checks if the user exists; if not, creates one with default values.
    Always generates a new API token and updates stored data.

    Args:
        user_data (dict): A dictionary containing user information. Must include:
            - id (int or str): Unique user ID.
            - username (str): The user's username.
            - discriminator (str, optional): User tag or identifier.
            - avatar (str, optional): Avatar URL or hash.

    Returns:
        str: A newly generated 64-byte hexadecimal API token.

    Raises:
        KeyError: If 'id' or 'username' is missing from `user_data`.

    Logs:
        - When a new user is created.
        - When an existing user is updated.
    """

    existing_user = get_one_query("SELECT * FROM users WHERE id = ?", [user_data["id"]])
    api_token = secrets.token_hex(64)
    user_id = user_data["id"]

    if not existing_user:
        new_user = User(
            id=user_data["id"],
            username=user_data["username"],
            discriminator=user_data.get("discriminator", "#0"),
            avatar=user_data.get("avatar"),
            points=0,
            apiToken=api_token,
            isAdmin=False,
            isBot=False,
            isStaff=False,
            isFlightStaff=False,
            rapidRwdStatus="Base",
            flightsAttended=0,
        )

        Users.add(new_user)
        logger.auth(f"New user {user_id} created with token {api_token}")
    else:
        updated_user = User(
            id=user_id,
            username=user_data["username"],
            discriminator=user_data.get("discriminator", "#0"),
            avatar=user_data.get("avatar"),
            points=existing_user.get("points", 0),
            apiToken=api_token,
            isAdmin=existing_user.get("isAdmin", False),
            isBot=existing_user.get("isBot", False),
            isStaff=existing_user.get("isStaff", False),
            isFlightStaff=existing_user.get("isFlightStaff", False),
            rapidRwdStatus=existing_user.get("rapidRwdStatus", "Base"),
            flightsAttended=existing_user.get("flightsAttended", 0),
        )

        Users.update_points(user_id, updated_user.points)
        Users.update(user_id, updated_user)
        logger.auth(f"Existing user {user_id} updated and with same token {api_token}")

    return api_token



@router.get("/discord")
async def discord_auth(redirect_to: str = "/"):
    """
    Redirect user to Discord OAuth2 authorization page.

    Builds the Discord OAuth2 URL with state data and redirects the user to authorize
    the app. Includes environment-based handling for development mode.

    Args:
        redirect_to (str): The path to redirect the user to after authorization.

    Returns:
        RedirectResponse: A redirect to the Discord OAuth2 authorization URL.

    Logs:
        - When redirecting the user to the Discord OAuth page.
    """

    dev = os.getenv("DEV_MODE", "false").lower() == "true"

    state_data = {
        "redirect_to": redirect_to,
        "timestamp": int(time.time())
    }

    state = base64.urlsafe_b64encode(
        json.dumps(state_data).encode()
    ).decode()

    if dev:
        base_url = (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={DISCORD_CLIENT_ID}"
            f"&redirect_uri={urllib.parse.quote(DISCORD_REDIRECT_URI)}"
            f"&response_type=code"
            f"&scope={urllib.parse.quote(DISCORD_SCOPE)}"
            f"&state={state}"
        )
    else:
        base_url = (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={DISCORD_CLIENT_ID}"
            f"&redirect_uri={urllib.parse.quote(DISCORD_REDIRECT_URI)}"
            f"&response_type=code"
            f"&scope={urllib.parse.quote(DISCORD_SCOPE)}"
            f"&state={state}"
        )

    logger.auth("Redirecting user to Discord OAuth authorization page")
    return RedirectResponse(base_url)


@router.get("/discord/callback")
async def discord_callback(request: Request):
    """
    Handle Discord OAuth2 callback and authenticate the user.

    Processes the OAuth2 callback by exchanging the code for a token, retrieving user data
    from Discord, saving user info, checking bans, and creating a session.

    Args:
        request (Request): The HTTP request containing query parameters and session data.

    Returns:
        RedirectResponse: Redirects to a success or error page after authentication.

    Raises:
        HTTPException: If code is missing or authentication with Discord fails.

    Logs:
        - When receiving the callback and requesting tokens.
        - When a user is authenticated or if authentication fails.
    """
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    logger.info(f"GET /discord/callback - code: {code}, state: {code}")

    redirect_path = "/"
    if state:
        try:
            state_data = json.loads(
                base64.urlsafe_b64decode(state.encode()).decode()
            )
            redirect_path = state_data.get("redirect_to", "/")
        except:  # noqa: E722
            pass

    if not code:
        logger.error("Discord callback missing code")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No code provided")

    try:
        logger.auth("Received Discord callback, requesting OAuth token")
        token_resp = requests.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
                "scope": DISCORD_SCOPE,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        user_resp = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        user_resp.raise_for_status()
        ud = user_resp.json()

        user_data = {
            "id": ud["id"],
            "username": ud["username"],
            "discriminator": ud.get("discriminator"),
            "avatar": ud.get("avatar"),
            "user_ip": request.client.host
        }

        banned_user = BannedUsers.get_by_id(user_data["id"])

        if banned_user:
            reason = banned_user.reason or "No reason provided"
            encoded_reason = urllib.parse.quote(reason)
            logger.auth(f"Banned user {user_data['id']} attempted login and redirected")
            base_redirect = os.getenv("BASE_REDIRECT", "/")
            return RedirectResponse(f"{base_redirect}/error/banned?reason={encoded_reason}")

        api_token = await save_user(user_data)
        request.session["user"] = {**user_data, "apiToken": api_token}
        logger.auth(f"User {user_data['id']} successfully authenticated via Discord")

        base_redirect = os.getenv("BASE_REDIRECT", "/")

        if state and state in linking_codes:
            link_data = linking_codes[state]

            if isinstance(link_data, dict):
                link_data["userId"] = user_data["id"]
                linking_codes[state] = link_data
            else:
                linking_codes[state] = {"userId": user_data["id"]}

            Users.add({**user_data})
            logger.auth(f"User {user_data['id']} completed link state {state}")
            return RedirectResponse(f"{base_redirect}/notice/authenticated?continueTo={redirect_path}")

        return RedirectResponse(f"{base_redirect}/notice/authenticated?continueTo={redirect_path}")
        

    except requests.HTTPError as e:
        resp_text = e.response.text if getattr(e, "response", None) is not None else str(e)
        logger.error("OAuth error: %s", resp_text)
        return HTTPException(status_code=500, detail="Failed to authenticate with Discord")
    except Exception as e:
        logger.error("OAuth error: %s", str(e))
        return HTTPException(status_code=500, detail="Failed to authenticate with Discord")


@router.get("/logout")
async def logout(request: Request):
    """
    Log out the authenticated user by clearing session data.

    Clears the current session, invalidating any stored user authentication info.

    Args:
        request (Request): The HTTP request containing the user session.

    Returns:
        JSONResponse: A response confirming logout or reporting a failure.

    Logs:
        - When a user logs out or if an error occurs during logout.
    """

    session = Session.from_request(request)
    logger.auth(f"GET /auth/logout - userId: {session.user_id} ({session.host})")

    try:
        request.session.clear()
        return JSONResponse({"message": "Logged out successfully"})
    except Exception as e:
        logger.error("Logout error: %s", str(e))
        return JSONResponse({"error": "Failed to log out"}, status_code=500)


@router.get("/user", dependencies=[Depends(is_authenticated)])
async def get_user(request: Request):
    """
    Fetch details of the currently authenticated user.

    Retrieves user data from the database using session information and returns it.
    Requires the user to be authenticated.

    Args:
        request (Request): The HTTP request containing the current session.

    Returns:
        dict: A dictionary containing basic user details (ID, username, discriminator, avatar).

    Raises:
        HTTPException: If the user is not found or a server error occurs.

    Logs:
        - When a user’s details are requested or when errors occur.
    """

    session = Session.from_request(request)
    logger.auth(f"GET /auth/user/details - userId: {session.user_id} ({session.host})")

    try:
        stored_user = Users.get_by_id(session.user_id)

        if not stored_user:
            logger.auth(f"User {session.user_id} not found in DB")
            raise HTTPException(status_code=401, detail="User not found")
        return {"user": {
            "id": stored_user.id,
            "username": stored_user.username,
            "discriminator": stored_user.discriminator,
            "avatar": stored_user.avatar,
        }}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in /auth/user: %s", str(e))
        raise HTTPException(status_code=500, detail="Server error")

