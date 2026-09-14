/* Agent Control Plane — read-only status dashboard.
 * The API key is requested once via prompt() and kept in sessionStorage
 * (tab lifetime only). It is never written to disk, localStorage, or logs.
 */
(function () {
  "use strict";

  var API = "/api/v1"; // served by the API at /dashboard -> proxies same-origin
  var keyInput = document.getElementById("apiKey");
  var tenantInput = document.getElementById("tenant");
  var statusEl = document.getElementById("status");
  var errEl = document.getElementById("err");

  function key() { return sessionStorage.getItem("acp_api_key") || ""; }
  function tenant() { return tenantInput.value.trim() || "default"; }

  function headers() {
    return {
      "Authorization": "Bearer " + key(),
      "X-Tenant-ID": tenant(),
      "Content-Type": "application/json"
    };
  }

  function fail(msg) {
    errEl.textContent = msg;
    statusEl.textContent = "error";
    statusEl.className = "bad";
  }

  async function api(path, opts) {
    var res = await fetch(API + path, Object.assign({ headers: headers() }, opts || {}));
    if (!res.ok) throw new Error("HTTP " + res.status + " on " + path + ": " + (await res.text()));
    return res.json();
  }

  function row(tableId, cells) {
    var tr = document.createElement("tr");
    cells.forEach(function (c) {
      var td = document.createElement("td");
      if (typeof c === "string" || typeof c === "number") td.textContent = c;
      else td.appendChild(c);
      tr.appendChild(td);
    });
    document.querySelector("#" + tableId + " tbody").appendChild(tr);
  }

  function pill(text, cls) {
    var s = document.createElement("span");
    s.className = "pill " + (cls || "");
    s.textContent = text;
    return s;
  }

  function statusPill(s) {
    var cls = "muted";
    if (/active|completed|approved/i.test(s)) cls = "ok";
    else if (/awaiting|requested|pending|quarantined/i.test(s)) cls = "warn";
    else if (/failed|denied|rejected|revoked/i.test(s)) cls = "bad";
    return pill(s, cls);
  }

  function actionBtn(label, cls, fn) {
    var b = document.createElement("button");
    b.className = cls;
    b.textContent = label;
    b.onclick = fn;
    return b;
  }

  async function decideApproval(id, decision) {
    try {
      await api("/approvals/" + id + "/" + decision, { method: "POST" });
      await refresh();
    } catch (e) { fail(String(e)); }
  }

  async function loadAgents() {
    var data = await api("/agents");
    var list = data.items || data.agents || data || [];
    list.forEach(function (a) {
      row("agents", [
        a.name || a.id,
        a.version || (a.current_version && a.current_version.version) || "—",
        statusPill(a.status || "unknown"),
        (a.capabilities || []).join(", ")
      ]);
    });
  }

  async function loadTasks() {
    var data = await api("/tasks");
    var list = data.items || data.tasks || data || [];
    list.slice(0, 25).forEach(function (t) {
      row("tasks", [
        String(t.id).slice(0, 8) + "…",
        (t.goal || "").slice(0, 80),
        t.agent_name || t.agent_id || "—",
        statusPill(t.status || "unknown")
      ]);
    });
  }

  async function loadApprovals() {
    var data = await api("/approvals?status=requested");
    var list = data.items || data.approvals || data || [];
    list.forEach(function (a) {
      var cell = document.createElement("span");
      cell.appendChild(actionBtn("Approve", "approve", function () {
        decideApproval(a.id, "approve");
      }));
      cell.appendChild(document.createTextNode(" "));
      cell.appendChild(actionBtn("Reject", "reject", function () {
        decideApproval(a.id, "reject");
      }));
      row("approvals", [
        String(a.id).slice(0, 8) + "…",
        String(a.task_id || "—").slice(0, 8) + "…",
        (a.action_summary || "").slice(0, 80),
        pill((a.risk_level || "?") + " (" + (a.risk_score != null ? a.risk_score : "?") + ")",
             /high|critical/i.test(a.risk_level || "") ? "bad" : "warn"),
        cell
      ]);
    });
  }

  async function loadAudit() {
    var data = await api("/audit?limit=25");
    var list = data.items || data.events || data || [];
    list.forEach(function (e) {
      row("audit", [
        e.seq != null ? e.seq : "—",
        e.event_type || e.type || "—",
        (e.actor && (e.actor.name || e.actor.id)) || "—",
        e.timestamp || e.created_at || "—"
      ]);
    });
  }

  function clearTables() {
    ["agents", "tasks", "approvals", "audit"].forEach(function (t) {
      document.querySelector("#" + t + " tbody").innerHTML = "";
    });
  }

  async function refresh() {
    errEl.textContent = "";
    if (!key()) { fail("No API key set — click Connect and enter one."); return; }
    clearTables();
    statusEl.textContent = "loading…";
    statusEl.className = "muted";
    try {
      await loadAgents();
      await loadTasks();
      await loadApprovals();
      await loadAudit();
      statusEl.textContent = "connected · tenant " + tenant();
      statusEl.className = "ok";
    } catch (e) { fail(String(e)); }
  }

  document.getElementById("connect").onclick = function () {
    var k = keyInput.value.trim();
    if (!k) {
      k = prompt("Enter your ACP API key (kept in sessionStorage for this tab only):") || "";
    }
    if (!k) { fail("No API key provided."); return; }
    sessionStorage.setItem("acp_api_key", k);
    keyInput.value = "";
    refresh();
  };

  // Auto-refresh every 15s once connected.
  setInterval(function () { if (key()) refresh(); }, 15000);
})();
