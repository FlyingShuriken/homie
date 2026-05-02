# Homie

[Project Pitching Video](https://drive.google.com/file/d/1Z2CedhMO_cFvnzi-G2JIJ7GXDB29U0Rx/view?usp=sharing)

AI-powered rental aggregation and search for Malaysia. Built for UMHackathon 2026 — Domain: AI Systems & Agentic Workflow Automation.

---

## What it does

Renters in Malaysia deal with listings scattered across ibilik, iProperty, and Facebook — each with different formats, languages, and data quality. Homie aggregates them into a single ranked, explainable shortlist.

You enter your preferences once — via a **manual form** or a **conversational chat agent** that extracts your filters from natural language. A GLM orchestration agent decides how to run the search, scrapes multiple platforms, normalises multilingual listings, scores each one against your priorities, and helps you draft outreach from one dashboard. Telegram sending is demo-target based: messages go to the configured demo account, not directly to landlords.

---

## Architecture

```
Browser (Next.js)
    │  POST /api/search              submit filters, start pipeline
    │  GET  /api/search/{id}/stream  SSE progress feed
    │  GET  /api/search/{id}/results scored listings
    │  POST /api/outreach/draft      request inquiry drafts
    │  POST /api/outreach/handoff    confirm + log handoff
    ▼
FastAPI (async)
    ▼
GLMOrchestrator  ← top-level ReAct loop: GLM decides pipeline shape
    ├── validate_filters      GLM sub-agent: parse, resolve, validate
    ├── run_scraper           ibilik / iProperty / Facebook
    ├── normalize_listings    GLM sub-agent: extract, translate, deduplicate
    ├── score_listings        deterministic 8-dimension scoring
    ├── generate_report       GLM sub-agent: summary
    ├── prepare_outreach      GLM sub-agent: draft + demo outreach prep
    ├── ask_user              pause + SSE question event
    └── relax_filters         suggest filter changes mid-workflow
    ▼
PostgreSQL  (listings, sessions, outreach_events)
    ▼
SSE stream → Next.js dashboard
```

GLM acts at two levels: the orchestrator decides what to do next across the whole workflow; per-stage sub-agents handle reasoning within each tool call (extraction, translation, scoring explanations, message drafting). Remove GLM and the system has no orchestrator — it cannot decide what to do next, parse intent, normalise listings, or draft outreach.

---

## Tech stack

| Layer | Technology |
|---|---|
| AI model | GLM-5.1 (ilmu.ai) via OpenAI-compatible SDK |
| Backend | Python 3.11, FastAPI (async) |
| Orchestrator | Custom ReAct loop (`glm/orchestrator.py`) |
| Scraping | Playwright (iProperty, Facebook), httpx + BeautifulSoup (ibilik) |
| Database | PostgreSQL + SQLAlchemy |
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Realtime | Server-Sent Events via sse-starlette |
| Messaging | Telethon (Telegram MTProto) for demo outreach to a configured target |

---

## Setup

### Requirements

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) for the frontend lockfile in this repo
- PM2 for the maintained deployment path
- A remote PostgreSQL database exposed through `DATABASE_URL`
- A GLM API key (ilmu.ai, OpenAI, or OpenRouter)

### Backend

```bash
cd backend
uv sync
playwright install chromium
cp .env.example .env
# Set GLM_API_KEY and DATABASE_URL in .env
# Set TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_PHONE / TELEGRAM_DEMO_TARGET
# if you want Telegram demo outreach.
```

To create the Telegram session file manually from a terminal:

```bash
cd backend
uv run python scripts/setup_telegram.py
```

The script prompts for the Telegram API ID/hash, phone number, demo target,
login code, and optional two-step verification password. It creates the
Telethon session file and updates `backend/.env` unless `--no-write-env` is
passed.

### Frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local
```

### Run (development)

```bash
# Terminal 1
cd backend && uv run uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Run (PM2)

PM2 is the maintained deployment path for this repo. Build the frontend first,
then start both processes from the repo root:

```bash
cd frontend && pnpm install && pnpm build
cd ../backend && uv sync
cd ..
pm2 start ecosystem.config.js
pm2 status
```

The backend process expects `DATABASE_URL` to point at a managed PostgreSQL
instance. The checked-in `compose.yml`/`nginx` files are not the supported
deployment path for this hardening pass.

---

## Environment variables

