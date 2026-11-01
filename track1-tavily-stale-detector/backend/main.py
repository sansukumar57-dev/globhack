from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import concurrent.futures

from services.claim_extractor import extract_claims
from services.tavily_verifier import search_claim
from services.freshness_scorer import score_freshness

app = FastAPI(title="Stale Answer Detector", version="1.0.0")

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
    total_claims: int
    stale_count: int
    fresh_count: int
    unverifiable_count: int
    overall_freshness: int
    claims: list[ClaimResult]


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Stale Answer Detector"}


def process_single_claim(claim_data: dict) -> ClaimResult:
    """Verify a single claim synchronously (for thread pool)."""
    claim = claim_data["claim"]
    query = claim_data["search_query"]
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
        sources=sources[:3],  # top 3 sources
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")

    # Step 1: Extract claims
    raw_claims = extract_claims(request.text)
    raw_claims = raw_claims[: request.max_claims]  # cap

    if not raw_claims:
        return AnalyzeResponse(
            original_text=request.text,
            total_claims=0,
            stale_count=0,
            fresh_count=0,
            unverifiable_count=0,
            overall_freshness=100,
            claims=[],
        )

    # Step 2: Verify all claims concurrently via thread pool
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            loop.run_in_executor(executor, process_single_claim, c)
            for c in raw_claims
        ]
        results: list[ClaimResult] = await asyncio.gather(*futures)

    # Step 3: Compute summary stats
    stale = [r for r in results if r.verdict == "STALE"]
    fresh = [r for r in results if r.verdict == "FRESH"]
    unverifiable = [r for r in results if r.verdict == "UNVERIFIABLE"]

    scores = [r.freshness_score for r in results]
    overall = int(sum(scores) / len(scores)) if scores else 100

    return AnalyzeResponse(
        original_text=request.text,
        total_claims=len(results),
        stale_count=len(stale),
        fresh_count=len(fresh),
        unverifiable_count=len(unverifiable),
        overall_freshness=overall,
        claims=results,
    )
