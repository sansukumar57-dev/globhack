from services.llm_client import call_llm, extract_json_block

EXTRACT_PROMPT = """You are a fact-checking assistant. Extract all factual claims from the given text that could potentially become stale over time.

Focus on claims about:
- Prices, costs, fees
- Software/API versions, model names
- Laws, regulations, policies
- Company leadership (CEOs, CTOs, founders)
- Statistics, rankings, market share
- Product features, availability
- Dates and timelines

For each claim, provide:
1. The exact claim text (verbatim from the input)
2. A short search query to verify it
3. Why it might be stale (staleness_reason)

Return ONLY a valid JSON array. No markdown fences, no conversational text. Format:
[
  {
    "claim": "exact text of the claim",
    "search_query": "concise search query to verify this",
    "staleness_reason": "why this might be outdated"
  }
]

If no verifiable factual claims are found, return an empty array: []"""


def validate_claims_json(text: str) -> list:
    """Parse an LLM response and enforce the claims-array schema.

    Raises ValueError when unusable so call_llm can fail over to the next
    provider rather than the extractor returning [] on a good overall answer.
    """
    claims = extract_json_block(text)
    if not isinstance(claims, list):
        raise ValueError("expected a JSON array")
    for c in claims:
        if not isinstance(c, dict) or not str(c.get("claim", "")).strip():
            raise ValueError("malformed claim item")
    return claims


def extract_claims(text: str) -> list[dict]:
    """Extract factual claims from LLM answer text."""
    try:
        prompt = f"{EXTRACT_PROMPT}\n\nExtract factual claims from this text:\n\n{text}"
        raw = call_llm(
            prompt,
            temperature=0.1,
            max_tokens=2048,
            # Fail over on non-JSON prose instead of treating the request as
            # claim-free; only a total provider outage reaches the heuristic
            # fallback inside call_llm.
            validate=validate_claims_json,
        )
        return validate_claims_json(raw)
    except Exception as e:
        print(f"[Claim Extraction Error] {e}")
        return []
