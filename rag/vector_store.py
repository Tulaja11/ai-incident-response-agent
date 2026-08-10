"""ChromaDB collection management and section-based chunking.

Each incident report becomes 3 semantic chunks rather than fixed-size
splits, because these documents have real structure worth exploiting:
  - problem_signature: what went wrong (the search target)
  - resolution:        how it was fixed (retrieved after a match)
  - full_context:      whole report (fallback)

Keeping resolution text OUT of the searchable problem chunk matters.
If they were combined, words from the fix would dilute the similarity
signal of the symptom, which is what incoming queries actually describe.
"""

import os
from collections import Counter
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_store")
COLLECTION_NAME = "incident_reports"

# Stable GA model. Avoid -2 and -2-preview: reproducibility matters more
# than recency when a metric from this pipeline goes on a resume.
EMBED_MODEL = "models/gemini-embedding-001"

# Model default is 3072. For a 24-document corpus that's wasted storage
# and slower similarity math with no quality gain. 768 also keeps the
# store small enough to commit to git, which matters because Render's
# free tier wipes the filesystem on every redeploy.
EMBED_DIM = 768

# task_type is the detail most tutorials skip. Google produces different
# vectors for documents vs queries; using the right one on each side is
# a measurable retrieval win and costs nothing.
_doc_embedder = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL,
    task_type="retrieval_document",
    output_dimensionality=EMBED_DIM,
)
_query_embedder = GoogleGenerativeAIEmbeddings(
    model=EMBED_MODEL,
    task_type="retrieval_query",
    output_dimensionality=EMBED_DIM,
)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _doc_embedder.embed_documents(texts)


def embed_query(text: str) -> list[float]:
    return _query_embedder.embed_query(text)


# ─────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────

def chunk_incident(incident: dict) -> list[dict]:
    """Split one incident into 3 chunks, each carrying metadata.

    Returns a list of {id, text, metadata} dicts ready for ChromaDB.
    """
    iid = incident["incident_id"]

    base_meta = {
        "incident_id": iid,
        "error_type": incident["error_type"],
        "severity": incident["severity"],
        "affected_system": incident["affected_system"],
        "date": incident["date"],
        "title": incident["title"],
        # Chroma metadata values must be scalars, so join the list
        "services_involved": ", ".join(incident["services_involved"]),
    }

    # ── Chunk A: problem signature (the primary search target) ──
    problem_text = (
        f"Title: {incident['title']}\n"
        f"Error type: {incident['error_type']}\n"
        f"Affected system: {incident['affected_system']}\n"
        f"Services involved: {', '.join(incident['services_involved'])}\n"
        f"Root cause: {incident['root_cause_summary']}"
    )

    # ── Chunk B: resolution (fetched by incident_id after a match) ──
    steps = "\n".join(
        f"{i + 1}. {s}" for i, s in enumerate(incident["resolution_steps"])
    )
    resolution_text = (
        f"Incident: {incident['title']}\n"
        f"Resolution steps:\n{steps}\n"
        f"Lessons learned: {incident['lessons_learned']}"
    )

    # ── Chunk C: full context (safety net) ──
    full_text = f"{problem_text}\n\n{resolution_text}"

    return [
        {
            "id": f"{iid}::problem",
            "text": problem_text,
            "metadata": {**base_meta, "chunk_type": "problem_signature"},
        },
        {
            "id": f"{iid}::resolution",
            "text": resolution_text,
            "metadata": {**base_meta, "chunk_type": "resolution"},
        },
        {
            "id": f"{iid}::full",
            "text": full_text,
            "metadata": {**base_meta, "chunk_type": "full_context"},
        },
    ]


# ─────────────────────────────────────────────────────────
# Collection management
# ─────────────────────────────────────────────────────────

def get_client():
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(reset: bool = False):
    """Get the incident collection, optionally wiping it first.

    embedding_function is None deliberately: we pass Google embeddings
    explicitly on add() and query(), so Chroma never silently falls back
    to its bundled local MiniLM model.
    """
    client = get_client()

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # collection didn't exist yet

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


def add_incidents(collection, incidents: list[dict], batch_size: int = 20):
    """Chunk, embed, and store every incident."""
    all_chunks = []
    for inc in incidents:
        all_chunks.extend(chunk_incident(inc))

    print(f"chunking {len(incidents)} incidents -> {len(all_chunks)} chunks")

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]

        vectors = embed_documents(texts)

        collection.add(
            ids=[c["id"] for c in batch],
            documents=texts,
            embeddings=vectors,
            metadatas=[c["metadata"] for c in batch],
        )
        print(f"  embedded and stored {i + len(batch)}/{len(all_chunks)}")

    return len(all_chunks)


def collection_stats(collection) -> dict:
    """Summary of what actually landed in the store."""
    data = collection.get(include=["metadatas"])
    metas = data["metadatas"]

    return {
        "total_chunks": len(metas),
        "unique_incidents": len({m["incident_id"] for m in metas}),
        "by_chunk_type": dict(Counter(m["chunk_type"] for m in metas)),
        "by_error_type": dict(
            Counter(
                m["error_type"]
                for m in metas
                if m["chunk_type"] == "problem_signature"
            )
        ),
    }