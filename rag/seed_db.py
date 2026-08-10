"""Populate ChromaDB from data/seed_incidents.json.

Run this once, or any time the seed corpus changes.
Safe to re-run: it wipes the collection first so you never
end up with duplicate or stale chunks.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.vector_store import get_collection, add_incidents, collection_stats


def main():
    with open("data/seed_incidents.json", encoding="utf-8") as f:
        incidents = json.load(f)

    print(f"loaded {len(incidents)} incidents from data/seed_incidents.json\n")

    collection = get_collection(reset=True)
    add_incidents(collection, incidents)

    print("\n--- collection stats ---")
    stats = collection_stats(collection)
    for k, v in stats.items():
        print(f"{k}: {v}")

    expected_chunks = len(incidents) * 3
    assert stats["total_chunks"] == expected_chunks, (
        f"expected {expected_chunks} chunks, got {stats['total_chunks']}"
    )
    assert stats["unique_incidents"] == len(incidents)
    print("\nseed complete")


if __name__ == "__main__":
    main()