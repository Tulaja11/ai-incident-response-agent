"""Agent 1: Error Analyzer.

Reads:  raw_log
Writes: error_type, affected_system, severity, severity_confidence, error_features

Uses Gemini for error_type + affected_system (language understanding),
sklearn for severity (numerical features + confidence score).
That split is deliberate: the LLM is better at classification from
unstructured text, the trained model is faster, deterministic, and
gives predict_proba.
"""

import time
import json
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import IncidentState
from models.severity_classifier import predict_with_features

load_dotenv()

VALID_ERROR_TYPES = [
    "NullPointerException",
    "ConnectionTimeout",
    "OutOfMemoryError",
    "AuthenticationFailure",
    "DatabaseDeadlock",
]

_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
)

CLASSIFICATION_PROMPT = """You are an expert SRE analyzing error logs.

Given the following error log, identify:
1. error_type: exactly one of {valid_types}
2. affected_system: the primary service or component name from the log

Respond ONLY with valid JSON, no markdown, no explanation:
{{"error_type": "...", "affected_system": "..."}}

ERROR LOG:
{log}"""


def _parse_llm_response(response) -> dict:
    """Extract JSON from Gemini response, handling content block format."""
    content = response.content
    if isinstance(content, list):
        text = "".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        )
    else:
        text = str(content)

    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


def error_analyzer_node(state: IncidentState) -> dict:
    """LangGraph node. Classifies error type, system, and severity."""
    t0 = time.perf_counter()
    errors = list(state.get("errors") or [])

    raw_log = state.get("raw_log", "")

    # ── LLM classification: error_type + affected_system ──
    error_type = "Unknown"
    affected_system = "unknown"

    try:
        prompt = CLASSIFICATION_PROMPT.format(
            valid_types=", ".join(VALID_ERROR_TYPES),
            log=raw_log[:3000],  # cap to avoid token limits
        )
        response = _llm.invoke(prompt)
        parsed = _parse_llm_response(response)

        et = parsed.get("error_type", "")
        if et in VALID_ERROR_TYPES:
            error_type = et
        else:
            errors.append(f"error_analyzer: LLM returned invalid error_type '{et}'")

        affected_system = parsed.get("affected_system", "unknown")

    except Exception as e:
        errors.append(f"error_analyzer: LLM classification failed: {e}")

    # ── Sklearn classification: severity ──
    try:
        severity, confidence, features = predict_with_features(raw_log)
    except Exception as e:
        errors.append(f"error_analyzer: severity prediction failed: {e}")
        severity = "Medium"
        confidence = 0.0
        features = {}

    elapsed = time.perf_counter() - t0
    timings = dict(state.get("agent_timings") or {})
    timings["error_analyzer"] = round(elapsed, 3)

    return {
        "error_type": error_type,
        "affected_system": affected_system,
        "severity": severity,
        "severity_confidence": round(confidence, 3),
        "error_features": features,
        "agent_timings": timings,
        "errors": errors,
    }