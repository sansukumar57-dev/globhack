"""Faultline CLI — headless reliability runs (no server needed).

  py -3.11 cli.py run quick --policy baseline
  py -3.11 cli.py run full --policy hardened
  py -3.11 cli.py redteam --policy hardened
"""
import json
import sys
import time

from faultline import agent as agent_mod
from faultline import harness, redteam, scenarios, store


def run_suite(suite: str, policy: dict) -> dict:
    scenario_ids = ([a["id"] for a in redteam.ATTACKS] if suite == "redteam"
                    else list(scenarios.SUITES[suite]["scenario_ids"]))
    execution = store.make_execution(suite, policy.get("name", "custom"), policy,
                                     scenario_ids,
                                     seed=abs(hash(suite + policy["name"])) % 10_000)
    execution["status"] = "running"
    for i, item_id in enumerate(scenario_ids):
        item = (redteam.get(item_id) if suite == "redteam"
                else scenarios.get_scenario(item_id))
        run = harness._run_one(execution, policy, dict(item), item["user_message"],
                               (execution["seed"] + i * 101) % (2 ** 31),
                               suite == "redteam")
        store.put_run(run)
        store.add_result(execution, harness._run_summary(run))
        outcome = run.get("redteam_outcome", "")
        print(f"  [{i + 1}/{len(scenario_ids)}] {item_id} "
              f"{'PASS' if run.get('passed') else 'FAIL'} "
              f"(rel={run.get('reliability')}) {outcome}".rstrip(), flush=True)
    execution["summary"] = store.summarize_execution(execution)
    execution["status"] = "done"
    execution["finished_at"] = time.time()
    return execution


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    cmd, policy_name, suite = argv[0], "baseline", "quick"
    if "--policy" in argv:
        i = argv.index("--policy")
        policy_name = argv[i + 1]
    if cmd == "run" and len(argv) > 1:
        suite = argv[1]
    if cmd == "policy":
        print(json.dumps(agent_mod.POLICY_PRESETS.get(argv[1], agent_mod.DEFAULT_POLICY),
                         indent=2))
        return
    if cmd not in ("run", "redteam"):
        print(__doc__)
        return

    policy = dict(agent_mod.POLICY_PRESETS.get(policy_name,
                                               agent_mod.DEFAULT_POLICY))
    print(f"Faultline · suite={suite} · policy={policy['name']}")
    exec_rec = run_suite(suite, policy)
    print(json.dumps(exec_rec["summary"], indent=2))


if __name__ == "__main__":
    main()
