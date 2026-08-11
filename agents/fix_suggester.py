"""Agent 4: Fix Suggester.

Reads:  raw_log, error_type, root_cause, historical_matches
Writes: suggested_fixes [{description, code_snippet, confidence, source}]

This agent benefits directly from Agent 3's output: when historical
matches exist, fixes are grounded in how similar incidents were
actually resolved. When they don't (garbage input, new error type),
it falls back to generating fixes from the root cause alone.
That dependency is the architectural reason Agent 3 runs before this.
"""

import time
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import IncidentState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0,
)

FIX_PROMPT = """You are an expert SRE suggesting fixes for a production incident.

Error type: {error_type}
Root cause: {root_cause}

{historical_context}

Based on the root cause{and_history}, suggest 2-3 specific fixes.
Each fix must include:
- description: what to do and why
- code_snippet: a concrete code change, config change, or command (not pseudocode)
- confidence: your confidence 0.0-1.0 that this fix addresses the root cause
- source: if based on a past incident, its ID; otherwise "generated"

Respond ONLY with a JSON array, no markdown, no explanation:
[{{"description": "...", "code_snippet": "...", "confidence": ..., "source": "..."}}]

ERROR LOG:
{log}"""


def _parse_llm_response(response) -> list:
    content = response.content
    if isinstance(content, list):
        text = "".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        )
    else:
        text = str(content)

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


def fix_suggester_node(state: IncidentState) -> dict:
    """LangGraph node. Generates fix suggestions."""
    t0 = time.perf_counter()
    errors = list(state.get("errors") or [])

    raw_log = state.get("raw_log", "")
    error_type = state.get("error_type", "Unknown")

    # Build root cause string
    rc = state.get("root_cause")
    if isinstance(rc, dict):
        root_cause_str = rc.get("explanation", "Unknown root cause")
    else:
        root_cause_str = "Unknown root cause"

    # Build historical context from Agent 3's matches
    matches = state.get("historical_matches") or []
    if matches:
        lines = ["Past similar incidents and their resolutions:"]
        for m in matches:
            lines.append(f"\n- {m['incident_id']}: {m['title']}")
            if m.get("resolution"):
                lines.append(f"  Resolution: {m['resolution'][:400]}")
        historical_context = "\n".join(lines)
        and_history = " and how similar incidents were resolved"
    else:
        historical_context = "No similar past incidents found."
        and_history = ""

    fixes = []
    try:
        prompt = FIX_PROMPT.format(
            error_type=error_type,
            root_cause=root_cause_str,
            historical_context=historical_context,
            and_history=and_history,
            log=raw_log[:2000],
        )
        response = _llm.invoke(prompt)
        parsed = _parse_llm_response(response)

        for fix in parsed[:3]:  # cap at 3
            fixes.append({
                "description": fix.get("description", ""),
                "code_snippet": fix.get("code_snippet", ""),
                "confidence": fix.get("confidence", 0.5),
                "source": fix.get("source", "generated"),
            })

    except Exception as e:
        errors.append(f"fix_suggester: {e}")

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("agent_timings") or {})
    timings["fix_suggester"] = round(elapsed, 3)

    return {
        "suggested_fixes": fixes,
        "agent_timings": timings,
        "errors": errors,
    }