from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from tokenslim.agent import TokenSlimAgent, StandardAgent, run_benchmark_comparison
from tokenslim.benchmarks import PRESET_BENCHMARKS

app = FastAPI(title="TokenSlim - Token-Efficient Coding Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolveRequest(BaseModel):
    code: str
    prompt: str
    run_comparison: Optional[bool] = True
    test_code: Optional[str] = None


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "TokenSlim Coding Agent",
        "track": "Bifrost Priority Track",
        "problem_statement": "#01 - Coding agent on fewest tokens"
    }


@app.get("/api/presets")
def get_presets():
    return [
        {
            "id": b["id"],
            "title": b["title"],
            "description": b["description"],
            "target_function": b["target_function"],
            "prompt": b["prompt"],
            "original_code": b["original_code"],
            "test_code": b["test_code"]
        }
        for b in PRESET_BENCHMARKS
    ]


@app.post("/api/solve")
def solve_code(req: SolveRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    if req.run_comparison:
        result = run_benchmark_comparison(req.code, req.prompt, req.test_code or "")
        return result
    else:
        slim_result = TokenSlimAgent.solve(req.code, req.prompt)
        return {"tokenslim": slim_result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
