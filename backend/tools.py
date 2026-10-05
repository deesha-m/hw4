"""Tools and helpers for the Campus Customs chat agent."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path
import json
import logging
import threading
import os
import re
import sqlite3
import ssl
import time
import urllib.parse
import urllib.request

import certifi
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.messages import ModelMessage, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic import ValidationError
from pydantic_core import to_jsonable_python
from pydantic_ai.providers.openai import OpenAIProvider

from models import (
    ChatHistoryMessage,
    ChatReply,
    ChatTurn,
    CustomerInfo,
    UserOut,
    WeatherPick,
    AuditEntry,
    AuditStep,
    AuditToolCall,
    AuditUsage,
    Alternative,
    Alternatives,
    CurrentPage,
    PageContext,
    PageProduct,
    PageResults,
    PriceInfo,
    ProductCard,
    ProductInfo,
    ProductNotFound,
    ProductSummary,
    SizeNotOffered,
    SizeStock,
    StockCheck,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs.db"
log = logging.getLogger("campus_customs")

# Secrets come from a .env file: homework/4 first, then the course folder (AI Foundations).
for env_file in (HERE.parent / ".env", HERE.parents[2] / ".env"):
    load_dotenv(env_file, override=False)
MODEL_NAME = os.getenv("CAMPUS_CUSTOMS_MODEL", "gpt-5.6-luna")

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
LOW_STOCK = 5  # 1-5 units left counts as low stock (matches the product page)
MAX_RESULTS = 8
MAX_PRICE_LOOKUPS = 10
MAX_PAGE_RESULTS = 30

# How shoppers write sizes -> the size codes in the inventory table.
SIZE_ALIASES = {
    "xs": "XS", "xsmall": "XS", "extrasmall": "XS",
    "s": "S", "sm": "S", "small": "S",
    "m": "M", "med": "M", "medium": "M",
    "l": "L", "lg": "L", "large": "L",
    "xl": "XL", "xlarge": "XL", "extralarge": "XL",
    "xxl": "XXL", "2xl": "XXL", "xxlarge": "XXL", "2xlarge": "XXL",
}

# Shopper words that don't literally appear in the catalogue text.
SYNONYMS = {
    "hoodie": ["hoodie", "hooded"],
    "hoodies": ["hoodie", "hooded"],
    "sweatshirt": ["sweatshirt", "crewneck", "hoodie"],
    "tee": ["t-shirt", "tee"],
    "tees": ["t-shirt", "tee"],
    "tshirt": ["t-shirt"],
    "shirt": ["t-shirt", "shirt"],
    "crew": ["crewneck"],
    "quarterzip": ["quarter-zip", "1/4 zip"],
    "zip": ["zip"],
    "fleece": ["fleece"],
    "jacket": ["jacket"],
    "grey": ["gray"],
    "hoody": ["hoodie", "hooded"],
    "hoodys": ["hoodie", "hooded"],
    "pullover": ["pullover"],
}
FUZZY_CUTOFF = 0.8  # how close a misspelling must be to a real catalogue word (0-1)
STOPWORDS = {"a", "an", "and", "any", "do", "for", "have", "i", "in", "is", "me", "my", "of",
             "show", "some", "the", "to", "want", "with", "you", "your", "what", "looking"}


# --- Database access ---


@contextmanager
def connect(write: bool = False) -> Iterator[sqlite3.Connection]:
    """Open the database for one block of work, then commit and close it.

    Read-only unless the caller needs to write (e.g. sign-up).
    """
    if write:
        conn = sqlite3.connect(DB_PATH)
    else:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- Model ---


def get_model() -> OpenAIChatModel:
    """The course model (gpt-5.6-luna by default) through the Portkey gateway."""
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY was not found in homework/4/.env or the course .env")
    client = AsyncOpenAI(
        base_url="https://api.portkey.ai/v1",
        api_key=key,
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
        timeout=60,
        max_retries=2,
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# --- Database helpers ---

PRODUCT_QUERY = """
    SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock,
           GROUP_CONCAT(CASE WHEN i.quantity > 0 THEN i.size END) AS sizes_csv
    FROM catalogue c
    LEFT JOIN inventory i ON i.product_id = c.product_id
