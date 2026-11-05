"""Uvicorn entrypoint: python main.py (or uvicorn main:app --port 8400)."""
from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("FORESIGHT_PORT", "8400"))
    uvicorn.run("foresight.app:app", host="127.0.0.1", port=port, log_level="info")
