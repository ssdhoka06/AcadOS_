import { useState, useEffect, useRef, useCallback } from "react";

// ─── COLOUR CONSTANTS ───────────────────────────────────────────────────────
const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  surfaceAlt: "#1a1a26",
  border: "#2a2a3a",
  text: "#e0dff0",
  textMuted: "#7a7a9a",
  accent: "#7c5cfc",
  exam: "#ff4d6a",
  evaluation: "#ff8c42",
  research: "#ffd166",
  practice: "#06d6a0",
  green: "#06d6a0",
  red: "#ff4d6a",
  orange: "#ff8c42",
  yellow: "#ffd166",
  blue: "#4ea8de",
};

const JOB_COLORS = { EXAM: C.exam, EVALUATION: C.evaluation, RESEARCH: C.research, PRACTICE: C.practice };

// Aligned with Shakti's shared.py State enum
const STATE_COLORS = {
  NEW: C.blue,
  READY: C.green,
  RUNNING: C.accent,
  BLOCKED: C.orange,
  EXIT: C.textMuted,
  THROTTLED: "#ff0055",
  SUSPENDED_READY: C.yellow,
  SUSPENDED_BLOCKED: "#cc8800",
};

// ─── DEMO DATA ──────────────────────────────────────────────────────────────
const DEMO_JOBS = [
  { pid: 1, user_id: 101, role: "STUDENT", job_type: "EXAM", state: "RUNNING", urgency_score: 0.0133, cpu_used: 12, abuse_flag: false, cpu_budget_ns: 100 },
  { pid: 2, user_id: 102, role: "STUDENT", job_type: "PRACTICE", state: "READY", urgency_score: 0.0001, cpu_used: 3, abuse_flag: false, cpu_budget_ns: 100 },
  { pid: 3, user_id: 201, role: "RESEARCHER", job_type: "RESEARCH", state: "READY", urgency_score: 0.0011, cpu_used: 7, abuse_flag: false, cpu_budget_ns: 100 },
  { pid: 4, user_id: 103, role: "STUDENT", job_type: "PRACTICE", state: "THROTTLED", urgency_score: 0.0001, cpu_used: 45, abuse_flag: true, cpu_budget_ns: 50 },
  { pid: 5, user_id: 301, role: "FACULTY", job_type: "EVALUATION", state: "BLOCKED", urgency_score: 0.025, cpu_used: 9, abuse_flag: false, cpu_budget_ns: 100 },
];

const generateDemoTimeline = () => {
  const tl = [];
  const schedule = [
    ...Array(8).fill([1, "EXAM"]),
    ...Array(4).fill([5, "EVALUATION"]),
    ...Array(3).fill([3, "RESEARCH"]),
    ...Array(5).fill([2, "PRACTICE"]),
    ...Array(5).fill([3, "RESEARCH"]),
    ...Array(5).fill([4, "PRACTICE"]),
    ...Array(5).fill([2, "PRACTICE"]),
    ...Array(5).fill([5, "EVALUATION"]),
    ...Array(5).fill([3, "RESEARCH"]),
    ...Array(5).fill([4, "PRACTICE"]),
  ];
  for (let t = 0; t < 50; t++) {
    const [pid, jt] = schedule[t] || [2, "PRACTICE"];
    tl.push([pid, jt, t]);
  }
  return tl;
};

// ─── COMPONENTS ─────────────────────────────────────────────────────────────

const mono = "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace";

const Pill = ({ label, color }) => (
  <span style={{
    display: "inline-block", padding: "2px 10px", borderRadius: 99,
    fontSize: 10, fontWeight: 700, fontFamily: mono, letterSpacing: "0.06em",
    color, background: color + "18", border: `1px solid ${color}40`,
  }}>{label}</span>
);

