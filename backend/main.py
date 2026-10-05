"""Campus Customs API.

Serves the product catalogue, stock levels and product images from
data/campus_customs.db, account sign-up and login (password hashing and signed
session cookies are below), live weather picks, and the shopping-assistant chat
(agent.py, with tools.py, models.py and prompts/prompt.md).

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000
"""

from collections import defaultdict, deque
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from agent import MAX_HISTORY_TURNS, chat
from models import (
    ChatDeps,
    ChatHistoryMessage,
    ChatReply,
    ChatRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
    WeatherPick,
)
from tools import (
    MissingModelKey,
    PRODUCT_QUERY,
    ROOT,
    SIZE_ORDER,
    clear_history,
    connect,
    current_weather,
    ensure_index,
    image_url,
    load_customer,
    load_history,
    recent_turns,
    resolve_page,
    save_exchange,
    sizes_in_stock,
)

# --- Password hashing and signed session cookies ---
#
# Passwords are never stored. We store a salted PBKDF2-SHA256 hash:
#     pbkdf2_sha256$<iterations>$<salt>$<hex digest>     (new accounts)
#     pbkdf2_sha256$<salt>$<hex digest>                  (seed accounts, 120,000 iterations)
# Seed-format hashes are upgraded to the stronger format the next time that user logs in.
# (.env files are loaded when tools is imported, so SESSION_SECRET is available here.)

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000          # OWASP 2023 recommendation for PBKDF2-SHA256
LEGACY_ITERATIONS = 120_000   # what the seed database used

SESSION_COOKIE = "cc_session"
SESSION_SECONDS = 7 * 24 * 60 * 60

# Signs session cookies so they can't be forged. Set SESSION_SECRET in .env to keep
# people logged in across restarts; otherwise a random secret is made at startup.
SESSION_SECRET = (os.getenv("SESSION_SECRET") or secrets.token_hex(32)).encode()


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def _parse(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == ALGORITHM and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 3 and parts[0] == ALGORITHM:
        return LEGACY_ITERATIONS, parts[1], parts[2]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse(stored)
    if parsed is None:
        return False
    iterations, salt, digest = parsed
    # Constant-time comparison, so response timing doesn't leak how close a guess was.
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parsed = _parse(stored)
    return parsed is None or parsed[0] < ITERATIONS or len(stored.split("$")) != 4


# Used when an email isn't registered, so a login attempt takes the same time either
# way and attackers can't tell which emails have accounts.
DUMMY_HASH = hash_password(secrets.token_hex(16))


def _sign(payload: str) -> str:
    return hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_session_token(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time()) + SESSION_SECONDS}"
    return f"{payload}.{_sign(payload)}"


def read_session_token(token: str | None) -> int | None:
    """Return the user ID if the token is genuine and unexpired, else None."""
    if not token or token.count(".") != 2:
        return None
    user_id, expires, signature = token.split(".")
    if not hmac.compare_digest(_sign(f"{user_id}.{expires}"), signature):
        return None
    if not (user_id.isdigit() and expires.isdigit()) or int(expires) < time.time():
        return None
    return int(user_id)


# --- Accounts: create account, log in, log out, who am I ---

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory throttle: after 5 failed logins for the same email from the same
# address within 15 minutes, further attempts are refused until the window passes.
MAX_FAILURES, FAILURE_WINDOW = 5, 15 * 60
_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _user_out(row: sqlite3.Row) -> UserOut:
    # Seed users may predate the first/last name columns, so fall back to `name`.
    first, _, last = (row["name"] or "").partition(" ")
    return UserOut(
        id=row["id"],
        first_name=row["first_name"] or first,
        last_name=row["last_name"] or last,
        email=row["email"],
    )


def _start_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user_id),
        max_age=SESSION_SECONDS,
        httponly=True,   # page scripts can't read it
        samesite="lax",  # other sites can't send it with forged form posts
        secure=False,    # set True when served over HTTPS
        path="/",
    )


def _too_many_failures(key: tuple[str, str]) -> bool:
    attempts = _failures[key]
    while attempts and attempts[0] < time.time() - FAILURE_WINDOW:
        attempts.popleft()
    return len(attempts) >= MAX_FAILURES


def current_user(request: Request) -> UserOut | None:
    """The logged-in user for this request, or None."""
    user_id = read_session_token(request.cookies.get(SESSION_COOKIE))
    if user_id is None:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_out(row) if row else None


