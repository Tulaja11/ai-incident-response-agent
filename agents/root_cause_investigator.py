"""Agent 2: Root Cause Investigator.

Reads:  raw_log, error_type, affected_system
Writes: root_cause {file, line, function, explanation, confidence}

Asks Gemini to identify the exact file, line, and function from the
stack trace, plus a plain-English explanation of why the error occurred.
"""

import time
import json
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import IncidentState

load_dotenv()

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
)

ROOT_CAUSE_PROMPT = """You are an expert SRE performing root cause analysis.

Given this error log from a {error_type} in {affected_system}, identify:
1. file: the source file where the error originates (from the stack trace)
2. line: the line number (integer or null if not visible)
3. function: the function or method name
4. explanation: 2-3 sentences explaining WHY this error occurred, not just what happened
5. confidence: your confidence 0.0-1.0 in this root cause

Respond ONLY with valid JSON, no markdown, no explanation:
{{"file": "...", "line": ..., "function": "...", "explanation": "...", "confidence": ...}}

ERROR LOG:
{log}"""


def _parse_llm_response(response) -> dict:
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


def root_cause_node(state: IncidentState) -> dict:
    """LangGraph node. Identifies root cause from stack trace."""
    t0 = time.perf_counter()
    errors = list(state.get("errors") or [])

    raw_log = state.get("raw_log", "")
    error_type = state.get("error_type", "Unknown")
    affected_system = state.get("affected_system", "unknown")

    root_cause = {
        "file": None,
        "line": None,
        "function": None,
        "explanation": "Could not determine root cause",
        "confidence": 0.0,
    }

    try:
        prompt = ROOT_CAUSE_PROMPT.format(
            error_type=error_type,
            affected_system=affected_system,
            log=raw_log[:3000],
        )
        response = _llm.invoke(prompt)
        parsed = _parse_llm_response(response)

        root_cause = {
            "file": parsed.get("file"),
            "line": parsed.get("line"),
            "function": parsed.get("function"),
            "explanation": parsed.get("explanation", ""),
            "confidence": parsed.get("confidence", 0.5),
        }

    except Exception as e:
        errors.append(f"root_cause_investigator: {e}")

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("agent_timings") or {})
    timings["root_cause_investigator"] = round(elapsed, 3)

    return {
        "root_cause": root_cause,
        "agent_timings": timings,
        "errors": errors,
    }