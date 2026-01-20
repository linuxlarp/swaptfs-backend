# Southwest Airlines PTFS (FastAPI Backend)
![Version 2.5.0 (Latest)](https://img.shields.io/badge/Version-2.5.0-red)
![FastAPI](https://img.shields.io/badge/Made_With-FastAPI-cyan)
![FastAPI](https://img.shields.io/badge/Database-SQLite3-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Python Version](https://img.shields.io/badge/Python-3.14-yellow)
[![Better Stack Badge](https://uptime.betterstack.com/status-badges/v1/monitor/28rgx.svg)](https://uptime.betterstack.com/?utm_source=status_badge)


## Overview
This repository contains the FastAPI backend I built for Southwest PTFS. It handled RESTful APIs, business logic, database integration, and authentication for both the website and our Discord applications. The group has since shut down, but I still own all rights to the code, and I’m open-sourcing it under the MIT license because I’m a FOSS advocate and want others to be able to **learn from and reuse this work**. I’m not providing ongoing modern support unless there are critical security issues that clearly need to be addressed.

This project is under the MIT license, meaning you may profit from my work or use it for your own projects, as long as you keep the original copyright and license notice. You are free to copy, modify, merge, publish, distribute, sublicense, and sell copies of the software, including as part of commercial products or services.  The software is provided “as is,” with no warranty, so you assume all responsibility for how you use it and any issues that may arise. ​

If you notice that this is the only commit in this repository, it’s because all of the code was merged in from a separate repository. I recently merged the latest `devops` branch into `main` from the previous repository, so I can’t guarantee the current state is fully functional, and you may need to do some manual debugging to get everything running smoothly.

## Tech Stack
- Framework: FastAPI
- Runtime: Python 3.9+
- Packaging: pip
- Database: SQLite 3

## Configuration
Environment variables:
```bash
## Basic Configuration
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=
DISCORD_BOT_ID=
DISCORD_BOT_USERNAME=
DISCORD_BOT_DISCRIM =
DISCORD_BOT_TOKEN = 
DEV_MODE=false/true
DEBUG_LOGS=false/true

## Server Configuration
PORT=
DEBUG=false
BASE_REDIRECT="https://southwestptfs.com"
SESSION_SECRET=
TURNSTILE_SITEKEY=
TURNSTILE_SECRET=
UNSPLASH_ACCESS_KEY=
UNSPLASH_SECRET_KEY=
DISCORD_INVITE="https://discord.gg/southwest"
API_BASE="https://dev.southwestptfs.com"

# SendRecieveServer (Discord Bot Communication)
SRS_URL = "https://srs.southwestptfs.com"
SRS_PASSWORD =
```


Store secrets securely; do not commit `.env` files to source control.

## Local development
1. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2. Run dev server:
    ```bash
    uvicorn app.main:app --reload
    OR
    python main.py
    ```
    Open http://localhost:8000/docs

## Production Build
We use [Docker](https://docs.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) for production. Visit https://docker.com for more information.

```bash
docker compose up --build -d # To freshly build
docker compose up -d # Use last build
```

## Acknowledgements
- **FastAPI & Uvicorn**
- **Starlette**
- **aiohttp**
- **pillow**

## AI Usage
AI (Artificial Intelligence) was used in this project to do the following:
- **Write Documentation**
- **Commit Message Documentation**

## License
```
Copyright © 2026 linuxlarp

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
