// Local dashboard for browsing recorded calls: metadata, transcript,
// recording playback, and flagged bugs. Reads straight off the
// data/calls/<call_id>/ layout that bot/orchestrator.py, bot/server.py,
// and bot/bug_analyzer.py write — no separate database.

import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CALLS_DIR = path.join(__dirname, "..", "data", "calls");
const PORT = process.env.PORT || 4000;

const app = express();
app.use(express.static(path.join(__dirname, "public")));

function readJson(filePath, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return fallback;
  }
}

const SAFE_CALL_ID = /^[a-zA-Z0-9_-]+$/;

function severityRank(severity) {
  return { High: 0, Medium: 1, Low: 2 }[severity] ?? 3;
}

function listCallIds() {
  if (!fs.existsSync(CALLS_DIR)) return [];
  return fs
    .readdirSync(CALLS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()
    .reverse(); // newest-looking (uuid-suffixed) call ids first, good enough locally
}

function callSummary(callId) {
  const dir = path.join(CALLS_DIR, callId);
  const metadata = readJson(path.join(dir, "metadata.json"), {});
  const transcript = readJson(path.join(dir, "transcript.json"));
  const findings = readJson(path.join(dir, "findings.json"), []) || [];

  const maxSeverity = findings.reduce(
    (worst, f) => (severityRank(f.severity) < severityRank(worst) ? f.severity : worst),
    null,
  );

  return {
    call_id: callId,
    scenario_id: metadata.scenario_id || transcript?.scenario_id || "unknown",
    status: metadata.status || "unknown",
    duration_seconds: metadata.duration_seconds ?? null,
    started_at: metadata.started_at ?? null,
    has_recording: fs.existsSync(path.join(dir, "recording.mp3")),
    has_transcript: fs.existsSync(path.join(dir, "transcript.json")),
    turn_count: transcript?.turns?.length ?? 0,
    findings_count: findings.length,
    max_severity: maxSeverity,
  };
}

app.get("/api/calls", (_req, res) => {
  res.json(listCallIds().map(callSummary));
});

app.get("/api/calls/:id", (req, res) => {
  if (!SAFE_CALL_ID.test(req.params.id)) {
    return res.status(400).json({ error: "invalid call id" });
  }
  const dir = path.join(CALLS_DIR, req.params.id);
  if (!fs.existsSync(dir)) {
    return res.status(404).json({ error: "call not found" });
  }
  res.json({
    metadata: readJson(path.join(dir, "metadata.json"), {}),
    transcript: readJson(path.join(dir, "transcript.json"), { turns: [] }),
    findings: readJson(path.join(dir, "findings.json"), []),
  });
});

app.get("/api/calls/:id/recording", (req, res) => {
  if (!SAFE_CALL_ID.test(req.params.id)) {
    return res.status(400).json({ error: "invalid call id" });
  }
  const filePath = path.join(CALLS_DIR, req.params.id, "recording.mp3");
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: "recording not found" });
  }
  res.type("audio/mpeg").sendFile(filePath);
});

app.listen(PORT, () => {
  console.log(`athena-voice-tester dashboard listening on http://localhost:${PORT}`);
  console.log(`Reading calls from ${CALLS_DIR}`);
});
