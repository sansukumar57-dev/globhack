import os
from pathlib import Path
import requests
import json
import re
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def call_llm(prompt: str, temperature: float = 0.1, max_tokens: int = 1024) -> str:
    """Call LLM via Groq (ultra fast) or OpenAI-compatible endpoint."""
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    model = LLM_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        raise e
