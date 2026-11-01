# 🌐 AI Global Hackathon — Project Submissions
> **Geek Room × HackCulture AI Global Hackathon**  
> Complete dual-track project submission portfolio covering both sponsor tracks.

---

## 🏆 Portfolio Overview

| Track | Partner | Problem Statement Selected | Project Name | Directory | Ports |
|---|---|---|---|---|---|
| **Track 1** | **Tavily by Nebius** | **#01: Stale-Answer Detector** | [🔍 Stale-Answer Detector](track1-tavily-stale-detector/README.md) | `track1-tavily-stale-detector/` | Backend: `8000`<br>Frontend: `5173` |
| **Track 2** | **Bifrost** *(Priority Track)* | **#01: Coding Agent on Fewest Tokens** | [⚡ TokenSlim](track2-bifrost-token-agent/README.md) | `track2-bifrost-token-agent/` | Backend: `8001`<br>Frontend: `5174`<br>CLI: `cli.py` |

---

## 🔍 Track 1: Stale-Answer Detector (Tavily × Nebius)

### Problem Addressed:
LLM apps confidently cite facts that have changed (pricing, API versions, laws, leadership). **Stale-Answer Detector** ingests any LLM output, extracts atomic factual claims, re-verifies them against live web sources via **Tavily Search API**, and generates a precision **Freshness Score (0–100)** with verified sources and real-time corrections.

### Quick Start:
```bash
# 1. Backend
cd track1-tavily-stale-detector/backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn main:app --reload --port 8000

# 2. Frontend
cd ../frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## ⚡ Track 2: TokenSlim — Fewest-Tokens Coding Agent (Bifrost Priority Track)

### Problem Addressed:
Standard coding agents waste 60% to 85% of their tokens dumping entire files into prompts and rewriting entire files for 2-line edits. **TokenSlim** solves coding tasks with maximum token efficiency using:
1. **AST Skeletonization**: Prunes non-target function bodies with `... # [elided]`.
2. **Search/Replace Patches**: Instructs the model to output minimal `<<<<<<< SEARCH ... >>>>>>>` blocks (under 50 tokens).
3. **Bifrost Gateway Compatible**: Routes queries directly through Bifrost AI Gateway (`localhost:8080/v1` or OpenAI proxy).
4. **Automated Verification Harness**: Runs live unit tests against patched code to guarantee functional correctness.

### Quick Start:
```bash
# Option A: Standalone CLI Benchmark (Terminal)
cd track2-bifrost-token-agent
py -3.11 cli.py --benchmark rate_limiter

# Option B: Full Web Playground
# 1. Backend
cd backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn main:app --reload --port 8001

# 2. Frontend
cd ../frontend
npm install
npm run dev
# Open http://localhost:5174
```

---

## 📁 Repository Structure

```
globalHack/
├── README.md                           <-- Master portfolio (this file)
│
├── track1-tavily-stale-detector/       <-- Track 1: Tavily Track Project
│   ├── README.md                       <-- Track 1 documentation & API spec
│   ├── backend/
│   │   ├── main.py                     <-- FastAPI backend (port 8000)
│   │   ├── requirements.txt
│   │   ├── .env
│   │   └── services/
│   │       ├── claim_extractor.py      <-- Extracts factual claims from LLM answer
│   │       ├── tavily_verifier.py      <-- Live search via Tavily Search API
│   │       ├── freshness_scorer.py     <-- Computes freshness score (0-100) & verdict
│   │       └── llm_client.py           <-- Fast LLM caller with retry backoff
│   └── frontend/                       <-- React 19 + Vite web dashboard (port 5173)
│
└── track2-bifrost-token-agent/         <-- Track 2: Bifrost Priority Track Project
    ├── README.md                       <-- Track 2 documentation & benchmark results
    ├── cli.py                          <-- Standalone CLI tool
    ├── backend/
    │   ├── main.py                     <-- FastAPI backend (port 8001)
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
2. Select the **"AI Models & Tech Leadership"** sample or paste any LLM answer containing facts (e.g. "Python 2.7 is the latest version. Sundar Pichai is CEO of Google").
3. Click **"Analyze Freshness"**.
4. Show the real-time breakdown:
   - Python 2.7 flagged as **STALE** (Score 0) with live Tavily sources and replacement: Python 3.14+.
   - Sundar Pichai flagged as **FRESH** (Score 100).

### Track 2 Demo Script (TokenSlim Coding Agent):
1. Terminal demo:
   `py -3.11 cli.py --benchmark rate_limiter`
   Highlight the **Token Savings % (43%+)**, speedup, and unit test pass.
2. Web UI demo:
   Open `http://localhost:5174`.
   Select **"Sliding Window Rate Limiter Bug"** or **"E-Commerce Cart Price & Discount"**.
   Click **"Solve with Fewest Tokens"**.
   Inspect the side-by-side token comparison bar, the AST pruned skeleton, and the verified patch!
