# Maestro AI

AI-powered dynamic workforce & task allocation platform. Tasks are assigned to
employees by a real Google OR-Tools CP-SAT optimizer using semantic skill
matching, workload fairness, SLA-risk prediction, and minimum-disruption
reallocation — with a bounded LangGraph agent workflow orchestrating the
pipeline and generating factual, structured-data-only explanations.

**The LLM never assigns anyone to anything.** It parses natural language into
structured parameters and rephrases already-computed decision data. The
CP-SAT solver makes every actual assignment, and a solution verifier
re-checks every hard constraint before anything is persisted or broadcast.

## The demo (primary scenario)

1. Log in as Manager (`manager@smartalloc.ai` / `manager123`).
2. Open **Live Allocation** — task `T4021` is assigned to **Priya**.
3. Click **🚨 Simulate Employee Unavailable**, select Priya.
4. Watch the pipeline run live: Disruption Detected → Impact Analysis →
   Re-Optimization (CP-SAT) → Solution Verification → Allocation Updated —
   then the dashboard updates over WebSocket, no page refresh.
5. `T4021` is now assigned to **Karthik**, with a factual explanation:
   *"Karthik was selected for Implement user authentication flow because
   Priya became unavailable, so Karthik has 100% skill compatibility,
   sufficient remaining capacity, low SLA risk, a workload-balanced choice,
   and the reassignment minimizes disruption to the existing schedule."*
6. Click **Explain** on any task to see the full decision trace: every
   candidate considered, their scores, and why the winner won.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
# frontend: http://localhost:3000   backend: http://localhost:8000
# (or http://localhost/ via the nginx reverse proxy)
```

The backend container runs `python -m app.seed` on startup, so the database
is populated with the full demo dataset automatically.

## Quick start (local, no Docker)

Backend:

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m app.ml.train_sla     # trains the SLA-risk / completion-time models
python -m app.seed             # seeds 30 employees, 100 tasks, runs initial optimization
uvicorn app.main:app --reload  # http://localhost:8000
```

With no `DATABASE_URL` set, the backend uses a local SQLite file
(`smartalloc.db`) automatically — no Postgres install required to run the
demo. With no `REDIS_URL` reachable, the event bus transparently falls back
to an in-process queue. Both are genuine "local deterministic fallback"
implementations, not stubs — set `DATABASE_URL`/`REDIS_URL` to point at real
Postgres/Redis (e.g. via `docker compose up postgres redis`) to use them
instead.

Frontend:

```bash
cd frontend
npm install
npm run dev                    # http://localhost:3000
```

## Login accounts (seeded)

| Role     | Email                      | Password      |
|----------|-----------------------------|---------------|
| Manager  | manager@smartalloc.ai      | manager123    |
| Admin    | admin@smartalloc.ai        | admin123      |
| Employee | employee@smartalloc.ai     | employee123   |

## Running tests

```bash
cd backend
pytest -q
```

35 tests cover employee/task CRUD, semantic skill matching (including
transferable-skill scoring via the skill graph), the CP-SAT solver's hard
constraints (capacity, availability, exactly-one-assignment), fairness
metrics, the SLA-risk model, JWT auth + RBAC, the WebSocket channel, and —
most importantly — the full disruption integration test: an employee
becomes unavailable → affected task detected → real optimizer re-solves →
verifier passes → decision trace generated → explanation is factual.

## Environment variables

See `.env.example` (root, for docker-compose) and `backend/.env.example`
(for local/backend-only dev). Every variable has a safe default; the only
one you would ever need to set for a real deployment is `JWT_SECRET`
(and `ANTHROPIC_API_KEY` if you want LLM-phrased explanations instead of the
deterministic template — both are fully factual either way).

## What's implemented vs. scoped out

Per the project's own stated priority order (P0 must never be sacrificed for
P2), this build is complete on P0 and P1, with two P2 items substituted for
lighter, dependency-free equivalents so the whole stack runs without any
external services or heavy downloads:

