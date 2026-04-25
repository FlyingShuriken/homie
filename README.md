# Homie

[Project Pitching Video](https://drive.google.com/file/d/1Z2CedhMO_cFvnzi-G2JIJ7GXDB29U0Rx/view?usp=sharing)

AI-powered rental aggregation and search for Malaysia. Built for UMHackathon 2026 — Domain: AI Systems & Agentic Workflow Automation.

---

## What it does

Renters in Malaysia deal with listings scattered across ibilik, iProperty, and Facebook — each with different formats, languages, and data quality. Homie aggregates them into a single ranked, explainable shortlist.

You enter your preferences once — via a **manual form** or a **conversational chat agent** that extracts your filters from natural language. A GLM orchestration agent decides how to run the search, scrapes multiple platforms, normalises multilingual listings, scores each one against your priorities, and helps you draft landlord outreach — all from one dashboard.

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
    ├── prepare_outreach      GLM sub-agent: draft + Telegram handoff
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
| Messaging | Telethon (Telegram MTProto) for automated landlord outreach |

---

## Setup

### Requirements

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker Desktop or another local PostgreSQL 15+ instance
- A GLM API key (ilmu.ai, OpenAI, or OpenRouter)

### Backend

```bash
docker compose up -d postgres

cd backend
uv sync
playwright install chromium
cp .env.example .env
# Set GLM_API_KEY in .env
# Set TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_PHONE if you want automated Telegram outreach
# Override DATABASE_URL if you are not using the bundled local Postgres service
```

### Frontend

```bash
cd frontend
npm install
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

---

## Environment variables

```bash
# backend/.env

# LLM (OpenAI-compatible endpoint)
GLM_API_KEY=your_api_key_here
GLM_MODEL=ilmu-glm-5.1
GLM_BASE_URL=https://api.ilmu.ai/v1    # or https://openrouter.ai/api/v1

# Database
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/homie

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

# Optional: required for automated Telegram outreach
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_SESSION_PATH=./telegram_session.session
TELEGRAM_DEMO_TARGET=@handle           # Telegram handle to demo-message
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
│   │   └── stages/              Tool implementations (validate, scrape, normalize, score, report, outreach)
│   ├── scrapers/                ibilik, iProperty, PropertyGuru, Facebook scraper modules
│   ├── scoring/                 Deterministic 8-dimension scoring engine
│   ├── models/db.py             SQLAlchemy models (Session, Listing, OutreachEvent, TelegramConversation)
│   ├── telegram/                Telethon client, outreach agent, reply handler, phone lookup
│   └── tests/                   Unit + integration tests
├── compose.yml                  Local PostgreSQL for development
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

Each listing is scored 0–100 across 8 dimensions. Unknown fields receive partial scores — a listing is not penalised for information its landlord didn't provide.

| Dimension | Max | Unknown score |
|---|---|---|
| Price | 25 | 10 |
| Location | 20 | 5 |
| Room type | 15 | 5 |
| Transport proximity | 15 | 5 |
| Furnished status | 10 | 5 |
| Parking | 8 | 4 |
| Pet-friendly | 4 | 2 |
| Gender restriction | 3 | 1.5 |

---

## Demo fallback

Set `DEMO_SEED=true` to have Stage 2 return pre-saved fixture listings instead of live scraping. All subsequent stages (normalization, scoring, report, outreach) run normally with real GLM calls. Use this if scrapers are blocked during a demo.
