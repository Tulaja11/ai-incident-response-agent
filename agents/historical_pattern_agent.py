"""Agent 3: Historical Pattern Investigator.

Reads:  raw_log, error_type, affected_system, root_cause
Writes: historical_matches

The retrieval logic lives in rag/retriever.py and is validated
independently (recall@3 1.000, recall@1 0.933 on the 15-case
benchmark). This module is only the LangGraph adapter around it.

Keeping retrieval out of the node is deliberate: it means the
retriever can be benchmarked without instantiating a graph, which
is exactly how those numbers were produced.
"""

import time

from agents.state import IncidentState
from rag.retriever import retrieve_for_log
from rag.vector_store import get_collection

# One collection handle reused across invocations. Opening a
# PersistentClient per request adds ~200ms for no benefit.
_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = get_collection()
    return _collection


def historical_pattern_node(state: IncidentState) -> dict:
    """LangGraph node. Returns only the fields this agent owns."""
    t0 = time.perf_counter()

    raw_log = state.get("raw_log", "")
    error_type = state.get("error_type")
    affected_system = state.get("affected_system")

    # Agent 2's explanation sharpens the query when available, but the
    # node must work without it — coldstart mode scored 0.933 recall@1
    # with no metadata at all, so a missing upstream field degrades
    # results rather than breaking them.
    root_cause = ""
    rc = state.get("root_cause")
    if isinstance(rc, dict):
        root_cause = rc.get("explanation", "") or ""

    errors = list(state.get("errors") or [])

    try:
        matches = retrieve_for_log(
            raw_log=raw_log,
            error_type=error_type,
            affected_system=affected_system,
            root_cause=root_cause,
            collection=_get_collection(),
        )
        # Only pass through matches worth standing behind. Agent 4
        # treats these as prior art, so a weak match is worse than no
        # match: it yields a confident fix citing an unrelated incident.
        matches = [m for m in matches if m.get("is_relevant", True)]
    except Exception as e:
        # A retrieval failure should not kill the investigation. The
        # remaining agents can still produce a useful report without
        # historical context; they just lose the prior-art signal.
        errors.append(f"historical_pattern: {type(e).__name__}: {e}")
        matches = []

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("agent_timings") or {})
    timings["historical_pattern"] = round(elapsed, 3)

    return {
        "historical_matches": matches,
        "agent_timings": timings,
        "errors": errors,
    }