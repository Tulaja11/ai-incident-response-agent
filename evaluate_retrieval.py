"""Measure retrieval quality against the 15-log ground truth.

Reports recall@1, recall@3, and MRR. Recall@3 is the headline:
with one true match per query, precision@3 caps at 0.33 by
construction, so it would understate performance.
"""

import json
import os
import time
from rag.retriever import retrieve_for_log
from rag.vector_store import get_collection


def load_ground_truth():
    with open("data/ground_truth.json", encoding="utf-8") as f:
        return json.load(f)


def load_log(name):
    with open(f"data/error_logs/{name}.txt", encoding="utf-8") as f:
        return f.read()


def evaluate(mode: str = "full", verbose: bool = True):
    """
    mode:
      "full"      - error_type + system + ground-truth root cause (LEAKY)
      "realistic" - error_type + system, no root cause
      "coldstart" - raw log only, no metadata at all
    """
    gt = load_ground_truth()
    collection = get_collection()

    hits_at_1 = hits_at_3 = 0
    reciprocal_ranks, latencies, failures = [], [], []

    for name, truth in gt.items():
        raw_log = load_log(name)
        expected = set(truth["expected_incident_ids"])

        if mode == "full":
            et, sysname, rc = truth["error_type"], truth["affected_system"], truth["root_cause"]
        elif mode == "realistic":
            et, sysname, rc = truth["error_type"], truth["affected_system"], ""
        else:  # coldstart
            et, sysname, rc = None, None, ""

        t0 = time.perf_counter()
        results = retrieve_for_log(
            raw_log, error_type=et, affected_system=sysname,
            root_cause=rc, collection=collection,
        )
        latencies.append((time.perf_counter() - t0) * 1000)

        ids = [r["incident_id"] for r in results]
        rank = next((i + 1 for i, x in enumerate(ids) if x in expected), None)
        if rank == 1:
            hits_at_1 += 1
        if rank and rank <= 3:
            hits_at_3 += 1
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

        if verbose:
            mark = "HIT " if rank else "MISS"
            top = results[0]["similarity_score"] if results else 0
            print(f"{mark} {name:24s} rank={rank or '-'} top_sim={top:.3f} got={ids}")

        if not rank:
            failures.append({"log": name, "expected": list(expected), "got": ids})

    n = len(gt)
    print("\n" + "=" * 60)
    print(f"mode: {mode}")
    print(f"recall@1 : {hits_at_1}/{n} = {hits_at_1/n:.3f}")
    print(f"recall@3 : {hits_at_3}/{n} = {hits_at_3/n:.3f}")
    print(f"MRR      : {sum(reciprocal_ranks)/n:.3f}")
    print(f"mean latency: {sum(latencies)/len(latencies):.0f} ms")
    print("=" * 60)

    if failures:
        print(f"\n{len(failures)} failures:")
        for f in failures:
            print(f"  {f['log']}: expected {f['expected']}, got {f['got']}")

    return {"mode": mode, "recall@1": hits_at_1/n, "recall@3": hits_at_3/n,
            "mrr": sum(reciprocal_ranks)/n,
            "mean_latency_ms": sum(latencies)/len(latencies)}


if __name__ == "__main__":
    results = []
    for mode in ("full", "realistic", "coldstart"):
        print(f"\n\n### MODE: {mode} ###\n")
        results.append(evaluate(mode))

    print("\n\n--- summary ---")
    print(f"{'mode':<12} {'recall@1':>9} {'recall@3':>9} {'MRR':>7}")
    for r in results:
        print(f"{r['mode']:<12} {r['recall@1']:>9.3f} {r['recall@3']:>9.3f} {r['mrr']:>7.3f}")


        import json, datetime
    os.makedirs("evaluation", exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"evaluation/retrieval_{stamp}.json", "w") as f:
        json.dump({"results": results, "corpus_size": 24, "test_cases": 15}, f, indent=2)
    print(f"\nsaved evaluation/retrieval_{stamp}.json")