import os
from pathlib import Path
import requests
import json
import time
from dotenv import load_dotenv

from .ast_pruner import ASTPruner
from .patcher import Patcher
from .token_counter import count_tokens

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
BIFROST_GATEWAY_URL = os.getenv("BIFROST_GATEWAY_URL", "https://api.groq.com/openai/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")


def call_llm_api(messages: list[dict], temperature: float = 0.1, max_tokens: int = 1024, retries: int = 3) -> str:
    """Invokes LLM via configured Gateway or direct OpenAI/Groq endpoint with retry backoff."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    last_err = None
    for attempt in range(retries):
        try:
            res = requests.post(BIFROST_GATEWAY_URL, headers=headers, json=payload, timeout=20)
            if res.status_code == 429:
                wait_time = 2.0 * (attempt + 1)
                time.sleep(wait_time)
                continue
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
            
    raise last_err or RuntimeError("LLM request failed after retries.")


class TokenSlimAgent:
    """Token-optimized coding agent utilizing AST skeletonization and search-replace patches."""

    @staticmethod
    def solve(original_code: str, prompt: str) -> dict:
        start_time = time.time()
        
        # 1. Identify target function/symbol
        target_symbol = ASTPruner.identify_target_symbol(original_code, prompt)
        
        # 2. Prune AST to skeleton
        skeleton, ast_stats = ASTPruner.skeletonize_python(original_code, target_symbol)
        
        # 3. Compact system & user prompt
        system_msg = "You are TokenSlim, a high-efficiency coding agent. Output ONLY a minimal <<<<<<< SEARCH ... ======= ... >>>>>>> block to apply the requested fix. Do not explain."
        user_msg = f"""TASK: {prompt}

TARGET CODE CONTEXT (non-target functions elided with `...`):
```python
{skeleton}
```

Return ONLY the patch block:
<<<<<<< SEARCH
<exact lines from target to replace>
=======
<fixed lines>
>>>>>>>"""

        input_tokens = count_tokens(system_msg) + count_tokens(user_msg)
        
        # 4. Invoke LLM
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
        raw_response = call_llm_api(messages, temperature=0.1, max_tokens=512)
        output_tokens = count_tokens(raw_response)
        
        # 5. Apply patch
        updated_code, success, msg = Patcher.extract_and_apply_patch(original_code, raw_response)
        elapsed = round(time.time() - start_time, 2)

        return {
            "mode": "tokenslim",
            "target_symbol": target_symbol,
            "skeleton_code": skeleton,
            "patch_text": raw_response,
            "updated_code": updated_code,
            "patch_success": success,
            "status_message": msg,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "duration_seconds": elapsed,
            "ast_stats": ast_stats
        }


class StandardAgent:
    """Baseline standard coding agent that sends entire files and asks for entire rewrites."""

    @staticmethod
    def solve(original_code: str, prompt: str) -> dict:
        start_time = time.time()
        
        system_msg = "You are a helpful software engineer AI coding assistant. You analyze full files and rewrite the complete file with fixes."
        user_msg = f"""Here is the complete source file for the application:

```python
{original_code}
```

Please solve the following task:
{prompt}

Rewrite the complete updated file with all imports, classes, and unchanged methods preserved. Output the full file within a code fence."""

        input_tokens = count_tokens(system_msg) + count_tokens(user_msg)
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
        
        raw_response = call_llm_api(messages, temperature=0.1, max_tokens=1500)
        output_tokens = count_tokens(raw_response)
        
        # Extract full code
        import re
        m = re.search(r"```(?:python)?\s*\n(.*?)\n```", raw_response, re.DOTALL)
        updated_code = m.group(1).strip() if m else raw_response
        elapsed = round(time.time() - start_time, 2)

        return {
            "mode": "standard",
            "prompt_length": len(user_msg),
            "updated_code": updated_code,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "duration_seconds": elapsed
        }


def run_benchmark_comparison(original_code: str, prompt: str, test_code: str = "") -> dict:
    """Runs both TokenSlim and Standard agents and measures token savings & functional correctness."""
    slim_result = TokenSlimAgent.solve(original_code, prompt)
    # slight sleep to be polite to free-tier API rate limits
    time.sleep(1.0)
    std_result = StandardAgent.solve(original_code, prompt)
    
    token_savings = std_result["total_tokens"] - slim_result["total_tokens"]
    savings_pct = round((token_savings / max(1, std_result["total_tokens"])) * 100, 1)

    test_passed = False
    test_output = ""
    if test_code:
        try:
            local_scope = {}
            exec(slim_result["updated_code"], local_scope)
            exec(test_code, local_scope)
            test_fn = local_scope.get("run_test")
            if callable(test_fn):
                test_output = test_fn(local_scope)
                test_passed = True
            else:
                test_output = "No run_test() function defined."
        except Exception as e:
            test_passed = False
            test_output = f"Test failure: {e}"

    return {
        "tokenslim": slim_result,
        "standard": std_result,
        "metrics": {
            "tokenslim_total": slim_result["total_tokens"],
            "standard_total": std_result["total_tokens"],
            "tokens_saved": token_savings,
            "savings_percentage": savings_pct,
            "speedup_factor": round(std_result["duration_seconds"] / max(0.01, slim_result["duration_seconds"]), 1)
        },
        "verification": {
            "test_passed": test_passed,
            "test_output": test_output
        }
    }
