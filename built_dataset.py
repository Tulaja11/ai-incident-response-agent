"""One-time script: writes the 15-log evaluation dataset and ground truth.
Run once, then delete or keep for reproducibility."""

import json, os, textwrap

LOGS = {}
GT = {}

# ─────────────────────────────────────────────────────────────
# TYPE 1 — NullPointerException / AttributeError
# ─────────────────────────────────────────────────────────────

LOGS["null_pointer_01"] = """\
2026-03-14T09:22:41.102Z INFO  order-service [http-nio-8080-exec-4] Received checkout request cart_id=CRT-88213 user_id=U-40192
2026-03-14T09:22:41.118Z INFO  order-service [http-nio-8080-exec-4] Resolving shipping address for user_id=U-40192
2026-03-14T09:22:41.121Z WARN  order-service [http-nio-8080-exec-4] Address lookup returned no rows for user_id=U-40192
2026-03-14T09:22:41.124Z ERROR order-service [http-nio-8080-exec-4] Unhandled exception processing checkout
java.lang.NullPointerException: Cannot invoke "com.shopflow.model.Address.getPostalCode()" because "shippingAddress" is null
	at com.shopflow.order.ShippingCalculator.calculateRate(ShippingCalculator.java:87)
	at com.shopflow.order.CheckoutService.buildOrderSummary(CheckoutService.java:214)
	at com.shopflow.order.CheckoutService.processCheckout(CheckoutService.java:139)
	at com.shopflow.api.CheckoutController.postCheckout(CheckoutController.java:56)
	at java.base/jdk.internal.reflect.DirectMethodHandleAccessor.invoke(DirectMethodHandleAccessor.java:103)
	at org.springframework.web.method.support.InvocableHandlerMethod.doInvoke(InvocableHandlerMethod.java:255)
2026-03-14T09:22:41.130Z ERROR order-service [http-nio-8080-exec-4] Returning 500 to client, order not created
"""

GT["null_pointer_01"] = {
    "error_type": "NullPointerException",
    "affected_system": "order-service",
    "severity": "High",
    "root_cause": "ShippingCalculator.calculateRate dereferences shippingAddress without a null check; the address lookup returned no rows for the user.",
    "expected_file": "ShippingCalculator.java",
    "expected_line": 87,
    "environment": "production",
}

LOGS["null_pointer_02"] = """\
[2026-04-02 17:44:03,881] INFO  analytics-worker: batch job daily_rollup started, partition=2026-04-01
[2026-04-02 17:44:09,204] INFO  analytics-worker: loaded 41892 event records from warehouse
[2026-04-02 17:44:09,377] WARN  analytics-worker: 37 records missing 'session' key, continuing
[2026-04-02 17:44:09,392] ERROR analytics-worker: batch job failed
Traceback (most recent call last):
  File "/app/analytics/jobs/daily_rollup.py", line 118, in run
    summary = build_session_summary(events)
  File "/app/analytics/transforms/sessions.py", line 64, in build_session_summary
    duration = event["session"]["end_ts"] - event["session"]["start_ts"]
TypeError: 'NoneType' object is not subscriptable
[2026-04-02 17:44:09,395] ERROR analytics-worker: partition 2026-04-01 not written, will retry next cycle
"""

GT["null_pointer_02"] = {
    "error_type": "NullPointerException",
    "affected_system": "analytics-worker",
    "severity": "Medium",
    "root_cause": "build_session_summary indexes into event['session'] which is None for 37 malformed records; the earlier warning was logged but not acted on.",
    "expected_file": "sessions.py",
    "expected_line": 64,
    "environment": "production",
}