"""


def sizes_in_stock(row: sqlite3.Row) -> list[str]:
    """Sizes with at least one unit, XS to XXL, from PRODUCT_QUERY's sizes_csv column."""
    have = set((row["sizes_csv"] or "").split(","))
    return [size for size in SIZE_ORDER if size in have]


# Bump when the served photos change (e.g. re-running scripts/clean_product_images.py), so
# browsers fetch the new files instead of showing cached ones.
IMAGE_VERSION = "clean-3"


def image_url(row: sqlite3.Row) -> str:
    return f"/images/{Path(row['image_file_path']).name}?v={IMAGE_VERSION}"


def _shorten(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _stem(word: str) -> str:
    """Crude plural -> singular: 'hoodies' -> 'hoodie', 't-shirts' -> 't-shirt'."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


@lru_cache
def _vocabulary() -> tuple[str, ...]:
    """Every word used in the catalogue (names, types, tags, colors), for spelling fixes."""
    with connect() as conn:
        rows = conn.execute("SELECT name, garment_type, search_tags, colors FROM catalogue").fetchall()
    words = set(SYNONYMS)
    for row in rows:
        text = " ".join(row).lower()
        words.update(w for w in re.findall(r"[a-z0-9'-]+", text) if len(w) > 2)
    return tuple(sorted(words))


def _correct(word: str) -> str:
    """Fix a misspelled query word: 'crewnek' -> 'crewneck'. Known words are left alone."""
    vocab = _vocabulary()
    if word in vocab or _stem(word) in vocab or len(word) < 4 or word.isdigit():
        return word
    match = get_close_matches(word, vocab, n=1, cutoff=FUZZY_CUTOFF)
    return match[0] if match else word


def _terms(query: str) -> list[list[str]]:
    """Split a query into words, each spell-checked and expanded to the catalogue words it can match."""
    words = [w for w in re.findall(r"[a-z0-9/'-]+", query.lower()) if w not in STOPWORDS]
    terms = []
    for word in words:
        word = _correct(word)
        key = word.replace("-", "")
        options = SYNONYMS.get(key) or SYNONYMS.get(_stem(key)) or [_stem(word)]
        terms.append(options)
    return terms


def corrected_query(query: str) -> str:
    """The query as the search understood it, e.g. 'crewnek sweatshrits' -> 'crewneck sweatshirts'."""
    return " ".join(_correct(w) for w in re.findall(r"[a-z0-9/'-]+", query.lower()))


def _score(row: sqlite3.Row, terms: list[list[str]]) -> tuple[int, float]:
    """(how many query words matched, weighted score). Name and type count most."""
    fields = [
        (row["name"].lower(), 3),
        (row["garment_type"].lower(), 3),
        (row["search_tags"].lower(), 2),
        (row["colors"].lower(), 2),
        (row["description"].lower(), 1),
    ]
    matched, score = 0, 0.0
    for options in terms:
        best = max((weight for text, weight in fields if any(o in text for o in options)), default=0)
        matched += best > 0
        score += best
    return matched, score


# --- Tools ---


def _matching_rows(
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[sqlite3.Row]:
    """Catalogue rows matching a keyword query and filters, best first.

    If some products match every query word, only those are kept ("navy hoodies" means navy
    AND hoodie). Otherwise, products matching any word are ranked by score.
    """
    size = normalize_size(size) or size.upper().strip() if size else None
    terms = _terms(query)
    with connect() as conn:
        rows = conn.execute(PRODUCT_QUERY + " GROUP BY c.product_id").fetchall()
        in_size = (
            {r["product_id"] for r in conn.execute(
                "SELECT product_id FROM inventory WHERE size = ? AND quantity > 0", (size,))}
            if size else None
        )

    scored = []
    for row in rows:
        if in_stock_only and row["total_stock"] == 0:
            continue
        if max_price is not None and row["price"] > max_price:
            continue
        if color and not any(color.lower() in c.lower() for c in json.loads(row["colors"])):
            continue
        if in_size is not None and row["product_id"] not in in_size:
            continue
        matched, score = _score(row, terms) if terms else (0, 1.0)
        if score > 0:
            scored.append((matched, score, row))

    if terms and any(m == len(terms) for m, _, _ in scored):
        scored = [item for item in scored if item[0] == len(terms)]
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]["name"]))
    return [row for _, _, row in scored]


def _summary(row: sqlite3.Row) -> ProductSummary:
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        short_description=_shorten(row["description"]),
        total_stock=row["total_stock"],
    )


def search_products(
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[ProductSummary]:
    """Search the catalogue by keywords with optional filters, best matches first."""
    rows = _matching_rows(query, color, max_price, size, in_stock_only)
    return [_summary(row) for row in rows[:MAX_RESULTS]]


def page_results(
    title: str,
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
) -> PageResults:
    """The same search, sized for the Products page: up to 30 cards with image and short info."""
    rows = _matching_rows(query, color, max_price, size, in_stock_only=False)
    # In-stock items first, but sold-out matches still appear (marked on the card).
    rows.sort(key=lambda row: row["total_stock"] == 0)
    return PageResults(
        title=title.strip()[:80] or "Search results",
        query=query,
        total_matches=len(rows),
        products=[
            PageProduct(
                product_id=row["product_id"],
                name=row["name"],
                garment_type=row["garment_type"],
                price=row["price"],
                image_url=image_url(row),
                short_description=_shorten(row["description"], 90),
                total_stock=row["total_stock"],
                sizes_in_stock=sizes_in_stock(row),
            )
            for row in rows[:MAX_PAGE_RESULTS]
        ],
    )


def normalize_size(size: str) -> str | None:
    """'medium' -> 'M', 'x-large' -> 'XL'. None if it isn't a size the shop carries."""
    key = re.sub(r"[\s._-]", "", size.lower())
    return SIZE_ALIASES.get(key)


def stock_status(quantity: int) -> str:
    if quantity <= 0:
        return "sold_out"
    return "low_stock" if quantity <= LOW_STOCK else "in_stock"


def _not_found(product_id: str) -> ProductNotFound:
    """Suggest real products whose names look like the bad ID, so the agent can recover."""
    guesses = search_products(product_id.replace("-", " "), in_stock_only=False)[:3]
    return ProductNotFound(
        requested_id=product_id,
        message=f"No product has the id {product_id!r}. Use an id from search_products.",
        suggestions=[PriceInfo(product_id=g.product_id, name=g.name, price=g.price) for g in guesses],
    )


def get_product_info(product_id: str) -> ProductInfo | ProductNotFound:
    """Description, price and colors for one product."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        return _not_found(product_id)
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        price=row["price"],
        colors=json.loads(row["colors"]),
        description=row["description"],
        search_tags=json.loads(row["search_tags"]),
    )


def get_prices(product_ids: list[str]) -> list[PriceInfo | ProductNotFound]:
    """Prices for several products at once, in the order asked."""
    ids = list(dict.fromkeys(product_ids))[:MAX_PRICE_LOOKUPS]
    if not ids:
        return []
    with connect() as conn:
        rows = conn.execute(
            f"SELECT product_id, name, price FROM catalogue WHERE product_id IN ({','.join('?' * len(ids))})",
            ids,
        ).fetchall()
    found = {r["product_id"]: PriceInfo(product_id=r["product_id"], name=r["name"], price=r["price"]) for r in rows}
    return [found.get(pid) or _not_found(pid) for pid in ids]


def check_stock(product_id: str, size: str | None = None) -> StockCheck | ProductNotFound | SizeNotOffered:
    """Units in stock for every size of one product, plus the requested size if given."""
    requested = None
    if size:
        requested = normalize_size(size)
        if requested is None:
            return SizeNotOffered(
                requested_size=size,
                offered_sizes=SIZE_ORDER,
                message=f"Campus Customs doesn't carry size {size!r}. Sizes run XS to XXL.",
            )
    with connect() as conn:
        name = conn.execute("SELECT name FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if name is None:
            return _not_found(product_id)
        rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()

    quantities = {r["size"]: r["quantity"] for r in rows}
    # A size with no inventory row counts as sold out rather than being skipped.
    sizes = [SizeStock(size=sz, quantity=quantities.get(sz, 0), status=stock_status(quantities.get(sz, 0)))
             for sz in SIZE_ORDER]
    return StockCheck(
        product_id=product_id,
        name=name["name"],
        requested_size=requested,
        requested_size_stock=next((s for s in sizes if s.size == requested), None),
        sizes=sizes,
        available_sizes=[s.size for s in sizes if s.quantity > 0],
        sold_out_sizes=[s.size for s in sizes if s.quantity == 0],
        total_stock=sum(s.quantity for s in sizes),
    )


def garment_family(garment_type: str) -> str:
    """Group the catalogue's 22 garment-type labels into the categories shoppers think in."""
    g = garment_type.lower()
    if "hood" in g:
        return "hoodie"
    if "quarter" in g:
        return "quarter-zip"
    if "jacket" in g or "fleece" in g:
        return "jacket"
    if "t-shirt" in g or "tee" in g:
        return "t-shirt"
    if "crew" in g or "sweatshirt" in g:
        return "crewneck"
    return "other"


MAX_ALTERNATIVES = 4


def find_alternatives(product_id: str, size: str | None = None) -> Alternatives | ProductNotFound | SizeNotOffered:
    """Similar products that are in stock (in `size`, if given), most similar first.

    Similarity: same garment category first, then shared colors and tags, then closeness in price.
    """
    wanted = None
    if size:
        wanted = normalize_size(size)
        if wanted is None:
            return SizeNotOffered(requested_size=size, offered_sizes=SIZE_ORDER,
                                  message=f"Campus Customs doesn't carry size {size!r}. Sizes run XS to XXL.")
    with connect() as conn:
        rows = conn.execute(PRODUCT_QUERY + " GROUP BY c.product_id").fetchall()
        stock = {(r["product_id"], r["size"]): r["quantity"]
                 for r in conn.execute("SELECT product_id, size, quantity FROM inventory")}
    by_id = {row["product_id"]: row for row in rows}
    original = by_id.get(product_id)
    if original is None:
        return _not_found(product_id)

    family = garment_family(original["garment_type"])
    colors = {c.lower() for c in json.loads(original["colors"])}
    tags = {t.lower() for t in json.loads(original["search_tags"])}

    def available(row) -> bool:
        return stock.get((row["product_id"], wanted), 0) > 0 if wanted else row["total_stock"] > 0

    def similarity(row) -> float:
        other_colors = {c.lower() for c in json.loads(row["colors"])}
        other_tags = {t.lower() for t in json.loads(row["search_tags"])}
        price_gap = abs(row["price"] - original["price"]) / max(original["price"], 1)
        return (5 * (garment_family(row["garment_type"]) == family)
                + 2 * len(colors & other_colors) + len(tags & other_tags) - 2 * price_gap)

    candidates = [row for row in rows if row["product_id"] != product_id and available(row)]
    candidates.sort(key=similarity, reverse=True)
    return Alternatives(
        original_product_id=product_id,
        original_name=original["name"],
        size=wanted,
        alternatives=[
            Alternative(
                product_id=row["product_id"],
                name=row["name"],
                garment_type=row["garment_type"],
                price=row["price"],
                colors=json.loads(row["colors"]),
                short_description=_shorten(row["description"]),
                size_quantity=stock.get((row["product_id"], wanted)) if wanted else None,
                same_category=garment_family(row["garment_type"]) == family,
            )
            for row in candidates[:MAX_ALTERNATIVES]
        ],
    )


# --- Page context ---


RESIDENTIAL_COLLEGES = (
    "Benjamin Franklin", "Berkeley", "Branford", "Davenport", "Ezra Stiles", "Grace Hopper",
    "Jonathan Edwards", "Morse", "Pauli Murray", "Pierson", "Saybrook", "Silliman",
    "Timothy Dwight", "Trumbull",
)


def _page_type(path: str) -> str:
    if path == "/":
        return "home"
    if path == "/products":
        return "products"
    if path.startswith("/products/"):
        return "product"
    if path == "/about":
        return "about"
    if path in ("/login", "/create-account"):
        return "account"
    return "other"


def resolve_page(context: PageContext | None) -> CurrentPage | None:
    """Turn what the browser says about the page into facts from the database.

    Only IDs are taken from the browser. Names, prices and colors are looked up here, so a
    tampered request can't make the agent believe a fake price.
    """
    if context is None:
        return None
    page_type = _page_type(context.path)
    product = None
    if page_type == "product":
        product_id = context.product_id or context.path.removeprefix("/products/")
        info = get_product_info(product_id)
        product = info if isinstance(info, ProductInfo) else None
    visible = []
    if page_type == "products" and context.visible_product_ids:
        visible = [p for p in get_prices(context.visible_product_ids[:12]) if isinstance(p, PriceInfo)]
    college = next((c for c in RESIDENTIAL_COLLEGES if context.college == c), None)
    return CurrentPage(
        path=context.path,
        college=college,
        page_type=page_type,
        product=product,
        # A browser-supplied heading, so keep only plain characters before it reaches the prompt.
        results_title=re.sub(r"[^\w\s$&',.-]", "", context.results_title or "")[:80] or None if visible else None,
        visible_products=visible,
    )


# --- Grounding check helpers ---

DOLLAR_AMOUNT = re.compile(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)")


def dollar_amounts(text: str) -> set[float]:
    """Every $ amount written in a piece of text, e.g. 'from $58' -> {58.0}."""
    return {float(m.replace(",", "")) for m in DOLLAR_AMOUNT.findall(text)}


def prices_in(value) -> set[float]:
    """Every `price` field inside a tool result (models, lists, dicts)."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    found: set[float] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "price" and isinstance(item, (int, float)):
                found.add(float(item))
            else:
                found |= prices_in(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= prices_in(item)
    return found


# --- Chat helpers ---


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Turn the agent's chosen IDs into cards, straight from the database.

    Unknown IDs are dropped, so the website only ever shows real products with real prices.
    """
    ids = list(dict.fromkeys(product_ids))  # dedupe, keep order
    if not ids:
        return []
    with connect() as conn:
        rows = conn.execute(
            PRODUCT_QUERY
            + f" WHERE c.product_id IN ({','.join('?' * len(ids))}) GROUP BY c.product_id",
            ids,
        ).fetchall()
    by_id = {row["product_id"]: row for row in rows}
    return [
        ProductCard(
            product_id=row["product_id"],
            name=row["name"],
            price=row["price"],
            image_url=image_url(row),
            total_stock=row["total_stock"],
        )
        for pid in ids
        if (row := by_id.get(pid))
    ]


# --- Chat history (logged-in shoppers) ---
#
# Saved in the chat_messages table: id, user_id -> users.id, role ('user' | 'assistant'),
# content, products_json (cards shown with an assistant reply), created_at (UTC).

MAX_RELOADED = 50  # messages shown in the chat panel when a shopper returns
CARDS_PER_MESSAGE = 4


def ensure_index() -> None:
    """Loading one shopper's history should stay fast as the table grows."""
    with connect(write=True) as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (user_id, id)"
        )


