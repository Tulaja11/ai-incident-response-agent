"""The shared state passed between all five LangGraph nodes.

This TypedDict IS the contract between agents. No agent calls another
agent directly — each one reads the fields it needs and writes the
fields it owns. That is what makes the pipeline a graph rather than
a chain, and what lets the SSE endpoint emit a meaningful event after
every node without knowing anything about what the node does.

Field ownership (who WRITES what):
  error_analyzer            -> error_type, affected_system, severity,
                               severity_confidence, error_features
  root_cause_investigator   -> root_cause
  historical_pattern        -> historical_matches
  fix_suggester             -> suggested_fixes
  report_writer             -> final_report

Everything else is read-only to the nodes: raw_log is the input,
agent_timings and errors are appended to by the graph runner.
"""

from typing import TypedDict, Optional, Any


class RootCause(TypedDict, total=False):
    """What Agent 2 produces. total=False because the LLM may not
    always resolve a file or line, and a missing line number should
    not break the pipeline."""
    file: Optional[str]
    line: Optional[int]
    function: Optional[str]
    explanation: str
    confidence: Optional[float]


class HistoricalMatch(TypedDict, total=False):
    """One retrieved past incident. Mirrors what rag.retriever returns
    so Agent 3 can pass results through without reshaping them."""
    incident_id: str
    title: str
    error_type: str
    severity: str
    affected_system: str
    date: str
    problem_summary: str
    resolution: str
    similarity_score: float
    final_score: float
    boosts_applied: list[str]


class SuggestedFix(TypedDict, total=False):
    """One fix from Agent 4. `source` records whether the fix came from
    a retrieved past incident or was generated fresh — that provenance
    is what makes Agent 3's output visibly useful downstream."""
    description: str
    code_snippet: Optional[str]
    confidence: Optional[float]
    source: Optional[str]          # e.g. "INC-2025-0114" or "generated"


class IncidentState(TypedDict, total=False):
    """The object every node receives and returns.

    total=False throughout: nodes run in sequence and each one fills in
    its own slice, so a state mid-pipeline is legitimately partial.
    """

    # ── Input ──
    raw_log: str

    # ── Agent 1: Error Analyzer ──
    error_type: Optional[str]
    affected_system: Optional[str]
    severity: Optional[str]                 # from the sklearn model
    severity_confidence: Optional[float]    # predict_proba of chosen class
    error_features: Optional[dict[str, Any]]

    # ── Agent 2: Root Cause Investigator ──
    root_cause: Optional[RootCause]

    # ── Agent 3: Historical Pattern (RAG) ──
    historical_matches: Optional[list[HistoricalMatch]]

    # ── Agent 4: Fix Suggester ──
    suggested_fixes: Optional[list[SuggestedFix]]

    # ── Agent 5: Report Writer ──
    final_report: Optional[str]

    # ── Pipeline bookkeeping ──
    agent_timings: Optional[dict[str, float]]   # node name -> seconds
    errors: Optional[list[str]]                 # non-fatal node failures


# Canonical node order. The SSE endpoint and the frontend both read
# this, so the sequence lives in exactly one place.
AGENT_ORDER = [
    "error_analyzer",
    "root_cause_investigator",
    "historical_pattern",
    "fix_suggester",
    "report_writer",
]

# Which fields each node writes. The SSE layer uses this to emit only
# the delta a node produced instead of dumping the whole state to the
# browser on every event.
AGENT_OUTPUT_FIELDS = {
    "error_analyzer": [
        "error_type", "affected_system", "severity", "severity_confidence"
    ],
    "root_cause_investigator": ["root_cause"],
    "historical_pattern": ["historical_matches"],
    "fix_suggester": ["suggested_fixes"],
    "report_writer": ["final_report"],
}


def new_state(raw_log: str) -> IncidentState:
    """Build a fresh state for one investigation."""
    return {
        "raw_log": raw_log,
        "agent_timings": {},
        "errors": [],
    }