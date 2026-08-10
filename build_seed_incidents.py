"""One-time script: writes the seed incident corpus for ChromaDB
and records the expected retrieval matches in ground_truth.json."""

import json, os
from collections import Counter

INC = {}

def add(iid, title, date, severity, error_type, system, root_cause,
        resolution, lessons, services):
    INC[iid] = {
        "incident_id": iid,
        "title": title,
        "date": date,
        "severity": severity,
        "error_type": error_type,
        "affected_system": system,
        "root_cause_summary": root_cause,
        "resolution_steps": resolution,
        "lessons_learned": lessons,
        "services_involved": services,
    }

# ═══════════════════════════════════════════════════════════
# TRUE MATCHES — same failure mode as a test log,
# but different service and different code path.
# ═══════════════════════════════════════════════════════════

add("INC-2025-0114",
    "Billing contact null dereference during invoice generation",
    "2025-08-19", "High", "NullPointerException", "billing-service",
    "The invoice renderer assumed every account had an associated billing contact record. "
    "For 41 accounts migrated from the legacy platform the contact row was never created, so "
    "the join returned null. The renderer called getEmail() on that null reference and threw. "
    "The lookup had logged a warning about the empty result set for three weeks before the "
    "first crash, but nothing consumed that warning.",
    ["Added a null guard in InvoiceRenderer before contact field access",
     "Backfilled the 41 missing contact records from the legacy export",
     "Promoted the empty-lookup warning to an alerting metric",
     "Added a not-null constraint on the contact foreign key"],
    "A warning log that nobody alerts on is the same as no log at all. Data migrations "
    "need a completeness check, not just a row count.",
    ["billing-service", "account-service", "postgres-primary"])

add("INC-2025-0231",
    "Nightly aggregation job crashes on records with absent nested field",
    "2025-10-03", "Medium", "NullPointerException", "reporting-worker",
    "The revenue aggregation job indexed into a nested 'attribution' object on every event "
    "record. A producer change three days earlier began emitting events without that object "
    "when the traffic source was unknown. The job processed 90% of records fine and then "
    "died partway through, leaving the output partition half-written.",
    ["Added a defensive .get() with a default in the attribution transform",
     "Made the job write to a staging partition and promote atomically on success",
     "Added a schema contract test between the producer and the job"],
    "Partial writes are worse than clean failures. Jobs that transform data should be "
    "atomic at the partition level.",
    ["reporting-worker", "event-collector", "warehouse"])

add("INC-2025-0087",
    "Template cache returns null on miss instead of loading",
    "2025-06-11", "Low", "NullPointerException", "email-renderer",
    "The template loader's cache lookup returned null on a miss rather than falling through "
    "to disk load. Any locale not pre-warmed at boot would fail on first use. Only affected "
    "a staging deploy where the warm-up step had been skipped.",
    ["Changed the loader to load-on-miss rather than return null",
     "Added a boot assertion that all configured locales are warm"],
    "A cache that returns null on miss is a footgun. Load-through is the safer default.",
    ["email-renderer", "template-store"])

add("INC-2025-0302",
    "Payment gateway unreachable after network ACL change",
    "2025-11-22", "Critical", "ConnectionTimeout", "checkout-service",
    "A routine security review tightened an egress ACL and removed the rule permitting "
    "checkout-service to reach the payment gateway subnet. All connection attempts hung "
    "until the 30s timeout. Every checkout failed for 22 minutes across all regions. "
    "The change had passed review because the rule it removed was undocumented.",
    ["Rolled back the ACL change",
     "Documented all egress dependencies in the service manifest",
     "Added a synthetic transaction probe that alerts within 60s",
     "Reduced connect timeout from 30s to 5s to fail faster"],
    "Undocumented network dependencies are invisible to change review. A long timeout "
    "turns a fast failure into a slow outage.",
    ["checkout-service", "payment-gateway", "network-acl"])

