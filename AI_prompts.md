# AI Prompts

This file records the prompts used while working on Homework 4.

## Problem 1: Vibe Coder Prompts

### Initial prompt

Create AI_prompts.md at the start of the assignment and keep it updated as we work, one problem at a time. Create one section for each problem. Each section must include the problem number and title, at least one prompt I typed summarized, and one follow-up prompt if we needed it, with one sentence on what was lacking after the first.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 2: Analyze the Database

### Initial prompt

Look through `data/campus_customs.db` and learn the fields in each table, at least `catalogue`, `inventory` and `users`. Start `output/harness.md` by listing each table and its fields, with one short line on why each field matters for the shop or the chatbot.

**Agent action:** The agent opened the database read-only and found four tables, including `chat_messages`. It checked row counts, sample values and how the tables link together, then documented every field in `output/harness.md`.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 3: Build the Campus Customs Website

### Initial prompt

Scaffold a React + Vite + TypeScript front end for Campus Customs with a top nav bar linking to Home, Products, About Us, Log In and Create Account. Base the tone of the Home and About Us pages on yalebulldogblue.com, but write them in your own words instead of copying. The Products page should show every catalogue item's image (from the database image paths), name, price and a short description. Clicking a card should open a single-item page with a large image on one side and the full description, price, sizes and stock on the other. Add a floating chat panel in the bottom-right corner that is only a stub for now, and start a small FastAPI app in `backend/main.py` to serve products and images from the database.

**Agent action:** The agent built the site with six pages and a chat stub in a black-and-pink style, plus a read-only FastAPI backend that serves only the product photo folder, not the database file. It checked every page in a browser.

### Follow-up prompt

Change the black-and-pink design to something more minimalist and luxurious: a blend of warm ivory and Yale navy, serif headings with a clean sans-serif body.

**What was lacking after the first prompt:** The first version used the course's default black-and-pink style, which felt too loud for the upscale boutique look I wanted.

## Problem 4: Create Account and Login

### Initial prompt

Build a standard create-account and login flow. Sign-up asks for first name, last name, email, password and confirm password, and new accounts go into the `users` table. Login asks for email and password. Store passwords securely so neither human nor AI attackers can recover them. Confirm that the seed test user (`test@campuscustoms.yale.edu` / `password`) can log in and that a brand-new account works too. Then document in `output/harness.md` how auth works, what is stored for each user and how passwords are protected.

**Agent action:** The agent worked out that the seed hashes were PBKDF2-SHA256 with 120,000 rounds and kept them working. New passwords get a salted 600,000-round hash, and seed hashes are upgraded when those users log in. It added signed HttpOnly session cookies, generic error messages and a brute-force throttle, and tested both the test user and new accounts through the API and the website.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 5: PydanticAI Agent Backend

### Initial prompt

Build the shop chatbot as a PydanticAI agent behind FastAPI and connect it to the website's chat widget. `backend/main.py` is the API app run with Uvicorn and needs a chat route that returns the agent's reply, along with the product and auth routes. Keep the agent as four files next to it, like Homework 3: `prompts/prompt.md` (system prompt with the Campus Customs voice and basic safety rules), `agent.py` (wiring), `tools.py` (tools) and `models.py` (structured types for chat replies and product cards). Use the course model API key. In `output/harness.md`, explain how the front end talks to FastAPI and how the agent is loaded from the prompt file and model. The backend must run from the `backend/` folder with `uvicorn main:app --reload --port 8000`.

**Agent action:** The agent built the agent on `gpt-5.6-luna` through Portkey, with product search and product-detail tools and a structured reply whose product IDs become real product cards from the database. It connected the chat widget, and tested accuracy, follow-ups, off-topic requests and jailbreak attempts from both the API and the browser.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 6: Tools: Product Info and Stock

### Initial prompt

Give the agent tools that look up product descriptions, prices and stock (by size when the shopper asks) from `campus_customs.db`, so it never invents prices or quantities, and have it state clearly when a size is sold out. Expand `prompts/prompt.md` so the agent knows to call these tools for price and stock questions, add or update the return types in `models.py`, and list each tool in `output/harness.md` with an explanation of the lookup-result fields and why they were chosen.

**Agent action:** The agent replaced the single details tool with `get_product_info`, `get_prices` and `check_stock`. `check_stock` accepts sizes however shoppers type them, labels each size sold out, low stock or in stock, and returns typed "not found" results with suggestions. The agent also added a code check that rejects any price the database didn't return, and tested it with a scripted fake model and nine real questions whose answers it checked against the database.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 7: Chat Search that Updates the Page

### Initial prompt

Add a feature where asking the chat about a type of item, like "what hoodies do you have?", makes the agent search the catalogue and the website show the matches as product cards (image, name, price, short info). Treat it as an API contract: the agent returns structured product matches and the front end renders them. Cards added by the chat must still open the single-item page from Problem 3 when clicked. Update `prompts/prompt.md` and `output/harness.md` to explain how search results reach the page.

