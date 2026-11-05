import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from main import health, get_presets, analyze, AnalyzeRequest
from fastapi import HTTPException

def test_health():
    print("Testing GET /api/health ...", end=" ")
    data = health()
    assert data["status"] == "online", f"Expected online, got {data['status']}"
    assert "providers" in data
    print("PASS! [Status: online]")

def test_presets():
    print("Testing GET /api/presets ...", end=" ")
    presets = get_presets()
    assert len(presets) >= 4
    assert any("GPT-4" in p["text"] for p in presets)
    print(f"PASS! [{len(presets)} benchmarks available]")

def test_analyze_stale_claim():
    print("Testing POST /api/analyze (Stale claim: Python 2.7) ...", end=" ")
    req = AnalyzeRequest(
        text="Python 2.7 is the active LTS release used in modern Linux servers.",
        max_claims=5
    )
    res = analyze(req)
    assert res.total_claims >= 1
    assert res.stale_count >= 1
    assert res.overall_freshness < 50
    assert "UPDATED" in res.corrected_text
    assert len(res.markdown_report) > 50
    print(f"PASS! [Freshness score: {res.overall_freshness}/100, Detected {res.stale_count} stale claims]")

def test_analyze_fresh_claim():
    print("Testing POST /api/analyze (Fresh claim: Sundar Pichai) ...", end=" ")
    req = AnalyzeRequest(
        text="Sundar Pichai is the CEO of Google and Alphabet.",
        max_claims=5
    )
    res = analyze(req)
    assert res.total_claims >= 1
    assert res.fresh_count >= 1
    assert res.overall_freshness >= 75
    print(f"PASS! [Freshness score: {res.overall_freshness}/100, Fresh count: {res.fresh_count}]")

def test_analyze_empty():
    print("Testing POST /api/analyze (Empty text validation) ...", end=" ")
    try:
        analyze(AnalyzeRequest(text="   "))
        assert False, "Should have raised HTTPException"
    except HTTPException as e:
        assert e.status_code == 400
        print("PASS! [Correctly rejected empty text with 400]")

if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING STALE-ANSWER DETECTOR TEST SUITE (TRACK 1)")
    print("=" * 60)
    try:
        test_health()
        test_presets()
        test_analyze_stale_claim()
        test_analyze_fresh_claim()
        test_analyze_empty()
        print("=" * 60)
        print("ALL TESTS PASSED SUCCESSFULLY! (5/5)")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        sys.exit(1)