add("INC-2025-0198",
    "Search cluster unreachable during rolling node replacement",
    "2025-09-14", "High", "ConnectionTimeout", "catalog-indexer",
    "During a rolling replacement of search cluster nodes, the indexer's connection pool "
    "held stale addresses for terminated instances. Bulk index requests timed out against "
    "hosts that no longer existed. Roughly 3100 catalog updates were not indexed, so search "
    "results were stale for four hours until the backlog cleared.",
    ["Restarted the indexer to refresh DNS resolution",
     "Switched the client from static host lists to service discovery",
     "Added a staleness metric on the indexing backlog"],
    "Clients that cache endpoint addresses need an invalidation path. Stale search results "
    "are a silent failure: nothing errors, users just get wrong answers.",
    ["catalog-indexer", "search-cluster", "service-discovery"])

add("INC-2025-0145",
    "Config service slow response causes report job to use stale settings",
    "2025-07-30", "Medium", "ConnectionTimeout", "scheduler-service",
    "The configuration service was under GC pressure and responses exceeded the 15s read "
    "timeout. The scheduler fell back to its last cached configuration, which was two days "
    "old and missing a recently changed retention setting. Jobs ran with the wrong retention "
    "window; no data was lost but seven exports were incorrectly scoped.",
    ["Increased config-service heap and tuned GC",
     "Added a max-age check on the cached config with an explicit alert when stale",
     "Made retention-critical settings fail closed rather than fall back"],
    "Graceful degradation is only graceful if you know it happened. Silent fallback to "
    "stale config is a correctness bug, not resilience.",
    ["scheduler-service", "config-service"])

add("INC-2025-0421",
    "Full-table load exhausts heap during data migration",
    "2025-12-08", "Critical", "OutOfMemoryError", "migration-runner",
    "The migration tool loaded the entire customer table into a list before transforming it. "
    "Against production volume (2.4M rows) this exceeded the 8G heap. The container was "
    "OOMKilled mid-migration, leaving the target table partially populated with no record "
    "of where it stopped. Recovery required a full truncate and restart.",
    ["Rewrote the loader to use a cursor with a 5000-row page size",
     "Added checkpointing so a restart resumes rather than redoes",
     "Set a heap dump on OOM so the next occurrence is diagnosable",
     "Load-tested the migration against a production-sized dataset"],
    "Code that works on a dev dataset tells you nothing about production volume. "
    "Any unbounded collection is a latent OOM.",
    ["migration-runner", "postgres-primary", "kubernetes"])

add("INC-2025-0356",
    "Inference worker OOM from oversized float64 feature arrays",
    "2025-11-05", "High", "OutOfMemoryError", "recommendation-service",
    "The feature builder allocated float64 arrays where float32 precision was sufficient, "
    "doubling memory per batch. Under peak traffic the batch size grew enough that a single "
    "allocation exceeded the remaining container memory. Two of four workers died and "
    "latency doubled while capacity was degraded.",
    ["Changed feature dtype from float64 to float32",
     "Capped maximum batch size in the serving config",
     "Added a memory headroom check before allocation",
     "Set container memory requests based on observed peak, not average"],
    "Numeric dtype is a capacity decision, not just a precision one. Batch size must be "
    "bounded by memory, not only by throughput targets.",
    ["recommendation-service", "model-registry", "kubernetes"])

add("INC-2025-0063",
    "Large image decode exhausts worker memory in dev",
    "2025-05-27", "Low", "OutOfMemoryError", "media-processor",
    "A developer uploaded a 100-megapixel test image. The processor decoded it fully into "
    "memory before checking dimensions. The worker died but the queue redelivered the job "
    "and it failed in a loop until the message hit the dead-letter threshold.",
    ["Added a dimension and file-size check before decode",
     "Set a max redelivery count so poison messages dead-letter quickly"],
    "Validate before you allocate. A poison message with unlimited retries is a "
    "self-inflicted denial of service.",
    ["media-processor", "upload-queue"])

add("INC-2025-0388",
    "JWKS cache not refreshed after identity provider key rotation",
    "2025-12-01", "Critical", "AuthenticationFailure", "edge-gateway",
    "The identity provider rotated its signing key as scheduled. The gateway cached the JWKS "
    "document with no TTL and never re-fetched it, so every token signed with the new key "
    "failed verification. All authenticated requests returned 401 for 31 minutes. Unauthenticated "
    "health checks stayed green, so monitoring did not fire.",
    ["Forced a JWKS refresh on the gateway fleet",
     "Set a 10-minute TTL on the JWKS cache",
     "Added retry-on-unknown-kid that triggers an immediate refresh",
     "Added an authenticated synthetic probe to monitoring"],
    "Health checks that skip authentication cannot detect authentication outages. "
    "Any cached security material needs a TTL and a refresh-on-miss path.",
    ["edge-gateway", "identity-provider", "monitoring"])

