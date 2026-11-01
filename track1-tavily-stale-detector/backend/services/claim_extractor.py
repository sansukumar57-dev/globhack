import json
import re
from services.llm_client import call_llm

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


def extract_claims(text: str) -> list[dict]:
    """Extract factual claims from LLM answer text."""
    try:
        prompt = f"{EXTRACT_PROMPT}\n\nExtract factual claims from this text:\n\n{text}"
        raw = call_llm(prompt, temperature=0.1, max_tokens=2048)
        
        # Clean markdown wrappers if any
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        
        # Attempt to parse
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)
            
        claims = json.loads(raw)
        return claims if isinstance(claims, list) else []
    except Exception as e:
        print(f"[Claim Extraction Error] {e}")
        return []
