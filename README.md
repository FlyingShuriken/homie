# Homie

AI-powered rental aggregation and search for Malaysia. Built for UMHackathon 2026 — Domain: AI Systems & Agentic Workflow Automation.

---

## What it does

Renters in Malaysia deal with listings scattered across ibilik, iProperty, and Facebook — each with different formats, languages, and data quality. Homie aggregates them into a single ranked, explainable shortlist.

You enter your preferences once. A GLM-5.1 orchestration agent decides how to run the search, scrapes multiple platforms, normalises multilingual listings, scores each one against your priorities, and helps you draft landlord outreach — all from one dashboard.

---

## Architecture

```
Browser (Next.js)
    │  POST /api/search          submit filters, start pipeline
    │  GET  /api/search/{id}/stream   SSE progress feed
    │  GET  /api/search/{id}/results  scored listings
    │  POST /api/outreach/draft   request inquiry drafts
    │  POST /api/outreach/handoff confirm + log handoff
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
| AI model | GLM-5.1 (ZhipuAI) via `zhipuai` Python SDK |
| Backend | Python 3.11, FastAPI (async) |
| Orchestrator | Custom ReAct loop (`glm/orchestrator.py`) |
| Scraping | Playwright (iProperty, Facebook), httpx + BeautifulSoup (ibilik) |
| Database | PostgreSQL + SQLAlchemy |
| Frontend | Next.js 14, Tailwind CSS, shadcn/ui |
| Realtime | Server-Sent Events via sse-starlette |

---

## Setup

### Requirements

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker Desktop or another local PostgreSQL 15+ instance
- A ZhipuAI API key with GLM-5.1 access

### Backend

```bash
docker compose up -d postgres

cd backend
uv sync
playwright install chromium
cp .env.example .env
# Set GLM_API_KEY in .env
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
GLM_API_KEY=your_zhipuai_api_key_here
GLM_MODEL=glm-5.1
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/homie
DEMO_SEED=false                      # true = use fixture data, skip live scraping
MAX_LISTINGS_PER_SOURCE=25
GLM_ORCHESTRATOR_MAX_ITERATIONS=30
GLM_MAX_ITERATIONS=10
GLM_RETRY_DELAY_SECONDS=5
SCRAPER_REQUEST_DELAY_MIN=1
SCRAPER_REQUEST_DELAY_MAX=3
LOG_LEVEL=INFO
```

---

## Project structure

```
homie/
├── backend/
│   ├── main.py                  FastAPI app, all routes, SSE endpoint
│   ├── config.py                Settings from .env
│   ├── glm/
│   │   ├── orchestrator.py      Top-level GLM ReAct loop
│   │   ├── agent.py             Per-stage GLM ReAct loop
│   │   ├── client.py            ZhipuAI SDK wrapper with retry logic
│   │   └── tools/
│   │       └── orchestrator_tools.py   9 orchestrator tool definitions + implementations
│   ├── workflow/
│   │   ├── state.py             SessionState dataclass
│   │   └── stages/              Tool implementations (validate, scrape, normalize, score, report, outreach)
│   ├── scrapers/                ibilik, iProperty, Facebook scraper modules
│   ├── scoring/                 Deterministic 8-dimension scoring engine
│   ├── models/db.py             SQLAlchemy models
│   └── tests/                   Unit + integration tests
├── compose.yml                  Local PostgreSQL for development
└── frontend/
    ├── app/
    │   ├── page.tsx             Filter form
    │   └── results/[id]/page.tsx  Progress feed + listing cards
    └── components/
        ├── FilterForm.tsx
        ├── ProgressFeed.tsx
        ├── ListingCard.tsx
        └── OutreachModal.tsx
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