@router.post("/register", status_code=201)
def register(body: RegisterRequest, response: Response) -> UserOut:
    password_hash = hash_password(body.password)
    try:
        with connect(write=True) as conn:
            cursor = conn.execute(
                """INSERT INTO users (name, email, password_hash, first_name, last_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    f"{body.first_name} {body.last_name}",
                    body.email,
                    password_hash,
                    body.first_name,
                    body.last_name,
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    _start_session(response, row["id"])
    return _user_out(row)


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> UserOut:
    email = body.email.strip().lower()
    key = (request.client.host if request.client else "unknown", email)
    if _too_many_failures(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")

    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()

    # Always run a hash check, even for unknown emails, and give one generic error,
    # so attackers can't learn which emails are registered.
    if not verify_password(body.password, row["password_hash"] if row else DUMMY_HASH) or row is None:
        _failures[key].append(time.time())
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _failures.pop(key, None)
    if needs_rehash(row["password_hash"]):
        with connect(write=True) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(body.password), row["id"]),
            )
    _start_session(response, row["id"])
    return _user_out(row)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(request: Request) -> UserOut:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


# Cleaned photos (same stone background and framing, from scripts/clean_product_images.py)
# are served when present; otherwise the originals.
CLEAN_IMAGES_DIR = ROOT / "data" / "products_clean"
IMAGES_DIR = CLEAN_IMAGES_DIR if CLEAN_IMAGES_DIR.is_dir() else ROOT / "data" / "products"

log = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(router)
ensure_index()

# Only the product photo folder is public, so the database file itself is
# never reachable over HTTP.
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


def product_from_row(row: sqlite3.Row) -> dict:
    """Turn a catalogue row into the JSON shape the front end uses."""
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "colors": json.loads(row["colors"]),
        "search_tags": json.loads(row["search_tags"]),
        "image_url": image_url(row),
        "price": row["price"],
        "total_stock": row["total_stock"],
        "sizes_in_stock": sizes_in_stock(row),
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/products")
def list_products() -> list[dict]:
    """Every catalogue product, with total units in stock."""
    with connect() as conn:
        rows = conn.execute(
            PRODUCT_QUERY + " GROUP BY c.product_id ORDER BY c.name"
        ).fetchall()
    return [product_from_row(row) for row in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    """One product, with stock broken down by size."""
    with connect() as conn:
        row = conn.execute(
            PRODUCT_QUERY + " WHERE c.product_id = ? GROUP BY c.product_id",
            (product_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Product not found")
        stock = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?",
            (product_id,),
        ).fetchall()

    product = product_from_row(row)
    product["inventory"] = sorted(
        ({"size": s["size"], "quantity": s["quantity"]} for s in stock),
        key=lambda s: SIZE_ORDER.index(s["size"]) if s["size"] in SIZE_ORDER else 99,
    )
    return product


@app.get("/api/weather")
def weather() -> WeatherPick:
    """Live New Haven weather plus 4 in-stock products that suit it (cached 20 minutes)."""
    pick = current_weather()
    if pick is None:
        raise HTTPException(status_code=503, detail="Weather unavailable")
    return pick


# --- Chat ---

# Each message costs a model call, so cap how fast one address can send them.
CHAT_LIMIT, CHAT_WINDOW = 15, 60
BLOCKED_REPLY = (
    "Sorry, I can't help with that. I'm happy to help you find Campus Customs gear, "
    "though. Are you looking for a hoodie, crewneck, tee or something else?"
)
_chat_times: dict[str, deque[float]] = defaultdict(deque)


def _chat_rate_limited(client: str) -> bool:
    times = _chat_times[client]
    while times and times[0] < time.time() - CHAT_WINDOW:
        times.popleft()
    if len(times) >= CHAT_LIMIT:
        return True
    times.append(time.time())
    return False


@app.post("/api/chat")
async def chat_route(body: ChatRequest, request: Request) -> ChatReply:
    """Send one shopper message to the agent and return its reply plus product cards.

    Logged-in shoppers: history is read from and saved to chat_messages.
    Guests: the browser's recent turns are used and nothing is saved.
    """
    if _chat_rate_limited(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="You're sending messages quickly. Please wait a moment.")

    user = current_user(request)
    customer = load_customer(user) if user else None
    history = recent_turns(user.id, MAX_HISTORY_TURNS) if user else body.history
    deps = ChatDeps(customer=customer, current_page=resolve_page(body.page), weather=current_weather())
    try:
        reply = await chat(body.message, history, deps)
    except ModelHTTPError as err:
        # The model provider's safety filter blocks jailbreak or harmful prompts before they
        # reach the model. Answer with a polite refusal instead of an error.
        if "content_filter" not in str(err.body):
            log.exception("Chat failed")
            raise HTTPException(status_code=502, detail="The assistant is unavailable right now. Please try again.")
        log.warning("Chat message blocked by the provider's content filter")
        reply = ChatReply(reply=BLOCKED_REPLY, products=[])
    except MissingModelKey as err:
        log.warning(str(err))
        raise HTTPException(status_code=503, detail="The shopping assistant isn't set up yet: add PORTKEY_API_KEY to hw4/.env and restart the backend.")
    except UsageLimitExceeded:
        log.warning("Chat hit its usage limit")
        raise HTTPException(status_code=502, detail="That question took too long to answer. Try asking it more simply.")
    except Exception:
        log.exception("Chat failed")
        raise HTTPException(status_code=502, detail="The assistant is unavailable right now. Please try again.")

    if user:
        save_exchange(user.id, body.message, reply)
    return reply


@app.get("/api/chat/history")
def chat_history(request: Request) -> list[ChatHistoryMessage]:
    """The logged-in shopper's saved messages (oldest first). Guests get an empty list."""
    user = current_user(request)
    return load_history(user.id) if user else []


@app.post("/api/chat/history/clear", status_code=204)
def chat_history_clear(request: Request) -> None:
    """Delete the logged-in shopper's saved chat."""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    clear_history(user.id)
