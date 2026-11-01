#!/usr/bin/env python3
"""
TokenSlim CLI: The Token-Efficient Coding Agent
Track 2: Bifrost Priority Track (#01 Fewest Tokens Coding Agent)
"""
import sys
import argparse
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from tokenslim.agent import TokenSlimAgent, run_benchmark_comparison
from tokenslim.benchmarks import PRESET_BENCHMARKS


def main():
    parser = argparse.ArgumentParser(
        description="TokenSlim: High-efficiency coding agent completing coding tasks with minimal tokens."
    )
    parser.add_argument("--file", "-f", help="Path to source code file to edit.")
    parser.add_argument("--prompt", "-p", help="Task instruction describing the fix or feature.")
    parser.add_argument("--benchmark", "-b", choices=[b["id"] for b in PRESET_BENCHMARKS],
                        help="Run an automated benchmark comparison.")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="Compare TokenSlim token metrics vs Standard Agent.")

    args = parser.parse_args()

    if args.benchmark:
        bm = next(b for b in PRESET_BENCHMARKS if b["id"] == args.benchmark)
        print("=" * 60)
        print(f"[RUNNING BENCHMARK]: {bm['title']}")
        print(f"Prompt: {bm['prompt']}")
        print("=" * 60)
        res = run_benchmark_comparison(bm["original_code"], bm["prompt"], bm["test_code"])
        
        print("\n=== TOKEN EFFICIENCY REPORT ===")
        print(f"  * Standard Agent Tokens:  {res['metrics']['standard_total']:,}")
        print(f"  * TokenSlim Agent Tokens: {res['metrics']['tokenslim_total']:,}")
        print(f"  * Tokens Saved:           {res['metrics']['tokens_saved']:,}")
        print(f"  * Token Reduction:        {res['metrics']['savings_percentage']}% SAVINGS")
        print(f"  * Execution Speedup:      {res['metrics']['speedup_factor']}x")
        print("\n=== VERIFICATION SUITE ===")
        print(f"  * Unit Tests Passed:      {'[YES]' if res['verification']['test_passed'] else '[NO]'}")
        print(f"  * Details:                {res['verification']['test_output']}")
        print("\n=== GENERATED PATCH ===")
        print(res["tokenslim"]["patch_text"])
        return

    if not args.file or not args.prompt:
        print("Usage:")
        print("  python cli.py --benchmark rate_limiter")
        print("  python cli.py --file path/to/code.py --prompt 'Fix divide by zero'")
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    code = file_path.read_text(encoding="utf-8")
    print(f"Analyzing {file_path.name} with TokenSlim...")
    
    if args.compare:
        res = run_benchmark_comparison(code, args.prompt)
        print("\n=== COMPARISON ===")
        print(f"  Standard Tokens:  {res['metrics']['standard_total']}")
        print(f"  TokenSlim Tokens: {res['metrics']['tokenslim_total']}")
        print(f"  Token Savings:    {res['metrics']['savings_percentage']}%")
        patch_text = res["tokenslim"]["patch_text"]
        updated_code = res["tokenslim"]["updated_code"]
    else:
        res = TokenSlimAgent.solve(code, args.prompt)
        patch_text = res["patch_text"]
        updated_code = res["updated_code"]
        print(f"Tokens consumed: {res['total_tokens']} (in: {res['input_tokens']}, out: {res['output_tokens']})")

    print("\nApplied Patch:")
    print(patch_text)
    print(f"\nSuccessfully generated patch for {file_path.name}.")


if __name__ == "__main__":
    main()
