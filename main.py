import asyncio
import database
import config

from config import LOGS as logger
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from datetime import timedelta

from database import get_query, run_query
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from core.time import parse_datetime, utc_now
import uvicorn

# // Import routes and routing from /routes
from routes import auth
from routes import booking
from routes import flights
from routes import user
from routes import bot
from routes import images
from routes import checkin
from routes import rewards
from routes import upgrades
from routes import turnstile
from routes import roblox

app = FastAPI(title="swa-api-fastapi", version=config.VERSION, docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if config.DEV_MODE == False:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["prod.southwestptfs.com"]
    )


app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    max_age=24 * 60 * 60 / 2,  # 12 hours
    same_site="lax",
    https_only=lambda: config.DEV_MODE is False,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    if "location" in response.headers:
        if not config.DEV_MODE:
            location = response.headers["location"]

            if location.startswith("http://"):
                response.headers["location"] = location.replace("http://", "https://", 1)
            
    return response

# // Load Routers
app.include_router(auth.router)
app.include_router(booking.router)
app.include_router(flights.router)
app.include_router(user.router)
app.include_router(bot.router)
app.include_router(images.router)
app.include_router(checkin.router)
app.include_router(rewards.router)
app.include_router(upgrades.router)
app.include_router(turnstile.router)
app.include_router(roblox.router)



async def cleanup_past_flights():
    logger.info("Cleaning up past flights...")
    rows = get_query("SELECT id, departure FROM flights;")
    if not rows:
        logger.warn("No flights found.")
        return

    cutoff = utc_now() - timedelta(hours=2)
    past_ids = [r["id"] for r in rows if (dt := parse_datetime(r.get("departure"))) and dt < cutoff]

    if not past_ids:
        logger.info("No past flights to clean up.")
        return

    placeholders = ",".join("?" for _ in past_ids)
    run_query(f"DELETE FROM bookings WHERE flightId IN ({placeholders})", past_ids)
    run_query(f"DELETE FROM flights WHERE id IN ({placeholders})", past_ids)
    logger.info(f"Deleted {len(past_ids)} past flights.")



async def periodic_cleanup_task():
    while True:
        try:
            await cleanup_past_flights()
        except Exception:
            logger.error("Periodic cleanup failed")
        await asyncio.sleep(20 * 60)


@app.on_event("startup")
async def on_startup():
    logger.startup()

    try:
        database.initialize_database()
    except Exception as e:
        logger.error("Database initialization failed: %s", e)
        raise


    await cleanup_past_flights()


    asyncio.create_task(periodic_cleanup_task())


@app.get("/", response_class=PlainTextResponse)
async def root(request: Request):
    ip = request.headers.get("x-forwarded-for", "").split(",")[0] or request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    logger.warn(f"Root endpoint accessed from {ip} - User-Agent: {user_agent}")
    
    version_line = f"SOUTHWEST PTFS API {config.VERSION}"
    refer_status = "https://status.southwestptfs.com/"
    ip_line = f"Your IP: {ip}"
    discord_link = config.SERVER_INVITE
    
    return PlainTextResponse(
        f"{version_line}\n"
        "\n"
        "👋 Hey there! It seems you stumbled upon our Backend API!\n"
        "\n"
        "If you're here as a normal user, Great! Thanks for using our\n"
        "services. Need help? Open a ticket in our Discord or email us.\n"
        f"Seeing this page unexpectedly? Please check out our status page: {refer_status}\n"
        "\n"
        "However, please be aware that we take security seriously:\n"
        "\n"
        "↪ Every request is logged and monitored.\n"
        "↪ Unauthorized access attempts are tracked and analyzed.\n"
        "↪ Attack patterns are detected and may be reported to appropriate authorities.\n"
        "↪ DDoS protection is active via Cloudflare.\n"
        "↪ We maintain comprehensive records of all activity.\n"
        "\n"
        f"{ip_line}\n"
        "Timestamp: recorded\n"
        "Status: monitoring\n"
        "\n"
        "We appreciate respectful use of our services. Any attempts to abuse,\n"
        "exploit, or attack this API will be taken seriously and handled\n"
        "accordingly.\n"
        "\n"
        "Support: support@southwestptfs.com\n"
        f"Discord: {discord_link}\n"
        "\n"
        "© 2025 Southwest Airlines PTFS. This is a fan-made project for use\n"
        "within Roblox PTFS and is not affiliated with, endorsed by, or\n"
        "connected to Southwest Airlines Co. All rights reserved.\n"
        "Unauthorized use, reproduction, or distribution of this code is\n"
        "strictly prohibited.\n",
        status_code=200
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)