add("INC-2025-0277",
    "Expired partner API credential halts overnight data sync",
    "2025-10-19", "High", "AuthenticationFailure", "integration-worker",
    "A partner rotated the API credential and sent notice to an unmonitored shared mailbox. "
    "The stored secret was never updated. The overnight sync failed with 403 for all tenants. "
    "Because the job only alerted on exceptions rather than on zero-records-processed, the "
    "failure went unnoticed for two nights.",
    ["Rotated the stored credential to the new key",
     "Moved partner notifications to a monitored channel",
     "Added an alert on records-processed falling to zero",
     "Added an expiry-date field to the secret store with advance warning"],
    "Alert on the absence of expected work, not only on errors. Credentials need "
    "expiry tracking the same as certificates.",
    ["integration-worker", "partner-api", "secret-store"])

add("INC-2025-0092",
    "TOTP clock drift locks single user out of internal tool",
    "2025-06-24", "Low", "AuthenticationFailure", "internal-console",
    "One user's authenticator device clock had drifted roughly 90 seconds, outside the "
    "verification tolerance window. Every code was rejected. Isolated to that one account; "
    "no service impact.",
    ["Walked the user through device re-enrolment",
     "Added a hint to the failure message suggesting clock sync"],
    "Single-user auth failures are usually device state, not system state. A clear "
    "error message prevents an unnecessary support ticket.",
    ["internal-console", "identity-provider"])

add("INC-2025-0410",
    "Inconsistent lock ordering causes deadlocks under concurrent stock updates",
    "2025-12-15", "Critical", "DatabaseDeadlock", "warehouse-service",
    "Two code paths updated the same stock rows in different orders: one iterated line items "
    "as supplied by the caller, the other sorted by SKU. Under concurrent load, transactions "
    "acquired row locks in opposing sequences and the database began killing victims. "
    "Roughly 200 orders rolled back over eight minutes and reserved-stock counters drifted "
    "out of sync with actual availability.",
    ["Standardised all stock update paths to sort by primary key before locking",
     "Added a retry with jitter around the transaction boundary",
     "Ran a reconciliation job to correct drifted stock counters",
     "Added a deadlock-rate dashboard panel"],
    "Deterministic lock ordering is the fix for deadlocks; retries only mask them. "
    "Any transaction touching multiple rows must acquire them in a stable order.",
    ["warehouse-service", "postgres-primary", "order-service"])

add("INC-2025-0164",
    "Concurrent month-end workers deadlock on overlapping account ranges",
    "2025-08-04", "Medium", "DatabaseDeadlock", "finance-batch",
    "Month-end processing ran eight parallel workers partitioned by account hash, but a "
    "secondary index update touched shared summary rows. Workers deadlocked intermittently. "
    "The built-in retry handled most cases; the job completed 40 minutes late.",
    ["Increased retry attempts from 2 to 5 with exponential backoff",
     "Moved summary row updates to a single post-processing pass",
     "Reduced worker parallelism from 8 to 4 during month-end"],
    "Partitioning the primary key does not partition secondary index contention. "
    "Retries buy time but the real fix is removing the shared write.",
    ["finance-batch", "mysql-primary"])

add("INC-2025-0219",
    "Unordered batch insert causes tuple lock contention in audit table",
    "2025-09-27", "Medium", "DatabaseDeadlock", "compliance-writer",
    "Two writer processes flushed audit batches with executemany without ordering rows. "
    "Overlapping tuples were locked in different sequences and the database detected a "
    "deadlock. Batches were re-queued so no audit events were lost, but write latency "
    "spiked and the buffer grew for twenty minutes.",
    ["Sorted rows by primary key before executemany",
     "Reduced batch size from 500 to 200 to shorten lock duration",
     "Added a buffer-depth alert"],
    "Batch inserts hold locks for the duration of the batch. Sorting rows and keeping "
    "batches small reduces the contention window.",
    ["compliance-writer", "postgres-primary"])