LOGS["null_pointer_03"] = """\
2026-02-19 11:08:55 DEBUG notification-service - dispatching template=welcome_email locale=de-DE
2026-02-19 11:08:55 DEBUG notification-service - template cache miss, loading from disk
2026-02-19 11:08:55 ERROR notification-service - failed to render notification
AttributeError: 'NoneType' object has no attribute 'render'
  File "/srv/notify/dispatch.py", line 92, in send
    body = template.render(context)
  File "/srv/notify/loader.py", line 41, in get_template
    return self._cache.get(name)
2026-02-19 11:08:55 WARN  notification-service - message queued for retry, attempt 1 of 3
"""

GT["null_pointer_03"] = {
    "error_type": "NullPointerException",
    "affected_system": "notification-service",
    "severity": "Low",
    "root_cause": "get_template returns None on cache miss instead of loading from disk; dispatch.send calls .render() on the None result.",
    "expected_file": "dispatch.py",
    "expected_line": 92,
    "environment": "staging",
}

# ─────────────────────────────────────────────────────────────
# TYPE 2 — ConnectionTimeout
# ─────────────────────────────────────────────────────────────

LOGS["connection_timeout_01"] = """\
2026-01-28T14:03:12.001Z INFO  payment-service [pool-3-thread-7] Processing order ORD-99214 amount=4820 currency=INR
2026-01-28T14:03:12.015Z INFO  payment-service [pool-3-thread-7] Opening connection to gateway-adapter at 10.0.3.42:8443
2026-01-28T14:03:42.019Z WARN  payment-service [pool-3-thread-7] Connect attempt 1/3 timed out after 30000ms
2026-01-28T14:04:12.024Z WARN  payment-service [pool-3-thread-7] Connect attempt 2/3 timed out after 30000ms
2026-01-28T14:04:42.031Z WARN  payment-service [pool-3-thread-7] Connect attempt 3/3 timed out after 30000ms
2026-01-28T14:04:42.033Z ERROR payment-service [pool-3-thread-7] All retries exhausted, failing transaction
java.net.SocketTimeoutException: connect timed out
	at java.base/java.net.PlainSocketImpl.socketConnect(Native Method)
	at com.shopflow.payment.GatewayClient.openChannel(GatewayClient.java:143)
	at com.shopflow.payment.GatewayClient.authorize(GatewayClient.java:98)
	at com.shopflow.payment.PaymentProcessor.charge(PaymentProcessor.java:187)
2026-01-28T14:04:42.040Z ERROR payment-service [pool-3-thread-7] ORD-99214 marked PAYMENT_FAILED, customer charged=false
2026-01-28T14:04:43.118Z ERROR payment-service [pool-3-thread-9] ORD-99215 connect timed out, gateway-adapter unreachable
2026-01-28T14:04:44.202Z ERROR payment-service [pool-3-thread-2] ORD-99216 connect timed out, gateway-adapter unreachable
"""

GT["connection_timeout_01"] = {
    "error_type": "ConnectionTimeout",
    "affected_system": "payment-service",
    "severity": "Critical",
    "root_cause": "gateway-adapter at 10.0.3.42:8443 is unreachable; all three retries exhausted and multiple concurrent orders are failing, indicating a full payment outage rather than a single transient failure.",
    "expected_file": "GatewayClient.java",
    "expected_line": 143,
    "environment": "production",
}

LOGS["connection_timeout_02"] = """\
[2026-05-07 02:15:44] INFO  search-indexer: starting incremental reindex, 2400 docs pending
[2026-05-07 02:15:44] INFO  search-indexer: connecting to elasticsearch cluster es-prod-01.internal:9200
[2026-05-07 02:16:14] ERROR search-indexer: reindex aborted
requests.exceptions.ConnectTimeout: HTTPConnectionPool(host='es-prod-01.internal', port=9200): Max retries exceeded with url: /_bulk (Caused by ConnectTimeoutError(<urllib3.connection.HTTPConnection object>, 'Connection to es-prod-01.internal timed out. (connect timeout=30)'))
  File "/opt/indexer/pipeline.py", line 203, in flush_batch
    resp = self.session.post(f"{self.host}/_bulk", data=payload, timeout=30)
  File "/opt/indexer/pipeline.py", line 156, in run
    self.flush_batch(batch)
[2026-05-07 02:16:14] WARN  search-indexer: 2400 docs remain unindexed, search results will be stale
"""

