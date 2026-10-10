"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Download, FileUp, LoaderCircle, Play, SearchCheck } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { agriRequest, downloadText } from "@/lib/agri-api";
import styles from "./AgriDashboard.module.css";

type Series = { series_id: string; market: string; variety: string; grade: string; unit: string; source: string; availability_basis: Record<string, number>; rows: number; start: string; end: string; missing_days: number; coverage: number; validation_start: string; test_start: string; semantic_archive: boolean; history: { date: string; price: number }[] };
type Dataset = { dataset_id: string; series: Series[] };
type Check = { ready: boolean; message: string; horizons: { horizon: number; training: number; validation: number; test: number; semantic_ready: boolean }[] };
type Job = { job_id: string; status: string; message?: string; limitations?: { reason: string }[] };
const HEADER = "date,state,district,market,commodity,variety,grade,min_price,max_price,modal_price,unit,source,availability_basis,available_at\n";

export function MarketDataSetup({ onComplete }: { onComplete: () => void }) {
  const [prices, setPrices] = useState<File | null>(null);
  const [events, setEvents] = useState<File | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [seriesId, setSeriesId] = useState("");
  const [validation, setValidation] = useState("");
  const [test, setTest] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [pollRetry, setPollRetry] = useState(0);
  const selected = dataset?.series.find(s => s.series_id === seriesId);
  const running = job?.status === "queued" || job?.status === "running";
  const jobId = job?.job_id;

  useEffect(() => {
    if (!jobId || !running) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await agriRequest<Job>(`workspace/jobs/${jobId}`, { signal: controller.signal });
        setJob(result); setError("");
        if (result.status === "completed") {
          setCheck(null); onComplete();
        } else if (["queued", "running"].includes(result.status)) timer = setTimeout(poll, 1500);
        else setCheck(null);
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not check evaluation status"); }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, running, onComplete, pollRetry]);

  function selectSeries(series: Series) {
    setSeriesId(series.series_id); setValidation(series.validation_start); setTest(series.test_start); setCheck(null); setJob(null);
  }

  async function upload() {
    if (!prices) return;
    setBusy("upload"); setError(""); setCheck(null); setJob(null); setDataset(null);
    try {
      if (prices.size > 5_000_000 || (events && events.size > 5_000_000)) throw new Error("Each file must be 5 MB or smaller.");
      const result = await agriRequest<Dataset>("workspace/datasets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prices_csv: await prices.text(), events_json: events ? await events.text() : null }) });
      setDataset(result); selectSeries(result.series[0]);
    } catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setBusy(""); }
  }

  async function evaluate(start: boolean) {
    if (!dataset) return;
    setBusy(start ? "evaluate" : "check"); setError("");
    try {
      const options = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: dataset.dataset_id, series_id: seriesId, validation_start: validation, test_start: test }) };
      if (start) setJob(await agriRequest<Job>("workspace/evaluate", options));
      else setCheck(await agriRequest<Check>("workspace/check", options));
    } catch (e) { setError(e instanceof Error ? e.message : "Evaluation unavailable"); }
    finally { setBusy(""); }
  }

  return <div className="space-y-5">
      <p>Bring historical market observations into Nexyra. Preview the data first, then run a chronological research evaluation for each horizon.</p>
    <div className={styles.steps} aria-label="Data setup progress">
      {["1. Add history", "2. Check periods", "3. Evaluate"].map((label, i) => <div key={label} className={`${styles.step} ${(i === 0 || (i === 1 && dataset) || (i === 2 && check?.ready)) ? styles.activeStep : ""}`}>{label}</div>)}
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <label className={styles.upload}><span className="flex items-center gap-2 font-semibold"><FileUp size={18} /> Price history CSV</span><span className="block mt-2 text-xs">Required · Maharashtra onion · one row per market, variety and day</span><input aria-label="Price history CSV" type="file" accept=".csv,text/csv" disabled={!!busy || running} onChange={e => { setPrices(e.target.files?.[0] || null); setDataset(null); setCheck(null); setJob(null); }} /></label>
      <label className={styles.upload}><span className="flex items-center gap-2 font-semibold"><FileUp size={18} /> News archive JSON</span><span className="block mt-2 text-xs">Optional · required to compare semantic Models B and C</span><input aria-label="News archive JSON" type="file" accept=".json,application/json" disabled={!!busy || running} onChange={e => { setEvents(e.target.files?.[0] || null); setDataset(null); setCheck(null); setJob(null); }} /></label>
    </div>
    <div className="flex flex-wrap gap-3">
      <button type="button" className={`${styles.button} ${styles.primary}`} disabled={!prices || !!busy || running} onClick={() => void upload()}>{busy === "upload" ? <LoaderCircle className={styles.spin} size={16} /> : <SearchCheck size={16} />} Validate & preview</button>
      <button type="button" className={styles.button} onClick={() => downloadText("nexyra-price-template.csv", HEADER, "text/csv")}><Download size={16} /> Download CSV template</button>
    </div>
    <details><summary className="cursor-pointer font-semibold">What do I put in the file?</summary><div className="space-y-3 mt-3 leading-relaxed">
      <p>Use actual historical wholesale observations, ideally at least 300 daily rows per market/variety. The readiness check uses usable dates, so gaps may require more history.</p>
      <p><strong>Dates:</strong> YYYY-MM-DD. <strong>State:</strong> Maharashtra. <strong>Commodity:</strong> Onion. <strong>Unit:</strong> INR/quintal. Preserve exact market, variety, grade and source identities.</p>
      <p><strong>Prices:</strong> the minimum, maximum and modal wholesale prices for that observation. <strong>Source:</strong> the original dataset identifier or URL.</p>
      <p><strong>availability_basis:</strong> use verified_source_timestamp only when your source provides the actual timestamp. Use retrospective_assumption_7d only for clearly labeled research with seven calendar days after observation date as the assumed release time; leave available_at blank for that basis. The assumption is not a verified publication time.</p>
      <p><strong>available_at:</strong> include the timezone for verified_source_timestamp, such as YYYY-MM-DDTHH:MM:SS+05:30. Do not guess availability or fill missing prices with invented values.</p>
      <p>Upload a timestamped news archive only if you have verified monitoring coverage. Without it, Nexyra can evaluate Model A and naive baselines; B/C stay unavailable.</p>
      <p>After activation, choose your mandi/variety, a 1-, 3- or 7-day horizon and a history range. Prices and forecasts then fill automatically; you do not enter a future price.</p>
    </div></details>
    {selected && <div className={`${styles.notice} space-y-4`}>
      <div className="flex flex-wrap items-center justify-between gap-3"><span className={styles.badge}><CheckCircle2 size={14} /> Validated history</span><label>Preview market <select className="input-field ml-2 max-w-full" aria-label="Preview market" value={seriesId} disabled={running || !!busy} onChange={e => { const s = dataset?.series.find(s => s.series_id === e.target.value); if (s) selectSeries(s); }}>{dataset?.series.map(s => <option key={s.series_id} value={s.series_id}>{s.market} / {s.variety}</option>)}</select></label></div>
      <p>{selected.rows} observations · {selected.start} to {selected.end} · {(selected.coverage * 100).toFixed(1)}% calendar coverage · {selected.missing_days} unobserved days</p>
      <p>Exact identity: {selected.market} / {selected.variety} / {selected.grade || "grade unspecified"} · {selected.unit || "unit unspecified"} · {selected.source || "source unspecified"}</p>
      <p>Availability basis: {Object.entries(selected.availability_basis || {}).map(([basis, count]) => `${basis} (${count})`).join("; ") || "not supplied"}</p>
      <div className="h-48" aria-label="Uploaded price history preview"><ResponsiveContainer width="100%" height="100%"><LineChart data={selected.history}><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} /><Tooltip contentStyle={{ background: "var(--bg-elevated)", borderColor: "var(--border-subtle)", color: "var(--text-primary)" }} /><Line dataKey="price" name="Observed INR/quintal" stroke="var(--accent-brand)" dot={false} /></LineChart></ResponsiveContainer></div>
      <p className="text-xs">Preview only: uploading does not train or register a model. Missing days are not interpolated. Evaluation artifacts remain research-only until separately accepted for production.</p>
      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-2">Validation starts<input className="input-field" type="date" value={validation} min={selected.start} max={selected.end} disabled={running || !!busy} onChange={e => { setValidation(e.target.value); setCheck(null); }} /></label>
        <label className="flex flex-col gap-2">Untouched test starts<input className="input-field" type="date" value={test} min={selected.start} max={selected.end} disabled={running || !!busy} onChange={e => { setTest(e.target.value); setCheck(null); }} /></label>
      </div>
      <p className="text-xs">Dates are suggested from history length. Check readiness before evaluating. Starting evaluation reserves this test history; it cannot be reused to tune another winner. Completed artifacts remain research-only until a separate production acceptance review.</p>
      <div className="flex flex-wrap gap-3"><button type="button" className={styles.button} disabled={!!busy || running || !validation || !test} onClick={() => void evaluate(false)}><SearchCheck size={16} /> {busy === "check" ? "Checking…" : "Check readiness"}</button><button type="button" className={`${styles.button} ${styles.primary}`} disabled={!check?.ready || !!busy || running} onClick={() => void evaluate(true)}><Play size={16} /> {running ? "Evaluating…" : "Run research evaluation"}</button></div>
      {check && <div role="status"><p>{check.message}</p>{check.ready && <ul className="mt-2 space-y-1 text-xs">{check.horizons.map(h => <li key={h.horizon}>{h.horizon} days: {h.training} initial training / {h.validation} validation / {h.test} test origins · {h.semantic_ready ? "A/B/C evaluable" : "A + baselines; semantic history unavailable"}</li>)}</ul>}</div>}
    </div>}
    {job && <div className={`${styles.notice} flex gap-3`} role="status" aria-live="polite">{running ? <LoaderCircle size={20} className={`${styles.spin} shrink-0`} /> : <CheckCircle2 size={20} className="shrink-0" />}<div><p className="font-semibold">{job.status === "completed" ? "Research evaluation completed" : job.status === "failed" || job.status === "interrupted" ? "Evaluation not completed" : "Evaluation in progress"}</p><p className="mt-1">{job.message}</p>{job.limitations?.map((item, i) => <p key={i}>{item.reason}</p>)}</div></div>}
    {error && <div role="alert" className={styles.notice}>{error}{running && <button className={`${styles.button} ml-3`} onClick={() => setPollRetry(r => r + 1)}>Retry status</button>}</div>}
  </div>;
}