**Agent action:** The agent added a `show_products_on_page` tool. It runs the search in code and attaches `PageResults` to the chat reply, and the chat widget passes them to the Products page through a shared React context, with animated cards and a "From your chat" banner. The agent also fixed plural searches ("crewnecks", "t-shirts"). It tested browsing, narrowing follow-ups, zero-match searches, and clicking chat-added cards through to the detail page and back.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 8: Customer Memory

### Initial prompt

When a shopper is logged in, save their chat history in a suitable database table and reload it when they come back. Guests can still chat, but only logged-in history has to persist. Give the agent the shopper's name and email through its deps (or a similarly clear pattern) or tools. Also send enough page context that "do you have this in pink?" on a product page refers to that product, using code in the agent's context. Document in `output/harness.md` how chat history is stored, which customer fields the agent sees, and how page context is passed.

**Agent action:** The agent reused the existing `chat_messages` table, adding an index and history, reload and clear endpoints. For logged-in shoppers it loads history from the database instead of the browser. It added customer details and database-checked page context to `ChatDeps`, fed into the agent through dynamic instruction functions. It then tested guests, a returning shopper in a new session, "this" on a product page, "the second one" on a results page, account questions, clearing, and logging out.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 9: Usability Improvements

### Initial prompt

Now that the core shop works, choose and build two front-end and two agent/backend usability improvements. Write `output/usability.md` before or while building, explaining for each improvement what was added and why it helps a Campus Customs shopper or the business. Make sure every improvement actually shows up in the running app, since graders will look for them.

**Agent action:** The agent added:
- page-aware suggested questions in the chat,
- category chips, an "in stock in size" filter and sorting on the Products page (replacing an "in stock only" toggle that never changed anything, since every product has some stock),
- a `find_alternatives` tool that suggests similar in-stock items when a size is sold out, and
- typo-tolerant search.

It documented each in `output/usability.md` and checked all four in the browser.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 10: Style the Website

### Initial prompt

Style the site so it feels like a real Campus Customs storefront (fonts, color, hierarchy, motion, product presentation and chat feel), using the heritage-shop theme. Include the walk-into-the-store hero, residential college mode, tag-style stock indicators, micro-interactions and weather-aware features. Give every product photo the same background, since some are on black and look badly edited. Add a pop-up confirming logout. Write a short, concrete `output/design.md` explaining what changed and why it should help customers stay and buy.

**Agent action:** The agent wrote a script that flood-fills each photo's backdrop from the edges and re-centers all 102 garments on one stone background. It tuned the script for a navy hoodie with near-black folds and for a white tee on pure white. It then:
- restyled the site in paper, brass, brick and Yale Blue with serif, varsity, script and mono fonts;
- built a CSS storefront of 57 Broadway with clickable display windows and a door that opens the chat;
- added college mode (14 colleges, recoloring the site and informing the agent);
- added live New Haven weather picks from Open-Meteo, hanging size tags, receipt-style chat recommendations and pop-up confirmations.

It checked each feature in the browser on desktop and mobile.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 11: Site Testing (App Check)

### Initial prompt

Test the live site and document it in `output/app_check.html`, a page that opens with a double-click. Include clear screenshots with short captions for: the chat checking an item's inventory with honest stock and price from the database; the dynamic search-result cards that appear after a category question like hoodies; and one of the Problem 9 usability features. Make it easy to grade, with a heading, screenshot and one or two sentences per check, and store the images in `output/app_check_images/` linked with relative paths.

**Agent action:** The agent scripted Chrome with Playwright to run each check as a guest on the live site, and compared the chat's answers with the database. It wrote the report with a pass/fail summary table, a database evidence table and a bonus check for sold-out alternatives. The screenshots also exposed black gaps between sleeves and body on some photos, so it improved the image cleaner (checking that logos stayed intact) and retook the screenshots.

### Follow-up prompt

No follow-up prompt was needed.

## Problem 12: Audit Trail, Safety, Finish Harness

### Initial prompt

Keep an append-only `output/audit_trail.json` of agent-loop activity (time, tool name, short args and results, stop reason) that is never wiped between runs. Write safety rules for the agent in `prompts/prompt.md`. Then finish `output/harness.md` so it clearly explains how the whole system works: the model fields in `models.py` and why they were chosen, the tools and abilities, the safety rules, and the specs (loop limits, result caps, models, and how to run the front and back ends).

**Agent action:** The agent:
- added `AuditEntry`, `AuditStep`, `AuditToolCall` and `AuditUsage` models, and logged every chat run with each loop step's tool calls, args, results, retries, the stop reason and token usage, including failed runs;
- appended entries by rewriting only the closing bracket, so earlier entries are never touched;
- wrote 13 safety rules into the prompt, and added a code check that blocks other customers' emails and secrets;
- tested everything with scripted fake models and live chats.

Testing showed card numbers being stored in the log and the assistant mentioning a checkout the site doesn't have. The agent added redaction and a no-checkout rule. It then rewrote the harness as one coherent document with a problem map, architecture, every model's fields, tools, safety, audit trail, and a specs and limits table.

### Follow-up prompt

No follow-up prompt was needed.
