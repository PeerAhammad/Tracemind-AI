import { useCallback, useEffect, useState } from "react";
import {
  Activity, AlertCircle, ArrowRight, BarChart3, CheckCircle2, FileSearch,
  LoaderCircle, Play, RefreshCw, Shield, ShieldAlert, Upload, Workflow,
} from "lucide-react";
import { api, type Analysis, type Corrections, type Run, type Scenario, type Task, type Trace } from "./lib/api";
import "./style.css";

type Page = "Overview" | "Trace Explorer" | "Analysis" | "Corrections" | "Replay Comparison" | "Benchmarks" | "Settings";

const pages: Page[] = ["Overview", "Trace Explorer", "Analysis", "Corrections", "Replay Comparison", "Benchmarks", "Settings"];

function label(value: unknown): string {
  return value === null || value === undefined || value === "" ? "n/a" : String(value).replaceAll("_", " ");
}
function percent(value: unknown): string {
  const number = Number(value);
  return value === null || value === undefined || !Number.isFinite(number) ? "n/a" : `${(number * 100).toFixed(1)}%`;
}
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return <article className="card"><div className="panel-title"><h2>{title}</h2></div>{children}</article>;
}
function Notice({ error, notice, busy }: { error: string; notice: string; busy: string }) {
  if (!error && !notice && !busy) return null;
  return <div className={`toast ${error ? "toast-error" : notice ? "toast-success" : "toast-progress"}`}>
    {error ? <AlertCircle size={16} /> : busy ? <LoaderCircle size={16} className="spin" /> : <CheckCircle2 size={16} />}
    <span>{error || notice || busy}</span>
  </div>;
}

