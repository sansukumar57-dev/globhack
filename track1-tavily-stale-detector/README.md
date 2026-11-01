# 🔍 Stale-Answer Detector
> **AI Global Hackathon** | **Track 1: Tavily by Nebius Track (Problem Statement #01)**  
> Built for the Geek Room AI Global Hackathon on HackCulture.

---

## 📌 Problem Overview
LLM applications confidently cite facts that change rapidly over time — API versions, pricing tiers, company leadership, legal regulations, and software releases.
**Stale-Answer Detector** is an autonomous verification layer that ingests any LLM-generated answer, extracts atomic factual claims, searches the live web in parallel via **Tavily Search API**, and computes a granular **Freshness Score (0–100)** with verified sources and real-time corrections.

---

## 🚀 Key Features
- **Atomic Claim Extraction**: Automatically identifies verifiable factual claims (pricing, versions, leadership, dates).
- **Parallel Live Web Search**: Queries Tavily Search API concurrently for low-latency live web evidence.
- **Deep Staleness Evaluation**: Calculates a precision 0–100 freshness score and classifies each claim into:
  - 🟢 **FRESH**: Verified accurate by current sources.
  - 🔴 **STALE**: Outdated; provides the current factual replacement.
  - ⚪ **UNVERIFIABLE**: Inconclusive or insufficient live web evidence.
- **Rich Dashboard UI**: Interactive React dashboard with visual score gauges, collapsible source citations, and preset benchmark examples.

---

## 🛠️ Architecture & Tech Stack

```
User Input (LLM Response / Text)
              │
              ▼
   [Atomic Claim Extractor]
              │
     ┌────────┴────────┐  (Concurrent Threads)
     ▼                 ▼
[Tavily Search]  [Tavily Search]
     │                 │
     └────────┬────────┘
              ▼
    [Freshness Scorer]
              │
              ▼
  JSON Verdict + Live Sources + Real-time Correct Value
```

- **Backend**: FastAPI (Python), Uvicorn, ThreadPoolExecutor
- **Search Provider**: Tavily Search API (Advanced Search, Live Summaries, Date Filtering)
- **Inference Engine**: Groq (Qwen 3.8 / Llama 3) & Nebius OpenAI-compatible API
- **Frontend**: React 19, Vite, Lucide-style badges, Responsive CSS

---

## ⚡ Quick Start

### 1. Backend Setup
```bash
cd track1-tavily-stale-detector/backend
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd track1-tavily-stale-detector/frontend
npm install
npm run dev
```

Open your browser at: `http://localhost:5173`

---

## 📡 API Specification

### `POST /api/analyze`
**Request Body:**
```json
{
  "text": "Sundar Pichai is the CEO of Google. Python 2.7 is the latest release.",
  "max_claims": 10
}
```

**Response:**
```json
{
  "original_text": "...",
  "total_claims": 2,
  "stale_count": 1,
  "fresh_count": 1,
  "unverifiable_count": 0,
  "overall_freshness": 50,
  "claims": [
    {
      "claim": "Python 2.7 is the latest release",
      "verdict": "STALE",
      "freshness_score": 0,
      "explanation": "Python 2.7 reached end-of-life in 2020. The current latest version is Python 3.14+.",
      "current_value": "Python 3.14+",
      "sources": [...]
    }
  ]
}
```
