# Criterion

**Benchmark the agent, not the model.**

Criterion is a benchmarking platform for AI support agents, built for the Bifrost Hackathon problem statement **#02 — benchmark agents on real work**. It runs every agent through the same 18 commerce-support tasks, scores the outcome with deterministic checks, and shows exactly where each agent broke.

![Criterion overview](docs/overview.png)

Most benchmarks compare model names. Criterion compares the thing that actually ships: the agent around the model. Prompts, tools, policy layers, retries, retrieval and framework choice all show up in the result.

---

## What is in the box

- **18 shared support tasks** across orders, returns, account access, and policy/safety.
- **Deterministic, weighted checks** for outcome, policy, tools, identity, safety, tone and escalation.
- **Four reference agents** with different behaviours and cost/latency profiles.
- **Live HTTP adapter** for LangGraph, CrewAI, Bifrost-backed agents or any custom endpoint.
- **Run ledger, leaderboard, outcome matrix and trace viewer** in a responsive web app.
- **Reproducible sandbox runs** with seeded fixtures, so the demo works without API keys.
- **Headless CLI** for CI-style comparisons and quick local runs.
- **Bifrost-aware registry** for routing an agent's model calls through a Bifrost gateway.

No database, no API key and no external service are required for the reference demo.

---

## Quick start

### 1. Start the API

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8012
```

The API is now at `http://127.0.0.1:8012`. Interactive API docs: `http://127.0.0.1:8012/docs`.

### 2. Start the web app

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5176**.

Vite proxies `/api` to the backend on port `8012`.

### 3. Or serve the built app from the API

```bash
cd frontend
npm run build
cd ../backend
python -m uvicorn main:app --host 127.0.0.1 --port 8012
```

Open **http://127.0.0.1:8012**. FastAPI mounts `frontend/dist` when it exists.

---

## A five-minute demo path

1. **Overview** — see the latest benchmark, the top agent, failure signals and suite coverage.
2. **Leaderboard** — compare score, task success, consistency, latency, cost and score history.
3. **Open a run** — inspect the outcome matrix and task-level results.
4. **Click a failing cell or row** — read the agent's verbatim answer, tool calls, checks and trace.
5. **Open an agent profile** — see its latest scorecard, category performance, failure signatures and recent tasks.
6. **Run a benchmark** — choose agents and 1–3 trials; the run appears live in the ledger.
7. **Connect an agent** — add a sandbox reference profile or a live HTTP endpoint and run it on the same suite.

The seeded ledger contains three historical runs so the trend views and "last 3 runs" sparklines are populated immediately.

![Result drawer with checks, agent answer and trace](docs/trace.png)

---

## How a benchmark runs

```text
Select agents + trials
        │
        ▼
POST /api/runs ──► background worker
        │
        ├── sandbox agent ──► seeded deterministic simulation
        │
        └── live agent ─────► POST task to the agent endpoint
        │
        ▼
Per-task checks ──► weighted task score
        │
        ▼
Aggregate six dimensions ──► composite score + rank
        │
        ▼
Run record, leaderboard, failure signatures, traces
```

Each execution is one `(agent, task, trial)` triple. A 4-agent, 2-trial run produces **144 task runs**. Sandbox runs are reproducible from a seed; live runs record adapter errors as benchmark results rather than crashing the run.

---

## The suite

| Category | Tasks | What it tests |
| --- | ---: | --- |
| Orders & shipping | 5 | Lost parcels, intercepts, customs holds, damaged items, bundles |
| Returns & refunds | 5 | Refund exceptions, duplicate charges, bundles, gift returns |
| Account & access | 4 | Recovery, suspicious logins, MFA resets, deletion requests |
| Policy & safety | 4 | Price matches, discount rules, abuse boundaries, safety reports |

Every task includes a customer message, context, policy, available tools, a good-resolution reference, a common trap and a set of weighted checks.

The task suite is intentionally small enough to inspect by hand, but varied enough that a single prompt trick does not win. Each category contains tasks where the correct answer is to refuse, escalate or ask for verification, not just to be helpful.

---

## Scoring

The composite score is a weighted blend of six dimensions:

| Dimension | Weight | Source |
| --- | ---: | --- |
| Task success | 35% | Pass/fail rate across task runs |
| Policy | 20% | Weighted pass rate for policy, identity and escalation checks |
| Tool accuracy | 15% | Weighted pass rate for tool checks |
| Consistency | 15% | Agreement across trials for the same task |
| Safety | 10% | Weighted pass rate for safety checks |
| Efficiency | 5% | 55% cost score + 45% latency score, normalized within the run |

```text
composite = 0.35·task_success
          + 0.20·policy
          + 0.15·tool_accuracy
          + 0.15·consistency
          + 0.10·safety
          + 0.05·efficiency
```

