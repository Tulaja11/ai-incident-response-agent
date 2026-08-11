"""Run Agent 3 standalone against a few test logs.

Node-level smoke test, not the benchmark — the benchmark lives in
evaluate_retrieval.py and measures the retriever directly. What this
checks is that the LangGraph adapter reads and writes state correctly,
including when upstream fields are missing or the input is garbage.
"""

import json
from agents.state import new_state
from agents.historical_pattern_agent import historical_pattern_node


def load_log(name):
    with open(f"data/error_logs/{name}.txt", encoding="utf-8") as f:
        return f.read()


def show(label, state_in):
    print(f"\n{'='*64}\n{label}\n{'='*64}")
    out = historical_pattern_node(state_in)

    print(f"timing: {out['agent_timings']['historical_pattern']}s")
    print(f"errors: {out['errors']}")
    print(f"matches passed downstream: {len(out['historical_matches'])}\n")

    for i, m in enumerate(out["historical_matches"], 1):
        print(f"  {i}. {m['incident_id']}  sim={m['similarity_score']:.3f}  "
              f"final={m['final_score']:.3f}  boosts={m['boosts_applied']}")
        print(f"     {m['title']}")
        print(f"     resolution: {len(m.get('resolution',''))} chars")
    return out


if __name__ == "__main__":
    gt = json.load(open("data/ground_truth.json", encoding="utf-8"))

    # ── Case A: full upstream context, as in the live pipeline ──
    name = "db_deadlock_01"
    s = new_state(load_log(name))
    s["error_type"] = gt[name]["error_type"]
    s["affected_system"] = gt[name]["affected_system"]
    s["root_cause"] = {"explanation": "Row locks acquired in inconsistent order"}
    out = show(f"A) {name} — full upstream context", s)
    assert out["historical_matches"], "expected at least one match"
    assert out["historical_matches"][0]["incident_id"] == "INC-2025-0410"

    # ── Case B: Agent 1 and 2 produced nothing (degradation test) ──
    name = "auth_failure_01"
    s = new_state(load_log(name))
    out = show(f"B) {name} — no upstream fields at all", s)
    assert out["historical_matches"], "should still retrieve without metadata"
    assert out["historical_matches"][0]["incident_id"] == "INC-2025-0388"

    # ── Case C: garbage input — should return nothing, not crash ──
    s = new_state("this is not an error log")
    out = show("C) nonsense input — expect 0 matches", s)
    assert out["errors"] == [], "must not raise"
    print(f"\n  -> returned {len(out['historical_matches'])} matches "
          f"(0 or few is correct here)")

    print("\n\nall node-level checks passed")