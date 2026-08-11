"""Agent 5: Report Writer.

Reads:  ALL state fields
Writes: final_report (markdown string)

Compiles everything from the previous four agents into a structured
professional incident report. This is the deliverable the user sees.
"""

import time
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import IncidentState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.1,  # slight creativity for readable prose
)

REPORT_PROMPT = """You are an expert SRE writing a professional incident report.

Compile the following investigation data into a clear, structured markdown report.

ERROR LOG:
{log}

CLASSIFICATION:
- Error Type: {error_type}
- Affected System: {affected_system}
- Severity: {severity} (confidence: {severity_confidence})

ROOT CAUSE:
- File: {file}
- Line: {line}
- Function: {function}
- Explanation: {explanation}

HISTORICAL CONTEXT:
{historical_context}

SUGGESTED FIXES:
{fixes_context}

PIPELINE TIMING:
{timing_context}

Write the report with these exact sections:
## Incident Summary
## Error Classification
## Root Cause Analysis
## Historical Context
## Recommended Fixes
## Severity Assessment

Rules:
- Be specific and technical, not generic
- Reference the actual file, line, and function names
- Reference past incident IDs when citing historical context
- Include code snippets from the suggested fixes
- Note the severity confidence from the ML classifier
- Keep it under 800 words
- Output clean markdown only, no preamble"""


def report_writer_node(state: IncidentState) -> dict:
    """LangGraph node. Compiles the final incident report."""
    t0 = time.perf_counter()
    errors = list(state.get("errors") or [])

    raw_log = state.get("raw_log", "")
    error_type = state.get("error_type", "Unknown")
    affected_system = state.get("affected_system", "unknown")
    severity = state.get("severity", "Medium")
    severity_confidence = state.get("severity_confidence", 0.0)

    # Root cause
    rc = state.get("root_cause") or {}
    file = rc.get("file", "Unknown")
    line = rc.get("line", "Unknown")
    function = rc.get("function", "Unknown")
    explanation = rc.get("explanation", "Could not determine")

    # Historical matches
    matches = state.get("historical_matches") or []
    if matches:
        hist_lines = []
        for m in matches:
            hist_lines.append(
                f"- {m['incident_id']}: {m['title']} "
                f"(similarity: {m['similarity_score']:.2f})"
            )
            if m.get("resolution"):
                hist_lines.append(f"  Resolution: {m['resolution'][:300]}")
        historical_context = "\n".join(hist_lines)
    else:
        historical_context = "No similar past incidents found in the knowledge base."

    # Fixes
    fixes = state.get("suggested_fixes") or []
    if fixes:
        fix_lines = []
        for i, f in enumerate(fixes, 1):
            fix_lines.append(f"{i}. {f['description']}")
            if f.get("code_snippet"):
                fix_lines.append(f"   ```\n   {f['code_snippet']}\n   ```")
            fix_lines.append(f"   Source: {f.get('source', 'generated')} | "
                           f"Confidence: {f.get('confidence', 'N/A')}")
        fixes_context = "\n".join(fix_lines)
    else:
        fixes_context = "No fixes could be generated."

    # Timing
    timings = state.get("agent_timings") or {}
    timing_context = "\n".join(
        f"- {name}: {t:.2f}s" for name, t in timings.items()
    )

    report = ""
    try:
        prompt = REPORT_PROMPT.format(
            log=raw_log[:2000],
            error_type=error_type,
            affected_system=affected_system,
            severity=severity,
            severity_confidence=severity_confidence,
            file=file,
            line=line,
            function=function,
            explanation=explanation,
            historical_context=historical_context,
            fixes_context=fixes_context,
            timing_context=timing_context,
        )
        response = _llm.invoke(prompt)
        content = response.content
        if isinstance(content, list):
            report = "".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        else:
            report = str(content)

    except Exception as e:
        errors.append(f"report_writer: {e}")
        report = f"# Incident Report\n\nReport generation failed: {e}"

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("agent_timings") or {})
    timings["report_writer"] = round(elapsed, 3)

    return {
        "final_report": report,
        "agent_timings": timings,
        "errors": errors,
    }