GT["connection_timeout_02"] = {
    "error_type": "ConnectionTimeout",
    "affected_system": "search-indexer",
    "severity": "High",
    "root_cause": "Elasticsearch cluster es-prod-01.internal is not accepting connections on port 9200; the bulk indexing request times out after 30s, leaving 2400 documents unindexed.",
    "expected_file": "pipeline.py",
    "expected_line": 203,
    "environment": "production",
}

LOGS["connection_timeout_03"] = """\
2026-06-11 19:33:02 INFO  report-generator - scheduled export starting for tenant=acme-corp
2026-06-11 19:33:02 INFO  report-generator - fetching metadata from config-service:7070
2026-06-11 19:33:17 WARN  report-generator - config-service slow response, 15021ms elapsed
2026-06-11 19:33:22 ERROR report-generator - read timeout contacting config-service
java.net.SocketTimeoutException: Read timed out
	at com.shopflow.report.ConfigClient.fetchTenantConfig(ConfigClient.java:71)
	at com.shopflow.report.ExportJob.prepare(ExportJob.java:44)
2026-06-11 19:33:22 INFO  report-generator - falling back to cached config from 2026-06-10, export continuing with stale settings
"""

GT["connection_timeout_03"] = {
    "error_type": "ConnectionTimeout",
    "affected_system": "report-generator",
    "severity": "Medium",
    "root_cause": "config-service response exceeded the read timeout; the job degraded gracefully to a cached config from the previous day rather than failing outright.",
    "expected_file": "ConfigClient.java",
    "expected_line": 71,
    "environment": "production",
}

# ─────────────────────────────────────────────────────────────
# TYPE 3 — OutOfMemoryError
# ─────────────────────────────────────────────────────────────

LOGS["memory_exhaustion_01"] = """\
2026-03-30T08:11:20.443Z INFO  export-service [main] Beginning full catalogue export, estimated 1.2M rows
2026-03-30T08:14:55.019Z WARN  export-service [G1 Young Gen] GC pause 2841ms, heap 7.6G/8.0G after collection
2026-03-30T08:15:31.887Z WARN  export-service [G1 Young Gen] GC pause 4102ms, heap 7.9G/8.0G after collection
2026-03-30T08:15:44.220Z ERROR export-service [main] Fatal error, terminating
java.lang.OutOfMemoryError: Java heap space
	at java.base/java.util.Arrays.copyOf(Arrays.java:3512)
	at java.base/java.util.ArrayList.grow(ArrayList.java:237)
	at java.base/java.util.ArrayList.add(ArrayList.java:487)
	at com.shopflow.export.CatalogueExporter.loadAllProducts(CatalogueExporter.java:76)
	at com.shopflow.export.CatalogueExporter.run(CatalogueExporter.java:39)
2026-03-30T08:15:44.502Z ERROR export-service [main] Process exiting with code 137, container OOMKilled
2026-03-30T08:15:47.001Z ERROR api-gateway [health-check] export-service /health unreachable, removing from pool
"""

GT["memory_exhaustion_01"] = {
    "error_type": "OutOfMemoryError",
    "affected_system": "export-service",
    "severity": "Critical",
    "root_cause": "loadAllProducts accumulates all 1.2M product rows into a single in-memory ArrayList instead of streaming or paginating, exhausting the 8G heap and triggering an OOMKill.",
    "expected_file": "CatalogueExporter.java",
    "expected_line": 76,
    "environment": "production",
}

