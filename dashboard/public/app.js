const listEl = document.getElementById("call-list");
const detailEl = document.getElementById("call-detail");

let activeCallId = null;

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function prettyScenario(id) {
  return String(id ?? "unknown")
    .replace(/^edge_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDuration(seconds) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

async function loadCalls() {
  const res = await fetch("/api/calls");
  const calls = await res.json();

  if (calls.length === 0) {
    listEl.innerHTML = `<div class="empty-state">No calls yet.<br><br>Run <code>python -m bot.cli call --scenario &lt;id&gt;</code> to place one.</div>`;
    return;
  }

  listEl.innerHTML = "";
  for (const call of calls) {
    const card = document.createElement("button");
    card.className = "call-card";
    card.dataset.callId = call.call_id;
    card.innerHTML = `
      <div class="scenario">${escapeHtml(prettyScenario(call.scenario_id))}</div>
      <div class="meta-row">
        <span class="badge status-${escapeHtml(call.status)}">${escapeHtml(call.status)}</span>
        ${call.max_severity ? `<span class="badge severity-${escapeHtml(call.max_severity)}">${escapeHtml(call.max_severity)}</span>` : ""}
        <span>${formatDuration(call.duration_seconds)}</span>
        <span>${call.turn_count} turns</span>
      </div>
    `;
    card.addEventListener("click", () => selectCall(call.call_id));
    listEl.appendChild(card);
  }

  if (activeCallId && calls.some((c) => c.call_id === activeCallId)) {
    selectCall(activeCallId);
  }
}

function renderTranscript(turns) {
  if (!turns || turns.length === 0) {
    return `<div class="empty-state">No transcript captured for this call.</div>`;
  }
  return `<div class="transcript">${turns
    .map((t) => {
      const speakerClass = t.speaker === "patient_bot" ? "patient_bot" : "athena_agent";
      const label = t.speaker === "patient_bot" ? "Patient (bot)" : "Athena (agent)";
      return `<div class="turn ${speakerClass}">
        <span class="speaker-label">${label}</span>
        ${escapeHtml(t.text)}
      </div>`;
    })
    .join("")}</div>`;
}

function renderFindings(findings) {
  if (!findings || findings.length === 0) {
    return `<div class="empty-state">No bugs flagged for this call.</div>`;
  }
  const order = { High: 0, Medium: 1, Low: 2 };
  const sorted = [...findings].sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3));
  return `<div class="findings-list">${sorted
    .map(
      (f) => `
      <div class="finding">
        <div class="finding-title">
          <span class="badge severity-${escapeHtml(f.severity)}">${escapeHtml(f.severity)}</span>
          ${escapeHtml(f.summary)}
        </div>
        <div class="detail-text">${escapeHtml(f.detail)}</div>
        ${f.quoted_turn ? `<div class="quote">"${escapeHtml(f.quoted_turn)}"</div>` : ""}
      </div>`,
    )
    .join("")}</div>`;
}

async function selectCall(callId) {
  activeCallId = callId;
  document.querySelectorAll(".call-card").forEach((el) => {
    el.classList.toggle("active", el.dataset.callId === callId);
  });

  detailEl.innerHTML = `<div class="loading">Loading…</div>`;
  const res = await fetch(`/api/calls/${encodeURIComponent(callId)}`);
  if (!res.ok) {
    detailEl.innerHTML = `<div class="empty-state">Could not load this call.</div>`;
    return;
  }
  const { metadata, transcript, findings } = await res.json();

  detailEl.innerHTML = `
    <div class="detail-header">
      <h2>${escapeHtml(prettyScenario(metadata.scenario_id ?? transcript.scenario_id))}</h2>
      <div class="meta-row">
        call_id: ${escapeHtml(callId)} &nbsp;·&nbsp;
        status: ${escapeHtml(metadata.status ?? "unknown")} &nbsp;·&nbsp;
        duration: ${formatDuration(metadata.duration_seconds)}
      </div>
    </div>
    <audio controls src="/api/calls/${encodeURIComponent(callId)}/recording"></audio>
    <div class="section-title">Findings</div>
    ${renderFindings(findings)}
    <div class="section-title">Transcript</div>
    ${renderTranscript(transcript.turns)}
  `;

  const audioEl = detailEl.querySelector("audio");
  audioEl.addEventListener("error", () => {
    audioEl.outerHTML = `<div class="empty-state">No recording available for this call.</div>`;
  });
}

loadCalls();
setInterval(loadCalls, 15000);
