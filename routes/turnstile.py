import os
import secrets
import time
from typing import Dict

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse


router = APIRouter(prefix="/verify", tags=["Cloudflare Turnstile"])
redirects: Dict[str, float] = {}

@router.post("/discord")
async def verify_discord(request: Request):
    """
    Verify a Cloudflare Turnstile token and return a Discord verification redirect.

    Accepts JSON or form data containing a `token`, validates it against the
    Turnstile API, and on success returns a short-lived redirect URL used to
    continue Discord verification.

    Args:
        request (Request): The HTTP request containing Turnstile token data.

    Returns:
        JSONResponse: On success, {"success": True, "redirect": "<url>"}.
        PlainTextResponse: For missing token or server errors.
        JSONResponse: {"success": False} with 403 if Turnstile verification fails.

    Raises:
        None: Errors are returned as HTTP responses rather than exceptions.

    Logs:
        - Not explicitly logged in this function but relies on upstream logging.
    """


    token = None
    ctype = request.headers.get("content-type", "")
    
    if "application/json" in ctype:
        try:
            body = await request.json()
            token = body.get("token")
        except Exception:
            token = None
    else:
        form = await request.form()
        token = form.get("token")

    if not token:
        return PlainTextResponse("missing token", status_code=400)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": os.getenv("TURNSTILE_SECRET", ""),
                    "response": token,
                },
            )
            data = r.json()
    except Exception:
        return PlainTextResponse("server error", status_code=500)

    if not data.get("success"):
        return JSONResponse({"success": False}, status_code=403)

    id_ = secrets.token_hex(16)
    redirects[id_] = time.time() + 60

    host = request.headers.get("host", "").split(":")[0]
    redirect_domain = "southwestptfs.com" if host == "southwestptfs.com" else "prod.southwestptfs.com"
    return JSONResponse({"success": True, "redirect": f"https://{redirect_domain}/verify/go/{id_}"})


@router.get("/go/{id_}")
async def go(id_: str):
    """
    Consume a verification redirect ID and send the user to the Discord invite.

    Checks that the ID is present and not expired, then removes it and redirects
    the client to the configured Discord invite URL.

    Args:
        id_ (str): The one-time verification identifier.

    Returns:
        PlainTextResponse: 410 if the link is expired, or 500 on config error.
        RedirectResponse: Redirects the user to the Discord invite URL.

    Raises:
        None: Errors are returned as HTTP responses rather than exceptions.

    Logs:
        - Not explicitly logged in this function but relies on upstream logging.
    """


    expiry = redirects.get(id_)
    now = time.time()
    if not expiry or expiry < now:
        return PlainTextResponse("Link expired. Please verify again.", status_code=410)
    redirects.pop(id_, None)

    invite = os.getenv("DISCORD_INVITE")
    if not invite:
        return PlainTextResponse("Server configuration error", status_code=500)
    return RedirectResponse(invite)