LOGS["memory_exhaustion_02"] = """\
[2026-04-22 13:07:41,332] INFO  ml-inference: loading model artifact recommender_v7.pkl (2.1 GB)
[2026-04-22 13:07:58,914] INFO  ml-inference: model loaded, warming up with 64 sample batches
[2026-04-22 13:08:12,006] WARN  ml-inference: RSS 5.8 GB of 6.0 GB container limit
[2026-04-22 13:08:14,551] ERROR ml-inference: worker crashed
Traceback (most recent call last):
  File "/app/serving/handler.py", line 88, in predict
    features = np.stack([self._embed(r) for r in batch])
  File "/app/serving/handler.py", line 134, in _embed
    return np.zeros((seq_len, 4096), dtype=np.float64)
numpy.core._exceptions.MemoryError: Unable to allocate 3.12 GiB for an array with shape (100000, 4096) and data type float64
[2026-04-22 13:08:14,600] ERROR ml-inference: worker 3 of 4 exited, capacity degraded to 75%
"""

GT["memory_exhaustion_02"] = {
    "error_type": "OutOfMemoryError",
    "affected_system": "ml-inference",
    "severity": "High",
    "root_cause": "_embed allocates a float64 array of shape (100000, 4096) per batch; using float32 or chunking the batch would fit within the 6 GB container limit.",
    "expected_file": "handler.py",
    "expected_line": 134,
    "environment": "production",
}

LOGS["memory_exhaustion_03"] = """\
2026-05-18 10:02:11 INFO  image-thumbnailer - dev worker started, watching queue thumbs.dev
2026-05-18 10:02:33 INFO  image-thumbnailer - processing upload id=8821 dimensions=12000x9000
2026-05-18 10:02:35 ERROR image-thumbnailer - failed to allocate decode buffer
MemoryError: cannot allocate 3.9 GiB for image decode buffer
  File "/work/thumbs/resize.py", line 57, in load_source
    raw = Image.open(path).convert("RGB")
2026-05-18 10:02:35 INFO  image-thumbnailer - job 8821 moved to dead-letter queue, worker recovered
"""

GT["memory_exhaustion_03"] = {
    "error_type": "OutOfMemoryError",
    "affected_system": "image-thumbnailer",
    "severity": "Low",
    "root_cause": "load_source decodes a 12000x9000 source image fully into memory; no dimension guard exists before decode. Occurred in dev and the worker self-recovered.",
    "expected_file": "resize.py",
    "expected_line": 57,
    "environment": "development",
}

# ─────────────────────────────────────────────────────────────
# TYPE 4 — AuthenticationFailure
# ─────────────────────────────────────────────────────────────

LOGS["auth_failure_01"] = """\
2026-02-03T06:00:04.117Z INFO  api-gateway [auth-filter] Validating bearer token for /v2/accounts request_id=REQ-77120
2026-02-03T06:00:04.119Z WARN  api-gateway [auth-filter] JWT signature verification failed, kid=sk-2025-11 not found in JWKS
2026-02-03T06:00:04.121Z ERROR api-gateway [auth-filter] Rejecting request with 401
com.shopflow.auth.TokenValidationException: Unknown signing key id: sk-2025-11
	at com.shopflow.auth.JwksResolver.resolve(JwksResolver.java:64)
	at com.shopflow.auth.TokenValidator.validate(TokenValidator.java:112)
	at com.shopflow.gateway.AuthFilter.doFilter(AuthFilter.java:78)
2026-02-03T06:00:04.140Z ERROR api-gateway [auth-filter] 1204 requests rejected with 401 in the last 60s across all endpoints
2026-02-03T06:00:05.002Z ERROR api-gateway [auth-filter] All authenticated traffic failing, signing key rotation suspected
"""

GT["auth_failure_01"] = {
    "error_type": "AuthenticationFailure",
    "affected_system": "api-gateway",
    "severity": "Critical",
    "root_cause": "The identity provider rotated its signing key to kid sk-2025-11 but the gateway's cached JWKS was not refreshed, so every issued token fails signature verification and all authenticated traffic is rejected.",
    "expected_file": "JwksResolver.java",
    "expected_line": 64,
    "environment": "production",
}

