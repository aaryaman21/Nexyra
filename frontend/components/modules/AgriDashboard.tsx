"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Download, RefreshCw, Search, Upload } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ContextualLoader } from "@/components/loaders/ContextualLoaders";
import { MarketDataSetup } from "./MarketDataSetup";
import { agriRequest, downloadText } from "@/lib/agri-api";
import styles from "./AgriDashboard.module.css";

type Metrics = { n: number; mae: number; rmse: number; smape: number; directional_accuracy: number; interval_coverage: number; interval_width: number };
type Comparison = { id: string; family: string; status: string; reason?: string; validation?: Metrics; test?: Metrics; stability_mae_std?: number; features?: string[]; params?: Record<string, unknown> };
type Evaluation = { selected_model: string; baseline: string; selection_reason: string; comparison: Comparison[]; training_period: { origin_start: string; target_end: string }; validation_period: { origin_start: string; origin_end: string }; test_period: { origin_start: string; target_end: string }; interval_method: string };
type Market = { series_id: string; market: string; variety: string; grade?: string; source?: string; district: string; version: string; horizons: Record<string, Evaluation> };
type Registry = { status: string; reason?: string; markets: Market[] };
type CatalogSeries = { series_id: string; market: string; variety: string; grade: string | null; district: string; source: string; unit: string; observations: number; last_date: string; availability_status: string; forecast_status: string };
type SeriesCatalog = { status: string; reason?: string; series: CatalogSeries[] };
type MarketData = { latest_price: number; change: number | null; volatility: number | null; as_of: string; grade?: string; source?: string; unit?: string; unit_status?: string; availability_status?: string; observation_age_days?: number; stale?: boolean; limitations: string[]; history: { date: string; price: number }[]; news: { id: string; title: string; url: string; category: string; published_at: string }[] };
type EventCapture = { id: string; title: string; url: string; source: string; published_at: string | null; published_date?: string | null; publication_precision?: string; publication_status: string; published_time_source_text?: string | null; retrieved_at: string; available_at?: string; first_seen_at?: string; availability_basis?: string; category: string; severity: number | null; geographic_relevance: string; commodity_relevance: string; relevance_status: string; evidence: string[]; impact_hypothesis: string | null; classification_status: string; article_text?: string | null; content_status?: string; text_representation?: string; text_imported_at?: string | null; text_raw_sha256?: string | null; text_content_sha256?: string | null; issuing_ministry?: string | null; prid?: string | null; event_classifications?: { category: string; status: string; evidence: { text: string; start: number; end: number; source_article_id: string; supports: string }[] }[]; reported_facts?: { kind: string; value: string; period?: string; announcement_date?: string; evidence: { text: string } }[]; date_mentions?: { text: string; normalized_date?: string | null; role: string }[]; source_relevance?: string };
type EventFeed = { status: string; events: EventCapture[]; reason?: string; classification_method?: string; predictive_status?: string; dataset_health?: { unique_articles: number; full_body_articles: number; human_reviewed_articles: number; source_diversity: number; evaluation_status: string; accuracy_metrics_available: boolean | null } };
type Forecast = { status: string; prediction: number; lower: number; upper: number; origin: string; target_date: string; stale: boolean; interval_status: string; calibration: { nominal_coverage: number }; selected_model: string; version: string; explanation?: { method: string; description: string; features: { feature: string; contribution: number }[] } };
type ResearchSeries = CatalogSeries & { commodity: string; source_url: string; source_publisher: string; source_attribution_claim: string; unit_status: string; replay_origin: string; test_status: string; test_period: { start: string; target_end: string; fresh_untouched: boolean; status: string }; horizons: Record<string, Evaluation> };
type ResearchCatalog = { status: string; reason?: string; series: ResearchSeries[] };
type Replay = { mode: string; status: string; series_id: string; origin: string; horizon_days: number; target_date: string; prediction: number; lower: number; upper: number; interval_status: string; selected_model: string; unit: string; unit_status: string; latest_available_observation_date: string; latest_available_price: number; latest_price_age_days: number; series_staleness_days: number; stale_warning: string; availability_policy: string; outcome: { status: string; modal_price: number | null; forecast_error_prediction_minus_actual: number | null } };
const number = (value: number | undefined | null, percent = false) => value == null ? "Unavailable" : `${(value * (percent ? 100 : 1)).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${percent ? "%" : ""}`;

