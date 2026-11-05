"""Headless Criterion runs.

Useful for CI, quick comparisons and demos without the web app:

    python cli.py
    python cli.py --agents meridian,drift --trials 3
    python cli.py --json > run.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from criterion.agents import get_builtin_agents
from criterion.runner import build_run
from criterion.tasks import get_suite


def _fmt_ms(value: int | float | None) -> str:
    if value is None:
        return "-"
    value = int(value)
    if value < 1000:
        return f"{value}ms"
    return f"{value / 1000:.1f}s"


def _print_run(run: dict) -> None:
    suite = get_suite()
    summary = run["summary"]
    print()
    print("Criterion - Commerce support v3")
    print(f"{run['id']} | {run['trials']} trial(s) | {len(run['agent_ids'])} agents | {summary['total_executions']} task runs")
    print()
    header = f"{'#':<3} {'Agent':<16} {'Score':>7} {'Success':>8} {'Policy':>7} {'Tools':>7} {'Consist':>8} {'Safety':>7} {'p95':>7}"
    print(header)
    print("-" * len(header))
    for result in run["agent_results"]:
        print(
            f"{result['rank']:<3} {result['name']:<16} {result['score']:>7.1f} "
            f"{result['task_success']:>7.1f}% {result['policy']:>6.1f}% {result['tool_accuracy']:>6.1f}% "
            f"{result['consistency']:>7.1f}% {result['safety']:>6.1f}% {_fmt_ms(result['p95_latency_ms']):>7}"
        )
    print()
    print(f"Pass rate {summary['pass_rate']:.1f}% | Avg score {summary['avg_score']:.1f} | Best {summary['best_agent']} {summary['best_score']:.1f}")
    if summary["top_signatures"]:
        failures = ", ".join(f"{item['label']} ({item['count']})" for item in summary["top_signatures"])
        print(f"Top failures: {failures}")
    print(f"Suite: {suite['task_count']} tasks across {len(suite['categories'])} categories | deterministic checks")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Criterion commerce-support benchmark headlessly.")
    parser.add_argument("--agents", default="all", help="Comma-separated agent ids, or 'all'.")
    parser.add_argument("--trials", type=int, default=2, choices=(1, 2, 3), help="Trials per task (default: 2).")
    parser.add_argument("--seed", default="cli-demo", help="Run seed for reproducible sandbox results.")
    parser.add_argument("--json", action="store_true", help="Print the full run record as JSON.")
    parser.add_argument("--list-agents", action="store_true", help="List built-in agents and exit.")
    args = parser.parse_args()

    agents = get_builtin_agents()
    if args.list_agents:
        for agent in agents:
            print(f"{agent['id']:<12} {agent['name']:<12} {agent['adapter'].replace('·', '-')}")
        return 0

    if args.agents.strip().lower() == "all":
        selected = agents
    else:
        requested = {item.strip() for item in args.agents.split(",") if item.strip()}
        selected = [agent for agent in agents if agent["id"] in requested]
        if not selected:
            parser.error(f"No matching agents. Available: {', '.join(agent['id'] for agent in agents)}")
        missing = requested - {agent["id"] for agent in selected}
        if missing:
            parser.error(f"Unknown agents: {', '.join(sorted(missing))}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run = build_run(f"cli-{stamp}", selected, args.trials, args.seed)
    if args.json:
        print(json.dumps(run, indent=2))
    else:
        _print_run(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