export default function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [health, setHealth] = useState("checking");
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [benchmark, setBenchmark] = useState<any>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [corrections, setCorrections] = useState<Corrections | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparison, setComparison] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    setHealth("checking");
    try {
      const [healthResult, benchmarkResult, scenarioResult, taskResult] = await Promise.all([
        api.health(), api.benchmark(), api.scenarios(), api.tasks(),
      ]);
      setHealth(healthResult.status === "ok" ? "online" : "offline");
      setBenchmark(benchmarkResult);
      setScenarios(scenarioResult);
      setTasks(taskResult);
    } catch (e) {
      setHealth("offline");
      setError(e instanceof Error ? e.message : "Could not connect to the backend.");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const perform = async <T,>(message: string, request: () => Promise<T>, success: (value: T) => void) => {
    setBusy(message); setError(""); setNotice("");
    try { success(await request()); }
    catch (e) { setError(e instanceof Error ? e.message : "The request failed."); }
    finally { setBusy(""); }
  };

  const loadScenario = (id: string) => void perform("Loading scenario", async () => {
    const loaded = await api.loadScenario(id);
    return api.trace(loaded.id);
  }, data => {
    setTrace(data); setRun(null); setAnalysis(null); setCorrections(null); setComparison(null);
    setPage("Trace Explorer"); setNotice(`Loaded trace ${data.run_id}.`);
  });

  const startTask = (id: string) => void perform("Running task", async () => {
    const created = await api.runTask(id);
    return { run: created, trace: await api.trace(created.run_id) };
  }, result => {
    setRun(result.run); setTrace(result.trace); setAnalysis(null); setCorrections(null); setComparison(null);
    setPage("Trace Explorer"); setNotice(`Created run ${result.run.run_id}.`);
  });

  const analyze = () => {
    if (!trace) return;
    void perform("Analyzing trace", () => run ? api.analyzeRun(trace.run_id) : api.analyzeTrace(trace.run_id), result => {
      setAnalysis(result); setPage("Analysis"); setNotice(`Analysis complete: ${result.findings.length} finding(s).`);
    });
  };

  const getCorrections = () => {
    if (!run) { setError("Create a controlled task run before requesting corrections."); return; }
    void perform("Loading corrections", async () => ({
      corrections: await api.corrections(run.run_id),
      analysis: await api.analyzeRun(run.run_id),
    }), result => {
      setCorrections(result.corrections);
      setSelected(result.corrections.corrections.map(item => item.correction_id));
      setAnalysis(result.analysis); setPage("Corrections");
    });
  };

  const replay = () => {
    if (!run || !corrections) return;
    const chosen = corrections.corrections.filter(item => selected.includes(item.correction_id));
    const changes = Object.assign({}, ...chosen.map(item => item.config_changes));
    if (!chosen.length || !Object.keys(changes).length) { setError("Select at least one correction before replay."); return; }
    if (!window.confirm(`Approve ${chosen.length} correction(s) and replay with these changes?\n\n${JSON.stringify(changes, null, 2)}`)) return;
    void perform("Replaying approved corrections", async () => {
      const replayed = await api.replay(run.run_id, changes);
      return { run: replayed, trace: await api.trace(replayed.run_id), comparison: await api.comparison(replayed.run_id) };
    }, result => {
      setRun(result.run); setTrace(result.trace); setComparison(result.comparison);
      setPage("Replay Comparison"); setNotice("Replay completed. Verification comes from the backend response.");
    });
  };

  const upload = (file?: File) => {
    if (!file) return;
    void perform("Uploading trace", async () => {
      const uploaded = await api.uploadTrace(file);
      return api.trace(uploaded.id);
    }, data => {
      setTrace(data); setRun(null); setAnalysis(null); setCorrections(null); setComparison(null);
      setPage("Trace Explorer"); setNotice(`Uploaded trace with ${data.events?.length ?? 0} events.`);
    });
  };

  const overall = benchmark?.overall ?? benchmark;
  const heldOut = benchmark?.held_out ?? benchmark?.test;
  const dev = benchmark?.dev;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Shield size={20} /></div><div><div className="brand-name">TraceMind<span> AI</span></div><div className="brand-caption">AGENT RELIABILITY</div></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <div className="workspace-card"><div className="workspace-avatar">T</div><div className="workspace-copy"><strong>TraceMind Lab</strong><span>Local environment</span></div></div>
      <div className="nav-label">PLATFORM</div>
      <nav>{pages.map(item => <button key={item} className={`nav-item ${page === item ? "nav-active" : ""}`} onClick={() => setPage(item)}>{item === "Overview" ? <Activity size={17} /> : item === "Benchmarks" ? <BarChart3 size={17} /> : item === "Analysis" ? <ShieldAlert size={17} /> : item === "Corrections" ? <Workflow size={17} /> : <FileSearch size={17} />}<span>{item}</span></button>)}</nav>
      <div className="sidebar-spacer" />
      <div className="sidebar-status"><div className="status-heading"><span className={`status-dot ${health === "online" ? "dot-green" : health === "offline" ? "dot-red" : "dot-amber"}`} />API connection <span className="status-right">{health}</span></div><button className="text-button" onClick={() => void refresh()}><RefreshCw size={12} /> Refresh status</button></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> {page}</div><div className="topbar-right"><span>{health === "online" ? "System operational" : health === "offline" ? "API unavailable" : "Connecting"}</span><button className="icon-button" onClick={() => void refresh()} aria-label="Refresh data"><RefreshCw size={16} /></button></div></header>
      <div className="page-content">
        <Notice error={error} notice={notice} busy={busy} />
        {page === "Overview" && <section className="page-section">
          <div className="page-heading"><div><div className="eyebrow">SYSTEM OVERVIEW</div><h1>Agent reliability, at a glance.</h1><p>Inspect execution traces, diagnose failures, and validate corrective actions.</p></div><button className="btn btn-primary" onClick={() => setPage("Trace Explorer")}>Start investigation <ArrowRight size={15} /></button></div>
          <div className="metric-grid">
            <div className="metric card"><div className="metric-icon"><BarChart3 size={18} /></div><div className="metric-label">Scenarios</div><div className="metric-value">{benchmark?.total_cases ?? scenarios.length}</div><div className="metric-detail">Reported benchmark cases</div></div>
            <div className="metric card"><div className="metric-icon"><Activity size={18} /></div><div className="metric-label">Precision</div><div className="metric-value">{percent(overall?.precision)}</div><div className="metric-detail">Overall benchmark</div></div>
            <div className="metric card"><div className="metric-icon"><ShieldAlert size={18} /></div><div className="metric-label">Recall</div><div className="metric-value">{percent(overall?.recall)}</div><div className="metric-detail">Misses matter too</div></div>
            <div className="metric card"><div className="metric-icon"><CheckCircle2 size={18} /></div><div className="metric-label">Evidence hit rate</div><div className="metric-value">{percent(overall?.evidence_hit_rate)}</div><div className="metric-detail">Evidence IDs matched</div></div>
          </div>
          <div className="overview-grid"><Card title="Start with a scenario">{scenarios.slice(0, 8).map(s => <div className="scenario-row" key={s.scenario_id}><div className="scenario-icon"><FileSearch size={16} /></div><div className="scenario-copy"><strong>{s.scenario_id}</strong><span>{s.description}</span></div><button className="mini-button" disabled={!!busy} onClick={() => loadScenario(s.scenario_id)}>Load</button></div>)}{!scenarios.length && <p>No scenarios available. Check the backend connection.</p>}</Card><Card title="Quick actions"><button className="quick-action" onClick={() => setPage("Trace Explorer")}>Explore traces <ArrowRight size={15} /></button><button className="quick-action" onClick={() => setPage("Analysis")}>Review findings <ArrowRight size={15} /></button><button className="quick-action" onClick={() => setPage("Benchmarks")}>View benchmarks <ArrowRight size={15} /></button><p className="micro-copy">Rule-based analysis. No LLM integration is enabled.</p></Card></div>
        </section>}

        {page === "Trace Explorer" && <section className="page-section">
          <div className="page-heading compact-heading"><div><div className="eyebrow">INVESTIGATION WORKSPACE</div><h1>Trace Explorer</h1><p>Load a labelled example, run a controlled task, or upload a trace JSON file.</p></div><label className="btn btn-secondary upload-button"><Upload size={15} /> Upload JSON<input type="file" accept=".json,application/json" onChange={event => { upload(event.target.files?.[0]); event.currentTarget.value = ""; }} /></label></div>
          <div className="explorer-grid"><Card title="Scenario library">{scenarios.map(s => <div className="scenario-list-row" key={s.scenario_id}><div className="scenario-list-copy"><strong>{s.scenario_id}</strong><p>{s.description}</p><span>{label(s.split)} · expected {label(s.expected_task_outcome)}</span></div><button className="mini-button" disabled={!!busy} onClick={() => loadScenario(s.scenario_id)}>Load</button></div>)}</Card><Card title="Run a controlled task"><p className="panel-description">The runner is deterministic and simulated.</p>{tasks.map(task => <div className="task-row" key={task.task_id}><div className="task-copy"><strong>{label(task.task_id)}</strong><p>{task.description}</p></div><button className="mini-button" disabled={!!busy} onClick={() => startTask(task.task_id)}><Play size={12} /> Run</button></div>)}{!tasks.length && <p>No tasks available.</p>}</Card></div>
          {trace && <Card title={`Active trace · ${trace.run_id}`}><div className="trace-meta-grid"><div><span>Events</span><strong>{trace.events?.length ?? 0}</strong></div><div><span>Source</span><strong>{run ? "Task runner" : "Loaded / uploaded trace"}</strong></div><div><span>Outcome</span><strong>{run ? label(run.task_outcome) : "Not applicable"}</strong></div></div><button className="btn btn-primary" disabled={!!busy} onClick={analyze}><ShieldAlert size={14} /> Analyze trace</button><div className="timeline">{(trace.events ?? []).map((event, index) => <div className="timeline-item" key={`${event.event_id}-${index}`}><div className="timeline-event"><strong>{event.event_id}</strong><pre>{JSON.stringify(event, null, 2)}</pre></div></div>)}</div></Card>}
        </section>}

        {page === "Analysis" && <section className="page-section"><div className="page-heading compact-heading"><div><div className="eyebrow">RULE-BASED DIAGNOSTICS</div><h1>Trace Analysis</h1><p>Observed facts are separated from root-cause hypotheses.</p></div><div className="heading-actions"><button className="btn btn-secondary" disabled={!trace || !!busy} onClick={analyze}>Analyze again</button><button className="btn btn-primary" disabled={!run || !!busy} onClick={getCorrections}>Review corrections</button></div></div>
          {!analysis ? <Card title="No analysis available"><p>Load a trace and select Analyze trace.</p></Card> : <Card title={`${analysis.findings.length} finding(s) · ${analysis.run_id}`}>{analysis.findings.map(finding => <div className="detail-block" key={finding.finding_id}><h3>{label(finding.category)} · {label(finding.severity)}</h3><p><strong>Observed:</strong> {finding.observed_facts.join("; ") || "No observed facts returned."}</p><p><strong>Hypothesis:</strong> {finding.likely_root_cause}</p><p>{finding.explanation}</p><p><strong>Evidence events:</strong> {finding.evidence_event_ids.join(", ") || "None"}</p><p><strong>Recommended action:</strong> {finding.recommended_action}</p><p className="micro-copy">Source: {finding.explanation_source} · Verification: {label(finding.verification_status)}</p></div>)}{!analysis.findings.length && <p>No findings detected. This does not prove the trace is error-free.</p>}</Card>}
        </section>}

        {page === "Corrections" && <section className="page-section"><div className="page-heading compact-heading"><div><div className="eyebrow">HUMAN-IN-THE-LOOP CONTROL</div><h1>Corrective Actions</h1><p>Nothing is replayed until you explicitly approve.</p></div></div>
          {!corrections ? <Card title="No correction proposals"><p>Create a controlled task run, then request corrections.</p><button className="btn btn-primary" onClick={() => setPage("Trace Explorer")}>Open Trace Explorer</button></Card> : <div className="overview-grid"><Card title="Proposed changes">{corrections.corrections.map(item => <label className="correction-item" key={item.correction_id}><input type="checkbox" checked={selected.includes(item.correction_id)} onChange={event => setSelected(old => event.target.checked ? [...old, item.correction_id] : old.filter(id => id !== item.correction_id))} /><span className="correction-body"><strong>{item.title}</strong><span>{item.description}</span><code>{JSON.stringify(item.config_changes, null, 2)}</code></span></label>)}</Card><Card title="Approval summary"><p>{selected.length} of {corrections.corrections.length} proposals selected.</p><button className="btn btn-primary" disabled={!selected.length || !!busy || !run} onClick={replay}><Shield size={15} /> Approve &amp; replay</button><p className="micro-copy">A confirmation dialog appears before approved changes are sent to the backend.</p></Card></div>}
        </section>}

        {page === "Replay Comparison" && <section className="page-section"><div className="page-heading compact-heading"><div><div className="eyebrow">POST-REPLAY VERIFICATION</div><h1>Replay Comparison</h1><p>Verification reflects the backend comparison response.</p></div></div>
          {!comparison ? <Card title="No comparison available"><p>Approve corrections and replay a controlled task to compare runs.</p><button className="btn btn-primary" onClick={() => setPage("Corrections")}>Review corrections</button></Card> : <><Card title={comparison.regression ? "Regression detected" : "Replay result"}><div className="comparison-outcome"><div><span>BASELINE</span><strong>{label(comparison.baseline?.task_outcome)}</strong><small>{comparison.baseline?.run_id}</small></div><ArrowRight size={20} /><div><span>CORRECTED RUN</span><strong>{label(comparison.corrected?.task_outcome)}</strong><small>{comparison.corrected?.run_id}</small></div></div>{comparison.regression && <p className="warning-note">Regression detected. Review the changes before relying on this configuration.</p>}</Card><Card title="Verification results">{(comparison.verifications ?? []).map((item: any, index: number) => <div className="scenario-row" key={`${item.finding_id}-${index}`}><strong>{label(item.category)}</strong><span>{label(item.verification_status)}</span></div>)}<p className="data-source-note">Data source: {comparison.data_source ?? "Not specified by API"}</p></Card></>}
        </section>}

        {page === "Benchmarks" && <section className="page-section"><div className="page-heading compact-heading"><div><div className="eyebrow">EVALUATION &amp; LIMITATIONS</div><h1>Benchmark Lab</h1><p>Live detector performance and split-specific metrics.</p></div><button className="btn btn-secondary" disabled={!!busy} onClick={() => void perform("Refreshing benchmark", api.benchmark, setBenchmark)}><RefreshCw size={14} /> Refresh</button></div>
          {!benchmark ? <Card title="Benchmark unavailable"><p>Check backend health and refresh.</p></Card> : <><div className="metric-grid"><div className="metric card"><div className="metric-label">Precision</div><div className="metric-value">{percent(overall?.precision)}</div></div><div className="metric card"><div className="metric-label">Recall</div><div className="metric-value">{percent(overall?.recall)}</div></div><div className="metric card"><div className="metric-label">False positive rate</div><div className="metric-value">{percent(overall?.false_positive_rate)}</div></div><div className="metric card"><div className="metric-label">Evidence hit rate</div><div className="metric-value">{percent(overall?.evidence_hit_rate)}</div></div></div><div className="overview-grid"><Card title="Development split"><div className="split-big">{percent(dev?.recall)} recall</div><p>Precision: {percent(dev?.precision)}</p><p>Scenarios: {label(dev?.scenarios)}</p><p>False positives: {label(dev?.fp)} · False negatives: {label(dev?.fn)}</p></Card><Card title="Held-out split"><div className="split-big">{percent(heldOut?.recall)} recall</div><p>Precision: {percent(heldOut?.precision)}</p><p>Scenarios: {label(heldOut?.scenarios)}</p><p>False positives: {label(heldOut?.fp)} · False negatives: {label(heldOut?.fn)}</p><p className="micro-copy">The held-out set is small and not blind; treat these values as limited evidence.</p></Card></div>{Array.isArray(benchmark.limitations) && <Card title="Benchmark limitations">{benchmark.limitations.map((item: any, index: number) => <p key={index}>{typeof item === "string" ? item : JSON.stringify(item)}</p>)}</Card>}</>}
        </section>}

        {page === "Settings" && <section className="page-section"><div className="page-heading compact-heading"><div><div className="eyebrow">ENVIRONMENT & DISCLOSURES</div><h1>Settings</h1><p>Connection and capability disclosures.</p></div></div><Card title="Backend API"><p>Base URL: {import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"}</p><p>Health status: {health}</p><button className="btn btn-secondary" onClick={() => void refresh()}><RefreshCw size={14} /> Check connection</button></Card><Card title="Model disclosure"><p>Detection and explanations are rule-based. No LLM integration is enabled.</p><p>The controlled runner is deterministic and simulated. Durations are not wall-clock measurements.</p></Card></section>}

        <footer className="app-footer"><span>TraceMind AI · v0.5.0</span><span>Research prototype · Rule-based detection</span></footer>
      </div>
    </main>
  </div>;
}
