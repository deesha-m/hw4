# Campus Customs: Yale Apparel Shop + AI Shopping Assistant

MGT 409 AI Foundations for Managers, Homework 4.

A storefront for Campus Customs (57 Broadway, New Haven) with a PydanticAI shopping assistant. Shoppers can:
- browse products, filter by category and size, and open product pages with stock by size;
- create an account and log in;
- chat with "The Shop Counter," which answers price and stock questions from the database, fills the page with search results, remembers returning shoppers, and understands the page they're on.

- **Front end:** React + Vite + TypeScript (`frontend/`)
- **Back end:** FastAPI (`backend/main.py`)
- **Agent:** PydanticAI with `gpt-5.6-luna` via Portkey. It's four files in `backend/`: `prompts/prompt.md`, `agent.py`, `tools.py`, `models.py`.
- **Docs:** `output/harness.md` (how the whole system works), `output/usability.md`, `output/design.md`, `output/app_check.html` (live-site test with screenshots), `output/audit_trail.json` (append-only agent log), `AI_prompts.md`

## Layout

```
hw4/
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── frontend/                 # Vite React TypeScript app
├── backend/
│   ├── main.py               # FastAPI app: run with uvicorn main:app --reload --port 8000
│   ├── agent.py
│   ├── models.py
│   ├── tools.py
│   └── prompts/
│       └── prompt.md
├── scripts/
│   └── clean_product_images.py   # optional: gives every product photo the same background
└── output/
    ├── harness.md
    ├── design.md
    ├── usability.md
    ├── app_check.html
    ├── app_check_images/     # screenshots linked from app_check.html
    └── audit_trail.json
```

## 1. Add the data pack (not in git)

The database and product images aren't in this repository. Place the data pack inside `hw4/` so it looks like this:

```
hw4/
└── data/
    ├── campus_customs.db
    └── products/             # images referenced by the catalogue
```

## 2. Set up (once)

You need Python 3.11+ and Node.js 20+. From the `hw4` folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your real PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

**Recommended:** build the cleaned product photos. These are the originals re-centered on one uniform stone background, written to `data/products_clean/`. Without them, the site falls back to the original photos.

```bash
.venv/bin/python scripts/clean_product_images.py
```

## 3. Run

Open two terminals in the `hw4` folder.

**Back end** (FastAPI on port 8000, run from `backend/`):

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

If the virtual environment is activated (`source .venv/bin/activate`), that's just `uvicorn main:app --reload --port 8000`.

**Front end** (Vite on port 5173):

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. Vite forwards `/api` and `/images` to the backend on port 8000.

Test login: `test@campuscustoms.yale.edu` / `password`, or create your own account.

## Things to try

- On a product page, open the chat and ask: *"How many of this are left in medium, and how much is it?"*
- *"What hoodies do you have?"* fills the Products page with matching cards. Click one to open its page.
- *"Is it in stock in XS?"* on the Baseball Left Chest Crewneck: sold out, with similar in-stock picks.
- Pick a residential college in the nav (college mode), click the storefront door on Home, or ask *"What should I wear today?"* (live New Haven weather).
- Log in, chat, log out and back in: your chat is saved.

Every chat run is appended to `output/audit_trail.json`.

## Notes

- **Secrets:** the real `.env`, database and images are excluded by `.gitignore`. `.env.example` has placeholders only.
- **Optional `.env` setting:** `SESSION_SECRET` keeps logins valid across backend restarts.
- **Without internet:** the weather strip hides itself if Open-Meteo can't be reached. Everything else works without it.
- **More detail:** see `output/harness.md` for the architecture, models, tools, safety rules, audit trail, and specs and limits.
