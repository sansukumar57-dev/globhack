import json
import re

from services.llm_client import call_llm, extract_json_block

SCORE_PROMPT = """You are an objective fact-checking and staleness verification system. Given a claim and live web search results, determine if the claim is still accurate (fresh) or has become outdated (stale).

Return ONLY a valid JSON object. No markdown fences, no conversational text. Format:
{
  "freshness_score": <integer 0-100>,
  "verdict": "<FRESH|STALE|UNVERIFIABLE>",
  "explanation": "<one or two sentence explanation with key details>",
  "current_value": "<what the current correct value is if stale/outdated, else empty string>"
}

Scoring criteria:
- 90-100: Claim is confirmed completely accurate and up to date by recent sources.
- 70-89: Claim is mostly accurate, minor details or newer variants exist.
- 40-69: Partially outdated, superseded, or conflicting reports found.
- 10-39: Clearly STALE — pricing, version, CEO, or laws have changed.
- 0-9: Definitively wrong/outdated based on live sources.
- UNVERIFIABLE: If search results do not have relevant info to confirm or refute."""


VALID_VERDICTS = {"FRESH", "STALE", "UNVERIFIABLE"}


def validate_score_json(text: str) -> dict:
    """Parse an LLM response and enforce the scoring schema.

    Raises ValueError when unusable so call_llm can fail over to the next
    provider instead of the caller blindly landing on UNVERIFIABLE@50.
    """
    data = extract_json_block(text)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"invalid verdict: {verdict!r}")
    data["verdict"] = verdict
    data["freshness_score"] = int(data.get("freshness_score", 0))
    data["explanation"] = str(data.get("explanation", ""))
    data["current_value"] = str(data.get("current_value", ""))
    return data


def score_freshness(claim: str, search_results: list[dict], tavily_answer: str) -> dict:
    """Use LLM to score how fresh/stale a claim is based on live web search results."""
    context = f"Tavily Live Summary: {tavily_answer}\n\nSearch Results:\n"
    for i, r in enumerate(search_results, 1):
        context += f"\n[{i}] {r.get('title', 'Source')}\n"
        if r.get("published_date"):
            context += f"Date: {r.get('published_date')}\n"
        context += f"URL: {r.get('url', '')}\n"
        context += f"Content: {r.get('content', '')}\n"

    prompt = f"""{SCORE_PROMPT}

CLAIM TO VERIFY: "{claim}"

LIVE WEB EVIDENCE:
{context}"""

    try:
        raw = call_llm(
            prompt,
            temperature=0.1,
            max_tokens=1024,
            # Fail over on non-JSON prose instead of accepting it; only a
            # total provider outage (no valid answer anywhere) reaches the
            # heuristic fallback inside call_llm.
            validate=validate_score_json,
        )
        return validate_score_json(raw)
    except Exception as e:
        print(f"[Freshness Scoring Error] {e}")
        return {
            "freshness_score": 50,
            "verdict": "UNVERIFIABLE",
            "explanation": f"Evaluation error: {e}",
            "current_value": "",
        }
