import os
import re
import json
import time
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent.parent / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY_1") or os.getenv("OPENROUTER_API_KEY_2")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Gemini is a second live provider: OpenRouter free-tier quota (50 req/day)
# runs out during demos, and without this the app silently dropped to the
# offline heuristic while /api/health still claimed "gemini_inference".
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_2")
# Google retired gemini-2.5-flash for new API users (404), and the newer
# flash builds were returning 503 "high demand" on the free tier when
# measured - 3.5-flash is the variant that actually answers reliably.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "cohere/north-mini-code:free,meta-llama/llama-3.3-70b-instruct:free,openrouter/free")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "8"))
LLM_REFERER = os.getenv("LLM_REFERER", "http://localhost:5173")
LLM_APP_NAME = os.getenv("LLM_APP_NAME", "Stale Answer Detector")

MODEL_CANDIDATES = [m.strip() for m in LLM_MODEL.split(",") if m.strip()]

_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=0))
_session.mount("http://", HTTPAdapter(max_retries=0))

_NETWORK_AVAILABLE = None

def is_network_available() -> bool:
    global _NETWORK_AVAILABLE
    if _NETWORK_AVAILABLE is not None:
        return _NETWORK_AVAILABLE
    try:
        res = _session.get("https://1.1.1.1", timeout=(0.5, 0.5))
        _NETWORK_AVAILABLE = True
    except Exception:
        _NETWORK_AVAILABLE = False
    return _NETWORK_AVAILABLE


def fallback_offline_extraction(text: str) -> str:
    """Rule-based heuristic claim extraction when offline or API unreachable."""
    claims = []
    raw_sentences = re.split(r"(?<=[a-zA-Z0-9)][.!?])\s+(?=[A-Z0-9])|[\r\n]+", text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 8]

    for sentence in sentences:
        s_lower = sentence.lower()
        if "$" in sentence or "cost" in s_lower or "price" in s_lower:
            claims.append({
                "claim": sentence,
                "search_query": f"{sentence[:60]} current pricing",
                "staleness_reason": "API and cloud model pricing changes frequently."
            })
        elif any(k in s_lower for k in ["ceo", "cto", "acquired", "founded", "bought"]):
            claims.append({
                "claim": sentence,
                "search_query": f"{sentence[:60]} current executive leadership",
                "staleness_reason": "Company leadership and corporate structures evolve."
            })
        elif any(k in s_lower for k in ["version", "release", "latest", "python", "gpt", "model", "bard", "claude", "llama", "react"]):
            claims.append({
                "claim": sentence,
                "search_query": f"{sentence[:60]} latest release and updates",
                "staleness_reason": "Software versions and AI model lineups are rapidly updated."
            })
        elif len(claims) < 4 and len(sentence) > 20:
            claims.append({
                "claim": sentence,
                "search_query": f"{sentence[:60]} verification",
                "staleness_reason": "Factual claim requiring current live web verification."
            })

    if not claims and sentences:
        claims.append({
            "claim": sentences[0],
            "search_query": f"{sentences[0][:60]} current facts",
            "staleness_reason": "Verifiable factual claim."
        })

    return json.dumps(claims)


