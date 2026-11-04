# 🌐 AI Global Hackathon — Dual-Track Portfolio
> **Geek Room × HackCulture AI Global Hackathon**  
> Complete dual-track project submission portfolio covering both sponsor tracks.

---

## 🏆 Portfolio Overview

| Track | Partner | Problem Statement Selected | Project Name | Directory | Ports |
|---|---|---|---|---|---|
| **Track 1** | **Tavily by Nebius** | **#01: Stale-Answer Detector** | [🔍 Stale-Answer Detector](track1-tavily-stale-detector/README.md) | `track1-tavily-stale-detector/` | Backend: `8000`<br>Frontend: `5173` |
| **Track 2** | **Bifrost / Maxim AI** *(Title Partner)* | **#01: Coding Agent on Fewest Tokens** | [⚡ TokenSlim](track2-bifrost-token-agent/README.md) | `track2-bifrost-token-agent/` | Backend: `8001`<br>Frontend: `5174`<br>CLI: `cli.py` |
| **Track 2** | **Bifrost / Maxim AI** *(Title Partner)* | **#02: Agent Reliability Platform** | [⚗ Faultline](track2-bifrost-agent-reliability/README.md) | `track2-bifrost-agent-reliability/` | Backend: `8002`<br>Frontend: `5175`<br>CLI: `cli.py` |

---

## 🚀 One-Command Automated Portfolio Verification

Run all automated test suites across both projects with a single command from the project root:
```bash
npm test
```
This runs:
1. Track 1 Backend Test Suite (Health, Presets, Stale Detection, Fresh Scoring, Input Validation)
2. Track 2 Backend Test Suite (Health, Presets, TokenSlim Verification, Input Validation)
3. Track 2 CLI Benchmark Verification (Sliding Window Rate Limiter Edge Case)

---

## 🔍 Track 1: Stale-Answer Detector (Tavily Search API)

### Problem Addressed:
LLM apps confidently cite facts that have changed (pricing, API versions, laws, leadership). **Stale-Answer Detector** ingests any LLM output, extracts atomic factual claims, re-verifies them against live web sources via **Tavily Search API**, and generates a precision **Freshness Score (0–100)** with verified sources, side-by-side diffs, and real-time corrections.

### Quick Start:
```bash
# 1. Backend
cd track1-tavily-stale-detector/backend
pip install -r requirements.txt
python test_runner.py
python -m uvicorn main:app --reload --port 8000

# 2. Frontend
cd ../frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## ⚡ Track 2: TokenSlim — Fewest-Tokens Coding Agent (Bifrost / Maxim AI)

### Problem Addressed:
Standard coding agents waste 60% to 85% of their tokens dumping entire files into prompts and rewriting entire files for 2-line edits. **TokenSlim** solves coding tasks with maximum token efficiency using:
1. **AST Skeletonization**: Prunes non-target function bodies with `... # [elided]`.
2. **Search/Replace Patches**: Instructs the model to output minimal `<<<<<<< SEARCH ... >>>>>>>` blocks (under 50 tokens).
3. **Verified Bifrost Gateway Integration**: Every LLM call is routed through the Bifrost AI Gateway (`localhost:8080/v1/chat/completions`) with request, token and latency logging. See [`bifrost/README.md`](bifrost/README.md).
4. **Automated Verification Harness**: Runs live unit tests against patched code to guarantee functional correctness.

### Quick Start:
```bash
# Option A: Standalone CLI Benchmark (Terminal)
cd track2-bifrost-token-agent
python cli.py --benchmark rate_limiter

# Option B: Full Web Playground
# 1. Backend
cd backend
pip install -r requirements.txt
python test_runner.py
python -m uvicorn main:app --reload --port 8001

# 2. Frontend
cd ../frontend
npm install
npm run dev
# Open http://localhost:5174
```

> **Bifrost demo:** start the gateway first with `.\bifrost\start.ps1`, then run the
> backend as above. `backend/.env` already points `BIFROST_GATEWAY_URL` at
> `http://127.0.0.1:8080/v1/chat/completions`; `GET /api/health` reports
> `llm_provider: "bifrost"`. Details: [`bifrost/README.md`](bifrost/README.md).

---

## 🌐 Track 2: Faultline — Agent Reliability Platform (Bifrost / Maxim AI)