LOGS["auth_failure_02"] = """\
[2026-04-09 21:18:30] INFO  sync-worker: starting nightly CRM sync for 14 tenants
[2026-04-09 21:18:31] INFO  sync-worker: authenticating to partner API as service account svc-sync@shopflow
[2026-04-09 21:18:31] ERROR sync-worker: authentication rejected
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url: https://partner.example.com/api/v3/contacts
  File "/opt/sync/client.py", line 74, in _request
    resp.raise_for_status()
  File "/opt/sync/jobs/crm.py", line 39, in fetch_contacts
    return self.client._request("GET", "/api/v3/contacts")
Response body: {"error":"credential_expired","detail":"API key rotated on 2026-04-08, previous key deactivated"}
[2026-04-09 21:18:31] ERROR sync-worker: sync aborted for all 14 tenants, no records updated
"""

GT["auth_failure_02"] = {
    "error_type": "AuthenticationFailure",
    "affected_system": "sync-worker",
    "severity": "High",
    "root_cause": "The partner API key was rotated on 2026-04-08 but the stored credential for svc-sync@shopflow was never updated, so all 14 tenant syncs fail with 403 credential_expired.",
    "expected_file": "client.py",
    "expected_line": 74,
    "environment": "production",
}

LOGS["auth_failure_03"] = """\
2026-06-25 15:41:09 DEBUG admin-portal - login attempt user=priya.n@shopflow source_ip=10.4.2.88
2026-06-25 15:41:09 WARN  admin-portal - MFA challenge failed, code mismatch attempt 1 of 5
2026-06-25 15:41:24 WARN  admin-portal - MFA challenge failed, code mismatch attempt 2 of 5
2026-06-25 15:41:41 ERROR admin-portal - authentication failed, session not established
AuthenticationError: TOTP verification failed, drift exceeded tolerance window
  File "/srv/portal/auth/mfa.py", line 118, in verify_totp
    raise AuthenticationError("TOTP verification failed, drift exceeded tolerance window")
2026-06-25 15:41:41 INFO  admin-portal - user prompted to re-enroll device, account not locked
"""

GT["auth_failure_03"] = {
    "error_type": "AuthenticationFailure",
    "affected_system": "admin-portal",
    "severity": "Low",
    "root_cause": "A single user's TOTP device clock has drifted beyond the tolerance window in verify_totp; isolated to one account with a self-service re-enrolment path available.",
    "expected_file": "mfa.py",
    "expected_line": 118,
    "environment": "production",
}

# ─────────────────────────────────────────────────────────────
# TYPE 5 — DatabaseDeadlock
# ─────────────────────────────────────────────────────────────

LOGS["db_deadlock_01"] = """\
2026-01-15T12:47:03.220Z INFO  inventory-service [txn-executor-2] Reserving stock for order ORD-51002, 6 line items
2026-01-15T12:47:03.244Z INFO  inventory-service [txn-executor-5] Reserving stock for order ORD-51003, 4 line items
2026-01-15T12:47:53.891Z ERROR inventory-service [txn-executor-2] Transaction rolled back by database
org.postgresql.util.PSQLException: ERROR: deadlock detected
  Detail: Process 41882 waits for ShareLock on transaction 990214; blocked by process 41890.
  Process 41890 waits for ShareLock on transaction 990211; blocked by process 41882.
  Hint: See server log for query details.
	at org.postgresql.core.v3.QueryExecutorImpl.receiveErrorResponse(QueryExecutorImpl.java:2725)
	at com.shopflow.inventory.StockRepository.decrementBatch(StockRepository.java:158)
	at com.shopflow.inventory.ReservationService.reserve(ReservationService.java:91)
2026-01-15T12:47:53.902Z ERROR inventory-service [txn-executor-2] ORD-51002 reservation failed, stock counts may be inconsistent
2026-01-15T12:47:54.118Z ERROR inventory-service [txn-executor-8] deadlock detected, ORD-51007 rolled back
2026-01-15T12:47:55.330Z ERROR inventory-service [txn-executor-3] deadlock detected, ORD-51011 rolled back
"""

