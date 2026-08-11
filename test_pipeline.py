"""Run the full 5-agent pipeline on one test log.

This is the moment everything connects: Agent 1 classifies,
Agent 2 finds root cause, Agent 3 retrieves history, Agent 4
suggests fixes grounded in that history, Agent 5 writes the report.
"""

import time
from agents.graph import build_graph
from agents.state import new_state, AGENT_ORDER


def load_log(name):
    with open(f"data/error_logs/{name}.txt", encoding="utf-8") as f:
        return f.read()


def run_investigation(name):
    print(f"\n{'='*64}")
    print(f"INVESTIGATING: {name}")
    print(f"{'='*64}\n")

    graph = build_graph()
    state = new_state(load_log(name))

    start = time.perf_counter()

    # Stream mode: yields {node_name: state_delta} after each node
    final_state = dict(state)
    for chunk in graph.stream(state, stream_mode="updates"):
        for node_name, delta in chunk.items():
            final_state.update(delta)
            elapsed = time.perf_counter() - start
            print(f"  [{elapsed:5.1f}s] {node_name} complete")

            # Show what each agent produced
            if node_name == "error_analyzer":
                print(f"         type={delta.get('error_type')} "
                      f"system={delta.get('affected_system')} "
                      f"severity={delta.get('severity')} "
                      f"({delta.get('severity_confidence', 0):.0%})")

            elif node_name == "root_cause_investigator":
                rc = delta.get("root_cause", {})
                print(f"         {rc.get('file')}:{rc.get('line')} "
                      f"-> {rc.get('explanation', '')[:80]}...")

            elif node_name == "historical_pattern":
                matches = delta.get("historical_matches", [])
                print(f"         {len(matches)} matches")
                for m in matches:
                    print(f"           {m['incident_id']} "
                          f"sim={m['similarity_score']:.3f} "
                          f"{m['title'][:50]}")

            elif node_name == "fix_suggester":
                fixes = delta.get("suggested_fixes", [])
                print(f"         {len(fixes)} fixes")
                for f in fixes:
                    print(f"           - {f['description'][:60]}...")

            elif node_name == "report_writer":
                report = delta.get("final_report", "")
                print(f"         report: {len(report)} chars")

    total = time.perf_counter() - start
    print(f"\n  TOTAL: {total:.1f}s")
    print(f"  errors: {final_state.get('errors', [])}")

    # Print first 500 chars of the report as a preview
    report = final_state.get("final_report", "")
    print(f"\n--- report preview (first 500 chars) ---\n{report[:500]}")

    return final_state


if __name__ == "__main__":
    # Run on one log from each error type
    result = run_investigation("connection_timeout_01")