def load_customer(user: UserOut) -> CustomerInfo:
    with connect() as conn:
        created = conn.execute("SELECT created_at FROM users WHERE id = ?", (user.id,)).fetchone()
        count = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user.id,)
        ).fetchone()[0]
    return CustomerInfo(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        member_since=(created["created_at"] or "")[:10] if created else "",
        past_messages=count,
    )


def _cards(products_json: str | None) -> list[ProductCard]:
    """Parse saved cards. Older rows hold full product dicts, and extra keys are ignored."""
    if not products_json:
        return []
    cards = []
    for item in json.loads(products_json)[:CARDS_PER_MESSAGE]:
        try:
            cards.append(ProductCard.model_validate(item))
        except ValidationError:
            continue
    return cards


def load_history(user_id: int, limit: int = MAX_RELOADED) -> list[ChatHistoryMessage]:
    """The shopper's most recent messages, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT role, content, products_json, created_at FROM chat_messages
               WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [
        ChatHistoryMessage(
            role=row["role"],
            content=row["content"],
            products=_cards(row["products_json"]),
            created_at=row["created_at"],
        )
        for row in reversed(rows)
        if row["role"] in ("user", "assistant")
    ]


def recent_turns(user_id: int, limit: int) -> list[ChatTurn]:
    """The last few turns as agent history. Read from the database, not the browser."""
    return [ChatTurn(role=m.role, content=m.content[:4000]) for m in load_history(user_id, limit)]


def save_exchange(user_id: int, message: str, reply: ChatReply) -> None:
    """Store the shopper's message and the assistant's reply together."""
    cards = reply.products or [
        ProductCard(
            product_id=p.product_id,
            name=p.name,
            price=p.price,
            image_url=p.image_url,
            total_stock=p.total_stock,
        )
        for p in (reply.page.products if reply.page else [])
    ]
    products_json = (
        json.dumps([c.model_dump() for c in cards[:CARDS_PER_MESSAGE]]) if cards else None
    )
    with connect(write=True) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
            (user_id, message),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply.reply, products_json),
        )


def clear_history(user_id: int) -> int:
    with connect(write=True) as conn:
        return conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount


# --- Weather ---
#
# Live New Haven weather (Open-Meteo, no API key) and what to wear for it. Used by
# GET /api/weather for the "Today on Broadway" strip, and by the agent.

URL = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
    "latitude": 41.3083,     # 57 Broadway, New Haven
    "longitude": -72.9279,
    "current": "temperature_2m,apparent_temperature,precipitation,weather_code",
    "temperature_unit": "fahrenheit",
    "timezone": "America/New_York",
})
WEATHER_CACHE_SECONDS = 20 * 60
_cache: tuple[float, WeatherPick | None] = (0.0, None)

# WMO weather codes -> plain words (https://open-meteo.com/en/docs)
CONDITIONS = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
    51: "drizzly", 53: "drizzly", 55: "drizzly", 61: "rainy", 63: "rainy", 65: "pouring",
    66: "icy rain", 67: "icy rain", 71: "snowy", 73: "snowy", 75: "snowing hard", 77: "snowy",
    80: "showery", 81: "showery", 82: "stormy", 85: "snow showers", 86: "snow showers",
    95: "stormy", 96: "stormy", 99: "stormy",
}


def _pick(feels_like: float, code: int) -> tuple[str, str, str]:
    """(garment family, search query, headline) for the weather right now."""
    if code in (71, 73, 75, 77, 85, 86) or feels_like < 45:
        return "jacket", "fleece jacket", "Bundle up: our warmest fleeces and jackets"
    if code >= 51:
        return "hoodie", "hoodie", "Wet out there, so pull up a hood"
    if feels_like < 58:
        return "quarter-zip", "quarter zip", "Crisp enough for a quarter-zip"
    if feels_like < 72:
        return "crewneck", "crewneck", "Perfect crewneck weather"
    return "t-shirt", "t-shirt", "Warm day: T-shirt weather"


def _fetch() -> WeatherPick:
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(URL, timeout=6, context=context) as response:
        current = json.loads(response.read())["current"]
    temp, feels, code = current["temperature_2m"], current["apparent_temperature"], int(current["weather_code"])
    family, query, headline = _pick(feels, code)
    page = page_results(headline, query)
    products = [p for p in page.products
                if p.total_stock > 0 and garment_family(p.garment_type) == family][:4] or page.products[:4]
    return WeatherPick(
        temperature_f=round(temp),
        feels_like_f=round(feels),
        condition=CONDITIONS.get(code, "changeable"),
        category=family,
        headline=headline,
        products=products,
    )


def current_weather() -> WeatherPick | None:
    """Cached for 20 minutes. Returns None if the weather service can't be reached."""
    global _cache
    fetched_at, value = _cache
    if value is not None and time.time() - fetched_at < WEATHER_CACHE_SECONDS:
        return value
    try:
        value = _fetch()
    except Exception as err:  # the shop works fine without weather
        log.warning("Weather unavailable: %s", err)
        return value  # last good value, if any
    _cache = (time.time(), value)
    return value


