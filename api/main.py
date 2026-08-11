"""FastAPI backend: REST endpoints + SSE streaming.

The SSE design uses a two-step handshake because browser-native
EventSource only supports GET, but we need to POST the error log:
  1. POST /api/investigate        → returns {job_id}
  2. GET  /api/investigate/stream/{job_id} → SSE event stream

This lets us use real EventSource with automatic reconnection
instead of hand-rolling an SSE parser over fetch+ReadableStream.
"""

import os
import sys
import json
import time
import uuid
import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.graph import build_graph
from agents.state import new_state, AGENT_ORDER, AGENT_OUTPUT_FIELDS
from database import insert_incident, get_incidents, get_incident_by_id

app = FastAPI(title="AI Incident Response Agent")

STATIC_DIR = Path(__file__).parent / "static"

# ─────────────────────────────────────────────────────────
# In-memory job store. Fine for single-worker free tier.
# Jobs live ~30 seconds. Would need Redis for multi-worker.
# ─────────────────────────────────────────────────────────

JOBS: dict[str, str] = {}


class InvestigateRequest(BaseModel):
    raw_log: str


def sse(event: str, data: dict) -> str:
    """SSE wire format: event line, data line, blank line terminator."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────
# API ROUTES — declared BEFORE the static mount
# ─────────────────────────────────────────────────────────

@app.post("/api/investigate")
async def start_investigation(request: InvestigateRequest):
    """Step 1: stash the log, return a job id immediately."""
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = request.raw_log
    return {"job_id": job_id}


@app.get("/api/investigate/stream/{job_id}")
async def stream_investigation(job_id: str):
    """Step 2: EventSource connects here and receives the live feed."""

    raw_log = JOBS.pop(job_id, None)
    if raw_log is None:
        return JSONResponse(
            status_code=404,
            content={"error": "Unknown or expired job_id"}
        )

    async def event_generator():
        graph = build_graph()
        state = new_state(raw_log)
        start = time.time()
        final_state = dict(state)

        yield sse("pipeline_start", {
            "agents": AGENT_ORDER,
            "timestamp": start,
        })

        try:
            for chunk in graph.stream(state, stream_mode="updates"):
                for node_name, delta in chunk.items():
                    final_state.update(delta)

                    # Send only the fields this agent owns
                    fields = AGENT_OUTPUT_FIELDS.get(node_name, [])
                    result = {}
                    for f in fields:
                        val = delta.get(f)
                        if val is not None:
                            # Truncate large fields for the SSE preview
                            if f == "final_report":
                                result[f] = val[:200] + "..." if len(val) > 200 else val
                            elif f == "historical_matches":
                                result[f] = [
                                    {"incident_id": m["incident_id"],
                                     "title": m["title"],
                                     "similarity_score": m["similarity_score"]}
                                    for m in (val or [])
                                ]
                            else:
                                result[f] = val

                    yield sse("agent_complete", {
                        "agent": node_name,
                        "result": result,
                        "elapsed": round(time.time() - start, 2),
                    })

                    await asyncio.sleep(0.15)

            total = round(time.time() - start, 2)

            incident_id = insert_incident(
                raw_log=raw_log,
                error_type=final_state.get("error_type", "Unknown"),
                affected_system=final_state.get("affected_system", "unknown"),
                severity=final_state.get("severity", "Medium"),
                severity_confidence=final_state.get("severity_confidence", 0.0),
                report=final_state.get("final_report", ""),
                processing_time=total,
            )

            yield sse("pipeline_complete", {
                "incident_id": incident_id,
                "total_time": total,
                "error_type": final_state.get("error_type", ""),
                "severity": final_state.get("severity", ""),
            })

        except Exception as e:
            yield sse("pipeline_error", {
                "error": str(e),
                "elapsed": round(time.time() - start, 2),
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/incidents")
async def list_incidents():
    """Dashboard: list all past investigations."""
    return get_incidents()


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: int):
    """Report page: full investigation detail."""
    result = get_incident_by_id(incident_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok", "agents": len(AGENT_ORDER)}


# ─────────────────────────────────────────────────────────
# HTML PAGE ROUTES — clean URLs without .html extension
# ─────────────────────────────────────────────────────────

@app.get("/")
async def page_dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/investigate")
async def page_investigate():
    return FileResponse(STATIC_DIR / "investigate.html")


@app.get("/report")
async def page_report():
    return FileResponse(STATIC_DIR / "report.html")


# ─────────────────────────────────────────────────────────
# STATIC MOUNT — LAST LINE. Serves style.css, api.js, etc.
# ─────────────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")