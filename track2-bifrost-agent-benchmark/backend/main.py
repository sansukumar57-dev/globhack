"""Criterion API — benchmark support agents on the work they actually do."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from criterion import store


app = FastAPI(
    title="Criterion",
    description="A benchmarking platform for AI support agents.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=1, max_length=8)
    trials: int = Field(default=2, ge=1, le=3)


class AgentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=48)
    operator: str = Field(default="Connected workspace", max_length=48)
    adapter: str = Field(default="http", max_length=32)
    model: str = Field(default="endpoint-defined", max_length=48)
    endpoint: str = Field(default="", max_length=500)
    description: str = Field(default="A newly connected agent waiting for its first benchmark.", max_length=180)
    mode: str = Field(default="sandbox", pattern="^(sandbox|live)$")
    sandbox_profile: str = Field(default="balanced", max_length=24)


@app.get("/api/health")
def health():
    return store.health()


@app.get("/api/stats")
def stats():
    return store.stats()


@app.get("/api/suite")
def suite():
    return store.get_suite_data()


@app.get("/api/adapters")
def adapters():
    return {"adapters": store.get_adapters_registry()}


@app.get("/api/agents")
def agents():
    return {"agents": store.get_agents()}


@app.get("/api/agents/{agent_id}")
def agent(agent_id: str):
    found = store.get_agent(agent_id)
    if not found:
        raise HTTPException(status_code=404, detail="Agent not found")
    return found


@app.post("/api/agents", status_code=201)
def add_agent(payload: AgentRequest):
    try:
        return store.create_agent(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/leaderboard")
def leaderboard():
    return store.get_leaderboard()


@app.get("/api/failures")
def failures():
    return {"failures": store.get_failures()}


@app.get("/api/runs")
def runs():
    return {"runs": store.get_runs()}


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    found = store.get_run(run_id)
    if not found:
        raise HTTPException(status_code=404, detail="Run not found")
    return found


@app.post("/api/runs", status_code=202)
def start_run(payload: RunRequest):
    try:
        return store.start_run(payload.agent_ids, payload.trials)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Serve the built frontend when it exists. In development, Vite proxies /api here.
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8012, reload=True)