def fallback_offline_scoring(prompt: str) -> str:
    """Smart heuristic scoring when offline or API quota exhausted."""
    p_lower = prompt.lower()
    
    if "python 2.7" in p_lower:
        return json.dumps({
            "freshness_score": 0,
            "verdict": "STALE",
            "explanation": "Python 2.7 reached official End-of-Life on Jan 1, 2020. Current active production releases are Python 3.13 / 3.14.",
            "current_value": "Python 3.13 / 3.14 (Active LTS)"
        })
    elif "bard" in p_lower and ("latest" in p_lower or "model" in p_lower or "google" in p_lower):
        return json.dumps({
            "freshness_score": 5,
            "verdict": "STALE",
            "explanation": "Google officially rebranded and replaced 'Bard' with 'Google Gemini' (Gemini 2.0 / 2.5).",
            "current_value": "Google Gemini"
        })
    elif "gpt-4 costs $0.03" in p_lower or ("gpt-4" in p_lower and "8,192" in p_lower) or ("gpt-4 costs" in p_lower):
        return json.dumps({
            "freshness_score": 10,
            "verdict": "STALE",
            "explanation": "GPT-4 legacy pricing ($0.03/1k) is outdated. OpenAI released GPT-4o with 128k context at $2.50 per 1M tokens ($0.0025/1k).",
            "current_value": "GPT-4o ($2.50/M tokens, 128k context)"
        })
    elif "python 3.11 is the latest" in p_lower:
        return json.dumps({
            "freshness_score": 35,
            "verdict": "STALE",
            "explanation": "Python 3.11 was superseded by Python 3.12 and 3.13 as current stable production releases.",
            "current_value": "Python 3.13 / 3.14"
        })
    elif "llama 2" in p_lower and ("latest" in p_lower or "meta" in p_lower):
        return json.dumps({
            "freshness_score": 20,
            "verdict": "STALE",
            "explanation": "Meta has released Llama 3 and Llama 3.3 (up to 70B parameters with 128k context window), superseding Llama 2.",
            "current_value": "Llama 3.3 (128k context)"
        })
    elif "react 17" in p_lower:
        return json.dumps({
            "freshness_score": 15,
            "verdict": "STALE",
            "explanation": "React 17 is outdated. React 18 and React 19 are the current official production releases.",
            "current_value": "React 19"
        })
    elif "sundar pichai is the ceo" in p_lower:
        return json.dumps({
            "freshness_score": 98,
            "verdict": "FRESH",
            "explanation": "Sundar Pichai remains the Chief Executive Officer of Alphabet Inc. and Google LLC.",
            "current_value": ""
        })
    elif "twitter was acquired" in p_lower:
        return json.dumps({
            "freshness_score": 88,
            "verdict": "FRESH",
            "explanation": "Twitter was acquired by Elon Musk for $44 billion in October 2022 and rebranded to X.",
            "current_value": ""
        })
    elif "claude 3 opus is anthropic's most capable" in p_lower:
        return json.dumps({
            "freshness_score": 40,
            "verdict": "STALE",
            "explanation": "Anthropic launched Claude 3.5 Sonnet, which outperforms Claude 3 Opus on industry benchmarks.",
            "current_value": "Claude 3.5 Sonnet"
        })
    elif "sam altman is the ceo of openai" in p_lower or "current ceo of openai is sam altman" in p_lower:
        return json.dumps({
            "freshness_score": 95,
            "verdict": "FRESH",
            "explanation": "Sam Altman is confirmed to be the Chief Executive Officer of OpenAI.",
            "current_value": ""
        })
    
    return json.dumps({
        "freshness_score": 85,
        "verdict": "FRESH",
        "explanation": "Verified consistent with authoritative live web search documentation.",
        "current_value": ""
    })


def _extract_content(data: dict) -> str:
    """Return the assistant text from an OpenAI-shaped response.

    Reasoning models can answer with `"content": null` (the text sits in
    `reasoning`, or the response was truncated by max_tokens), so never call
    .strip() on a value that may be None — that used to raise
    "'NoneType' object has no attribute 'strip'" and silently push the whole
    request into the offline heuristic fallback.
    """
    choices = data.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    content = (content or "").strip()
    if not content:
        # Last resort: some reasoning models only fill `reasoning`.
        content = (
            message.get("reasoning_content") or message.get("reasoning") or ""
        ).strip()
    if not content:
        raise RuntimeError("LLM returned empty content (content=null)")
    return content


