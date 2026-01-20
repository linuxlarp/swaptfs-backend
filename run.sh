#!/bin/bash
# FOR LINUX/DEBIAN USE ONLY

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
BACKUP_DIR="/root/BACKUPS/BACKEND"
DATA_DB="$PROJECT_DIR/data/airline.db"
MAIN_SCRIPT="main.py"

mkdir -p "$LOG_DIR"

mkdir -p "$BACKUP_DIR"

log() {

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/runner.log"

}

cleanup() {

    if [[ -d "$VENV_DIR" ]]; then

        rm -rf "$VENV_DIR"

    fi

}

trap cleanup EXIT SIGINT SIGTERM

log "=== SWA FastAPI Backend Runner ==="

if [[ -f "$DATA_DB" ]]; then

    BACKUP_DATE=$(date '+%Y-%m-%d_%H-%M-%S')

    BACKUP_FILE="$BACKUP_DIR/${BACKUP_DATE}-airline.db"

    cp "$DATA_DB" "$BACKUP_FILE"

    log "Database backed up to $BACKUP_FILE"

fi

if [[ -d "$VENV_DIR" ]]; then

    rm -rf "$VENV_DIR"

fi

log "Creating new virtual environment..."

python3 -m venv "$VENV_DIR"

source "$VENV_DIR/bin/activate"

log "Upgrading pip..."

pip install --upgrade pip > /dev/null 2>&1

if [[ -f "requirements.txt" ]]; then

    log "Installing dependencies..."

    pip install -r requirements.txt | tee -a "$LOG_DIR/pip-install.log"

else

    log "Error: requirements.txt not found!"

    exit 1

fi

if [[ ! -f "$MAIN_SCRIPT" ]]; then

    log "Error: $MAIN_SCRIPT not found!"

    exit 1

fi

log "Starting application: $MAIN_SCRIPT"

python "$MAIN_SCRIPT" 2>&1 | tee "$LOG_DIR/app.log"

log "Application exited."

exit 0