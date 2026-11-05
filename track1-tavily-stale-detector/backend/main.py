from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import asyncio
import concurrent.futures

from services.claim_extractor import extract_claims
from services.tavily_verifier import search_claim
from services.freshness_scorer import score_freshness

app = FastAPI(title="Stale Answer Detector API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str
    max_claims: Optional[int] = 10


class ClaimResult(BaseModel):
    claim: str
    staleness_reason: str
    search_query: str
    freshness_score: int
    verdict: str
    explanation: str
    current_value: str
    sources: list[dict]


class AnalyzeResponse(BaseModel):
    original_text: str
    corrected_text: str
    markdown_report: str
    total_claims: int
    stale_count: int
    fresh_count: int
    unverifiable_count: int
    overall_freshness: int
    claims: list[ClaimResult]


PRESET_BENCHMARKS = [
    {
        "id": "ai-pricing-models",
        "title": "GPT-4 & LLM Pricing",
        "category": "AI Models & Pricing",
        "text": "GPT-4 costs $0.03 per 1K input tokens and $0.06 per 1K output tokens. It has a context window of 8,192 tokens. OpenAI was founded by Sam Altman and Elon Musk. The current CEO of OpenAI is Sam Altman."
    },
    {
        "id": "tech-leadership",
        "title": "Big Tech Acquisitions & Leadership",
        "category": "Corporate Governance",
        "text": "Sundar Pichai is the CEO of Google and Alphabet. Twitter was acquired by Elon Musk for $44 billion in 2022. Python 3.11 is the latest stable version of Python."
    },
    {
        "id": "ai-frontier",
        "title": "Frontier AI Models & Branding",
        "category": "Frontier AI",
        "text": "Claude 3 Opus is Anthropic's most capable model. Google's latest conversational AI model is called Bard. Meta's latest open weights model family is Llama 2 with 4096 context tokens."
    },
    {
        "id": "software-eol",
        "title": "Software Versions & End-of-Life",
        "category": "Software Engineering",
        "text": "Python 2.7 is the active LTS release used in modern Linux servers. React 17 is the current version powering frontend web frameworks."
    }
]


@app.get("/api/health")
def health():
    tavily_key = bool(os.getenv("TAVILY_API_KEY"))
    groq_key = bool(os.getenv("GROQ_API_KEY"))
    openrouter_key = bool(os.getenv("OPENROUTER_API_KEY_1") or os.getenv("OPENROUTER_API_KEY_2"))
    gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    
    return {
        "status": "online",
        "service": "Stale Answer Detector",
        "version": "2.0.0",
        "providers": {
            "tavily_search": "configured" if tavily_key else "fallback_mode",
            "groq_inference": "configured" if groq_key else "unconfigured",
            "openrouter_inference": "configured" if openrouter_key else "unconfigured",
            "gemini_inference": "configured" if gemini_key else "unconfigured",
        }
    }


@app.get("/api/presets")
def get_presets():
    return PRESET_BENCHMARKS


def process_single_claim(claim_data: dict) -> ClaimResult:
    """Verify a single claim synchronously (for thread pool)."""
    claim = claim_data.get("claim", "")
    query = claim_data.get("search_query", claim)
    staleness_reason = claim_data.get("staleness_reason", "")

    sources, tavily_answer = search_claim(query)
    score_data = score_freshness(claim, sources, tavily_answer)

    return ClaimResult(
        claim=claim,
        staleness_reason=staleness_reason,
        search_query=query,
        freshness_score=score_data.get("freshness_score", 50),
        verdict=score_data.get("verdict", "UNVERIFIABLE"),
        explanation=score_data.get("explanation", ""),
        current_value=score_data.get("current_value", ""),
        sources=sources[:3],
    )


def build_corrected_text(original_text: str, claims: list[ClaimResult]) -> str:
    """Construct an updated version of the text with corrected values."""
    corrected = original_text
    stale_claims = [c for c in claims if c.verdict == "STALE" and c.current_value]
    
    for c in stale_claims:
        if c.claim in corrected:
            corrected = corrected.replace(c.claim, f"{c.current_value} [UPDATED]")
        else:
            # Fallback fuzzy word match if claim text has minor punctuation differences
            clean_claim = c.claim.strip(" .?!\"'")
            if clean_claim in corrected:
                corrected = corrected.replace(clean_claim, f"{c.current_value} [UPDATED]")
                
    return corrected


def build_markdown_report(original_text: str, corrected_text: str, overall: int, results: list[ClaimResult]) -> str:
    """Generate a clean, publication-ready Markdown audit dossier."""
    verdict_emoji = "🟢 EXCELLENT" if overall >= 80 else ("🟡 CAUTION" if overall >= 50 else "🔴 HIGH STALENESS DETECTED")
    lines = [
        "# 🔍 Stale-Answer Detection Audit Report",
        f"**Freshness Index:** {overall}/100 — {verdict_emoji}\n",
        "## 📊 Executive Summary",
        f"- **Total Factual Claims Audited:** {len(results)}",
        f"- **Fresh (Up-to-Date):** {len([r for r in results if r.verdict == 'FRESH'])}",
        f"- **Stale (Outdated):** {len([r for r in results if r.verdict == 'STALE'])}",
        f"- **Unverifiable:** {len([r for r in results if r.verdict == 'UNVERIFIABLE'])}\n",
        "## 📝 Original vs Corrected Output",
        "### Original Text",
        f"> {original_text}\n",
        "### Corrected Text (With Live Verified Facts)",
        f"> {corrected_text}\n",
        "## 🔬 Granular Claim Breakdown\n"
    ]

    for i, c in enumerate(results, 1):
        tag = "🟢 FRESH" if c.verdict == "FRESH" else ("🔴 STALE" if c.verdict == "STALE" else "⚪ UNVERIFIABLE")
        lines.append(f"### Claim #{i}: `{c.claim}`")
        lines.append(f"- **Verdict:** {tag} (Score: {c.freshness_score}/100)")
        lines.append(f"- **Explanation:** {c.explanation}")
        if c.current_value:
            lines.append(f"- **Current Fact:** **{c.current_value}**")
        if c.staleness_reason:
            lines.append(f"- **Staleness Factor:** {c.staleness_reason}")
        if c.sources:
            lines.append("- **Verified Sources:**")
            for s in c.sources:
                title = s.get("title") or "Source Link"
                url = s.get("url") or "#"
                date_str = f" ({s.get('published_date')})" if s.get("published_date") else ""
                lines.append(f"  - [{title}]({url}){date_str}")
        lines.append("")

    lines.append("---\n*Generated by Stale-Answer Detector (Tavily Search API × Nebius / Groq)*")
    return "\n".join(lines)


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")

    # Step 1: Extract claims
    raw_claims = extract_claims(request.text)
    raw_claims = raw_claims[: request.max_claims]

    if not raw_claims:
        report = build_markdown_report(request.text, request.text, 100, [])
        return AnalyzeResponse(
            original_text=request.text,
            corrected_text=request.text,
            markdown_report=report,
            total_claims=0,
            stale_count=0,
            fresh_count=0,
            unverifiable_count=0,
            overall_freshness=100,
            claims=[],
        )

    # Step 2: Verify all claims
    results: list[ClaimResult] = [process_single_claim(c) for c in raw_claims]

    # Step 3: Compute summary stats
    stale = [r for r in results if r.verdict == "STALE"]
    fresh = [r for r in results if r.verdict == "FRESH"]
    unverifiable = [r for r in results if r.verdict == "UNVERIFIABLE"]

    scores = [r.freshness_score for r in results]
    overall = int(sum(scores) / len(scores)) if scores else 100

    # Step 4: Generate reconstructed text & Markdown report
    corrected_text = build_corrected_text(request.text, results)
    markdown_report = build_markdown_report(request.text, corrected_text, overall, results)

    return AnalyzeResponse(
        original_text=request.text,
        corrected_text=corrected_text,
        markdown_report=markdown_report,
        total_claims=len(results),
        stale_count=len(stale),
        fresh_count=len(fresh),
        unverifiable_count=len(unverifiable),
        overall_freshness=overall,
        claims=results,
    )
