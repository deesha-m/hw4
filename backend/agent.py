"""Campus Customs chat agent (PydanticAI): wiring and entry point.

The system prompt comes from prompts/prompt.md, the model from tools.get_model()
(loaded on the first chat, so the website runs even before PORTKEY_API_KEY is set)
(gpt-5.6-luna through Portkey), and the tools from tools.py.

Quick test from the backend/ folder:
    ../.venv/bin/python agent.py "Do you have navy hoodies in medium?"
"""

import asyncio
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import UsageLimits

from models import (
    Alternatives,
    ChatAnswer,
    ChatDeps,
    PageUpdate,
    ChatReply,
    ChatTurn,
    PriceInfo,
    ProductInfo,
    ProductNotFound,
    ProductSummary,
    SizeNotOffered,
    StockCheck,
)
from tools import (
    MODEL_NAME,
    append_audit_entry,
    build_audit_entry,
    dollar_amounts,
    get_model,
    prices_in,
    product_cards,
)
import tools

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "prompt.md"

# Per-message caps, so one chat can't loop or run up the bill.
LIMITS = UsageLimits(request_limit=6, tool_calls_limit=8, total_tokens_limit=40_000)
MAX_HISTORY_TURNS = 12

agent = Agent(
    None,  # the model is passed to each run by chat(), via get_model()
    instructions=PROMPT_PATH.read_text(encoding="utf-8"),
    output_type=ChatAnswer,
    deps_type=ChatDeps,
    retries=2,
)


@agent.instructions
def customer_context(ctx: RunContext[ChatDeps]) -> str:
    """Who is chatting, from the session cookie and the users table (never from the browser)."""
    c = ctx.deps.customer
    if c is None:
        return "## Who is chatting\nA guest who is not logged in. Their chat is not saved."
    history = (
        f"They have {c.past_messages} saved messages from earlier visits; recent ones are in the conversation history."
        if c.past_messages
        else "This is their first chat."
    )
    return (
        "## Who is chatting\n"
        f"A logged-in customer: {c.first_name} {c.last_name}, email {c.email}, customer since {c.member_since}. "
        f"{history} Use their first name naturally. Only mention their email if they ask what email is on their account."
    )


@agent.instructions
def page_context(ctx: RunContext[ChatDeps]) -> str:
    """What the shopper is looking at, looked up in the database from the page they're on."""
    page = ctx.deps.current_page
    if page is None:
        return ""
    lines = ["## Where the shopper is on the site"]
    if page.college:
        lines.append(
            f"They turned on college mode for {page.college} College. When it fits, mention pieces for "
            f"their college (search \"{page.college}\"). If there are none, say so and suggest Yale classics."
        )
    if page.product:
        p = page.product
        lines.append(
            f"They are on the product page for {p.name} (product_id {p.product_id}, ${p.price:g}, "
            f"colors: {', '.join(p.colors)}). Words like \"this\", \"it\" or \"this one\" mean this product "
            "unless they name another. Use check_stock for sizes, and include this product_id in product_ids "
            "when you talk about it."
        )
    elif page.page_type == "product":
        lines.append("They are on a product page, but the product couldn't be found.")
    elif page.visible_products:
        shown = "; ".join(f"{i}. {p.name} ({p.product_id}, ${p.price:g})" for i, p in enumerate(page.visible_products, 1))
        lines.append(
            f"They are on the Products page, viewing chat results titled \"{page.results_title}\". "
            f"The first cards, in order: {shown}. \"The second one\" and similar refer to this order."
        )
    else:
        label = {"home": "home page", "products": "Products page (full catalogue)", "about": "About Us page",
                 "account": "log-in or sign-up page"}.get(page.page_type, f"page {page.path}")
        lines.append(f"They are on the {label}.")
    return "\n".join(lines)


@agent.instructions
def weather_context(ctx: RunContext[ChatDeps]) -> str:
    """Live New Haven weather, so "what should I wear today?" gets a real answer."""
    w = ctx.deps.weather
    if w is None:
        return ""
    return (
        f"## Weather on Broadway right now\n{w.temperature_f}°F (feels like {w.feels_like_f}°F), {w.condition}. "
        f"Suggested category: {w.category}. Mention it only if the shopper asks what to wear, or about "
        "the weather, layering or a gift for today. Use the tools for the actual products."
    )


