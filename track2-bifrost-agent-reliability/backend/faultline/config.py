"""Faultline configuration: env loading, model registry, cost table."""
import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    env_path = _BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini-3.5-flash-lite")
PROVIDER = os.environ.get("PROVIDER", "gemini").lower().strip()
if PROVIDER not in ("gemini", "bifrost", "openrouter"):
    PROVIDER = "gemini"
BIFROST_GATEWAY_URL = os.environ.get("BIFROST_GATEWAY_URL", "").rstrip("/")
BIFROST_API_KEY = os.environ.get("BIFROST_API_KEY", "")
BIFROST_MODEL = os.environ.get("BIFROST_MODEL", "gpt-4o-mini")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Rough list-price estimates (USD per 1M tokens: input, output), used only for
# the "est. cost" readouts. Labelled as an estimate everywhere it appears.
COST_PER_MTOK = {
    "gemini-3.5-flash": (0.15, 0.60),
    "gemini-3.5-flash-lite": (0.05, 0.20),
}

DATA_DIR = _BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

RUNS_JSONL = DATA_DIR / "runs.jsonl"