# ═══════════════════════════════════════════════════════════
# NEAR MISSES — same error_type as a test log,
# genuinely different root cause. These test discrimination.
# ═══════════════════════════════════════════════════════════

add("INC-2025-0501",
    "Connection timeouts caused by DNS resolver saturation",
    "2025-11-12", "High", "ConnectionTimeout", "mesh-sidecar",
    "The cluster DNS resolver was saturated by a misconfigured client issuing lookups in a "
    "tight loop. Unrelated services saw connection attempts time out during name resolution, "
    "not during TCP connect. The target hosts were healthy throughout.",
    ["Rate-limited the misbehaving client",
     "Increased resolver replica count",
     "Enabled DNS caching in the sidecar"],
    "A connection timeout does not always mean the target is down. Distinguish resolution "
    "failures from connect failures in metrics.",
    ["mesh-sidecar", "cluster-dns"])

add("INC-2025-0512",
    "Connection pool exhaustion presents as timeouts",
    "2025-10-08", "Medium", "ConnectionTimeout", "profile-service",
    "A slow downstream call held pool connections open. New requests waited for a free "
    "connection and timed out at the pool-acquire boundary, not the network boundary. "
    "The downstream service was reachable the entire time.",
    ["Added a separate pool-acquire timeout distinct from connect timeout",
     "Set a request timeout on the slow downstream call",
     "Increased pool size as a stopgap"],
    "Pool exhaustion and network timeout look identical in logs unless you instrument "
    "them separately.",
    ["profile-service", "preferences-service"])

add("INC-2025-0523",
    "Memory growth from unbounded metrics cardinality",
    "2025-09-02", "High", "OutOfMemoryError", "telemetry-collector",
    "A deploy began emitting a metric labelled with a request ID, creating unbounded label "
    "cardinality. The collector's in-memory series index grew until the process was OOMKilled. "
    "No single allocation was large; the growth was gradual over six hours.",
    ["Dropped the high-cardinality label at ingestion",
     "Added a cardinality limit per metric name",
     "Added an alert on series count growth rate"],
    "Not every OOM is one big allocation. Gradual unbounded growth needs trend alerting, "
    "not threshold alerting.",
    ["telemetry-collector", "metrics-store"])

add("INC-2025-0534",
    "Native memory leak in compression library",
    "2025-07-16", "Medium", "OutOfMemoryError", "archive-service",
    "A compression library version had a native allocation leak that heap metrics did not "
    "show. RSS grew steadily while heap stayed flat, which made it look like a container "
    "limit problem rather than a leak.",
    ["Pinned the compression library to the previous version",
     "Added RSS-versus-heap divergence to the service dashboard"],
    "Heap metrics do not capture native allocations. Watch RSS and heap together.",
    ["archive-service"])

add("INC-2025-0545",
    "Authorization failure mistaken for authentication failure",
    "2025-08-28", "Medium", "AuthenticationFailure", "document-service",
    "A role mapping change removed a scope from a service account. Tokens were valid and "
    "verified correctly, but the request was rejected at the authorization layer. Logs "
    "reported it as an auth failure without distinguishing 401 from 403, sending responders "
    "down the wrong path for forty minutes.",
    ["Restored the missing scope on the service account",
     "Separated authentication and authorization failures in logging and metrics"],
    "Conflating 401 and 403 in logs costs real minutes during an incident.",
    ["document-service", "identity-provider"])

add("INC-2025-0556",
    "Lock wait timeout on long-running transaction, not a deadlock",
    "2025-06-05", "Medium", "DatabaseDeadlock", "pricing-service",
    "An analytics query held a long transaction open against the pricing table. Writers "
    "blocked and eventually hit the lock wait timeout. No circular dependency existed, so "
    "the database never reported a deadlock, but the symptom in application logs looked "
    "similar and was triaged as one.",
    ["Moved the analytics query to a read replica",
     "Set a statement timeout on analytics connections",
     "Separated lock-wait-timeout from deadlock in error handling"],
    "Lock wait timeouts and deadlocks have different fixes. Treating one as the other "
    "wastes an investigation cycle.",
    ["pricing-service", "postgres-primary", "analytics"])