async function request<T>(path: string, signal: AbortSignal): Promise<T> {
  return agriRequest<T>(path, { signal });
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  const prefersReducedMotion = useReducedMotion();
  const reduceMotion = prefersReducedMotion;
  return <motion.section className={`glass-panel p-6 space-y-4 min-w-0 ${styles.panel}`} initial={{ opacity: 0, y: reduceMotion ? 0 : 24 }} whileInView={{ opacity: 1, y: 0 }} whileHover={reduceMotion ? undefined : { y: -3 }} viewport={{ once: true }} transition={{ duration: .25 }}>
    <h2 className="text-lg font-bold text-slate-900 dark:text-white">{title}</h2>{children}
  </motion.section>;
}

export function AgriDashboard() {
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [catalog, setCatalog] = useState<SeriesCatalog | null>(null);
  const [researchCatalog, setResearchCatalog] = useState<ResearchCatalog | null>(null);
  const [series, setSeries] = useState("");
  const [horizon, setHorizon] = useState("1");
  const [days, setDays] = useState("90");
  const [market, setMarket] = useState<MarketData | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [replayOrigin, setReplayOrigin] = useState("");
  const [replayBusy, setReplayBusy] = useState(false);
  const [error, setError] = useState("");
  const [forecastError, setForecastError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [setupOpen, setSetupOpen] = useState(true);
  const [newsQuery, setNewsQuery] = useState("");
  const [eventFeed, setEventFeed] = useState<EventFeed | null>(null);
  const refresh = useCallback(() => { setMarket(null); setForecast(null); setReplay(null); setForecastError(""); setRetry(r => r + 1); }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.allSettled([request<Registry>("models", controller.signal), request<SeriesCatalog>("series", controller.signal), request<ResearchCatalog>("research/series", controller.signal)])
      .then(([modelsResult, catalogResult, researchResult]) => {
        if (controller.signal.aborted) return;
        if (modelsResult.status === "fulfilled") setRegistry(modelsResult.value);
        else setRegistry(null);
        if (catalogResult.status === "fulfilled") setCatalog(catalogResult.value);
        else setCatalog(null);
        if (researchResult.status === "fulfilled") setResearchCatalog(researchResult.value);
        else setResearchCatalog(null);
        const available = [
          ...(modelsResult.status === "fulfilled" ? modelsResult.value.markets : []),
          ...(catalogResult.status === "fulfilled" ? catalogResult.value.series : []),
          ...(researchResult.status === "fulfilled" ? researchResult.value.series : []),
        ];
        setSeries(previous => available.some(item => item.series_id === previous) ? previous : available[0]?.series_id || "");
        if (modelsResult.status === "rejected") setError(modelsResult.reason instanceof Error ? modelsResult.reason.message : "Agricultural model status is unavailable.");
        else if (catalogResult.status === "rejected") setError(catalogResult.reason instanceof Error ? catalogResult.reason.message : "Agricultural observation catalog is unavailable.");
        else setError("");
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    const controller = new AbortController();
    request<EventFeed>("events/recent?limit=50", controller.signal)
      .then(setEventFeed)
      .catch(() => { if (!controller.signal.aborted) setEventFeed({ status: "unavailable", events: [], reason: "Official event captures are unavailable. Run a one-shot collection after source access is restored." }); });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    if (!series) return;
    const controller = new AbortController();
    const evaluated = registry?.markets.some(item => item.series_id === series) || false;
    const historical = researchCatalog?.series.find(item => item.series_id === series);
    const endpoint = evaluated ? `market/${series}` : historical ? `research/series/${series}` : `series/${series}`;
    request<MarketData>(endpoint, controller.signal).then(data => { setMarket(data); setError(""); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    if (evaluated) {
      request<Forecast>(`forecast/${series}?horizon=${horizon}`, controller.signal).then(data => { setForecast(data); setForecastError(""); })
        .catch(e => { if (!controller.signal.aborted) setForecastError(e.message); });
    } else if (historical) {
      setForecast(null); setReplay(null); setForecastError("");
      setReplayOrigin(previous => previous || historical.replay_origin);
    } else {
      setForecast(null); setReplay(null);
      setForecastError("Evaluation blocked: no evaluated model is available for this exact series.");
    }
    return () => controller.abort();
  }, [series, horizon, retry, registry, researchCatalog]);
  const selected = registry?.markets.find(m => m.series_id === series);
  const selectedResearch = researchCatalog?.series.find(item => item.series_id === series);
  const evaluation = selected?.horizons[horizon] || selectedResearch?.horizons[horizon];
  const winner = evaluation?.comparison.find(c => c.id === evaluation.selected_model);
  const baseline = evaluation?.comparison.find(c => c.id === evaluation.baseline);
  async function runHistoricalReplay() {
    if (!selectedResearch || !replayOrigin) return;
    setReplayBusy(true); setReplay(null); setForecastError("");
    try {
      const query = new URLSearchParams({ origin: replayOrigin, horizon });
      setReplay(await agriRequest<Replay>(`research/replay/${selectedResearch.series_id}?${query.toString()}`));
    } catch (e) {
      setForecastError(e instanceof Error ? e.message : "Historical replay is unavailable for this origin.");
    } finally { setReplayBusy(false); }
  }
  if (loading) return <ContextualLoader module="futureflow" text="Loading agricultural model evaluations" />;
  return <div id="agri-dashboard" className={`${styles.dashboard} space-y-8 text-sm text-slate-600 dark:text-slate-300`}>
    <div className="flex flex-wrap items-center justify-between gap-3"><span className={styles.badge}>{error ? "Backend disconnected" : registry?.markets.length ? "Research models evaluated" : catalog?.series.length ? "Observations present · evaluation unavailable" : "Connected · Add history to get started"}</span><div className="flex flex-wrap gap-2"><button type="button" className={styles.button} onClick={refresh}><RefreshCw size={15} /> Refresh data</button><button type="button" className={styles.button} aria-expanded={setupOpen} aria-controls="market-data-setup" onClick={() => setSetupOpen(open => !open)}><Upload size={15} /> {setupOpen ? "Hide data setup" : "Add market data"}</button></div></div>
    {error && <div className="glass-panel p-6 space-y-3" role="alert"><p>{error}</p><p className="text-xs">In a separate terminal, run the backend from C:\Nexyra:</p><code className="block text-xs overflow-auto">.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000</code><button className={styles.button} onClick={refresh}><RefreshCw size={15} /> Retry connection</button></div>}
    <div id="market-data-setup" hidden={!setupOpen}><Panel title="Add market data"><MarketDataSetup onComplete={refresh} /></Panel></div>
    <Panel title="Market explorer">
      <p>Onion · Maharashtra · Modal wholesale price in INR per quintal</p>
      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-2">Market / variety / grade<select className="input-field" aria-label="Mandi, variety and grade" value={series} disabled={!registry?.markets.length && !catalog?.series.length} onChange={e => { setSeries(e.target.value); setMarket(null); setForecast(null); setReplay(null); }}>
          {researchCatalog?.series.map(m => <option key={m.series_id} value={m.series_id}>{m.market} / {m.variety} / {m.grade} · {m.district} · {m.source_publisher}</option>)}
          {!registry?.markets.length && !catalog?.series.length && <option value="">No observed or evaluated series</option>}
          {[...(registry?.markets || []), ...(catalog?.series.filter(item => !registry?.markets.some(model => model.series_id === item.series_id)) || [])].map(m => <option key={m.series_id} value={m.series_id}>{m.market} / {m.variety} / {m.grade || "grade unspecified"} · {m.district}</option>)}
        </select></label>
        <label className="flex flex-col gap-2">Forecast horizon<select aria-label="Forecast horizon" className="input-field" value={horizon} onChange={e => { setHorizon(e.target.value); setForecast(null); setForecastError(""); }}>
          {[1, 3, 7].map(h => <option key={h} value={h}>{h} calendar day{h > 1 ? "s" : ""}</option>)}
        </select></label>
        <label className="flex flex-col gap-2">History<select className="input-field" value={days} onChange={e => setDays(e.target.value)}>{[30, 60, 90].map(d => <option key={d} value={d}>Last {d} observations</option>)}</select></label>
      </div>
      {!registry?.markets.length && <p role="status">{registry?.reason || "No verified agricultural history and evaluated model are available"}. No winning model or market prices are assumed.</p>}
    </Panel>
    <div className="workspace-grid">
      <Panel title="Market overview">
        {market ? <><p className="text-3xl font-mono font-bold">₹{number(market.latest_price)} <span className="text-xs">/ {market.unit || "INR/quintal"}</span></p><p>Latest recorded observation · exact grade {market.grade || "not supplied"}</p><p>Stored unit status: {market.unit_status || "not independently verified"}.</p><p>Change from previous observation: ₹{number(market.change)}</p><p>Observation date: {market.as_of} · source availability: {market.availability_status === "unknown" ? "unknown (date only)" : market.availability_status || "uploader-declared; not independently verified"}</p>{market.observation_age_days != null && <p>Observation age: {market.observation_age_days} calendar days{market.stale ? " · stale by the 7-day display threshold" : ""}</p>}<p>Source: {market.source || "included in evaluation snapshot"}</p><div className="h-64" aria-label="Historical modal prices"><ResponsiveContainer width="100%" height="100%"><LineChart data={market.history.slice(-Number(days))}><CartesianGrid stroke="var(--border-subtle)" /><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} /><Tooltip /><Line dataKey="price" name="Observed modal price" stroke="var(--accent-brand)" dot={false} /></LineChart></ResponsiveContainer></div></> : <p>No recorded observations are available for this exact series.</p>}
      </Panel>
      <Panel title="Price forecast">
        {!selectedResearch && (forecastError ? <p role="status">{forecastError}</p> : forecast ? <><p className="text-3xl font-mono font-bold">₹{number(forecast.prediction)}</p><p>{horizon}-calendar-day forecast for {forecast.target_date}, issued as of {forecast.origin}.</p><p>Experimental {(forecast.calibration.nominal_coverage * 100).toFixed(0)}% interval: ₹{number(forecast.lower)} – ₹{number(forecast.upper)}</p><p>Selected research model: {forecast.selected_model}</p>{forecast.stale && <p role="status">This forecast target is historical relative to today; it is not a current market prediction.</p>}<p>Interval coverage is not guaranteed under temporal dependence.</p></> : <p>No evaluated forecast is available for this exact selection.</p>)}
      </Panel>
    </div>
    {selectedResearch && <Panel title="Historical research replay">
      <p>Exact series: {selectedResearch.market} / {selectedResearch.commodity} / {selectedResearch.variety} / {selectedResearch.grade} · {selectedResearch.source_publisher}. Stored unit: {selectedResearch.unit} ({selectedResearch.unit_status}).</p>
      <p>The saved 2024 test period has been examined before and is not a fresh holdout. Historical availability uses the seven-day retrospective assumption. This series is stale for a current market forecast.</p>
      <div className="flex flex-wrap items-end gap-3"><label className="flex flex-col gap-2">Historical replay origin<input aria-label="Historical replay origin" className="input-field" type="date" min={selectedResearch.test_period.start} max={selectedResearch.test_period.target_end} value={replayOrigin || selectedResearch.replay_origin} onChange={e => { setReplayOrigin(e.target.value); setReplay(null); setForecastError(""); }} /></label><button type="button" className={styles.button} disabled={replayBusy} onClick={() => void runHistoricalReplay()}>{replayBusy ? "Replaying…" : `Run ${horizon}-day replay`}</button></div>
      {forecastError && <p role="alert">{forecastError}</p>}
      {replay && <div role="status" className="space-y-2"><p className="text-3xl font-mono font-bold">₹{number(replay.prediction)} / {replay.unit}</p><p>{replay.horizon_days}-calendar-day historical forecast: origin {replay.origin}, target {replay.target_date}.</p><p>Latest as-of price: ₹{number(replay.latest_available_price)} from {replay.latest_available_observation_date} ({replay.latest_price_age_days} days old).</p><p>Selected model/baseline: {replay.selected_model} · research-only.</p><p>Experimental interval: ₹{number(replay.lower)} – ₹{number(replay.upper)}; temporal coverage is not guaranteed.</p>{replay.outcome.modal_price != null ? <p>Recorded outcome: ₹{number(replay.outcome.modal_price)} · forecast error (prediction minus actual): ₹{number(replay.outcome.forecast_error_prediction_minus_actual)}.</p> : <p>No exact target observation is present in this snapshot.</p>}<p>{replay.stale_warning} Test period was previously examined; replay errors are historical diagnostics, not independent validation.</p></div>}
    </Panel>}
    <Panel title="Model performance and automatic selection">
      <p>A: numerical · B: semantic only · C: combined. Selection uses rolling validation MAE, with RMSE and fold stability as secondary criteria. The test set never chooses the winner.</p>
      {evaluation ? <>
        {selectedResearch && <p role="status">Historical diagnostics only: the 2024 test outcomes were previously examined and are not a fresh untouched holdout.</p>}
        <p className="font-semibold">Selected: {evaluation.selected_model} · {selected?.version ? `version ${selected.version}` : selectedResearch ? "Phase 5A research artifact" : "research artifact"}</p>
        <p>{evaluation.selection_reason}</p>
        <p>Refit history: {evaluation.training_period.origin_start} to {evaluation.training_period.target_end}. Validation origins: {evaluation.validation_period.origin_start} to {evaluation.validation_period.origin_end}. Test: {evaluation.test_period.origin_start} to {evaluation.test_period.target_end}.</p>
        <p>Validation MAE: {number(winner?.validation?.mae)} versus {number(baseline?.validation?.mae)} for {evaluation.baseline}. Values in INR/quintal.</p>
        <div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="text-left py-3">Identical chronological origins within this horizon. Direction and coverage are percentages; sMAPE is percent.</caption><thead><tr>{["Configuration", "Period", "N", "MAE", "RMSE", "sMAPE", "Direction", "Coverage", "Width", "Fold MAE SD"].map(label => <th key={label} className="p-2 whitespace-nowrap">{label}</th>)}</tr></thead><tbody>
          {evaluation.comparison.flatMap(row => row.status !== "evaluated" ? [<tr key={row.id}><td className="p-2">{row.id}</td><td className="p-2" colSpan={9}>{row.reason || row.status}</td></tr>] : (["validation", "test"] as const).map(period => <tr key={`${row.id}-${period}`} className="border-t border-slate-200 dark:border-slate-700"><td className="p-2">{row.id}{row.id === evaluation.selected_model ? " ✓" : ""}</td><td className="p-2">{period}</td><td className="p-2">{row[period]?.n}</td>{(["mae", "rmse", "smape", "directional_accuracy", "interval_coverage", "interval_width"] as const).map(metric => <td key={metric} className="p-2">{number(row[period]?.[metric], ["directional_accuracy", "interval_coverage"].includes(metric))}</td>)}<td className="p-2">{period === "validation" ? number(row.stability_mae_std) : "—"}</td></tr>))}
        </tbody></table></div>
        <div className="flex flex-wrap gap-3"><button type="button" className={styles.button} onClick={() => downloadText(`nexyra-${series}-${horizon}day-evaluation.json`, JSON.stringify({ market: selected?.market, variety: selected?.variety, version: selected?.version, horizon, ...evaluation }, null, 2), "application/json")}><Download size={15} /> Download evaluation</button></div>
        <details><summary className="cursor-pointer">Selected configuration and uncertainty method</summary><p className="mt-3">Features: {winner?.features?.join(", ") || "Naive reference price"}</p><pre className="overflow-auto text-xs mt-2">{JSON.stringify(winner?.params, null, 2)}</pre><p>{evaluation.interval_method}</p></details>
      </> : <p>No agricultural evaluation has been completed. Missing semantic data will be reported as unavailable; Model C does not automatically win.</p>}
    </Panel>
    <div className="workspace-grid">
      <Panel title="Semantic intelligence">
        {eventFeed?.events.length ? <>
          <p>Official PIB captures · keyword classification is experimental; price prediction is not validated.</p>
          {eventFeed.dataset_health && <p className="text-xs">Dataset health | {eventFeed.dataset_health.unique_articles} unique source articles | {eventFeed.dataset_health.full_body_articles} full-body texts | {eventFeed.dataset_health.human_reviewed_articles} human-reviewed | {eventFeed.dataset_health.source_diversity} source organizations | evaluation: {eventFeed.dataset_health.evaluation_status.replaceAll("_", " ")}. No accuracy score is available.</p>}
          <label className="flex items-center gap-2"><Search size={16} /><input aria-label="Search news" className="input-field w-full" value={newsQuery} onChange={e => setNewsQuery(e.target.value)} placeholder="Search headlines or event categories" /></label>
          {eventFeed.events.filter(event => `${event.title} ${event.category} ${event.geographic_relevance} ${event.event_classifications?.map(item => item.category).join(" ") || ""}`.toLowerCase().includes(newsQuery.toLowerCase())).map(event => <article key={event.id} className="border-b border-slate-200 dark:border-slate-700 pb-3"><a className="underline" href={event.url} target="_blank" rel="noopener noreferrer">{event.title}</a><p className="text-xs mt-2">{event.source} · {event.category} · {event.geographic_relevance}</p><p className="text-xs">Published: {event.published_date || event.published_at || "not supplied"} ({event.publication_precision || event.publication_status}){event.published_time_source_text ? ` · Source time: ${event.published_time_source_text}` : ""} · Retrieved: {event.retrieved_at} · First seen/available: {event.available_at || event.first_seen_at}</p>{event.prid && <p className="text-xs">PIB release {event.prid}{event.issuing_ministry ? ` · ${event.issuing_ministry}` : ""} · source: {event.source_relevance || "unverified"}</p>}<p className="text-xs">Commodity: {event.commodity_relevance} · classification: {event.classification_status}{event.content_status ? ` · content: ${event.content_status}` : ""}{event.text_representation ? ` · text source: ${event.text_representation}` : ""}{event.text_imported_at ? ` · text imported: ${event.text_imported_at}` : ""}</p>{event.date_mentions?.map((item, i) => <p key={`${item.role}-${i}`} className="text-xs">Mentioned date: {item.normalized_date || item.text} · {item.role.replaceAll("_", " ")}</p>)}{event.event_classifications?.map(item => <section key={item.category} className="mt-2"><p className="font-medium">{item.category} · experimental</p>{item.evidence.map(ev => <blockquote key={`${ev.start}-${ev.end}`} className="border-l-2 pl-2 text-xs">“{ev.text}”</blockquote>)}</section>)}{event.reported_facts?.map((fact, i) => <section key={`${fact.kind}-${i}`} className="mt-2"><p className="font-medium">Reported {fact.kind.replaceAll("_", " ")}: {fact.value}{fact.period ? ` · ${fact.period}` : ""}{fact.announcement_date ? ` · announcement/publication date: ${fact.announcement_date}` : ""}</p><blockquote className="border-l-2 pl-2 text-xs">“{fact.evidence.text}”</blockquote></section>)}{event.impact_hypothesis && <p className="text-xs mt-2">Unvalidated mechanism hypothesis: {event.impact_hypothesis}</p>}{event.article_text && <details className="mt-2"><summary className="cursor-pointer text-xs">Best available source text ({event.content_status || "content status unknown"})</summary><p className="mt-2 text-xs leading-relaxed">{event.article_text}</p></details>}</article>)}
          {!eventFeed.events.some(event => `${event.title} ${event.category} ${event.geographic_relevance}`.toLowerCase().includes(newsQuery.toLowerCase())) && <p>No matching source captures.</p>}
        </> : <p>{eventFeed?.reason || "No verified official event captures are stored."} Semantic embeddings are unavailable; Model B is not a validated price predictor.</p>}
        <p className="text-xs"><a href="/review" className="underline underline-offset-4">Open local article review workspace</a> · Human review is explicit and append-only.</p>
        <p>News relevance is evidence of association, not proof of price causation. Retrieval and classification depend on source coverage.</p>
      </Panel>
      <Panel title="Market drivers, risk and volatility">
        <p>Observed price-change volatility: {number(market?.volatility, true)}</p>
        <p>Weather and arrivals are not yet available.</p>
        {forecast?.explanation ? <><p>{forecast.explanation.description}</p>{forecast.explanation.features.length > 0 && <ul className="space-y-2">{forecast.explanation.features.map(feature => <li key={feature.feature}>{feature.feature}: {number(feature.contribution)} INR/quintal</li>)}</ul>}</> : <p>Feature contributions require an available forecast.</p>}
        <p>Missing market dates are not interpolated. Forecasts target exact calendar dates.</p>
      </Panel>
    </div>
  </div>;
}