# --- Audit trail ---

AUDIT_PATH = HERE.parent / "output" / "audit_trail.json"
_audit_lock = threading.Lock()


# Sensitive things a shopper might type. They are masked before anything reaches the audit log.
CARD_NUMBER = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_NUMBER = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)")


def redact(text: str) -> str:
    text = CARD_NUMBER.sub("[card number removed]", text)
    text = EMAIL_ADDRESS.sub("[email removed]", text)
    return PHONE_NUMBER.sub("[phone removed]", text)


def _short(value, limit: int = 200) -> str:
    """Compact one-line JSON for the audit log: redacted, then cut to `limit` characters."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(to_jsonable_python(value), ensure_ascii=False, separators=(",", ":"))
    text = redact(" ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _summarize_result(content) -> str:
    """A short, readable summary of a tool result (lists get a count plus the first few names)."""
    data = to_jsonable_python(content)
    if isinstance(data, list):
        names = [d.get("name") or d.get("product_id") for d in data if isinstance(d, dict)]
        return _short(f"{len(data)} results: " + ", ".join(n for n in names[:3] if n) + ("…" if len(data) > 3 else ""))
    return _short(data)


def build_audit_entry(
    *,
    run_id: str,
    started: float,
    model: str,
    user_id: int | None,
    page: str | None,
    message: str,
    messages: list[ModelMessage],
    stop_reason: str,
    reply: str | None,
    product_ids: list[str],
    page_results: str | None,
) -> AuditEntry:
    """Turn one agent run's messages into a structured AuditEntry (one step per model response)."""
    results: dict[str, tuple[str, str]] = {}  # tool_call_id -> (status, summary)
    for msg in messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                results[part.tool_call_id] = ("ok", _summarize_result(part.content))
            elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                results[part.tool_call_id] = ("retry", _short(part.content))

    steps, input_tokens, output_tokens, tool_calls = [], 0, 0, 0
    for msg in messages:
        if not isinstance(msg, ModelResponse):
            continue
        input_tokens += msg.usage.input_tokens or 0
        output_tokens += msg.usage.output_tokens or 0
        calls = []
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                status, summary = results.get(part.tool_call_id, ("no_result", None))
                calls.append(AuditToolCall(tool_name=part.tool_name, args=_short(part.args_as_dict()),
                                           result=summary, status=status))
                tool_calls += part.tool_name != "final_result"
        text = " ".join(p.content for p in msg.parts if isinstance(p, TextPart)).strip()
        steps.append(AuditStep(
            step=len(steps) + 1,
            time=msg.timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
            tool_calls=calls,
            text=_short(text, 200) if text else None,
            finish_reason=msg.finish_reason,
        ))

    return AuditEntry(
        run_id=run_id,
        time=datetime.fromtimestamp(started, timezone.utc).isoformat(timespec="seconds"),
        duration_ms=round((datetime.now(timezone.utc).timestamp() - started) * 1000),
        # The model that actually answered (e.g. a test model), falling back to the configured one.
        model=next((m.model_name for m in messages if isinstance(m, ModelResponse) and m.model_name), model),
        user_id=user_id,
        page=page,
        message=_short(message, 200),
        steps=steps,
        stop_reason=stop_reason,
        reply=_short(reply, 300) if reply else None,
        product_ids=product_ids,
        page_results=page_results,
        usage=AuditUsage(model_requests=len(steps), tool_calls=tool_calls,
                         input_tokens=input_tokens, output_tokens=output_tokens),
    )


def append_audit_entry(entry: AuditEntry) -> None:
    """Append one entry to output/audit_trail.json without rewriting earlier entries.

    The file is a JSON array. A new entry is written over the closing "]" (followed by a new
    "]"), so existing entries are never touched and the file stays valid JSON. It is never
    cleared between runs or server restarts.
    """
    block = entry.model_dump_json(indent=2).encode()
    with _audit_lock:
        AUDIT_PATH.parent.mkdir(exist_ok=True)
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            AUDIT_PATH.write_bytes(b"[\n" + block + b"\n]\n")
            return
        with AUDIT_PATH.open("rb+") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 64))
            tail = f.read()
            close = tail.rfind(b"]")
            if close == -1:
                raise ValueError(f"{AUDIT_PATH} doesn't end with ']'; not appending to avoid damaging it")
            close_at = size - len(tail) + close
            # Is the array empty ("[ ]")? Then no comma is needed before the new entry.
            f.seek(max(0, close_at - 64))
            before = f.read(close_at - max(0, close_at - 64)).rstrip()
            separator = b"\n" if before.endswith(b"[") else b",\n"
            f.seek(close_at)
            f.write(separator + block + b"\n]\n")
            f.truncate()