# ═══════════════════════════════════════════════════════════
# NEGATIVE CONTROLS — unrelated failure modes.
# These should never surface in a top-3 result.
# ═══════════════════════════════════════════════════════════

add("INC-2025-0601",
    "TLS certificate expiry breaks internal service mesh",
    "2025-10-30", "Critical", "CertificateExpiry", "service-mesh",
    "An intermediate CA certificate expired. Mutual TLS handshakes failed mesh-wide. "
    "The expiry date was tracked in a spreadsheet nobody owned.",
    ["Issued a new intermediate and rolled it out",
     "Automated certificate renewal with 30-day advance alerting"],
    "Anything with an expiry date needs automated renewal and automated alerting.",
    ["service-mesh", "pki"])

add("INC-2025-0612",
    "Disk exhaustion from unrotated debug logs",
    "2025-07-09", "High", "DiskFull", "log-shipper",
    "A debug log level was enabled during an investigation and never reverted. Log volume "
    "filled the node disk, which caused unrelated pods on the same node to fail writes.",
    ["Reverted the log level and truncated the files",
     "Added log rotation with a size cap",
     "Added a disk usage alert at 80%"],
    "Temporary debug settings need an expiry. Disk is a shared resource across pods.",
    ["log-shipper", "kubernetes"])

add("INC-2025-0623",
    "Rate limit exhaustion from missing client-side backoff",
    "2025-11-18", "Medium", "RateLimitExceeded", "webhook-dispatcher",
    "A retry loop without backoff hammered a third-party API and exhausted the hourly quota "
    "for the whole organisation, affecting unrelated integrations.",
    ["Added exponential backoff with jitter",
     "Added a per-integration quota budget",
     "Added quota-consumption monitoring"],
    "Retries without backoff turn a transient failure into a shared-resource outage.",
    ["webhook-dispatcher", "third-party-api"])

# ═══════════════════════════════════════════════════════════
# Which incidents SHOULD be retrieved for each test log.
# This is what makes precision@3 computable.
# ═══════════════════════════════════════════════════════════

EXPECTED_MATCHES = {
    "null_pointer_01":        ["INC-2025-0114"],
    "null_pointer_02":        ["INC-2025-0231"],
    "null_pointer_03":        ["INC-2025-0087"],
    "connection_timeout_01":  ["INC-2025-0302"],
    "connection_timeout_02":  ["INC-2025-0198"],
    "connection_timeout_03":  ["INC-2025-0145"],
    "memory_exhaustion_01":   ["INC-2025-0421"],
    "memory_exhaustion_02":   ["INC-2025-0356"],
    "memory_exhaustion_03":   ["INC-2025-0063"],
    "auth_failure_01":        ["INC-2025-0388"],
    "auth_failure_02":        ["INC-2025-0277"],
    "auth_failure_03":        ["INC-2025-0092"],
    "db_deadlock_01":         ["INC-2025-0410"],
    "db_deadlock_02":         ["INC-2025-0164"],
    "db_deadlock_03":         ["INC-2025-0219"],
}


def main():
    os.makedirs("data", exist_ok=True)

    with open("data/seed_incidents.json", "w", encoding="utf-8") as f:
        json.dump(list(INC.values()), f, indent=2)
    print(f"wrote data/seed_incidents.json ({len(INC)} incidents)")

    # merge expected matches into the existing ground truth
    with open("data/ground_truth.json", encoding="utf-8") as f:
        gt = json.load(f)

    for log_name, matches in EXPECTED_MATCHES.items():
        if log_name not in gt:
            raise KeyError(f"{log_name} missing from ground_truth.json")
        gt[log_name]["expected_incident_ids"] = matches

    with open("data/ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2)
    print("updated data/ground_truth.json with expected_incident_ids")

    print("\nerror_type distribution:",
          dict(Counter(v["error_type"] for v in INC.values())))
    print("severity distribution:  ",
          dict(Counter(v["severity"] for v in INC.values())))
    print("total incidents:", len(INC))

    ids = [v["incident_id"] for v in INC.values()]
    assert len(ids) == len(set(ids)), "duplicate incident_id"
    for matches in EXPECTED_MATCHES.values():
        for m in matches:
            assert m in INC, f"expected match {m} not in corpus"
    print("all expected matches resolve to real incidents")


if __name__ == "__main__":
    main()