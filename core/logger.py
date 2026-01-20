import os
import logging
import json
import datetime
import traceback
import re
import config

from dotenv import load_dotenv
from pathlib import Path
from colorama import init as colorama_init, Fore, Back, Style

colorama_init(autoreset=True)
load_dotenv()

def _strip_ansi(s: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

class Logger:
    def __init__(self):
        self.log_dir = Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self._today_file()

        self.levels = {
            "error": (Fore.RED + Style.BRIGHT, "[ERROR]"),
            "warn": (Fore.YELLOW + Style.BRIGHT, "[WARN]"),
            "info": (Fore.BLUE + Style.BRIGHT, "[INFO]"),
            "success": (Fore.GREEN + Style.BRIGHT, "[SUCCESS]"),
            "debug": (Fore.WHITE + Style.DIM, "[DEBUG]"),
            "db": (Fore.MAGENTA + Style.BRIGHT, "[DATABASE]"),
            "http": (Back.BLUE + Fore.WHITE + Style.BRIGHT, "[HTTP]"),
            "auth": (Fore.GREEN + Style.BRIGHT, "[AUTH]"),
            "flight": (Fore.MAGENTA + Style.BRIGHT, "[FLIGHT]"),
            "booking": (Fore.CYAN + Style.BRIGHT, "[BOOKING]"),
        }

    def _today_file(self) -> Path:
        return self.log_dir / f"{datetime.datetime.now():%Y-%m-%d}.log"

    def _timestamp(self) -> str:
        return f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S.%f}]"[:-4] + "]"

    def _append_to_file(self, line: str):
        with open(self.log_file, "a", encoding="utf8") as f:
            f.write(line + "\n")

    def _log(self, level: str, message: str, data=None):
        if level not in self.levels:
            level = "info"
        color_code, prefix = self.levels[level]
        timestamp = self._timestamp()
        color_prefix = f"{color_code}{prefix}{Style.RESET_ALL}"

        console_line = f"{Fore.LIGHTBLACK_EX}{timestamp}{Style.RESET_ALL} {color_prefix} {message}"
        file_line = f"{timestamp} {prefix} { _strip_ansi(message) }"

        print(console_line)
        self._append_to_file(file_line)

        if data is not None:
            if isinstance(data, BaseException):
                detail = "".join(traceback.format_exception(type(data), data, data.__traceback__)).rstrip()
            elif isinstance(data, (dict, list, tuple)):
                detail = json.dumps(data, indent=2, default=str)
            else:
                detail = str(data)

            formatted = f" └─ {detail}"
            print(f"{Fore.LIGHTBLACK_EX}{formatted}{Style.RESET_ALL}")
            self._append_to_file(_strip_ansi(formatted))

    def error(self, m, d=None): self._log("error", m, d)
    def warn(self, m, d=None): self._log("warn", m, d)
    def info(self, m, d=None): self._log("info", m, d)
    def success(self, m, d=None): self._log("success", m, d)
    def debug(self, m, d=None):
        if config.DEV_MODE == "true" and config.DEBUG_LOGS == "true":
            self._log("debug", m, d)

    def http(self, method: str, path: str, status_code: int, duration: int, user_id: str = None):
        method_colors = {
            "GET": Fore.GREEN,
            "POST": Fore.BLUE,
            "PUT": Fore.YELLOW,
            "DELETE": Fore.RED,
            "PATCH": Fore.CYAN,
        }
        method_color = method_colors.get(method.upper(), Fore.WHITE) + Style.BRIGHT
        status_color = Fore.RED if status_code >= 500 else (Fore.YELLOW if status_code >= 400 else (Fore.CYAN if status_code >= 300 else Fore.GREEN))
        user_info = f"{Fore.LIGHTBLACK_EX}| User: {user_id}{Style.RESET_ALL}" if user_id else ""
        duration_str = f"{Fore.LIGHTBLACK_EX}{duration}ms{Style.RESET_ALL}"

        method_str = (method_color + method.upper().ljust(6) + Style.RESET_ALL)
        path_str = path.ljust(40)
        status_str = status_color + str(status_code) + Style.RESET_ALL

        msg = f"{method_str} {path_str} {status_str} {duration_str}{(' ' + user_info) if user_info else ''}"
        self._log("http", msg)

    def db(self, message: str, duration: int = None):
        duration_str = (
            f"{Fore.LIGHTBLACK_EX} ({duration}ms){Style.RESET_ALL}"
            if duration is not None
            else f"{Style.RESET_ALL}"
        )
        self._log("db", f"{message} {duration_str}")


    def flight(self, message, data=None): self._log("flight", message, data)
    def booking(self, message, data=None): self._log("booking", message, data)
    def auth(self, message, data=None): self._log("auth", message, data)

    def startup(self):
        os.system("cls" if os.name == "nt" else "clear")
        banner = f"""
{Fore.BLUE + Style.BRIGHT}
        ┌────────────────────────────────────────────────────────────┐
        │                                                            │
        │                   SouthwestPTFS Backend                    │
        │                                                            │
        └────────────────────────────────────────────────────────────┘
{Style.RESET_ALL}
"""
        print(banner)
        print(Fore.LIGHTBLACK_EX + "  Configuration:" + Style.RESET_ALL)
        print(Fore.LIGHTBLACK_EX + f"  ├─ Port:         {Style.RESET_ALL}{config.PORT}")
        print(Fore.LIGHTBLACK_EX + f"  ├─ DevMode:      {Style.RESET_ALL}{os.getenv('DEV_MODE', False)}")
        print(Fore.LIGHTBLACK_EX + f"  ├─ Version:      {Style.RESET_ALL}{config.VERSION}")
        print(Fore.LIGHTBLACK_EX + f"  └─ Database:     {Style.RESET_ALL}/data/airline.db")
        print()
        self._append_to_file(f"\n--- Startup at {datetime.datetime.now().isoformat()} ---\n")
        self._append_to_file(f"Port: {config.PORT}, DevMode: {os.getenv('DEV_MODE', False)}, DB: /data/airline.db\n")

    def rotate_logs(self):
        new_file = self._today_file()
        if self.log_file != new_file:
            self.log_file = new_file
            self._append_to_file(f"\n--- Log rotation at {datetime.datetime.now().isoformat()} ---\n")


logger = Logger()