### Problem Addressed:
Nobody knows how their agent behaves when the gateway rate-limits, a tool crashes mid-task, tool output arrives malformed/stale, or a prompt injection rides in on legitimate data. **Faultline** automatically *stresses, benchmarks and debugs* AI agents against exactly those failures:
1. **Chaos engine**: 12 scenarios (sanity / tooling / gateway / integrity) + 8 red-team attacks inject rate limits, tool crashes, malformed payloads, hang-ups, stale data, truncation and prompt injection — deterministically and locally.
2. **Benchmark**: every run scored by deterministic checks (45%) + an LLM judge (55%: task_success / resilience / honesty / efficiency), with latency, tokens, est. cost and a red-team safety score.
3. **Debugger**: clusters broken runs into failure signatures → recommends fixes → **auto-patches the agent's resilience policy** → one-click apply → A/B the same suite (measured: baseline 56-61 → hardened 100 reliability on the quick gauntlet; red-team safety 75% → 100% after the fixes it surfaced).
4. **Bifrost-ready**: agent traffic routes through any Bifrost gateway (`PROVIDER=bifrost`, OpenAI-compatible, `npx @maximhq/bifrost`); traces are OTel-shaped spans.

### Demo script (Faultline):
```bash
# 1. Backend (port 8002)
cd track2-bifrost-agent-reliability/backend
py -3.11 -m uvicorn main:app --port 8002

# 2. Frontend (port 5175)
cd ../frontend
npm install
npm run dev
# Open http://localhost:5175
```
1. Open `http://localhost:5175` → click **"☣ Run baseline"** → watch sc04/sc08 crash on the Runs page (crash banner, red spans, judge 0/10 task).
2. Open **Debugger** → the broken suite is pre-selected → **⚗ Debug exec-…** → failure signatures + recommended fixes + policy diff → **✓ Apply to working policy**.
3. Return to **Stress Lab** → run the same gauntlet with **hardened** → same chaos, now recovered: waterfall shows retries (↻), runs pass.
4. **Red Team** → launch the gauntlet (hardened) → 8 attacks scored blocked/partial/complied + safety score.

---

## 📁 Repository Structure

```
globalHack/
├── README.md                           <-- Master portfolio (this file)
├── package.json                        <-- Unified scripts & test runner
│
├── track1-tavily-stale-detector/       <-- Track 1: Tavily Track Project
│   ├── README.md                       <-- Track 1 documentation & API spec
│   ├── backend/
│   │   ├── main.py                     <-- FastAPI backend (port 8000)
│   │   ├── test_runner.py              <-- Automated backend test suite
│   │   ├── requirements.txt
│   │   ├── .env
│   │   └── services/
│   │       ├── claim_extractor.py      <-- Extracts factual claims from LLM answer
│   │       ├── tavily_verifier.py      <-- Live search via Tavily Search API
│   │       ├── freshness_scorer.py     <-- Computes freshness score (0-100) & verdict
│   │       └── llm_client.py           <-- Fast LLM caller with cascading fallbacks
│   └── frontend/                       <-- React 19 + Vite web dashboard (port 5173)
│
└── track2-bifrost-token-agent/         <-- Track 2: Bifrost Priority Track Project
    ├── README.md                       <-- Track 2 documentation & benchmark results
    ├── cli.py                          <-- Standalone CLI tool
    ├── backend/
    │   ├── main.py                     <-- FastAPI backend (port 8001)
    │   ├── test_runner.py              <-- Automated backend test suite
    │   ├── requirements.txt
    │   ├── .env
    │   └── tokenslim/
    │       ├── ast_pruner.py           <-- AST Skeletonizer & Symbol Locality Pruner
    │       ├── patcher.py              <-- Search/Replace Chunk Patch Engine
    │       ├── token_counter.py        <-- Tiktoken cl100k_base BPE counter
    │       ├── benchmarks.py           <-- Preset coding challenges & unit tests
    │       └── agent.py                <-- TokenSlim vs Standard Agent comparison loop
    └── frontend/                       <-- React 19 + Vite efficiency playground (port 5174)
```

---

## 🎥 Video Demo & Presentation Guide

### Track 1 Demo Script (Stale-Answer Detector):
1. Open `http://localhost:5173`.
2. Select any benchmark (e.g. **"⚡ GPT-4 & Model Pricing"** or **"🏢 Big Tech & Leadership"**).
3. Click **"🔍 Audit Claims & Detect Staleness"**.
4. Inspect:
   - **🔬 Claims Breakdown**: Individual freshness scores, verdicts, and live sources with publication dates.
   - **🔄 Before vs After**: Side-by-side view showing outdated facts replaced by live verified facts (`[UPDATED]`).
   - **📄 Full Audit Dossier**: 1-click **Copy Markdown** or **Download .md** report.

### Track 2 Demo Script (TokenSlim Coding Agent):
1. Terminal demo:
   ```bash
   cd track2-bifrost-token-agent
   python cli.py --benchmark rate_limiter
   ```
   Highlight the **Token Savings % (45.9%)**, 2.0x speedup, and passing unit test output.
2. Web UI demo:
   - Open `http://localhost:5174`.
   - Select **"Sliding Window Rate Limiter Bug"** or **"E-Commerce Cart Price & Discount"**.
   - Click **"⚡ Solve with Fewest Tokens"**.
   - Inspect the live token comparison bar, the AST pruned skeleton, and the verified patch!