const Panel = ({ title, icon, children, span = 1 }) => (
  <div style={{
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12,
    gridColumn: span > 1 ? `span ${span}` : undefined,
    display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0,
  }}>
    <div style={{
      padding: "14px 18px", borderBottom: `1px solid ${C.border}`,
      display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
    }}>
      <span style={{ fontSize: 16 }}>{icon}</span>
      <span style={{ color: C.text, fontWeight: 700, fontSize: 13, letterSpacing: "0.04em", textTransform: "uppercase", fontFamily: mono }}>{title}</span>
    </div>
    <div style={{ padding: 16, flex: 1, minHeight: 0, overflow: "auto" }}>{children}</div>
  </div>
);

// ─── GANTT CHART ────────────────────────────────────────────────────────────
const GanttChart = ({ timeline }) => {
  if (!timeline.length) return <div style={{ color: C.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>No timeline data yet.</div>;

  const pids = [...new Set(timeline.filter(t => t[0] !== -1).map(t => t[0]))].sort((a, b) => a - b);
  const maxTick = Math.max(...timeline.map(t => t[2])) + 1;
  const cellW = Math.max(10, Math.min(18, 680 / maxTick));

  return (
    <div style={{ overflowX: "auto", overflowY: "auto", maxHeight: 280 }}>
      {pids.map(pid => {
        const entries = timeline.filter(t => t[0] === pid);
        const jobType = entries[0]?.[1] || "PRACTICE";
        const color = JOB_COLORS[jobType] || C.textMuted;
        const tickSet = new Set(entries.map(e => e[2]));
        return (
          <div key={pid} style={{ display: "flex", alignItems: "center", marginBottom: 4, gap: 8 }}>
            <span style={{ color: C.text, fontSize: 11, fontFamily: mono, width: 60, flexShrink: 0, textAlign: "right" }}>PID {pid}</span>
            <div style={{ display: "flex", gap: 1 }}>
              {Array.from({ length: maxTick }, (_, t) => (
                <div key={t} title={`Tick ${t}`} style={{
                  width: cellW, height: 22, borderRadius: 3,
                  background: tickSet.has(t) ? color + "cc" : C.surfaceAlt,
                  border: tickSet.has(t) ? `1px solid ${color}` : `1px solid ${C.border}40`,
                }} />
              ))}
            </div>
            <Pill label={jobType} color={color} />
          </div>
        );
      })}
      <div style={{ display: "flex", alignItems: "center", marginTop: 8, gap: 8 }}>
        <span style={{ width: 60, flexShrink: 0 }} />
        <div style={{ display: "flex", gap: 1 }}>
          {Array.from({ length: maxTick }, (_, t) => (
            t % 5 === 0
              ? <span key={t} style={{ width: cellW, fontSize: 8, color: C.textMuted, textAlign: "center", fontFamily: "monospace" }}>{t}</span>
              : <span key={t} style={{ width: cellW }} />
          ))}
        </div>
      </div>
    </div>
  );
};

// ─── PROCESS TABLE ──────────────────────────────────────────────────────────
const ProcessTable = ({ jobs }) => {
  if (!jobs.length) return <div style={{ color: C.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>No processes.</div>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: mono }}>
        <thead>
          <tr>
            {["PID", "Role", "Job Type", "State", "Urgency", "CPU", "Abuse"].map(c => (
              <th key={c} style={{ padding: "8px 10px", textAlign: "left", color: C.textMuted, borderBottom: `2px solid ${C.border}`, fontWeight: 600, fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.pid} style={{ background: j.state === "THROTTLED" ? "#ff005510" : "transparent" }}>
              <td style={{ padding: "7px 10px", color: C.text, borderBottom: `1px solid ${C.border}40` }}>{j.pid}</td>
              <td style={{ padding: "7px 10px", color: C.text, borderBottom: `1px solid ${C.border}40` }}>{j.role}</td>
              <td style={{ padding: "7px 10px", borderBottom: `1px solid ${C.border}40` }}><Pill label={j.job_type} color={JOB_COLORS[j.job_type] || C.textMuted} /></td>
              <td style={{ padding: "7px 10px", borderBottom: `1px solid ${C.border}40` }}><Pill label={j.state} color={STATE_COLORS[j.state] || C.textMuted} /></td>
              <td style={{ padding: "7px 10px", color: C.yellow, borderBottom: `1px solid ${C.border}40` }}>{(j.urgency_score ?? j.urgency ?? 0).toFixed(4)}</td>
              <td style={{ padding: "7px 10px", color: C.text, borderBottom: `1px solid ${C.border}40` }}>{j.cpu_used}</td>
              <td style={{ padding: "7px 10px", borderBottom: `1px solid ${C.border}40` }}>{j.abuse_flag ? <span style={{ color: C.red, fontWeight: 700 }}>YES</span> : <span style={{ color: C.green }}>NO</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ─── MEMORY PANEL ───────────────────────────────────────────────────────────
const MemoryPanel = ({ status }) => {
  const used = status.total_frames - status.free_frames;
  const pct = (used / status.total_frames) * 100;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ color: C.textMuted, fontSize: 11 }}>Frames: {used}/{status.total_frames}</span>
        <span style={{ color: pct > 80 ? C.red : pct > 50 ? C.yellow : C.green, fontSize: 11, fontWeight: 700 }}>{pct.toFixed(0)}% used</span>
      </div>
      <div style={{ height: 10, background: C.surfaceAlt, borderRadius: 99, overflow: "hidden", marginBottom: 16 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${C.green}, ${pct > 80 ? C.red : C.accent})`, borderRadius: 99, transition: "width 0.5s" }} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 4, marginBottom: 16 }}>
        {Array.from({ length: status.total_frames }, (_, i) => (
          <div key={i} style={{
            aspectRatio: "1", borderRadius: 4,
            background: i < used ? C.accent + "60" : C.surfaceAlt,
            border: `1px solid ${i < used ? C.accent + "40" : C.border}40`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 8, color: C.textMuted, fontFamily: "monospace",
          }}>{i}</div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 11 }}>
        <span style={{ color: C.textMuted }}>TLB Size: <span style={{ color: C.green }}>{status.tlb_hits ?? 0}</span></span>
        <span style={{ color: C.textMuted }}>Faults: <span style={{ color: C.red }}>{status.tlb_misses ?? 0}</span></span>
      </div>
      <div style={{ marginTop: 12, fontSize: 11, color: C.textMuted, display: "flex", gap: 12, flexWrap: "wrap" }}>
        {Object.entries(status.page_faults || {}).map(([k, v]) => (
          <span key={k}><Pill label={k} color={JOB_COLORS[k] || C.textMuted} /> {v}</span>
        ))}
      </div>
    </div>
  );
};

// ─── DEADLOCK / BANKER'S PANEL ──────────────────────────────────────────────
const DeadlockPanel = ({ status }) => (
  <div>
    <div style={{
      display: "flex", alignItems: "center", gap: 12, marginBottom: 16, padding: "12px 16px", borderRadius: 8,
      background: status.safe_state ? C.green + "10" : C.red + "15",
      border: `1px solid ${status.safe_state ? C.green : C.red}30`,
    }}>
      <span style={{ fontSize: 22 }}>{status.safe_state ? "\u{1F6E1}\u{FE0F}" : "\u{26A0}\u{FE0F}"}</span>
      <div>
        <div style={{ color: status.safe_state ? C.green : C.red, fontWeight: 700, fontSize: 14 }}>
          {status.safe_state ? "SAFE STATE" : "UNSAFE \u2014 DEADLOCK RISK"}
        </div>
        <div style={{ color: C.textMuted, fontSize: 11, marginTop: 2 }}>Banker's Algorithm (Nikhil)</div>
      </div>
    </div>
    <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>Available Resources</div>
    <div style={{ display: "flex", gap: 12 }}>
      {Object.entries(status.available || {}).map(([res, val]) => (
        <div key={res} style={{
          flex: 1, padding: "12px 14px", borderRadius: 8,
          background: C.surfaceAlt, border: `1px solid ${C.border}`, textAlign: "center",
        }}>
          <div style={{ color: C.text, fontWeight: 700, fontSize: 20, fontFamily: mono }}>{val}</div>
          <div style={{ color: C.textMuted, fontSize: 10, marginTop: 4, letterSpacing: "0.06em" }}>{res}</div>
        </div>
      ))}
    </div>
    {status.allocation_count != null && (
      <div style={{ marginTop: 12, fontSize: 11, color: C.textMuted }}>
        Active allocations: <span style={{ color: C.accent }}>{status.allocation_count}</span>
      </div>
    )}
  </div>
);

// ─── DISK SEEKS ─────────────────────────────────────────────────────────────
const DiskSeeksPanel = ({ data }) => {
  if (!data.cscan_order?.length) return <div style={{ color: C.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>No disk data.</div>;
  const max = Math.max(...data.cscan_order, ...data.sstf_order, 200);
  const renderLine = (order, color, label) => (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 11, color, fontWeight: 600, marginBottom: 6, fontFamily: "monospace" }}>{label}</div>
      <svg viewBox={`0 0 ${order.length * 40 + 20} 60`} style={{ width: "100%", height: 50 }}>
        {order.map((cyl, i) => {
          if (i === 0) return null;
          return <line key={i} x1={(i-1)*40+20} y1={5+(order[i-1]/max)*45} x2={i*40+20} y2={5+(cyl/max)*45} stroke={color} strokeWidth="2" strokeLinecap="round" />;
        })}
        {order.map((cyl, i) => (
          <g key={i}>
            <circle cx={i*40+20} cy={5+(cyl/max)*45} r="4" fill={color} />
            <text x={i*40+20} y={5+(cyl/max)*45-8} textAnchor="middle" fontSize="8" fill={C.textMuted}>{cyl}</text>
          </g>
        ))}
      </svg>
    </div>
  );
  return (
    <div>
      <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 8 }}>Head: <span style={{ color: C.accent }}>{data.head}</span> {data.note && <span style={{ color: C.yellow }}> (stub)</span>}</div>
      {renderLine(data.cscan_order, C.blue, "C-SCAN (Sanat)")}
      {renderLine(data.sstf_order, C.orange, "SSTF (Sanat)")}
    </div>
  );
};

// ─── TERMINAL ───────────────────────────────────────────────────────────────
const TerminalPanel = ({ lines }) => {
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [lines]);
  return (
    <div style={{
      background: "#0d0d11", borderRadius: 8, padding: 12, fontFamily: mono,
      fontSize: 11, lineHeight: 1.6, maxHeight: 220, overflowY: "auto", border: `1px solid ${C.border}`,
    }}>
      <div style={{ color: C.green, marginBottom: 4 }}>AcadOS Terminal v0.2</div>
      <div style={{ color: C.textMuted, marginBottom: 8 }}>{"\u2500".repeat(40)}</div>
      {lines.map((line, i) => {
        let color = C.text;
        if (line.includes("THROTTLED") || line.includes("ABUSE")) color = C.red;
        else if (line.includes("EXAM") || line.includes("preempt")) color = C.exam;
        else if (line.includes("PRACTICE")) color = C.practice;
        else if (line.includes("RESEARCH")) color = C.research;
        else if (line.includes("[INFO]")) color = C.blue;
        else if (line.includes("[WARN]")) color = C.yellow;
        else if (line.includes("[ERROR]")) color = C.red;
        return <div key={i} style={{ color }}>{line}</div>;
      })}
      {!lines.length && <div style={{ color: C.textMuted }}>Waiting for simulation...</div>}
      <div ref={endRef} />
    </div>
  );
};

// ─── DB LOGS ────────────────────────────────────────────────────────────────
const DbLogsPanel = ({ logs }) => (
  <div style={{ fontSize: 11, fontFamily: mono }}>
    {!logs.length && <div style={{ color: C.textMuted, textAlign: "center", padding: 12 }}>acados.db empty</div>}
    {logs.map((log, i) => (
      <div key={i} style={{ padding: "6px 0", borderBottom: `1px solid ${C.border}30`, display: "flex", gap: 12, color: C.text }}>
        <span style={{ color: C.accent }}>PID {log.pid}</span>
        <Pill label={log.job_type} color={JOB_COLORS[log.job_type] || C.textMuted} />
        <span style={{ color: C.textMuted }}>{log.role}</span>
        <span style={{ marginLeft: "auto", color: C.yellow }}>CPU: {log.cpu_used}</span>
      </div>
    ))}
  </div>
);

// ─── JOB FORM ───────────────────────────────────────────────────────────────
const JobForm = ({ onSubmit }) => {
  const [form, setForm] = useState({ pid: "1", user_id: "", role: "1", job_type: "3", deadline_offset: "3600" });
  const handleSubmit = () => {
    if (!form.pid) return;
    onSubmit({
      pid: parseInt(form.pid),
      user_id: parseInt(form.user_id) || parseInt(form.pid) * 100,
      role: parseInt(form.role),
      job_type: parseInt(form.job_type),
      deadline_offset: parseFloat(form.deadline_offset),
      cpu_budget_ns: 100,
    });
    setForm(f => ({ ...f, pid: String(parseInt(f.pid) + 1) }));
  };
  const stl = {
    background: C.surfaceAlt, border: `1px solid ${C.border}`, borderRadius: 6,
    padding: "7px 10px", color: C.text, fontSize: 12, fontFamily: mono, outline: "none", width: "100%",
  };
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
      <div style={{ flex: "0 0 70px" }}>
        <label style={{ fontSize: 10, color: C.textMuted, display: "block", marginBottom: 3 }}>PID</label>
        <input style={stl} value={form.pid} onChange={e => setForm(f => ({ ...f, pid: e.target.value }))} />
      </div>
      <div style={{ flex: "0 0 110px" }}>
        <label style={{ fontSize: 10, color: C.textMuted, display: "block", marginBottom: 3 }}>Role</label>
        <select style={{ ...stl, appearance: "none" }} value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
          <option value="1">STUDENT</option><option value="2">RESEARCHER</option><option value="3">FACULTY</option>
        </select>
      </div>
      <div style={{ flex: "0 0 120px" }}>
        <label style={{ fontSize: 10, color: C.textMuted, display: "block", marginBottom: 3 }}>Job Type</label>
        <select style={{ ...stl, appearance: "none" }} value={form.job_type} onChange={e => setForm(f => ({ ...f, job_type: e.target.value }))}>
          <option value="1">PRACTICE</option><option value="2">RESEARCH</option><option value="3">EXAM</option><option value="4">EVALUATION</option>
        </select>
      </div>
      <div style={{ flex: "0 0 90px" }}>
        <label style={{ fontSize: 10, color: C.textMuted, display: "block", marginBottom: 3 }}>Deadline (s)</label>
        <input style={stl} value={form.deadline_offset} onChange={e => setForm(f => ({ ...f, deadline_offset: e.target.value }))} />
      </div>
      <button onClick={handleSubmit} style={{
        background: `linear-gradient(135deg, ${C.accent}, ${C.blue})`, color: "#fff", border: "none",
        borderRadius: 6, padding: "8px 18px", fontSize: 12, fontWeight: 700, cursor: "pointer", fontFamily: mono,
      }}>+ SUBMIT</button>
    </div>
  );
};

// ─── STATUS BAR ─────────────────────────────────────────────────────────────
const StatusBar = ({ tick, running, jobCount, onTick, onRun, onReset, demoMode, onToggleDemo }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 16, padding: "12px 20px",
    background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, flexWrap: "wrap",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: running ? C.green : C.textMuted, boxShadow: running ? `0 0 8px ${C.green}` : "none" }} />
      <span style={{ color: C.text, fontSize: 13, fontWeight: 700, fontFamily: mono }}>TICK {tick}</span>
    </div>
    <span style={{ color: C.textMuted, fontSize: 11 }}>{jobCount} processes</span>
    <div style={{ flex: 1 }} />
    <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 11, color: C.textMuted }}>
      <input type="checkbox" checked={demoMode} onChange={onToggleDemo} style={{ accentColor: C.accent }} />
      Demo Mode
    </label>
    <button onClick={onTick} disabled={running} style={{
      background: C.surfaceAlt, color: C.text, border: `1px solid ${C.border}`, borderRadius: 6,
      padding: "6px 14px", fontSize: 11, cursor: "pointer", fontFamily: mono, opacity: running ? 0.5 : 1,
    }}>&#9654; TICK</button>
    <button onClick={onRun} style={{
      background: running ? C.red + "30" : C.green + "20", color: running ? C.red : C.green,
      border: `1px solid ${running ? C.red : C.green}40`, borderRadius: 6, padding: "6px 14px",
      fontSize: 11, cursor: "pointer", fontFamily: mono, fontWeight: 700,
    }}>{running ? "\u23F9 STOP" : "\u23E9 RUN 50"}</button>
    <button onClick={onReset} style={{
      background: C.surfaceAlt, color: C.textMuted, border: `1px solid ${C.border}`, borderRadius: 6,
      padding: "6px 14px", fontSize: 11, cursor: "pointer", fontFamily: mono,
    }}>{"\u21BA"} RESET</button>
  </div>
);

// ─── MAIN APP ───────────────────────────────────────────────────────────────
export default function AcadOSDashboard() {
  const [tick, setTick] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [termLines, setTermLines] = useState([]);
  const [demoMode, setDemoMode] = useState(true);
  const [memStatus, setMemStatus] = useState({ total_frames: 32, free_frames: 32, page_faults: {}, tlb_hits: 0, tlb_misses: 0 });
  const [dlStatus, setDlStatus] = useState({ available: { CPU: 4, MEM_BLOCK: 8 }, safe_state: true });
  const [diskData, setDiskData] = useState({ cscan_order: [], sstf_order: [], head: 50 });
  const [dbLogs, setDbLogs] = useState([]);

  const apiBase = "http://localhost:8000";
  const apiFetch = async (path, opts = {}) => {
    const res = await fetch(`${apiBase}${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
    return res.json();
  };

  useEffect(() => {
    if (demoMode) {
      setJobs(DEMO_JOBS);
      setTimeline(generateDemoTimeline());
      setTick(50);
      setTermLines([
        "[INFO] AcadOS simulation started",
        "[INFO] 5 jobs submitted \u2014 EXAM\u00d71 EVAL\u00d71 RESEARCH\u00d71 PRACTICE\u00d72",
        "[TICK 00] PID 1 (EXAM)       \u2192 RUNNING   urgency=0.0133",
        "[TICK 05] Aging: Tier-2 RESEARCH jobs boosted +0.1",
        "[TICK 08] PID 5 (EVALUATION) \u2192 RUNNING   preempted PID 1 \u2192 READY",
        "[TICK 12] PID 3 (RESEARCH)   \u2192 RUNNING",
        "[TICK 15] PID 2 (PRACTICE)   \u2192 RUNNING",
        "[WARN] PID 4 cpu_used=45 > 2\u00d7budget \u2014 ABUSE DETECTED",
        "[TICK 20] PID 4 (PRACTICE)   \u2192 THROTTLED  abuse_flag=True",
        "[INFO] Note: Preempted jobs go RUNNING\u2192READY (no PREEMPTED state)",
        "[INFO] Simulation complete \u2014 50 ticks",
      ]);
      setMemStatus({ total_frames: 32, free_frames: 12, page_faults: { EXAM: 2, RESEARCH: 5, PRACTICE: 14 }, tlb_hits: 38, tlb_misses: 12 });
      setDlStatus({ available: { CPU: 2, MEM_BLOCK: 4 }, safe_state: true, allocation_count: 5 });
      setDiskData({ cscan_order: [62, 64, 66, 95, 119, 123, 180, 11, 34], sstf_order: [62, 64, 66, 34, 11, 95, 119, 123, 180], head: 50, note: "Stub" });
      setDbLogs(DEMO_JOBS.map(j => ({ pid: j.pid, job_type: j.job_type, role: j.role, cpu_used: j.cpu_used })));
    }
  }, [demoMode]);

  const addLine = useCallback((l) => setTermLines(p => [...p.slice(-100), l]), []);

  const handleSubmitJob = useCallback(async (jobData) => {
    if (demoMode) {
      const roles = { 1: "STUDENT", 2: "RESEARCHER", 3: "FACULTY" };
      const types = { 1: "PRACTICE", 2: "RESEARCH", 3: "EXAM", 4: "EVALUATION" };
      setJobs(p => [...p, { pid: jobData.pid, user_id: jobData.user_id, role: roles[jobData.role], job_type: types[jobData.job_type], state: "READY", urgency_score: 0.001, cpu_used: 0, abuse_flag: false, cpu_budget_ns: 100 }]);
      addLine(`[INFO] Job PID=${jobData.pid} (${types[jobData.job_type]}) submitted \u2192 READY`);
      return;
    }
    try {
      const res = await apiFetch("/jobs", { method: "POST", body: JSON.stringify(jobData) });
      addLine(`[INFO] ${res.message}`);
      const [updated, mem, dl] = await Promise.all([apiFetch("/jobs"), apiFetch("/memory/status"), apiFetch("/deadlock/status")]);
      setJobs(updated); setMemStatus(mem); setDlStatus(dl);
    } catch (e) { addLine(`[ERROR] ${e.message}`); }
  }, [demoMode, addLine]);

  const handleTick = useCallback(async () => {
    if (demoMode) { setTick(t => t + 1); addLine(`[TICK ${tick}] Demo tick`); return; }
    try {
      const res = await apiFetch("/scheduler/tick");
      setTick(res.tick + 1);
      addLine(`[TICK ${String(res.tick).padStart(2, '0')}] ${res.running_pid ? `PID ${res.running_pid} (${res.running_job_type}) \u2192 RUNNING` : 'IDLE'}${res.preempted_pid ? ` preempted PID ${res.preempted_pid} \u2192 READY` : ''}`);
      const [tl, updated, mem, dl] = await Promise.all([apiFetch("/timeline"), apiFetch("/jobs"), apiFetch("/memory/status"), apiFetch("/deadlock/status")]);
      setTimeline(tl); setJobs(updated); setMemStatus(mem); setDlStatus(dl);
    } catch (e) { addLine(`[ERROR] ${e.message}`); }
  }, [demoMode, tick, addLine]);

  const handleRun = useCallback(async () => {
    if (isRunning) { setIsRunning(false); addLine("[INFO] Stopped"); return; }
    if (demoMode) { addLine("[INFO] Demo mode \u2014 data preloaded"); return; }
    setIsRunning(true);
    addLine("[INFO] Running 50-tick simulation...");
    try {
      await apiFetch("/simulation/run", { method: "POST", body: JSON.stringify({ total_ticks: 50, tick_delay_ms: 150 }) });
      const [tl, updated, mem, dl] = await Promise.all([apiFetch("/timeline"), apiFetch("/jobs"), apiFetch("/memory/status"), apiFetch("/deadlock/status")]);
      setTimeline(tl); setJobs(updated); setTick(tl.length); setMemStatus(mem); setDlStatus(dl);
      addLine("[INFO] Simulation complete");
    } catch (e) { addLine(`[ERROR] ${e.message}`); }
    setIsRunning(false);
  }, [isRunning, demoMode, addLine]);

  const handleReset = useCallback(async () => {
    if (!demoMode) { try { await apiFetch("/scheduler/reset", { method: "POST" }); } catch {} }
    setTick(0); setJobs([]); setTimeline([]); setTermLines(["[INFO] Simulation reset"]);
    setMemStatus({ total_frames: 32, free_frames: 32, page_faults: {}, tlb_hits: 0, tlb_misses: 0 });
    setDlStatus({ available: { CPU: 4, MEM_BLOCK: 8 }, safe_state: true });
    setDiskData({ cscan_order: [], sstf_order: [], head: 50 }); setDbLogs([]);
    setDemoMode(false);
  }, [demoMode]);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Segoe UI', -apple-system, sans-serif", padding: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${C.border}` }}>
        <div style={{
          width: 44, height: 44, borderRadius: 10, background: `linear-gradient(135deg, ${C.accent}, ${C.blue})`,
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 900, color: "#fff",
          boxShadow: `0 4px 20px ${C.accent}40`,
        }}>A</div>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em" }}>
            AcadOS <span style={{ color: C.accent, fontSize: 14, fontWeight: 400 }}>v0.2</span>
          </h1>
          <p style={{ margin: 0, fontSize: 11, color: C.textMuted }}>Academic OS Simulator </p>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", gap: 20, fontSize: 11 }}>
          {[
            { label: "Scheduler", color: C.accent, status: "live" },
            { label: "Memory", color: C.green, status: "live" },
            { label: "Deadlock", color: C.red, status: "live" },
            { label: "I/O", color: C.orange, status: "stub" },
            { label: "Foundation", color: C.blue, status: "live" },
          ].map(m => (
            <div key={m.label} style={{ textAlign: "center" }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: m.status === "live" ? m.color : C.textMuted, margin: "0 auto 4px", boxShadow: m.status === "live" ? `0 0 6px ${m.color}60` : "none" }} />
              <div style={{ color: m.status === "live" ? C.textMuted : C.textMuted + "80", fontSize: 10 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </div>

      <StatusBar tick={tick} running={isRunning} jobCount={jobs.length} onTick={handleTick} onRun={handleRun} onReset={handleReset} demoMode={demoMode} onToggleDemo={() => setDemoMode(d => !d)} />

      <div style={{ marginTop: 16, padding: "14px 18px", background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12 }}>
        <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", fontFamily: mono }}>Submit Job</div>
        <JobForm onSubmit={handleSubmitJob} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <Panel title="CPU Gantt Chart" icon={"\uD83D\uDCCA"} span={2}><GanttChart timeline={timeline} /></Panel>
        <Panel title="Process Table" icon={"\uD83D\uDDA5\uFE0F"} span={2}><ProcessTable jobs={jobs} /></Panel>
        <Panel title="Memory Manager " icon={"\uD83E\uDDE0"}><MemoryPanel status={memStatus} /></Panel>
        <Panel title="Banker's Algorithm " icon={"\uD83D\uDD12"}><DeadlockPanel status={dlStatus} /></Panel>
        <Panel title="Disk Scheduling " icon={"\uD83D\uDCBF"}><DiskSeeksPanel data={diskData} /></Panel>
        <Panel title="Job Logs " icon={"\uD83D\uDDC4\uFE0F"}><DbLogsPanel logs={dbLogs} /></Panel>
        <Panel title="Terminal Output" icon={"\u2328\uFE0F"} span={2}><TerminalPanel lines={termLines} /></Panel>
      </div>

      <div style={{ marginTop: 20, padding: "12px 0", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", fontSize: 10, color: C.textMuted }}>
        <span>AcadOS — Sachi \u2022 Ragini \u2022 Nikhil \u2022 Shakti \u2022 Sanat</span>
        <span>Dept. CSE (AI & ML) | A.Y. 2025\u201326</span>
      </div>
    </div>
  );
}
