"""Pydantic / PydanticAI structured types for the Campus Customs backend."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- Accounts -----------------------------------------------------------------

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Enter a valid email address")
    return email


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: str = Field(max_length=254)
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)
    confirm_password: str

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name can't be blank")
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return normalize_email(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords don't match")
        return self


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=MAX_PASSWORD)


class UserOut(BaseModel):
    """What the website is allowed to see about a user. Never includes the hash."""

    id: int
    first_name: str
    last_name: str
    email: str


# --- Products (tool results and chat cards) -------------------------------------

Size = Literal["XS", "S", "M", "L", "XL", "XXL"]
StockStatus = Literal["in_stock", "low_stock", "sold_out"]


class ProductSummary(BaseModel):
    """A compact search result the agent reads. Short, so many fit in the context."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    short_description: str
    total_stock: int


class ProductInfo(BaseModel):
    """Description and price for one product (get_product_info)."""

    product_id: str
    name: str
    garment_type: str
    price: float = Field(description="Price in US dollars, straight from the catalogue.")
    colors: list[str]
    description: str
    search_tags: list[str]


class PriceInfo(BaseModel):
    """Price for one product (get_prices), for quick comparisons."""

    product_id: str
    name: str
    price: float = Field(description="Price in US dollars, straight from the catalogue.")


class SizeStock(BaseModel):
    """Stock for one size of one product."""

    size: Size
    quantity: int = Field(description="Units on hand right now.")
    status: StockStatus = Field(description="sold_out if 0, low_stock if 1-5, otherwise in_stock.")


class StockCheck(BaseModel):
    """Stock for one product (check_stock), optionally focused on one size."""

    product_id: str
    name: str
    requested_size: Size | None = Field(
        default=None, description="The size the shopper asked about, normalized (e.g. 'medium' -> 'M')."
    )
    requested_size_stock: SizeStock | None = Field(
        default=None, description="Stock for the requested size. None if no size was asked for."
    )
    sizes: list[SizeStock] = Field(description="Every size, XS to XXL.")
    available_sizes: list[Size]
    sold_out_sizes: list[Size]
    total_stock: int


class Alternative(BaseModel):
    """A similar product that is in stock, suggested when the shopper's pick is sold out."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    short_description: str
    size_quantity: int | None = Field(description="Units in stock in the requested size, if a size was given.")
    same_category: bool = Field(description="True if it's the same kind of garment (e.g. both crewnecks).")


class Alternatives(BaseModel):
    """Result of find_alternatives: in-stock products most like the original."""

    original_product_id: str
    original_name: str
    size: Size | None = Field(description="Every alternative has this size in stock.")
    alternatives: list[Alternative]


class ProductNotFound(BaseModel):
    """Returned instead of a result when a product_id doesn't exist."""

    requested_id: str
    message: str
    suggestions: list[PriceInfo] = Field(description="Closest real products, to ask the shopper about.")


class SizeNotOffered(BaseModel):
    """Returned when the shopper asks for a size the shop doesn't carry."""

    requested_size: str
    offered_sizes: list[Size]
    message: str


class ProductCard(BaseModel):
    """A product shown as a clickable card under the assistant's reply."""

    product_id: str
    name: str
    price: float
    image_url: str
    total_stock: int


class PageProduct(BaseModel):
    """One card the website puts on the Products page from a chat search."""

    product_id: str
    name: str
    garment_type: str = ""
    price: float
    image_url: str
    short_description: str
    total_stock: int
    sizes_in_stock: list[Size] = Field(default_factory=list)


class PageResults(BaseModel):
    """Chat search results for the website to render as product cards on the page."""

    title: str = Field(description="Heading shown above the cards, e.g. 'Hoodies' or 'Navy crewnecks under $60'.")
    query: str
    total_matches: int
    products: list[PageProduct]


class WeatherPick(BaseModel):
    """Live New Haven weather and the products that suit it."""

    temperature_f: int
    feels_like_f: int
    condition: str = Field(description="Plain words, e.g. 'mostly clear', 'rainy'.")
    category: str = Field(description="Garment family that suits the weather, e.g. 'crewneck'.")
    headline: str
    products: list[PageProduct]


class PageUpdate(BaseModel):
    """What show_products_on_page tells the agent after putting cards on the page."""

    shown: int
    total_matches: int
    title: str
    top_matches: list["PriceInfo"] = Field(description="The first 3 products shown; mention one or two by name.")