- **Neo4j → NetworkX.** The skill knowledge graph (`Employee -[:HAS_SKILL]->
  Skill`, `Skill -[:RELATED_TO]-> Skill`) is implemented with NetworkX
  in-process, exactly as the spec allows ("NetworkX if Neo4j is excessive for
  the MVP"). The graph API is isolated in `app/services/skills.py` so
  swapping in real Neo4j later only touches that module.
- **BGE-M3/E5 + cross-encoder → hashed n-gram embeddings + skill graph.**
  `sentence-transformers` is attempted first and used automatically if
  installed; otherwise a deterministic hashed-trigram embedding provides the
  same fixed-length-vector, cosine-similarity interface so candidate scoring
  never changes shape. This is a real, working, documented fallback — not a
  stub — and it's what the seeded demo actually runs on.
- **XGBoost/LightGBM → scikit-learn GradientBoosting.** Same reasoning:
  those libraries need platform-specific native wheels that are unreliable
  in a locked-down build environment. `GradientBoostingClassifier`/
  `Regressor` are the same algorithm family, trained on a clearly labeled
  **synthetic** dataset (see `app/ml/train_sla.py` for the generation code
  and the printed holdout AUC/MAE — no real-world accuracy is claimed).
- **pgvector → JSON float arrays + Python cosine similarity.** Works
  identically on SQLite (zero-install dev) and Postgres; swapping to a real
  `vector` column is a documented drop-in change once pgvector is enabled.
- **Kafka/Redpanda → Redis Streams, with an in-process fallback.** The event
  bus (`app/services/events.py`) tries Redis Streams first and falls back to
  an asyncio queue if Redis isn't reachable, matching the spec's own
  "in-process fallback" requirement and keeping the publish/consume
  interface stable for a future Kafka swap.
- **Neo4j/Kafka/RAG/predictive-unavailability/negotiation agents (P2)**:
  intentionally not built, per the spec's own instruction to never trade P0
  for P2 under time constraints.

Everything else — FastAPI, PostgreSQL-or-SQLite persistence, real OR-Tools
CP-SAT optimization (hard constraints + weighted multi-objective + a
lexicographic top tier that minimizes unassigned tasks), the candidate
generation funnel, minimum-disruption reallocation, Jain/Gini fairness,
JWT + RBAC, WebSocket real-time push, the bounded LangGraph agent workflow,
and all 11 frontend pages — is fully implemented and working end to end,
verified by the test suite and a live manual run of the disruption demo.

## Folder structure note

The spec's suggested monorepo layout lists `optimizer/`, `ai/`, `ml/`, and
`database/` as top-level siblings of `backend/`. Since all of that code
needs to import shared config/DB/model modules and run inside the one
FastAPI process, it's organized as sub-packages of the backend instead —
`backend/app/optimizer/`, `backend/app/agents/` (the LangGraph/agent code),
`backend/app/ml/`, `backend/app/services/` (skills, fairness, events,
websockets) — which avoids Python path hacks while keeping each concern in
its own clearly named module. `database/` becomes `backend/alembic/` +
`backend/app/models.py` (schema) and `backend/app/seed.py` (demo data),
since migrations and the ORM models are tightly coupled and benefit from
living together.

```
smartalloc-ai/
├── frontend/            Next.js app (11 pages, lib/, components/)
├── backend/
│   ├── app/
│   │   ├── routers/     FastAPI route handlers (REST + WebSocket)
│   │   ├── services/    skills, fairness, sla_model, events, websocket_manager
│   │   ├── optimizer/   candidates funnel, CP-SAT solver, engine, disruption
│   │   ├── agents/      LangGraph workflow, deterministic tools, explanation
│   │   ├── ml/          synthetic SLA-risk / completion-time model training
│   │   ├── models.py    SQLAlchemy schema (16 tables)
│   │   └── seed.py      deterministic demo data generator
│   ├── alembic/          migrations
│   └── tests/            35 pytest tests
├── docker/                nginx.conf
├── scripts/               dev_setup.sh
├── docker-compose.yml
├── .env.example
├── README.md
└── architecture.md
```

See `architecture.md` for the full design writeup.