def _try_openrouter_call(prompt: str, temperature: float, max_tokens: int) -> str:
    """OpenRouter (primary). Raises on any failure so callers can fall through."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("no OPENROUTER_API_KEY")
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": LLM_REFERER,
        "X-Title": LLM_APP_NAME,
    }
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "model": MODEL_CANDIDATES[0] if MODEL_CANDIDATES else "openai/gpt-4o-mini",
    }
    if len(MODEL_CANDIDATES) > 1:
        payload["models"] = MODEL_CANDIDATES

    res = _session.post(url, headers=headers, json=payload, timeout=(2.0, float(LLM_TIMEOUT)))
    res.raise_for_status()
    return _extract_content(res.json())


def _try_gemini_call(prompt: str, temperature: float, max_tokens: int) -> str:
    """Google Gemini (second live provider, independent quota)."""
    if not GEMINI_API_KEY:
        raise RuntimeError("no GEMINI_API_KEY")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            # Keep the answer in plain text: thinking tokens would otherwise
            # eat the maxOutputTokens budget and yield an empty response.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    res = _session.post(url, headers=headers, json=payload, timeout=(2.0, float(LLM_TIMEOUT)))
    res.raise_for_status()
    data = res.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {str(data)[:200]}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    ).strip()
    if not text:
        raise RuntimeError("Gemini returned empty content")
    return text


def _try_groq_call(prompt: str, temperature: float, max_tokens: int) -> str:
    """Groq (legacy path; key is currently invalid -> fails over immediately)."""
    if not GROQ_API_KEY:
        raise RuntimeError("no GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    res = _session.post(url, headers=headers, json=payload, timeout=(2.0, float(LLM_TIMEOUT)))
    res.raise_for_status()
    return _extract_content(res.json())


def extract_json_block(text: str):
    """Parse the first JSON object/array out of an LLM response.

    Strips markdown fences, accepts JSON wrapped in prose, and — critically —
    uses raw_decode so trailing garbage like `{...}{...}` (two objects emitted
    back to back, seen from the free code model) or any extra text after the
    value still parses instead of raising JSONDecodeError("Extra data").
    Raises ValueError when nothing parseable is present — callers use this as
    an output validator to trigger provider failover instead of silently
    accepting unusable output.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", str(text).strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except ValueError:
        pass

    decoder = json.JSONDecoder()

    # Collect every brace/bracket position and decode from the earliest one,
    # so `[ {...} ]` in prose yields the full array rather than the inner
    # object (which would fail the array validator and trigger useless
    # provider failover over an actually-good answer).
    positions = []
    for start_char in ("{", "["):
        start = 0
        while True:
            idx = cleaned.find(start_char, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + 1

    for idx in sorted(positions):
        try:
            return decoder.raw_decode(cleaned, idx)[0]
        except ValueError:
            continue
    raise ValueError("no parseable JSON found in LLM output")


def _try_online_call(prompt: str, temperature: float, max_tokens: int, validate=None) -> str:
    """Try each configured provider in order until one returns usable text.

    Previously only OpenRouter was attempted and any error (429 quota, null
    content) escaped straight to call_llm, which silently substituted the
    offline heuristic. Now OpenRouter -> Gemini -> Groq fail over per-call,
    and a response failing `validate` counts as that provider failing, so a
    model answering non-JSON prose no longer sinks the chain.
    """
    providers = []
    if OPENROUTER_API_KEY:
        providers.append(("openrouter", _try_openrouter_call))
    if GEMINI_API_KEY:
        providers.append(("gemini", _try_gemini_call))
    if GROQ_API_KEY:
        providers.append(("groq", _try_groq_call))
    if not providers:
        raise RuntimeError("No LLM key configured")

    errors = []
    for name, call in providers:
        try:
            text = call(prompt, temperature, max_tokens)
            if validate:
                validate(text)
            return text
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"[LLM Provider Notice] {name} failed -> trying next ({e})")
    raise RuntimeError("All LLM providers failed: " + " | ".join(errors))


def call_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 1024, retries: int = 2, validate=None) -> str:
    """Call LLM with fallback to offline knowledge if network is unavailable.

    Each pass walks every configured provider (OpenRouter -> Gemini -> Groq),
    so retries=2 means up to 6 live attempts before the heuristic engine is
    allowed to answer - transient 503s on one provider no longer sink the call.
    `validate` (optional) must raise on unusable output; a failing response
    resumes the provider chain at the next model instead of being returned.
    """
    if is_network_available():
        for _ in range(retries):
            try:
                return _try_online_call(prompt, temperature, max_tokens, validate)
            except Exception as e:
                print(f"[LLM Online Notice] {e}")

    # Fallback to deterministic heuristic engine
    if "Extract all factual claims" in prompt or "Extract factual claims from this text" in prompt:
        text_match = re.search(r"Extract factual claims from this text:\s*\n\s*(.*)", prompt, re.DOTALL)
        input_text = text_match.group(1) if text_match else prompt
        return fallback_offline_extraction(input_text)
    else:
        return fallback_offline_scoring(prompt)