# --- Chat -----------------------------------------------------------------------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class PageContext(BaseModel):
    """Where the shopper is on the site, sent by the website with each message.

    It comes from the browser, so the backend only uses it to look things up in the
    database (e.g. the product on screen); it never trusts names or prices from here.
    """

    path: str = Field(default="/", max_length=200, description="Current URL path, e.g. /products/basic-hoodie-big-yale.")
    product_id: str | None = Field(default=None, max_length=120, description="Set on a product detail page.")
    results_title: str | None = Field(default=None, max_length=80, description="Heading of chat results on the Products page.")
    visible_product_ids: list[str] = Field(default_factory=list, max_length=30, description="Chat results currently on the page.")
    college: str | None = Field(default=None, max_length=40, description="Residential college picked in college mode.")


class ChatRequest(BaseModel):
    """What the website sends: the new message, recent turns (guests only) and page context."""

    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page: PageContext | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message can't be blank")
        return value


class ChatAnswer(BaseModel):
    """The agent's structured output."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        description="The reply to the shopper, in the Campus Customs voice. Plain text; short "
        "paragraphs or '- ' bullets are fine. No markdown headings, bold or links."
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="IDs (from tool results) of up to 4 products you recommend or discuss, "
        "in order of relevance. They are shown as clickable cards. Empty if none apply.",
    )


class ChatReply(BaseModel):
    """What the chat route returns to the website (the API contract).

    `page` is set only when the agent ran a browse search; the website then renders
    those products as cards on the Products page.
    """

    reply: str
    products: list[ProductCard]
    page: PageResults | None = None


class ChatHistoryMessage(BaseModel):
    """One saved message, as reloaded into the chat panel for a returning shopper."""

    role: Literal["user", "assistant"]
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    created_at: str


class CustomerInfo(BaseModel):
    """What the agent knows about a logged-in shopper. Never includes the password hash."""

    user_id: int = Field(description="For backend lookups only; not shown to the model.")
    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date, YYYY-MM-DD.")
    past_messages: int = Field(description="How many chat messages are saved from earlier visits.")


class CurrentPage(BaseModel):
    """Page context after the backend has looked it up in the database."""

    path: str
    page_type: Literal["home", "products", "product", "about", "account", "other"]
    product: ProductInfo | None = Field(default=None, description="The product on screen, on a product page.")
    results_title: str | None = None
    visible_products: list[PriceInfo] = Field(default_factory=list, description="Chat results on the Products page, in order.")
    college: str | None = Field(default=None, description="A real Yale residential college name, if the shopper chose one.")


class ChatDeps(BaseModel):
    """Run-time state passed to the agent as deps.

    customer and current_page are filled in before the run; page is filled in by the
    show_products_on_page tool during the run.
    """

    customer: CustomerInfo | None = None
    current_page: CurrentPage | None = None
    weather: WeatherPick | None = None
    page: PageResults | None = None


# --- Audit trail ------------------------------------------------------------------

StopReason = Literal[
    "completed",                 # the agent produced a reply
    "usage_limit",               # hit a per-message cap (requests, tool calls or tokens)
    "output_retries_exhausted",  # an output check (price / private data) kept failing
    "content_filter",            # the model provider's safety filter blocked the message
    "model_error",               # the model API returned another error
    "error",                     # anything else
]


class AuditToolCall(BaseModel):
    """One tool call inside a loop step, with short args and result."""

    tool_name: str
    args: str = Field(description="Arguments as compact JSON, cut to ~200 characters.")
    result: str | None = Field(default=None, description="Short summary of what the tool returned.")
    status: Literal["ok", "retry", "no_result"] = Field(
        description="retry = the tool or an output check sent the model back to try again."
    )


class AuditStep(BaseModel):
    """One iteration of the agent loop: a single model response and what it asked for."""

    step: int
    time: str = Field(description="UTC timestamp of the model response.")
    tool_calls: list[AuditToolCall]
    text: str | None = Field(default=None, description="Any plain text the model wrote, shortened.")
    finish_reason: str | None = None


class AuditUsage(BaseModel):
    model_requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int


class AuditEntry(BaseModel):
    """One shopper message handled by the agent, appended to output/audit_trail.json."""

    run_id: str
    time: str = Field(description="UTC time the run started.")
    duration_ms: int
    model: str
    user_id: int | None = Field(description="Logged-in user's id, or None for a guest. No names or emails.")
    page: str | None = Field(description="Page path the shopper was on.")
    message: str = Field(description="The shopper's message, cut to 200 characters.")
    steps: list[AuditStep]
    stop_reason: StopReason
    reply: str | None = Field(description="The reply text, cut to 300 characters.")
    product_ids: list[str] = Field(default_factory=list, description="Products shown as chat cards.")
    page_results: str | None = Field(default=None, description="Title and count of page results, if any.")
    usage: AuditUsage