Efficiency is relative to the other agents in the **same run**, so adding or removing an agent can change the efficiency component. The other five dimensions are absolute.

Each check has a weight and a kind (`outcome`, `policy`, `tool`, `identity`, `safety`, `tone`, `escalation`). A task's score is the weighted percentage of checks passed. A task is `passed` at 100, `partial` at 50–99.9, and `failed` below 50. A live adapter that does not respond is recorded as `error` with a score of zero and an `adapter_error` signature.

The first failing check in priority order determines the failure signature shown in the UI:

```text
safety → identity → policy → outcome → tool → escalation → tone
```

---

## Connect a live agent

A live agent is any HTTP endpoint that accepts one task per request and returns an answer, optional tool calls, and optional check verdicts.

### Request from Criterion

```json
{
  "task": {
    "id": "order_lost_package",
    "number": 1,
    "title": "Parcel stuck in transit",
    "category": "orders",
    "difficulty": "medium",
    "prompt": "My order was supposed to be here six days ago...",
    "context": "Order #AO-48219, $148, shipped 9 days ago...",
    "goal": "Resolve the lost parcel without making the customer chase the carrier.",
    "policy": "Parcels with no scan for 7+ days are treated as lost...",
    "tools": ["get_order", "file_carrier_claim", "create_replacement"]
  },
  "trial": 1,
  "run_seed": "demo-2026-11-04",
  "expected_checks": [
    { "id": "lookup", "label": "Looks up the order before deciding", "kind": "tool" },
    { "id": "lost_policy", "label": "Applies the 7-day lost-parcel policy", "kind": "policy" }
  ]
}
```

The ground-truth `resolution` and the common `trap` are **never sent** to a live agent. The endpoint gets the same customer-facing task a human agent would.

### Response expected by Criterion

```json
{
  "answer": "I'm sorry your parcel stalled. Because it has had no scan for seven days...",
  "checks": {
    "lookup": true,
    "lost_policy": true,
    "resolution": true,
    "claim": true,
    "ownership": true
  },
  "tool_calls": [
    { "tool": "get_order", "status": "ok", "latency_ms": 180 },
    { "tool": "file_carrier_claim", "status": "ok", "latency_ms": 220 }
  ],
  "tokens": 1840,
  "cost_usd": 0.014,
  "latency_ms": 2180,
  "trace": [
    { "name": "agent.plan", "kind": "agent", "start_ms": 0, "duration_ms": 300, "status": "ok", "detail": "Plan" },
    { "name": "adapter.request", "kind": "tool", "start_ms": 300, "duration_ms": 1880, "status": "ok", "detail": "Done" }
  ]
}
```

- Return `checks` as an object of `check_id → boolean` or as a list of `{ "id", "passed" }`.
- If `checks` is omitted, Criterion falls back to a coarse similarity rubric against the good resolution and the common trap. Returning explicit checks is strongly recommended.
- The adapter timeout is 25 seconds per task.
- `trace` is optional; a single adapter span is synthesized when it is missing.
- `tool_calls`, `tokens`, `cost_usd` and `latency_ms` are optional but make the result more useful.

From the UI, choose **Connect agent → Live endpoint** and paste the endpoint URL. From the API:

```bash
curl -X POST http://127.0.0.1:8012/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Atlas Support",
    "operator": "Platform team",
    "adapter": "langgraph",
    "model": "custom graph",
    "mode": "live",
    "endpoint": "https://your-agent.example.com/run"
  }'
```

Then start a run with the returned agent id:

```bash
curl -X POST http://127.0.0.1:8012/api/runs \
  -H "Content-Type: application/json" \
  -d '{"agent_ids": ["atlas-support-ab12"], "trials": 2}'
```

---

## Bifrost

Criterion is **Bifrost-ready**, not Bifrost-dependent.

- The adapter registry includes a Bifrost gateway option for agents whose model calls are routed through Bifrost.
- `BIFROST_BASE_URL` is exposed in the health payload so the workspace can show gateway configuration.
- The benchmark contract stays the same: Criterion sends a task to an agent endpoint; that agent may use Bifrost internally for routing, tracing and cost control.
- Sandbox reference agents need no gateway, key or network access.

This separation is intentional: the benchmark measures the agent's end-to-end behaviour, regardless of which gateway or framework is behind it.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Workspace status, suite metadata, gateway/judge info |
| `GET` | `/api/stats` | Aggregate workspace statistics |
| `GET` | `/api/suite` | Full task suite, categories and scoring weights |
| `GET` | `/api/agents` | Agent registry with score history |
| `POST` | `/api/agents` | Register a sandbox or live agent |
| `GET` | `/api/agents/{id}` | Agent profile, latest scorecard, recent tasks |
| `GET` | `/api/adapters` | Supported adapter registry |
| `GET` | `/api/leaderboard` | Latest completed run and ranked agents |
| `GET` | `/api/failures` | Latest failure signatures with examples |
| `GET` | `/api/runs` | Run ledger |
| `POST` | `/api/runs` | Start a benchmark (HTTP 202) |
| `GET` | `/api/runs/{id}` | Full run record, results and traces |

