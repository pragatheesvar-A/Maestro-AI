# Maestro AI — Architecture

## 1. Design principle

```
LLM / Agents  ->  understand requirements  ->  structured parameters
             ->  candidate generation  ->  OR-Tools CP-SAT
             ->  solution  ->  verification  ->  LLM explanation
```

The LLM never assigns anyone to anything. `app/agents/graph.py` runs a
bounded (acyclic) LangGraph workflow: Manager Agent parses a natural
language instruction into structured optimizer weights, three "sub-agent"
nodes attach read-only context (skill-graph size, current fairness/SLA
snapshot), then a single deterministic tool call (`optimizer/engine.py`)
does candidate generation, scoring, and the actual CP-SAT solve. A
verification step re-checks every hard constraint on the solver's output.
Only then does the Explanation Agent (`app/agents/explanation.py`) turn the
already-computed structured facts (reason codes, scores) into a sentence —
and it is constitutionally incapable of introducing a fact that isn't in
that structured input, whether it's using the deterministic template or an
LLM rephrasing pass.

## 2. Request-time architecture

```
Next.js (React/TS/Tailwind, TanStack Query, Zustand)
        |  REST (JWT) + WebSocket
FastAPI (Pydantic, SQLAlchemy, JWT/RBAC, rate limiting)
        |
Event Orchestrator (Redis Streams, in-process fallback)
        |
LangGraph bounded workflow (app/agents/graph.py)
   Manager Agent -> Skill Agent -> Workload Agent -> SLA Agent
        |
Intelligence Engine (app/optimizer/engine.py)
   Vector similarity (sentence-transformers or hashed fallback)
   Skill graph (NetworkX)             ML prediction (SLA-risk / completion-time)
        |
Candidate Generator -> Top-K funnel (app/optimizer/candidates.py)
        |
Optimization Engine -> OR-Tools CP-SAT (app/optimizer/solver.py)
        |
Solution Verifier (re-checks hard constraints; app/optimizer/engine.py::_verify_solution)
        |
Decision Trace + Explanation Agent -> persisted (DecisionLog)
        |
WebSocket broadcast (/ws/allocation) -> React dashboard updates live
```

## 3. Technology stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, TanStack Query, Zustand, Recharts | shadcn/ui-style components hand-built to avoid a CLI/network dependency at build time; same visual language |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | async-ready; `app/main.py` |
| Auth | JWT (python-jose), passlib/bcrypt, RBAC (ADMIN/MANAGER/EMPLOYEE) | `app/auth.py` |
| Optimization | Google OR-Tools CP-SAT | `app/optimizer/solver.py` |
| Semantic matching | hashed n-gram embeddings (sentence-transformers auto-used if installed) + NetworkX skill graph | `app/services/skills.py` |
| ML | scikit-learn GradientBoosting (XGBoost/LightGBM substitute — see README) | `app/ml/train_sla.py` |
| Data | PostgreSQL (docker-compose) or SQLite (zero-install local dev) | `app/database.py` |
| Events | Redis Streams with in-process asyncio fallback | `app/services/events.py` |
| Real-time | native WebSockets | `app/routers/ws.py`, `lib/ws.ts` |
| Agents | LangGraph (bounded, acyclic) | `app/agents/graph.py` |
| DevOps | Docker, docker-compose, GitHub Actions, Nginx | `docker-compose.yml`, `.github/workflows/ci.yml` |

## 4. Optimization formulation

Decision variable: `X(employee, task) ∈ {0,1}`, generated only for
candidates that survive the hard-constraint funnel (never one variable per
employee × per task for the whole company).

**Hard constraints**
1. `sum_e X(e,t) + u(t) = 1` for every task `t` (assigned to exactly one
   candidate, or explicitly unassigned via slack variable `u(t)`).
2. An employee with `availability_status != AVAILABLE` has no candidate
   variable for any task at all (enforced upstream in the funnel, not just
   in the solver).
3. `sum_t hours(t) * X(e,t) <= headroom(e)` for every employee `e`
   (capacity), where `headroom` already accounts for hours committed by
   tasks outside the current optimization batch.
4. Mandatory certifications and working-hours/location eligibility are
   enforced in the hard-filter stage before any variable is created.

**Soft objective (scalarized, weight-tiered to approximate lexicographic
ordering — see `app/optimizer/solver.py` docstring for the full rationale):**

```
maximize  Σ [ W_SLA*(1-sla_risk) + W_PRIORITY*priority + W_SKILL*skill_match
            + W_FAIRNESS*(1-fairness_penalty) + W_PREFERENCE*preference
            + W_CONTINUITY*(kept same employee) - W_TRAVEL*travel
            - W_REASSIGNMENT*(changed employee) ] * X(e,t)
          - UNASSIGNED_PENALTY * Σ u(t)
```

A genuine two-stage lexicographic solve runs first: stage 1 minimizes
`Σ u(t)` (total unassigned tasks) to optimality and pins that count as a
constraint; stage 2 then maximizes the weighted objective only among
solutions that already achieve the minimum unassigned count. If stage 2
can't re-converge within its time budget, the engine falls back to stage
1's already-proven-feasible solution rather than ever returning "nothing
assigned."

## 5. Minimum-disruption reallocation

`app/optimizer/disruption.py`: when an employee goes `UNAVAILABLE`,
`find_affected_tasks` selects only their active assignments; every other
assignment in the system is left untouched (never re-solved). The affected
tasks are re-optimized against the full previous-assignment map (so the
reassignment-cost term in the objective is computed correctly), and
`engine._verify_solution` re-checks all hard constraints on the result
before it's persisted or broadcast.

## 6. Candidate generation funnel

`app/optimizer/candidates.py`: hard filter (availability, capacity headroom,
certifications) → semantic skill scoring (embedding cosine similarity +
skill-graph transferability, `max()`'d together) → Top-K (default 20) by
score. Only the survivors get a CP-SAT variable.

## 7. Database schema

All 16 tables from the spec are implemented in `app/models.py`: `users`,
`employees`, `skills`, `employee_skills`, `skill_relationships` (graph
edges), `tasks`, `task_requirements`, `assignments`, `availability`,
`employee_preferences`, `workload_history`, `task_history`,
`allocation_events`, `decision_logs`, `sla_predictions`, `notifications`.
Embeddings are JSON-encoded float arrays (see README for the pgvector
upgrade path).

## 8. API surface

`POST /auth/login`, `GET/POST/PATCH /employees`, `PATCH
/employees/{id}/availability`, `GET/POST/PATCH /tasks`, `POST
/allocation/optimize`, `POST /allocation/reallocate`, `POST
/events/employee-unavailable`, `GET /allocation/{task_id}`, `GET
/allocation/{task_id}/explanation`, `GET
/allocation/{task_id}/decision-trace`, `POST /agents/manager`, `GET
/analytics/{workload,fairness,sla,dashboard,notifications}`, `WS
/ws/allocation`.

## 9. Frontend pages

Login, Dashboard, Employees, Tasks, Live Allocation (the primary demo
surface, including the "Simulate Employee Unavailable" pipeline animation
and "Why this employee?" decision-trace modal), Workload & Fairness, SLA
Analytics, AI Decision Center, Alerts, Admin Settings — all 11 pages from
the spec, each backed by real API calls (no dead buttons).
