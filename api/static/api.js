const AGENTS = [
    { key: "error_analyzer",          label: "Error Analyzer",            icon: "🔍" },
    { key: "root_cause_investigator", label: "Root Cause Investigator",   icon: "🔬" },
    { key: "historical_pattern",      label: "Historical Pattern Search", icon: "📚" },
    { key: "fix_suggester",           label: "Fix Suggester",             icon: "🛠" },
    { key: "report_writer",           label: "Report Writer",             icon: "📄" },
];

async function fetchIncidents() {
    const res = await fetch("/api/incidents");
    if (!res.ok) throw new Error("Failed to load incidents");
    return res.json();
}

async function fetchIncident(id) {
    const res = await fetch(`/api/incidents/${id}`);
    if (!res.ok) throw new Error("Incident not found");
    return res.json();
}

async function investigate(rawLog, onEvent) {
    const res = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_log: rawLog }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { job_id } = await res.json();

    return new Promise((resolve, reject) => {
        const source = new EventSource(`/api/investigate/stream/${job_id}`);

        source.addEventListener("pipeline_start", (e) => {
            onEvent("pipeline_start", JSON.parse(e.data));
        });
        source.addEventListener("agent_complete", (e) => {
            onEvent("agent_complete", JSON.parse(e.data));
        });
        source.addEventListener("pipeline_complete", (e) => {
            const data = JSON.parse(e.data);
            onEvent("pipeline_complete", data);
            source.close();
            resolve(data);
        });
        source.addEventListener("pipeline_error", (e) => {
            const data = JSON.parse(e.data);
            onEvent("pipeline_error", data);
            source.close();
            reject(new Error(data.error));
        });
        source.onerror = () => { source.close(); reject(new Error("SSE connection lost")); };
    });
}

function severityBadge(severity) {
    const s = (severity || "medium").toLowerCase();
    return `<span class="badge badge-${s}">${severity || "Unknown"}</span>`;
}

function renderMarkdown(md) {
    if (!md) return "";
    let html = md
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/```[\w]*\n([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/^## (.+)$/gm, "<h2>$1</h2>")
        .replace(/^### (.+)$/gm, "<h3>$1</h3>")
        .replace(/^\* (.+)$/gm, "<li>$1</li>")
        .replace(/^\- (.+)$/gm, "<li>$1</li>")
        .replace(/^\d+\. (.+)$/gm, "<li>$1</li>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n{2,}/g, "</p><p>")
        .replace(/\n/g, "<br>");
    return `<p>${html}</p>`;
}

function timeAgo(timestamp) {
    if (!timestamp) return "";
    const diff = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

const SAMPLE_LOG = `2026-01-28T14:03:12.001Z INFO  payment-service [pool-3-thread-7] Processing order ORD-99214 amount=4820 currency=INR
2026-01-28T14:03:12.015Z INFO  payment-service [pool-3-thread-7] Opening connection to gateway-adapter at 10.0.3.42:8443
2026-01-28T14:03:42.019Z WARN  payment-service [pool-3-thread-7] Connect attempt 1/3 timed out after 30000ms
2026-01-28T14:04:12.024Z WARN  payment-service [pool-3-thread-7] Connect attempt 2/3 timed out after 30000ms
2026-01-28T14:04:42.031Z WARN  payment-service [pool-3-thread-7] Connect attempt 3/3 timed out after 30000ms
2026-01-28T14:04:42.033Z ERROR payment-service [pool-3-thread-7] All retries exhausted, failing transaction
java.net.SocketTimeoutException: connect timed out
\tat java.base/java.net.PlainSocketImpl.socketConnect(Native Method)
\tat com.shopflow.payment.GatewayClient.openChannel(GatewayClient.java:143)
\tat com.shopflow.payment.GatewayClient.authorize(GatewayClient.java:98)
\tat com.shopflow.payment.PaymentProcessor.charge(PaymentProcessor.java:187)
2026-01-28T14:04:42.040Z ERROR payment-service [pool-3-thread-7] ORD-99214 marked PAYMENT_FAILED, customer charged=false`;