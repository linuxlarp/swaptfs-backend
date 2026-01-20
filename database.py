import sqlite3
import time
import config
import os

from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Sequence, Union
from pathlib import Path

load_dotenv()
logger = config.LOGS

data_dir = Path(__file__).parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)

logger.db(f"Ensured data directory exists: {data_dir}")
db_path = data_dir / "airline.db"

try:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    logger.db(f"Connected to SQLite database at: {str(db_path)}")
except sqlite3.Error as e:
    logger.error("Error opening database:", e)
    raise

def safe_execute(sql: str, params=None, success_msg=None, error_msg=None):
    start = time.time()

    try:
        if params:
            conn.execute(sql, params)
        else:
            conn.execute(sql)

        conn.commit()
        if success_msg:
            logger.db(success_msg, int((time.time() - start) * 1000))

    except sqlite3.Error as e:
        msg = str(e).lower()
        if "duplicate column name" in msg or ("column" in msg and "already exists" in msg):
            logger.db(success_msg or "Column already exists or ignored.", int((time.time() - start) * 1000))
        else:
            if error_msg:
                logger.error(error_msg, e)
            else:
                logger.error("SQL error:", e)



def _ensure_table(name, cols):
    logger.db(f"Performing integrity check on table: {name}")

    sql = f"CREATE TABLE IF NOT EXISTS {name} ({', '.join(cols)})"
    safe_execute(sql, success_msg=f"Table {name} created/existing...")

    cur = db.cursor()
    cur.execute(f"PRAGMA table_info({name})")
    existing = {row[1]for row in cur.fetchall()}

    for col_def in cols:
        if "FOREIGN KEY" in col_def.upper():
            continue  # Skip FK lines

        col_name = col_def.strip().split()[0].strip('`"\'')

        if col_name not in existing:
            add_sql = f'ALTER TABLE {name} ADD COLUMN {col_def}'
            safe_execute(add_sql, success_msg=f"Added {name}.{col_name}")
        else:
            pass

    logger.success(f"Integrity check complete for table: {name}, no issues found!")


def _add_bot():
    sql = """INSERT OR IGNORE INTO users
             (id, username, discriminator, isBot, isAdmin, apiToken)
             VALUES (?,?,?,?,?,?)"""
    safe_execute(sql,
                 params=(
                     config.DISCORD_CLIENT_ID,
                     config.DISCORD_BOT_USERNAME,
                     config.DISCORD_BOT_DISCRIMINATOR,
                     1, 1,
                     config.DISCORD_BOT_TOKEN
                 ),
                 success_msg="Bot account ready!")

def initialize_database():
    db.execute("PRAGMA foreign_keys = ON")

    logger.db("Initalizing and starting database...")
    start = time.time()
    
    logger.db("Performing database integrity check...")
    for name, cols in config.DB_SCHEMA.items():
        _ensure_table(name, cols)

    logger.db("Adding foreign keys...")
    logger.db("Registering bot account...")
    _add_bot()

    logger.success(f"Database initilzation complete! Took {round(time.time() - start, 4)} ms")


Params = Union[Sequence[Any], Dict[str, Any]]

def _get_conn(c: Optional[sqlite3.Connection]) -> sqlite3.Connection:
    return c or conn

def run_query(query: str, params: Params = (), c: Optional[sqlite3.Connection] = None) -> Dict[str, int]:
    connection = _get_conn(c)
    cur = connection.cursor()
    cur.execute(query, params)
    connection.commit()
    return {"lastrowid": cur.lastrowid, "rowcount": cur.rowcount}

def get_query(query: str, params: Params = (), c: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    connection = _get_conn(c)
    connection.row_factory = sqlite3.Row
    cur = connection.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def get_one_query(query: str, params: Params = (), c: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    connection = _get_conn(c)
    connection.row_factory = sqlite3.Row
    cur = connection.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    return dict(row) if row is not None else None

def get_all_query(query: str, params: Params = (), c: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    return get_query(query, params, c)

def begin_transaction(c: Optional[sqlite3.Connection] = None) -> None:
    _get_conn(c).execute("BEGIN TRANSACTION")

def commit_transaction(c: Optional[sqlite3.Connection] = None) -> None:
    _get_conn(c).commit()

def rollback_transaction(c: Optional[sqlite3.Connection] = None) -> None:
    _get_conn(c).rollback()


db = conn
