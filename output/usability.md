# Usability Improvements

Four improvements to the Campus Customs shop: two on the front end and two in the agent/backend. Each section says what was added, why it helps a shopper or the business, and where to see it in the running app.

| # | Improvement | Type | Where to see it |
|---|---|---|---|
| 1 | Suggested questions in the chat | Front end | Open the chat on any page, especially a product page |
| 2 | Category filters, "in stock in size" filter and sorting on Products | Front end | Products page, above the grid |
| 3 | Sold-out size → in-stock alternatives | Agent / backend | Chat: "Is the Baseball Left Chest Crewneck in XS?" |
| 4 | Typo-tolerant product search | Agent / backend | Chat: "show me crewnek sweatshrits" |

---

## 1. Suggested questions in the chat (front end)

**What we added:** one-tap question chips above the chat input that change with the page. On a product page they're about that item: "Is this in stock in M?", "What colors does this come in?", "Show me similar items". On the Products page: "What hoodies do you have?", "Tees under $35". Everywhere else: "What should I wear today?" (answered using live New Haven weather), "What hoodies do you have?" (or "Anything for Davenport?" in college mode), and "Gift for a Yale parent under $60". Tapping a chip sends it right away. The chips hide while the assistant is answering.

**Why it helps:**
- **Shoppers:** many people don't know what a shop chatbot can do, and an empty text box is intimidating. The chips show what's possible (stock by size, colors, browsing, budgets) and turn a question into one tap, which matters most on phones.
- **The business:** more shoppers try the assistant, and each suggestion leads toward a product or a size check, the steps just before a purchase. Product-page chips also show off the page-context feature ("this" means the item on screen).

## 2. Category filters, "in stock in size" filter and sorting (front end)

**What we added:** a toolbar above the product grid with:
- **Category chips:** All, Hoodies, Crewnecks, T-shirts, Quarter-zips, Jackets & fleece. Each shows a live count, and empty categories hide.
- **"In stock in [size]" picker:** Any size, or XS to XXL. It shows only products that actually have that size in stock, and the category counts update to match.
- **Sort menu:** Featured, Price: low to high, Price: high to low, Name.
- **"Clear filters" link.**

These combine with the search box and also work on results the chat put on the page. To support the size filter, `GET /api/products` (and chat page results) now include `sizes_in_stock` for each product.

**Why it helps:**
- **Shoppers:** the catalogue has 102 items and 22 inconsistent garment-type labels (e.g. "hoodie", "pullover hoodie", "hooded sweatshirt"). The chips group them into the six categories shoppers actually think in, so finding "all the crewnecks" is one click instead of scrolling. The size picker matters because 145 of the 612 product-size combinations are sold out. Someone who wears XS can now see only the 75 items they can actually buy, instead of opening product pages one by one to find "Sold out." Sorting by price helps gift buyers with a budget.
- **The business:** shoppers who find something in their size quickly are more likely to buy, and fewer leave frustrated.

*While building:* the first version had an "in stock only" toggle. Every product has at least one size in stock, so the toggle never changed anything. It was replaced with the size picker, which is what shoppers actually need.

## 3. Sold-out size → in-stock alternatives (agent / backend)

**What we added:** a new agent tool, `find_alternatives(product_id, size)`, in `backend/tools.py` and `agent.py`. It finds the most similar products (same garment category, overlapping colors and tags, close in price) that have the requested size in stock. The prompt tells the agent to call it whenever a requested size is sold out, or when a shopper asks for "something similar". The alternatives appear as clickable product cards under the reply.

**Why it helps:**
- **Shoppers:** before, "XS is sold out" was a dead end. Now the answer continues with "…but these similar crewnecks are in stock in XS," with cards to click, so the shopper still leaves with something that fits.
- **The business:** 145 of the 612 product-size combinations are sold out, so this comes up often. Turning a sold-out answer into an in-stock recommendation saves sales that would otherwise be lost.

## 4. Typo-tolerant product search (agent / backend)

**What we added:** the catalogue search behind `search_products` and `show_products_on_page` now fixes misspellings. Each query word that isn't in the catalogue's vocabulary is matched to the closest real word (using Python's `difflib`, 80% similarity cutoff), so "crewnek" → "crewneck", "sweatshrit" → "sweatshirt", "quater zip" → "quarter zip", "harvrd" → "harvard". Common shopper words like "hoody" are also added to the synonym list.

**Why it helps:**
- **Shoppers:** people type quickly into a chat box, especially on phones. Before, a single typo returned "no matches" even though the item was in stock. Now the search finds what they meant without making them retype.
- **The business:** a "no results" answer is one of the most common reasons shoppers leave. Fixing typos in code is instant and free (no extra model call), and it works for both the chat answers and the page cards.

---

## Checked in the running app

| # | Where we tried it | What happened |
|---|---|---|
| 1 | Opened the chat on the Baseball Left Chest Crewneck page | The chips read "Is this in stock in M?", "What colors does this come in?" and "Show me similar items". On the Products page they switch to "What hoodies do you have?", "Tees under $35" and "What's in stock in size S?". The chips hide while the assistant is answering. Tapping "Show me similar items" sent it and returned 4 similar crewnecks as cards. |
| 2 | Products page | Counts: All 102, Hoodies 27, Crewnecks 29, T-shirts 25, Quarter-zips 11, Jackets & fleece 8. "In stock in XS" → 75 items (the Baseball crewneck, sold out in XS, disappears), with counts updating (Crewnecks 18). Crewnecks + XS + "Price: low to high" → 18 items. "Price: high to low" starts with the $98 jackets and ends with the $32 tees. "Clear filters" resets everything. |
| 3 | On the Baseball Left Chest Crewneck page: "Is this available in XS?" | "The XS is sold out right now. This crewneck is still available in S, M, L, and XXL. Similar crewnecks in XS include the Davenport College, Yale University Offside, and Pierson College styles." Cards appeared for each, all $58 with XS in stock. |
| 4 | "show me crewnek sweatshrits under $60" | Read as "crewneck sweatshirt". The page showed "Crewnecks under $60", 28 cards. In the search function directly: "quater zip" → 12 quarter-zips, "flece jacket" → 7, "harvrd yale" → the 2025 Harvard–Yale tee, "davenprot" → the Davenport crewneck, "bulldgo" → 10 bulldog items, "hoodei"/"hoody" → 27 hoodies. Correct words like "pink" and "yale" are left alone. |

## Where the code lives

| # | Files |
|---|---|
| 1 | `frontend/src/components/ChatWidget.tsx` (`suggestionsFor`, `send`), `frontend/src/index.css` (`.chat-chip`) |
| 2 | `frontend/src/pages/Products.tsx` (`CATEGORIES`, `categoryOf`, size and sort state), `backend/tools.py` (`sizes_in_stock`, and `sizes_csv` in `PRODUCT_QUERY`), `backend/main.py` (`sizes_in_stock` in product JSON) |
| 3 | `backend/tools.py` (`find_alternatives`, `garment_family`), `backend/agent.py` (tool registration), `backend/models.py` (`Alternative`, `Alternatives`), `backend/prompts/prompt.md` (sold-out rule) |
| 4 | `backend/tools.py` (`_vocabulary`, `_correct`, `corrected_query`, `FUZZY_CUTOFF`, new `SYNONYMS` entries), `backend/prompts/prompt.md` (don't ask shoppers to retype) |