GT["db_deadlock_01"] = {
    "error_type": "DatabaseDeadlock",
    "affected_system": "inventory-service",
    "severity": "Critical",
    "root_cause": "decrementBatch updates stock rows in the order line items are supplied rather than a deterministic sorted order, so concurrent reservations acquire row locks in opposite sequences. Multiple orders are now rolling back and stock counts are inconsistent.",
    "expected_file": "StockRepository.java",
    "expected_line": 158,
    "environment": "production",
}

LOGS["db_deadlock_02"] = """\
[2026-03-06 04:22:10,556] INFO  billing-service: running monthly invoice finalisation, 8200 accounts
[2026-03-06 04:22:44,102] WARN  billing-service: lock wait 8.4s on invoices table, account_id=A-3391
[2026-03-06 04:22:51,338] ERROR billing-service: transaction aborted
sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (1213, 'Deadlock found when trying to get lock; try restarting transaction')
[SQL: UPDATE invoices SET status=%s, finalised_at=%s WHERE account_id=%s AND period=%s]
  File "/app/billing/repository.py", line 227, in finalise_invoice
    session.execute(stmt)
  File "/app/billing/tasks/monthly.py", line 95, in run
    self.repo.finalise_invoice(account_id, period)
[2026-03-06 04:22:51,341] WARN  billing-service: retrying transaction for A-3391, attempt 2 of 3
[2026-03-06 04:22:52,880] INFO  billing-service: A-3391 finalised on retry, job continuing
"""

GT["db_deadlock_02"] = {
    "error_type": "DatabaseDeadlock",
    "affected_system": "billing-service",
    "severity": "Medium",
    "root_cause": "Concurrent workers update the invoices table for overlapping account/period ranges, producing MySQL error 1213. The built-in retry succeeded on attempt 2, so the job completed.",
    "expected_file": "repository.py",
    "expected_line": 227,
    "environment": "production",
}

LOGS["db_deadlock_03"] = """\
2026-05-29 16:55:02 INFO  audit-logger - flushing buffered audit events, batch size 500
2026-05-29 16:55:09 ERROR audit-logger - batch insert failed
psycopg2.errors.DeadlockDetected: deadlock detected
DETAIL:  Process 8821 waits for ExclusiveLock on tuple (441,12) of relation 16783 of database 16400; blocked by process 8834.
  File "/srv/audit/writer.py", line 63, in flush
    cur.executemany(INSERT_AUDIT_SQL, rows)
2026-05-29 16:55:09 WARN  audit-logger - batch re-queued, 500 events delayed but not lost
"""

GT["db_deadlock_03"] = {
    "error_type": "DatabaseDeadlock",
    "affected_system": "audit-logger",
    "severity": "Medium",
    "root_cause": "Two audit writer processes contend for the same tuple during batch insert; flush uses executemany without ordering rows by primary key. Events were re-queued rather than lost.",
    "expected_file": "writer.py",
    "expected_line": 63,
    "environment": "production",
}

# ─────────────────────────────────────────────────────────────

def main():
    os.makedirs("data/error_logs", exist_ok=True)

    for name, content in LOGS.items():
        path = f"data/error_logs/{name}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"wrote {path}")

    with open("data/ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(GT, f, indent=2)
    print("wrote data/ground_truth.json")

    # sanity summary
    from collections import Counter
    print("\nerror_type distribution:", dict(Counter(v["error_type"] for v in GT.values())))
    print("severity distribution:  ", dict(Counter(v["severity"] for v in GT.values())))
    print("total logs:", len(LOGS))
    assert len(LOGS) == len(GT) == 15


if __name__ == "__main__":
    main()