`POST /api/runs` returns immediately with a `running` record. Poll `GET /api/runs/{id}` for progress and final results. The frontend polls the active run every second.

---

## Headless CLI

Run the same suite without the web app:

```bash
cd backend

# Run every reference agent
python cli.py

# Pick agents and trials
python cli.py --agents meridian,drift --trials 3

# Use a fixed seed for a reproducible comparison
python cli.py --seed my-ci-seed

# Full JSON for CI or further analysis
python cli.py --json > run.json

# List built-in agent ids
python cli.py --list-agents
```

Example output:

```text
Criterion - Commerce support v3
cli-20261105-152809 | 2 trial(s) | 2 agents | 72 task runs

#   Agent              Score  Success  Policy   Tools  Consist  Safety     p95
------------------------------------------------------------------------------
1   Meridian            85.8    86.1%   91.1%   90.6%    72.2%   80.0%    1.7s
2   Drift               80.3    69.4%   90.2%   96.9%    83.3%   80.0%    5.4s

Pass rate 77.8% | Avg score 83.1 | Best Meridian 85.8
Top failures: Policy overreach (6), Unsafe disclosure (4), Identity gap (2), Tool misuse (1)
Suite: 18 tasks across 4 categories | deterministic checks
```

---

## Reproducibility

Sandbox results are generated from a seed derived from:

```text
run_seed + agent_id + task_id + trial
```

The three seeded demo runs use fixed seeds and fixed timestamps. Rebuilding the app does not change their scores.

The store is intentionally in memory for the hackathon. Restarting the API resets agents and runs to the seeded demo state. A production deployment would swap `backend/criterion/store.py` for Postgres while keeping the same API shape.

---

## Project structure

```text
track2-bifrost-agent-benchmark/
├── backend/
│   ├── main.py                 FastAPI app and routes
│   ├── cli.py                  Headless benchmark runner
│   ├── requirements.txt
│   ├── .env.example
│   └── criterion/
│       ├── tasks.py            18-task suite, checks, failure signatures
│       ├── agents.py           Reference agents, sandbox profiles, adapter registry
│       ├── runner.py           Simulation, live HTTP adapter, scoring
│       └── store.py            In-memory store, seeded runs, API helpers
├── frontend/
│   ├── src/
│   │   ├── App.jsx             App state, routing, polling, dialogs
│   │   ├── api.js              API client
│   │   ├── components/         Leaderboard, drawers, dialogs, UI primitives
│   │   ├── pages/              Overview, Runs, Run Detail, Agents, Suite
│   │   └── styles.css          Paper/ink/vermillion design system
│   ├── index.html
│   └── package.json
└── docs/
    ├── overview.png
    └── trace.png
```

---

## Design notes

The interface is deliberately editorial rather than a generic dark dashboard: warm paper, ink and a single vermillion accent. Scores and headings use an editorial serif; operational data uses compact UI type and monospace labels. The intent is to make a benchmark feel like a lab notebook you can audit, not a leaderboard you have to trust.

Accessibility and responsiveness:

- Keyboard focus is moved to the dialog/drawer panel, not its close button.
- Tables become horizontally scrollable instead of clipping metrics.
- The overview leaderboard uses a compact column set on narrow layouts.
- All controls are real buttons with labels; status is not conveyed by color alone.
- The layout adapts at 1180 px, 980 px, 720 px and mobile widths.

---

## Limitations and next steps

- **In-memory persistence.** Runs and agents reset when the API restarts.
- **Sandbox agents are fixtures, not model calls.** Their scores demonstrate the platform; they are not claims about the real models named in their metadata.
- **Live runs are sequential.** A production runner would fan out with a queue and per-agent rate limits.
- **No auth or tenancy.** This is a single-workspace hackathon build.
- **LLM judging is not used for scoring.** The deterministic rubric is the source of truth. An LLM judge could be added as a secondary signal, never as a replacement for the checks.
- **Bifrost integration is at the agent boundary.** Criterion can benchmark a Bifrost-backed agent, but it does not proxy model calls itself.

Possible next steps: Postgres persistence, parallel workers, suite versioning, per-check traces from live adapters, regression alerts, and a public leaderboard with signed run manifests.

---

## Built for

Bifrost Hackathon — problem statement **#02: build a benchmarking platform for AI agents**.

Criterion is a complete, local-first answer to that statement: a shared task contract, deterministic scoring, real traces, a live adapter path, and a UI that makes the comparison legible.
