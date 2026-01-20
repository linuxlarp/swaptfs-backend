import os
from dotenv import load_dotenv
from core.logger import Logger

load_dotenv()


## // Basic Server-wide config
PORT = int(os.getenv("PORT", 6942))
VERSION = "2.5.0 DEV"
SESSION_SECRET = os.getenv("SESSION_SECRET")
BLOXLINK_API_KEY = os.getenv("BLOXLINK_API_KEY")
SERVER_INVITE = os.getenv("DISCORD_INVITE", "https://discord.gg/southwestptfs")
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
DEBUG_LOGS = os.getenv("DEBUG_LOGS", "false").lower() == "false"
LOGS = Logger() 

ALLOWED_ORIGINS = [
    "https://api.southwestptfs.com",
    "https://prod.southwestptfs.com",
    "https://southwestptfs.com",
    "https://api.southwestptfs.com",
    "https://luvcrew.southwestptfs.com",
    "https://staging.southwestptfs.com",
    "https://dev.southwestptfs.com",
]

if DEV_MODE:
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:6942",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:6942"
    ]


## // Database Configuration
DB_SCHEMA = {
    "flights": [
        'id TEXT PRIMARY KEY',
        '"from" TEXT NOT NULL',
        '"to" TEXT NOT NULL',
        'aircraft TEXT NOT NULL',
        'departure TEXT NOT NULL',
        'seats INTEGER NOT NULL',
        'booked INTEGER DEFAULT 0',
        'acftReg TEXT NOT NULL',
        'deptGate TEXT NOT NULL',
        'arrGate TEXT NOT NULL',
        'codeshareIds TEXT',

        # Ingame details / other details
        'host TEXT',
        'discordEventId TEXT'
        'robloxPrivateServerLink TEXT',
    ],

    "bookings": [
        'confirmationNumber TEXT PRIMARY KEY',
        'userId TEXT NOT NULL',
        'username TEXT',
        'flightId TEXT NOT NULL',
        'bookedAt TEXT NOT NULL',
        'boardingGroup TEXT',
        'boardingPosition TEXT',
        'checkedInAt TEXT',
        'FOREIGN KEY (flightId) REFERENCES flights(id)',
        'FOREIGN KEY (userId) REFERENCES users(id)',
    ],

    "users": [
        'id TEXT PRIMARY KEY',
        'robloxId TEXT',
        'username TEXT NOT NULL',
        'discriminator TEXT NOT NULL',
        'avatar TEXT',
        'points INTEGER DEFAULT 0',
        'apiToken TEXT',
        'isAdmin BOOLEAN DEFAULT 0',
        'isBot BOOLEAN DEFAULT 0',
        'isStaff BOOLEAN DEFAULT 0',
        'isFlightStaff BOOLEAN DEFAULT 0',
        'rapidRwdStatus TEXT DEFAULT \'Base\'',
        'flightsAttended INTEGER DEFAULT 0',
        'hasEarlyBird BOOLEAN DEFAULT 0',

        'email TEXT',
        'emailVerified BOOLEAN DEFAULT 0',
        'subscribed BOOLEAN DEFAULT 0',
    ],

    "baggage": [
        'owner TEXT PRIMARY KEY',
        'username TEXT NOT NULL',
        'confirmationNumber TEXT NOT NULL',
        'checkedBags INTEGER',
        'carryOnBags INTEGER',
        'pointsCharged INTEGER',
        'timestamp DATETIME DEFAULT CURRENT_TIMESTAMP',
    ],

    "banned_users": [
        'userId TEXT PRIMARY KEY',
        'reason TEXT',
    ],
    
}

DB_PATH = os.getenv("DB_PATH", "./data/airline.db")



## // Discord Login Config
DISCORD_SERVER_ID = os.getenv("DISCORD_SERVER_ID")
DISCORD_BOT_USERNAME = os.getenv("DISCORD_BOT_USERNAME")
DISCORD_BOT_DISCRIMINATOR = os.getenv("DISCORD_BOT_DISCRIM")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_SCOPE = "identify"

## // Website/UX Config
EARLYBIRD_PRICE = 30000
