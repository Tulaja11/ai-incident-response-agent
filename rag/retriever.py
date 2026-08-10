"""Two-stage retrieval over the incident corpus.

Stage 1: semantic search over problem_signature chunks only.
         Resolution text is excluded from search deliberately — an
         incoming error log describes symptoms, not fixes, so fix
         vocabulary in the search target only adds noise.

Stage 2: metadata-boosted re-ranking. Semantic similarity does the
         heavy lifting; metadata nudges. Boosts are kept small on
         purpose — if error_type alone could rank correctly, the
         embeddings would not be earning their place.

Stage 3: pair each match with its resolution chunk, fetched by
         incident_id. This is what Agent 4 consumes.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.vector_store import get_collection, embed_query

# Re-ranking weights. Deliberately small relative to a cosine score
# that typically lands in the 0.6-0.9 band for real matches.
BOOST_ERROR_TYPE = 0.15
BOOST_SYSTEM = 0.10
BOOST_RECENCY = 0.05

CANDIDATE_POOL = 10   # stage 1 breadth
FINAL_K = 3           # what the agent actually sees
MIN_SIMILARITY = 0.30 # discard obvious noise


def build_query(
    error_type: str | None = None,
    affected_system: str | None = None,
    error_detail: str = "",
    root_cause: str = "",
) -> str:
    """Construct a structured retrieval query.

    Dumping a raw log into the embedder performs badly: timestamps,
    thread IDs and repeated stack frames dilute the semantic signal.
    This mirrors the shape of the indexed problem_signature chunks.
    """
    parts = []
    if error_type:
        parts.append(f"Error type: {error_type}")
    if affected_system:
        parts.append(f"Affected system: {affected_system}")
    if error_detail:
        parts.append(f"Error details: {error_detail.strip()[:600]}")
    if root_cause:
        parts.append(f"Root cause: {root_cause.strip()[:400]}")
    return "\n".join(parts)


def extract_error_lines(raw_log: str, max_lines: int = 12) -> str:
    """Pull the semantically dense lines out of a raw log.

    Keeps ERROR/exception lines and the first few stack frames,
    drops INFO/DEBUG noise and repeated framework frames.
    """
    keep = []
    for line in raw_log.splitlines():
        s = line.strip()
        if not s:
            continue
        upper = s.upper()
        is_error = any(k in upper for k in ("ERROR", "FATAL", "EXCEPTION", "TRACEBACK"))
        is_frame = s.startswith(("at ", "File ", "  File"))
        is_detail = s.startswith(("Detail:", "DETAIL:", "Caused by", "Response body"))
        if is_error or is_frame or is_detail:
            keep.append(s)
        if len(keep) >= max_lines:
            break
    return "\n".join(keep) if keep else raw_log[-600:]


def _recency_bonus(date_str: str) -> float:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return 0.0
    age_days = (datetime.now() - d).days
    return BOOST_RECENCY if age_days <= 270 else 0.0


def retrieve(
    query_text: str,
    error_type: str | None = None,
    affected_system: str | None = None,
    k: int = FINAL_K,
    collection=None,
    verbose: bool = False,
) -> list[dict]:
    """Run the full retrieval pipeline. Returns top-k matches."""
    if collection is None:
        collection = get_collection()

    qvec = embed_query(query_text)

    # ── Stage 1: broad semantic search, problem chunks only ──
    raw = collection.query(
        query_embeddings=[qvec],
        n_results=CANDIDATE_POOL,
        where={"chunk_type": "problem_signature"},
        include=["documents", "metadatas", "distances"],
    )

    candidates = []
    for doc, meta, dist in zip(
        raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        # Chroma cosine space returns distance; similarity = 1 - distance
        similarity = 1.0 - dist
        if similarity < MIN_SIMILARITY:
            continue

        # ── Stage 2: metadata boosting ──
        boost = 0.0
        reasons = []
        if error_type and meta.get("error_type") == error_type:
            boost += BOOST_ERROR_TYPE
            reasons.append("error_type")
        if affected_system and meta.get("affected_system") == affected_system:
            boost += BOOST_SYSTEM
            reasons.append("system")
        rb = _recency_bonus(meta.get("date", ""))
        if rb:
            boost += rb
            reasons.append("recent")

        candidates.append({
            "incident_id": meta["incident_id"],
            "title": meta["title"],
            "error_type": meta["error_type"],
            "severity": meta["severity"],
            "affected_system": meta["affected_system"],
            "date": meta["date"],
            "problem_summary": doc,
            "similarity_score": round(similarity, 4),
            "final_score": round(similarity + boost, 4),
            "boosts_applied": reasons,
        })

    candidates.sort(key=lambda c: c["final_score"], reverse=True)
    top = candidates[:k]

    # ── Stage 3: attach resolution text for each match ──
    if top:
        res = collection.get(
            ids=[f"{c['incident_id']}::resolution" for c in top],
            include=["documents"],
        )
        by_id = dict(zip(res["ids"], res["documents"]))
        for c in top:
            c["resolution"] = by_id.get(f"{c['incident_id']}::resolution", "")

    if verbose:
        for i, c in enumerate(top, 1):
            print(f"  {i}. {c['incident_id']} sim={c['similarity_score']:.3f} "
                  f"final={c['final_score']:.3f} boosts={c['boosts_applied']}")
            print(f"     {c['title']}")

    return top


def retrieve_for_log(
    raw_log: str,
    error_type: str | None = None,
    affected_system: str | None = None,
    root_cause: str = "",
    k: int = FINAL_K,
    collection=None,
    verbose: bool = False,
) -> list[dict]:
    """Convenience wrapper: raw log in, matches out."""
    detail = extract_error_lines(raw_log)
    q = build_query(error_type, affected_system, detail, root_cause)
    return retrieve(q, error_type, affected_system, k, collection, verbose)