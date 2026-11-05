# 🔍 Stale-Answer Detector
> **AI Global Hackathon** | **Track 1: Tavily by Nebius Track (Problem Statement #01)**  
> Built for the Geek Room AI Global Hackathon on HackCulture.
> **Geek Room AI Global Hackathon** | **Track 1: Tavily Search API (Problem Statement #01)**  
> Autonomous verification and freshness scoring layer for LLM outputs.

---

## 📌 Problem Overview
LLM applications confidently cite facts that change rapidly over time — API versions, pricing tiers, company leadership, legal regulations, and software releases.
**Stale-Answer Detector** is an autonomous verification layer that ingests any LLM-generated answer, extracts atomic factual claims, searches the live web in parallel via **Tavily Search API**, and computes a granular **Freshness Score (0–100)** with verified sources and real-time corrections.
**Stale-Answer Detector** is an autonomous verification layer that ingests any LLM-generated answer, extracts atomic factual claims, searches the live web via **Tavily Search API**, and computes a granular **Freshness Index (0–100)** with verified sources, side-by-side diffs, and real-time corrections.

---

## 🚀 Key Features
- **Atomic Claim Extraction**: Automatically identifies verifiable factual claims (pricing, versions, leadership, dates).
- **Parallel Live Web Search**: Queries Tavily Search API concurrently for low-latency live web evidence.
- **Atomic Claim Extraction**: Automatically parses unstructured LLM responses into verifiable factual claims (pricing, versions, leadership, dates).
- **Parallel Live Web Search**: Queries Tavily Search API for low-latency live web ground truth with publication date extraction.
- **Deep Staleness Evaluation**: Calculates a precision 0–100 freshness score and classifies each claim into:
  - 🟢 **FRESH**: Verified accurate by current sources.
  - 🔴 **STALE**: Outdated; provides the current factual replacement.
  - ⚪ **UNVERIFIABLE**: Inconclusive or insufficient live web evidence.
- **Rich Dashboard UI**: Interactive React dashboard with visual score gauges, collapsible source citations, and preset benchmark examples.
- **Reconstructed Text & Diff View**: Automatically rebuilds the input response with outdated facts replaced by live verified data (`[UPDATED]`).
- **Publication-Ready Dossier**: Generates full Markdown audit reports with one-click clipboard copy and `.md` file download.
- **Built-in Benchmark Presets**: Instant one-click test cases for judges (AI Pricing, Big Tech Leadership, Frontier AI Models, Software EOL).
- **Resilient Multi-Provider Inference**: OpenRouter → Gemini → Groq cascading failover, so a single exhausted provider never sinks a request; if every live provider fails, the clearly-labelled offline heuristic answers as a last resort.

---

## 🛠️ Architecture & Tech Stack

```
User Input (LLM Response / Text)
              │
              ▼
   [Atomic Claim Extractor]
    [Atomic Claim Extractor]
              │
     ┌────────┴────────┐  (Concurrent Threads)
     ▼                 ▼
[Tavily Search]  [Tavily Search]
     │                 │
     └────────┬────────┘
      ┌───────┴───────┐
      ▼               ▼
[Tavily Search]  [Tavily Search]  (Live Web Grounding)
      │               │
      └───────┬───────┘
              ▼
    [Freshness Scorer]
     [Freshness Scorer]
              │
              ▼
  JSON Verdict + Live Sources + Real-time Correct Value
   ┌────────────────────────────────────────────────────────┐
   │ • Granular Freshness Index (0-100)                     │
   │ • Classified Verdicts (FRESH / STALE / UNVERIFIABLE)   │
   │ • Live Source URLs + Publication Dates                 │
   │ • Reconstructed Corrected Text                         │
   │ • Exportable Markdown Audit Dossier                    │
   └────────────────────────────────────────────────────────┘
```

- **Backend**: FastAPI (Python), Uvicorn, ThreadPoolExecutor
- **Search Provider**: Tavily Search API (Advanced Search, Live Summaries, Date Filtering)
- **Inference Engine**: Groq (Qwen 3.8 / Llama 3) & Nebius OpenAI-compatible API
- **Frontend**: React 19, Vite, Lucide-style badges, Responsive CSS
- **Backend**: FastAPI (Python), Uvicorn, Pydantic v2, Requests
- **Search Provider**: Tavily Search API (Advanced Search, Real-Time Summaries, Date Filtering)
- **Inference Engine**: OpenRouter / Nebius (Cohere, Llama 3.3, Qwen 2.5) & Groq fallback
- **Frontend**: React 19, Vite, Responsive CSS, Live Score Gauges, Interactive Diffs

---

## ⚡ Quick Start

### 1. Backend Setup
```bash
cd track1-tavily-stale-detector/backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn main:app --reload --port 8000
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
Backend will be live at `http://localhost:8000`. Interactive Swagger docs available at `http://localhost:8000/docs`.

### 2. Frontend Setup
```bash
cd track1-tavily-stale-detector/frontend
npm install
npm run dev
```

Open your browser at: `http://localhost:5173`

### 3. Run Automated Tests
```bash
cd track1-tavily-stale-detector/backend
python test_runner.py
```
Output:
```
============================================================
RUNNING STALE-ANSWER DETECTOR TEST SUITE (TRACK 1)
============================================================
Testing GET /api/health ... PASS! [Status: online]
Testing GET /api/presets ... PASS! [4 benchmarks available]
Testing POST /api/analyze (Stale claim: Python 2.7) ... PASS! [Freshness score: 0/100, Detected 1 stale claims]
Testing POST /api/analyze (Fresh claim: Sundar Pichai) ... PASS! [Freshness score: 98/100, Fresh count: 1]
Testing POST /api/analyze (Empty text validation) ... PASS! [Correctly rejected empty text with 400]
============================================================
ALL TESTS PASSED SUCCESSFULLY! (5/5)
============================================================
```

### 4. Run JSON Parser Unit Tests
```bash
cd track1-tavily-stale-detector/backend
python test_json_block.py
```
 Validates that the LLM output parser survives real-world model quirks: JSON emitted inside prose, markdown fences, trailing text, and the free code model's `{...}{...}` double-object output — ensuring a bad parse fails over to the next provider instead of marking a claim `UNVERIFIABLE`.

---

## 📡 API Specification

### `GET /api/health`
Returns live status and provider configuration.

### `GET /api/presets`
Returns curated benchmark test scenarios.

### `POST /api/analyze`
**Request Body:**
```json
{
  "text": "Sundar Pichai is the CEO of Google. Python 2.7 is the latest release.",
  "text": "Sundar Pichai is the CEO of Google. Python 2.7 is the active LTS release.",
  "max_claims": 10
}
```

**Response:**
```json
{
  "original_text": "...",
  "original_text": "Sundar Pichai is the CEO of Google. Python 2.7 is the active LTS release.",
  "corrected_text": "Sundar Pichai is the CEO of Google. Python 3.13 / 3.14 (Active LTS) [UPDATED]",
  "markdown_report": "# 🔍 Stale-Answer Detection Audit Report...",
  "total_claims": 2,
  "stale_count": 1,
  "fresh_count": 1,
  "unverifiable_count": 0,
  "overall_freshness": 50,
  "overall_freshness": 49,
  "claims": [
    {
      "claim": "Python 2.7 is the latest release",
      "claim": "Python 2.7 is the active LTS release",
      "verdict": "STALE",
      "freshness_score": 0,
      "explanation": "Python 2.7 reached end-of-life in 2020. The current latest version is Python 3.14+.",
      "current_value": "Python 3.14+",
      "sources": [...]
      "explanation": "Python 2.7 reached official End-of-Life on Jan 1, 2020. Current active production releases are Python 3.13 / 3.14.",
      "current_value": "Python 3.13 / 3.14 (Active LTS)",
      "sources": [
        {
          "title": "Python Developer's Guide - Status of Python Branches",
          "url": "https://devguide.python.org/versions/",
          "published_date": "2026-05-10"
        }
      ]
    }
  ]
}
```
