"""Simple real authentication: salted PBKDF2 password hashes, one data folder per user."""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path

USERS_FILE = Path(__file__).parent / "data" / "users.json"
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
ITERATIONS = 200_000


def _load():
    try:
        return json.loads(USERS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(users):
    USERS_FILE.parent.mkdir(exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)


def register(username: str, display_name: str, password: str):
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        return False, "Username must be 3-20 characters: letters, numbers or underscore."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    users = _load()
    if username in users:
        return False, "That username is already taken."
    salt = os.urandom(16)
    users[username] = {
        "display_name": display_name.strip() or username,
        "salt": salt.hex(),
        "hash": _hash(password, salt).hex(),
    }
    _save(users)
    return True, "Account created. You can log in now."


def login(username: str, password: str):
    username = username.strip().lower()
    user = _load().get(username)
    salt = bytes.fromhex(user["salt"]) if user else b"\x00" * 16
    expected = bytes.fromhex(user["hash"]) if user else b"\x00" * 32
    ok = hmac.compare_digest(_hash(password, salt), expected) and user is not None
    if not ok:
        return None
    return {"username": username, "display_name": user["display_name"]}