# --- Tools ---


@agent.tool_plain
def search_products(
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    in_stock_only: bool = True,
) -> list[ProductSummary]:
    """Search the Campus Customs catalogue. Returns up to 8 matches, best first.

    Args:
        query: Keywords, e.g. "navy hoodie", "Harvard Yale game tee", "baseball crewneck".
        color: Only products that come in this color, e.g. "navy", "gray", "white".
        max_price: Only products at or below this price in US dollars.
        size: Only products with this size in stock: XS, S, M, L, XL or XXL.
        in_stock_only: Skip products that are sold out in every size (default True).
    """
    return tools.search_products(query, color, max_price, size, in_stock_only)


@agent.tool_plain
def get_product_info(product_id: str) -> ProductInfo | ProductNotFound:
    """Description, price, colors and tags for one product, from the catalogue.

    Call this for any question about what a product looks like, what it's made of or how much it costs.

    Args:
        product_id: A product_id from search_products results.
    """
    return tools.get_product_info(product_id)


@agent.tool_plain
def get_prices(product_ids: list[str]) -> list[PriceInfo | ProductNotFound]:
    """Current prices for up to 10 products at once, for comparisons or totals.

    Args:
        product_ids: product_ids from search_products results.
    """
    return tools.get_prices(product_ids)


@agent.tool_plain
def check_stock(product_id: str, size: str | None = None) -> StockCheck | ProductNotFound | SizeNotOffered:
    """Units in stock right now for every size of one product (XS to XXL).

    Call this before saying anything is available, sold out or low, and whenever the shopper
    asks about a size or "how many". If `size` is given, `requested_size_stock` holds that size.

    Args:
        product_id: A product_id from search_products results.
        size: Optional size the shopper asked about, e.g. "M", "medium", "XL", "2XL".
    """
    return tools.check_stock(product_id, size)


@agent.tool_plain
def find_alternatives(product_id: str, size: str | None = None) -> Alternatives | ProductNotFound | SizeNotOffered:
    """Up to 4 similar products that ARE in stock, in the given size if one is named.

    Call this whenever check_stock shows the size the shopper wants is sold out (pass that size),
    or when they ask for "something similar" or "other options like this". Put the alternatives'
    product_ids in product_ids so they show as cards.

    Args:
        product_id: The product the shopper wanted.
        size: The size they need, e.g. "XS". Omit for general "similar items".
    """
    return tools.find_alternatives(product_id, size)


@agent.tool
def show_products_on_page(
    ctx: RunContext[ChatDeps],
    title: str,
    query: str = "",
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
) -> PageUpdate:
    """Search the catalogue and show every match as product cards on the website's Products page.

    Use this when the shopper wants to browse a type or group of items, e.g. "what hoodies do
    you have?", "show me navy crewnecks", "tees under $35". The website renders the results
    automatically. Don't list them all in your reply. Call it at most once per message.

    Args:
        title: Short heading for the page, e.g. "Hoodies", "Navy crewnecks under $60".
        query: Keywords, e.g. "hoodie", "crewneck", "quarter zip", "harvard yale".
        color: Only products in this color, e.g. "navy", "gray".
        max_price: Only products at or below this price in US dollars.
        size: Only products with this size in stock: XS, S, M, L, XL or XXL.
    """
    page = tools.page_results(title, query, color, max_price, size)
    if page.products:  # with no matches the page stays as it is
        ctx.deps.page = page
    return PageUpdate(
        shown=len(page.products),
        total_matches=page.total_matches,
        title=page.title,
        top_matches=[PriceInfo(product_id=p.product_id, name=p.name, price=p.price) for p in page.products[:3]],
    )


# --- Grounding check ---


