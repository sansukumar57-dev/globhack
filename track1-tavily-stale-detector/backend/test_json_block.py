"""Unit tests for extract_json_block resilience against LLM output quirks."""
import sys

sys.path.insert(0, ".")

from services.llm_client import extract_json_block

cases = [
    # (description, input, expected)
    ("plain object", '{"verdict": "STALE"}', {"verdict": "STALE"}),
    ("two objects back-to-back (observed failure)", '{"a":1}{"b":2}', {"a": 1}),
    ("json in prose", 'Here you go: [ {"claim": "x"} ]', [{"claim": "x"}]),
    ("fenced json", '```json\n{"verdict": "STALE"}\n```', {"verdict": "STALE"}),
    ("object then trailing text", '{"a":1} -- hope that helps!', {"a": 1}),
    ("nested braces in prose", 'Answer: {"x": {"y": 2}} done', {"x": {"y": 2}}),
]

fails = 0
for desc, sample, expected in cases:
    try:
        got = extract_json_block(sample)
        ok = got == expected
    except Exception:
        got = "<raised>"
        ok = False
    print(f"{desc!r:50} -> {'PASS' if ok else f'FAIL got {got!r}'}")
    if not ok:
        fails += 1

# "no json at all" must raise
try:
    extract_json_block("no json at all")
    print("'no json' case -> FAIL (should raise)")
    fails += 1
except ValueError:
    print("'no json' case -> PASS (raises ValueError)")

print("---")
print("ALL PASSED" if fails == 0 else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