```bash
# backend/.env

# LLM (OpenAI-compatible endpoint)
GLM_API_KEY=your_api_key_here
GLM_MODEL=ilmu-glm-5.1
GLM_BASE_URL=https://api.ilmu.ai/v1    # or https://openrouter.ai/api/v1

# Database
DATABASE_URL=postgresql+psycopg://user:password@host:5432/homie

# Pipeline tuning
DEMO_SEED=false                        # true = use fixture data, skip live scraping
MAX_LISTINGS_PER_SOURCE=25
GLM_ORCHESTRATOR_MAX_ITERATIONS=30
GLM_MAX_ITERATIONS=10
GLM_RETRY_DELAY_SECONDS=5

# Scraper anti-bot delays (seconds)
SCRAPER_REQUEST_DELAY_MIN=1
SCRAPER_REQUEST_DELAY_MAX=3

LOG_LEVEL=INFO

# Optional: required for Facebook scraping
FB_COOKIES_PATH=./fb_cookies.json

# Optional: required for Telegram demo outreach
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_SESSION_PATH=./telegram_session.session
TELEGRAM_DEMO_TARGET=@handle           # demo account that receives messages

# Operator-only setup controls
HOMIE_ADMIN_API_TOKEN=                  # optional token gate; enforced if set
ENABLE_RUNTIME_TELEGRAM_SETUP=false     # true = setup form for API ID/hash, phone, demo target, OTP
ENABLE_FACEBOOK_LOGIN_FLOW=false
GOOGLE_MAPS_API_KEY=
```

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=
```

---

## Project structure

```
homie/
├── backend/
│   ├── main.py                  FastAPI app, all routes, SSE endpoint
│   ├── config.py                Settings from .env
│   ├── glm/
│   │   ├── orchestrator.py      Top-level ReAct loop
│   │   ├── agent.py             Per-stage ReAct loop
│   │   ├── client.py            OpenAI SDK wrapper with retry logic
│   │   ├── chat_agent.py        Conversational intake agent
│   │   └── tools/
│   │       └── orchestrator_tools.py   9 orchestrator tool definitions + implementations
│   ├── workflow/
│   │   ├── state.py             SessionState, FilterObject, NormalizedListing dataclasses
│   │   └── stages/              Legacy stage stubs retained for reference, not runtime
│   ├── scrapers/                ibilik, iProperty, PropertyGuru, Facebook scraper modules
│   ├── scoring/                 Deterministic 8-dimension scoring engine
│   ├── models/db.py             SQLAlchemy models (Session, Listing, OutreachEvent, TelegramConversation)
│   ├── telegram/                Telethon client, outreach agent, reply handler, phone lookup
│   └── tests/                   Unit + integration tests
├── ecosystem.config.js          PM2 process definitions for backend + frontend
├── compose.yml                  Unsupported Docker path retained for reference
└── frontend/
    ├── app/
    │   ├── page.tsx             Landing page (hero, features)
    │   ├── chat/page.tsx        Chat-based filter intake
    │   ├── search/page.tsx      Manual filter form + Telegram setup
    │   ├── workflow/[id]/       Realtime progress feed (SSE consumer)
    │   └── results/[id]/
    │       ├── page.tsx         Ranked listing grid
    │       └── listing/[listingId]/
    │           ├── page.tsx     Single listing deep dive + score breakdown
    │           └── outreach/    Draft, confirm, and send inquiry
    └── components/
        ├── FilterForm.tsx
        ├── ChatFilterSidebar.tsx
        ├── ProgressFeed.tsx
        ├── ListingCard.tsx
        ├── OutreachModal.tsx
        └── TelegramSetupModal.tsx
```

---

## Scoring

Each listing is scored across the active deterministic rubric in
`backend/glm/tools/orchestrator_tools.py`. Base scores are clamped to 0–100
after any GLM-assisted must-have bonus or penalty.

| Dimension | Max | Missing / neutral behavior |
|---|---:|---|
| Price | 30 | Unknown price receives 15 |
| Location | 20 | Empty requested location receives 10; requested locations use word overlap |
| Room type | 15 | `any` or unknown receives 10 |
| Contact info | 10 | No phone or Telegram receives 0 |
| Images | 5 | No images receives 0 |
| Furnished status | 10 | `any` or unknown receives 7 |
| Gender restriction | 5 | `any`, unknown, or mixed receives 5 |
| Transport proximity | 5 | No transport preference receives 5 |

---

## Demo fallback

Set `DEMO_SEED=true` to have Stage 2 return pre-saved fixture listings instead of live scraping. All subsequent stages (normalization, scoring, report, outreach) run normally with real GLM calls. Use this if scrapers are blocked during a demo.

## Operational notes

- Runtime Telegram credential setup and Facebook browser login are disabled by default. Telegram setup is exposed by `ENABLE_RUNTIME_TELEGRAM_SETUP=true`; if `HOMIE_ADMIN_API_TOKEN` is set, the setup form requires it. Facebook browser login still requires `HOMIE_ADMIN_API_TOKEN` plus its matching feature flag.
- Telegram demo outreach sends generated messages to `TELEGRAM_DEMO_TARGET`. It does not contact landlords directly.
- Use the PM2 path above for deployment. Docker Compose and nginx config are retained for reference only and are not the supported release path.