@agent.output_validator
def prices_come_from_tools(ctx: RunContext[ChatDeps], answer: ChatAnswer) -> ChatAnswer:
    """Reject replies that quote a $ price the database never returned.

    Allowed amounts: prices in tool results or the current page context, amounts the shopper typed (e.g. "under $40"),
    amounts from earlier replies, and simple multiples or pairs of those (e.g. two for $116).
    """
    allowed: set[float] = prices_in(ctx.deps.current_page) if ctx.deps.current_page else set()
    for message in ctx.messages:
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                allowed |= prices_in(part.content)
            elif isinstance(part, (UserPromptPart, TextPart)) and isinstance(part.content, str):
                allowed |= dollar_amounts(part.content)
    base = set(allowed)
    allowed |= {round(p * k, 2) for p in base for k in range(2, 11)}
    allowed |= {round(a + b, 2) for a in base for b in base}

    invented = sorted(a for a in dollar_amounts(answer.message) if round(a, 2) not in allowed)
    if invented:
        amounts = ", ".join(f"${a:g}" for a in invented)
        raise ModelRetry(
            f"Your reply mentions {amounts}, which doesn't match any price from the tools. "
            "Call get_product_info or get_prices and quote only those prices."
        )
    return answer


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SECRET_MARKERS = re.compile(r"pbkdf2_sha256|password_hash|PORTKEY|SESSION_SECRET|sk-[A-Za-z0-9]{8,}", re.I)


@agent.output_validator
def no_private_data(ctx: RunContext[ChatDeps], answer: ChatAnswer) -> ChatAnswer:
    """Safety check in code: a reply may only mention the logged-in shopper's own email, and
    never anything that looks like a password hash, API key or server secret."""
    own = ctx.deps.customer.email.lower() if ctx.deps.customer else None
    others = [e for e in EMAIL.findall(answer.message) if e.lower() != own]
    if others:
        raise ModelRetry(
            "Don't include email addresses other than the shopper's own. Rewrite the reply without them."
        )
    if SECRET_MARKERS.search(answer.message):
        raise ModelRetry("Don't mention passwords, hashes, keys or server settings. Rewrite the reply.")
    return answer


# --- Entry point ---


def to_model_history(history: list[ChatTurn]) -> list[ModelMessage]:
    """Convert recent website chat turns into PydanticAI message history."""
    messages: list[ModelMessage] = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


log = logging.getLogger("campus_customs")


async def chat(message: str, history: list[ChatTurn], deps: ChatDeps) -> ChatReply:
    """Answer one shopper message.

    Returns the reply, up to 4 in-chat product cards, and, if the agent called
    show_products_on_page, the page results for the website to render. Every run, including
    ones that fail, is appended to output/audit_trail.json.
    """
    model = get_model()  # raises MissingModelKey before anything is logged if the key isn't set
    run_id, started = uuid.uuid4().hex[:12], time.time()
    model_history = to_model_history(history)
    stop_reason, reply = "error", None
    with capture_run_messages() as messages:
        try:
            result = await agent.run(
                message, model=model, message_history=model_history, deps=deps, usage_limits=LIMITS
            )
            answer = result.output
            reply = ChatReply(
                reply=answer.message.strip(),
                # When results go on the page, the page is the card view, so skip the in-chat cards.
                products=[] if deps.page else product_cards(answer.product_ids),
                page=deps.page,
            )
            stop_reason = "completed"
            return reply
        except UsageLimitExceeded:
            stop_reason = "usage_limit"
            raise
        except UnexpectedModelBehavior:
            stop_reason = "output_retries_exhausted"
            raise
        except ModelHTTPError as err:
            stop_reason = "content_filter" if "content_filter" in str(err.body) else "model_error"
            raise
        finally:
            try:
                append_audit_entry(build_audit_entry(
                    run_id=run_id,
                    started=started,
                    model=MODEL_NAME,
                    user_id=deps.customer.user_id if deps.customer else None,
                    page=deps.current_page.path if deps.current_page else None,
                    message=message,
                    messages=messages[len(model_history):],  # this run only, not earlier turns
                    stop_reason=stop_reason,
                    reply=reply.reply if reply else None,
                    product_ids=[p.product_id for p in reply.products] if reply else [],
                    page_results=(f"{deps.page.title} ({len(deps.page.products)} of {deps.page.total_matches})"
                                  if deps.page else None),
                ))
            except Exception:  # the audit log must never break the chat
                log.exception("Could not write audit entry")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What hoodies do you have?"
    reply = asyncio.run(chat(question, [], ChatDeps()))
    print(reply.reply)
    if reply.page:
        print(f"  [page] {reply.page.title}: {len(reply.page.products)} of {reply.page.total_matches} cards")
    for card in reply.products:
        print(f"  - {card.name} (${card.price:.0f}) [{card.product_id}]")
