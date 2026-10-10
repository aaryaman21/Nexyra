"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { agriRequest } from "@/lib/agri-api";
import { ThemeToggle } from "@/components/ThemeToggle";

type Evidence = { text: string };
type Prediction = { category: string; evidence?: Evidence[] };
type DateMention = { normalized_date?: string | null; text?: string; role: string };
type HumanEvent = { category: string; decision: "approved" | "corrected" | "added"; source_prediction_category?: string; evidence: { quote: string }[]; dates: { date: string; role: string }[] };
type Decision = { prediction_category: string; decision: "approved" | "rejected" | "corrected" | "unsupported"; corrected_category?: string };
type SavedReview = { review_id: string; capture_id: string; reviewer_id: string; reviewed_at_utc: string; supersedes_review_id?: string | null; payload: Record<string, unknown> };
type Article = {
  id: string; article_identity: string; title: string; url: string; source: string; published_date?: string;
  publication_precision?: string; issuing_ministry?: string; prid?: string; article_text?: string;
  content_status?: string; text_content_sha256?: string; normalized_content_sha256?: string;
  title_status?: string; publication_metadata_status?: string; source_url_status?: string;
  relevance_status?: string; commodity_relevance?: string; geographic_relevance?: string;
  event_classifications: Prediction[]; date_mentions?: DateMention[]; review_status: string;
  review_history: SavedReview[]; evaluation_group_key?: string;
};
type Queue = { status?: "ready" | "empty" | "unavailable"; reason?: string; events: Article[]; dataset_health?: { unique_articles: number; human_reviewed_articles: number } };
type Evaluation = { status: string; review_history_records: number; reviewed_article_count: number; eligible_article_count: number; metrics?: Record<string, unknown> | null; exclusions?: Record<string, number>; warning?: string; message?: string };

const taxonomy = ["export_duty_reduction", "export_duty_increase", "export_restriction_removal", "export_restriction_introduction", "mep_introduction", "mep_revision", "government_procurement", "buffer_stock_release", "market_arrivals", "market_price_report", "production_estimate", "crop_damage", "extreme_weather", "storage_logistics_disruption", "supply_shortage", "demand_event", "reported_export_volume"];
const inputClass = "input-field w-full rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-950/50 dark:text-slate-100";
const buttonClass = "rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 transition hover:border-cyan-500 hover:text-cyan-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-100";

function latest(article: Article) {
  const checksum = article.normalized_content_sha256 || article.text_content_sha256;
  return article.review_history?.find(review => review.capture_id === article.id
    && review.payload.source_content_sha256 === checksum);
}

export function EventReviewWorkspace() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [relevance, setRelevance] = useState("");
  const [commodity, setCommodity] = useState("");
  const [geography, setGeography] = useState("");
  const [publicationCorrectness, setPublicationCorrectness] = useState("");
  const [correctedPublication, setCorrectedPublication] = useState("");
  const [decisions, setDecisions] = useState<Record<string, Decision["decision"]>>({});
  const [correctedCategories, setCorrectedCategories] = useState<Record<string, string>>({});
  const [events, setEvents] = useState<HumanEvent[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const saveInFlight = useRef(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const selected = useMemo(() => queue?.events.find(item => item.id === selectedId) || null, [queue, selectedId]);
  const selectedReview = selected ? latest(selected) : undefined;
  const pendingCount = queue?.events.filter(item => item.review_status === "pending").length || 0;
  const completedArticles = queue?.events.filter(item => item.review_status !== "pending") || [];

  const load = useCallback(async (keepId?: string) => {
    setError("");
    setLoadingQueue(true);
    try {
      const data = await agriRequest<Queue>("review/queue?limit=200");
      if (!data || !Array.isArray(data.events)) throw new Error("The review API returned an invalid queue response.");
      if (data.status === "unavailable") throw new Error(data.reason || "The review API could not read the saved article archive.");
      setQueue(data);
      setSelectedId(previous => keepId && data.events.some(row => row.id === keepId) ? keepId : previous && data.events.some(row => row.id === previous) ? previous : data.events[0]?.id || "");
      const currentEvaluation = await agriRequest<Evaluation>("review/evaluation");
      setEvaluation(currentEvaluation);
    } catch (err) { setError(err instanceof Error ? err.message : "Review queue could not be loaded."); }
    finally { setLoadingQueue(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!loadingQueue) window.dispatchEvent(new Event("nexyra:review-ready"));
  }, [loadingQueue]);

  useEffect(() => {
    if (!selected) return;
    const saved = latest(selected)?.payload;
    const savedEvents = Array.isArray(saved?.events) ? saved.events as HumanEvent[] : [];
    const savedDecisions = Array.isArray(saved?.classification_decisions) ? saved.classification_decisions as Decision[] : [];
    setReviewer("");
    setRelevance(typeof saved?.relevance === "string" ? saved.relevance : "");
    setCommodity(typeof saved?.commodity_relevance === "string" ? saved.commodity_relevance : "");
    setGeography(typeof saved?.geographic_relevance === "string" ? saved.geographic_relevance : "");
    const pub = saved?.publication_date_review as { correctness?: string; gold_date?: string | null } | undefined;
    setPublicationCorrectness(pub?.correctness || "");
    setCorrectedPublication(pub?.gold_date || "");
    setDecisions(Object.fromEntries(savedDecisions.map(row => [row.prediction_category, row.decision])));
    setCorrectedCategories(Object.fromEntries(savedDecisions.filter(row => row.corrected_category).map(row => [row.prediction_category, row.corrected_category!])));
    setEvents(savedEvents.map(event => ({...event, evidence: event.evidence || [], dates: event.dates || []})));
    setNotes(typeof saved?.notes === "string" ? saved.notes : "");
  }, [selected]);

  const markPrediction = (prediction: Prediction, decision: Decision["decision"]) => {
    if (!selected) return;
    setDecisions(current => ({ ...current, [prediction.category]: decision }));
    setEvents(current => {
      const without = current.filter(event => event.source_prediction_category !== prediction.category);
      if (decision === "rejected" || decision === "unsupported") return without;
      const category = decision === "corrected" ? correctedCategories[prediction.category] || prediction.category : prediction.category;
      return [...without, { category, decision: decision === "corrected" ? "corrected" : "approved", source_prediction_category: prediction.category,
        // Predictions may cite the headline as well as body text. Review
        // evidence must be an exact span in the saved article body.
        evidence: (prediction.evidence || []).filter(item => !!selected.article_text?.includes(item.text)).map(item => ({ quote: item.text })), dates: [] }];
    });
  };

  const updateEvent = (index: number, update: Partial<HumanEvent>) => setEvents(current => current.map((event, position) => position === index ? { ...event, ...update } : event));
  const save = async () => {
    if (!selected || saveInFlight.current || !canSave) return;
    saveInFlight.current = true;
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = {
        reviewer_id: reviewer.trim(), relevance, commodity_relevance: commodity, geographic_relevance: geography,
        publication_date_correctness: publicationCorrectness,
        corrected_publication_date: publicationCorrectness === "incorrect" ? correctedPublication : null,
        classification_decisions: selected.event_classifications.map(prediction => ({
          prediction_category: prediction.category, decision: decisions[prediction.category],
          corrected_category: decisions[prediction.category] === "corrected" ? correctedCategories[prediction.category] : null,
        })), events, notes,
      };
      const result = await agriRequest<{ review_count: number; reviewed_at_utc: string }>(`review/articles/${selected.id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (result.review_count !== 1 || !result.reviewed_at_utc) throw new Error("The API did not confirm that a review was persisted. Check the queue and history before retrying.");
      setMessage(`Review saved at ${result.reviewed_at_utc}. A new append-only history entry was created.`);
      await load(selected.id);
    } catch (err) { setError(err instanceof Error ? err.message : "Review was not saved."); }
    finally { saveInFlight.current = false; setBusy(false); }
  };

  const canSave = !!selected && !!reviewer.trim() && !!relevance && !!commodity && !!geography && !!publicationCorrectness &&
    (publicationCorrectness !== "incorrect" || /^\d{4}-\d{2}-\d{2}$/.test(correctedPublication)) &&
    selected.event_classifications.every(item => !!decisions[item.category]) &&
    (relevance !== "relevant" || (events.length > 0 && events.every(event => !!event.category && event.evidence.length > 0 &&
      event.evidence.every(evidence => !!evidence.quote.trim() && !!selected.article_text?.includes(evidence.quote)) &&
      event.dates.every(date => /^\d{4}-\d{2}-\d{2}$/.test(date.date) && !Number.isNaN(Date.parse(`${date.date}T00:00:00Z`)) && !!date.role.trim()))));

  const validationMessages = !selected ? [] : [
    ...(!reviewer.trim() ? ["Enter your reviewer identifier."] : []),
    ...(!relevance ? ["Choose article relevance."] : []),
    ...(!commodity ? ["Choose commodity relevance."] : []),
    ...(!geography ? ["Choose geographic relevance."] : []),
    ...(!publicationCorrectness ? ["Review publication date extraction."] : []),
    ...(publicationCorrectness === "incorrect" && !/^\d{4}-\d{2}-\d{2}$/.test(correctedPublication) ? ["Enter the corrected publication date."] : []),
    ...selected.event_classifications.filter(item => !decisions[item.category]).map(item => `Choose an action for “${item.category}”.`),
    ...(relevance === "relevant" ? events.flatMap((event, index) => [
      ...(!event.category ? [`Choose a category for reviewed event ${index + 1}.`] : []),
      ...(event.evidence.length === 0 ? [`Add an exact supporting passage for reviewed event ${index + 1}.`] : event.evidence.flatMap((evidence, evidenceIndex) =>
        !evidence.quote.trim() ? [`Evidence ${evidenceIndex + 1} for reviewed event ${index + 1} is empty.`] : !selected.article_text?.includes(evidence.quote) ? [`Evidence ${evidenceIndex + 1} for reviewed event ${index + 1} must exactly match the saved article text.`] : [])),
      ...event.dates.flatMap((date, dateIndex) => !/^\d{4}-\d{2}-\d{2}$/.test(date.date) || Number.isNaN(Date.parse(`${date.date}T00:00:00Z`))
        ? [`Enter a valid date for event ${index + 1}, date ${dateIndex + 1}.`] : !date.role.trim() ? [`Enter a date role for event ${index + 1}, date ${dateIndex + 1}.`] : []),
    ]) : []),
  ];

  return <main className="min-h-screen px-4 py-8 text-slate-800 dark:text-slate-100 sm:px-6 lg:px-8">
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="font-mono text-xs uppercase tracking-[.2em] text-cyan-600 dark:text-cyan-400">NEXYRA · MODEL B</p><h1 className="mt-1 text-2xl font-semibold">Article review</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Local review workspace · experimental predictions remain separate from human labels.</p></div>
        <div className="flex items-center gap-2"><ThemeToggle /><a className={buttonClass} href="/">Return to observatory</a></div>
      </header>

      <section className="glass-panel space-y-2 rounded-2xl p-4 text-sm" role="note">
        <p><strong>Explicit local review only.</strong> Enter your own reviewer identifier. Nexyra records the actual submission time. Nothing is approved until you save a review.</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">Existing articles were used during development; their reviews remain descriptive and cannot be called an independent test set. No accuracy score is available until eligible human labels exist.</p>
        {queue?.dataset_health && <p className="text-xs">{queue.dataset_health.unique_articles} source articles · {queue.dataset_health.human_reviewed_articles} currently reviewed · every correction is retained in history.</p>}
        {evaluation && <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-700"><p><strong>Evaluation status:</strong> {evaluation.status.replaceAll("_", " ")} · {evaluation.reviewed_article_count} reviewed · {evaluation.eligible_article_count} eligible for descriptive scoring.</p>{evaluation.metrics ? <details className="mt-1"><summary className="cursor-pointer">View metric counts and denominators</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap">{JSON.stringify(evaluation.metrics, null, 2)}</pre></details> : <p className="mt-1">Metrics unavailable because no matching human-reviewed labels are eligible. {evaluation.message}</p>}{evaluation.warning && <p className="mt-1">{evaluation.warning}</p>}</div>}
      </section>

      {error && !selected && <p className="glass-panel rounded-xl border border-rose-400/50 p-3 text-sm" role="alert">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(15rem,0.32fr)_minmax(0,1fr)]">
        <aside className="glass-panel max-h-[75vh] space-y-3 overflow-auto rounded-2xl p-4" aria-label="Article review queue">
          <div className="flex items-center justify-between gap-2"><div><h2 className="font-semibold">Review queue</h2><p className="text-xs text-slate-500">{queue ? `${pendingCount} awaiting review · oldest pending articles first` : loadingQueue ? "Loading saved articles…" : "Queue unavailable"}</p></div><button className={buttonClass} onClick={() => void load(selectedId)}>Refresh</button></div>
          {queue?.events.filter(article => article.review_status === "pending").map(article => <button key={article.id} type="button" onClick={() => { setError(""); setMessage(""); setSelectedId(article.id); }} className={`block w-full rounded-xl border p-3 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-500 ${selectedId === article.id ? "border-cyan-500 bg-cyan-500/10" : "border-slate-200 dark:border-slate-700"}`}>
            <span className="block text-sm font-medium">{article.title}</span>
            <span className="mt-1 block text-xs text-slate-500">{article.published_date || "Date unavailable"} · {article.source || "Source unavailable"}</span>
            <span className="mt-1 block text-xs text-slate-500">Predicted: {article.event_classifications.length ? article.event_classifications.map(item => item.category).join(", ") : "no event categories"}</span>
            <span className={`mt-1 block text-xs font-medium ${article.review_status === "pending" ? "text-amber-700 dark:text-amber-300" : "text-emerald-700 dark:text-emerald-300"}`}>{article.review_status === "pending" ? "Awaiting review" : "Reviewed"}</span>
          </button>)}
          {!loadingQueue && !error && queue && pendingCount === 0 && <p className="text-sm text-emerald-700 dark:text-emerald-300">All current articles have a saved review.</p>}
          {!!completedArticles.length && <details className="border-t border-slate-200 pt-3 dark:border-slate-700"><summary className="cursor-pointer text-sm font-medium">Completed reviews ({completedArticles.length})</summary><div className="mt-3 space-y-2">{completedArticles.map(article => <button key={article.id} type="button" onClick={() => { setError(""); setMessage(""); setSelectedId(article.id); }} className={`block w-full rounded-xl border p-3 text-left transition ${selectedId === article.id ? "border-cyan-500 bg-cyan-500/10" : "border-slate-200 dark:border-slate-700"}`}><span className="block text-sm font-medium">{article.title}</span><span className="mt-1 block text-xs text-slate-500">{article.published_date || "Date unavailable"} · {article.review_history.find(review => review.capture_id === article.id)?.reviewed_at_utc || "Saved review"}</span><span className="mt-1 block text-xs text-emerald-700 dark:text-emerald-300">Completed · read-only</span></button>)}</div></details>}
          {!loadingQueue && !error && queue?.status === "empty" && queue.events.length === 0 && <p className="text-sm text-slate-500">No saved source articles are available to review.</p>}
        </aside>

        {selected ? <article className="space-y-5">
          <section className="glass-panel space-y-2 rounded-2xl p-5">
            <h2 className="text-xl font-semibold">{selected.title}</h2>
            <p className="text-sm">{selected.source}{selected.issuing_ministry ? ` · ${selected.issuing_ministry}` : ""}</p>
            <p className="text-xs text-slate-500">Publication: {selected.published_date || "not supplied"} ({selected.publication_precision || "date precision unknown"}) · {selected.prid ? `PIB PRID ${selected.prid} · ` : ""}Content: {selected.content_status || "unknown"}</p>
            {(selected.title_status || selected.publication_metadata_status || selected.source_url_status) && <p className="text-xs text-slate-500">Metadata provenance: headline {selected.title_status || "source capture"} · publication {selected.publication_metadata_status || "source capture"} · URL {selected.source_url_status || "source capture"}</p>}
            <p className="break-all text-xs"><a className="underline" href={selected.url} target="_blank" rel="noopener noreferrer">Open original source</a> · Revision checksum: {selected.normalized_content_sha256 || selected.text_content_sha256 || "unavailable"} · Evaluation group: {selected.evaluation_group_key || "unassigned"}</p>
            <details className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><summary className="cursor-pointer font-medium">Read saved article text</summary><p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{selected.article_text || "No full text available."}</p></details>
          </section>

          {selectedReview && <section className="glass-panel space-y-3 rounded-2xl p-5" aria-label="Saved human review">
            <h2 className="font-semibold text-emerald-700 dark:text-emerald-300">Review saved · read-only</h2>
            {message && <p className="rounded-xl border border-emerald-400/50 p-3 text-sm" role="status">{message}</p>}
            <p className="text-xs text-slate-500">Reviewer: {selectedReview.reviewer_id} · saved {selectedReview.reviewed_at_utc} · append-only history retained.</p>
            <p>Article: {String(selectedReview.payload.relevance || "not recorded")} · commodity: {String(selectedReview.payload.commodity_relevance || "not recorded")} · geography: {String(selectedReview.payload.geographic_relevance || "not recorded")}</p>
            <p>Publication date extraction: {String((selectedReview.payload.publication_date_review as { correctness?: string } | undefined)?.correctness || "not recorded")}</p>
            {(Array.isArray(selectedReview.payload.classification_decisions) ? selectedReview.payload.classification_decisions as Decision[] : []).map(decision => <p key={decision.prediction_category}>Prediction {decision.prediction_category}: {decision.decision}{decision.corrected_category ? ` → ${decision.corrected_category}` : ""}</p>)}
            {(Array.isArray(selectedReview.payload.events) ? selectedReview.payload.events as HumanEvent[] : []).map((event, index) => <div key={`${event.category}-${index}`} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><p className="font-medium">{event.category}</p>{event.evidence.map((item, n) => <blockquote key={n} className="mt-2 border-l-2 border-cyan-500 pl-3 text-xs">“{item.quote}”</blockquote>)}{event.dates.map((date, n) => <p key={n} className="mt-2 text-xs">{date.date} · {date.role}</p>)}</div>)}
            {!!selectedReview.payload.notes && <p className="text-sm">Notes: {String(selectedReview.payload.notes)}</p>}
          </section>}
          {!selectedReview && <>
          <section className="glass-panel space-y-4 rounded-2xl p-5">
            <h2 className="font-semibold">Article-level review</h2>
            <label className="block text-sm">Your reviewer identifier<input aria-invalid={!reviewer.trim()} className={`${inputClass} mt-1`} value={reviewer} onChange={event => setReviewer(event.target.value)} autoComplete="off" />{!reviewer.trim() && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Enter a reviewer identifier to save.</span>}</label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">Article relevance<select aria-invalid={!relevance} className={`${inputClass} mt-1`} value={relevance} onChange={event => setRelevance(event.target.value)}><option value="">Choose review</option><option value="relevant">Relevant</option><option value="irrelevant">Irrelevant</option><option value="uncertain">Uncertain</option></select>{!relevance && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Choose article relevance.</span>}</label>
              <label className="text-sm">Commodity relevance<select aria-invalid={!commodity} className={`${inputClass} mt-1`} value={commodity} onChange={event => setCommodity(event.target.value)}><option value="">Choose review</option><option value="onion_direct">Onion direct</option><option value="onion_related">Onion related</option><option value="other_agriculture">Other agriculture</option><option value="unrelated">Unrelated</option><option value="uncertain">Uncertain</option></select>{!commodity && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Choose commodity relevance.</span>}</label>
              <label className="text-sm">Geographic relevance<select aria-invalid={!geography} className={`${inputClass} mt-1`} value={geography} onChange={event => setGeography(event.target.value)}><option value="">Choose review</option><option value="Nashik">Nashik</option><option value="Maharashtra">Maharashtra</option><option value="India-wide">India-wide</option><option value="international">International</option><option value="unrelated">Unrelated</option><option value="uncertain">Uncertain</option></select>{!geography && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Choose geographic relevance.</span>}</label>
              <label className="text-sm">Publication date extraction<select aria-invalid={!publicationCorrectness} className={`${inputClass} mt-1`} value={publicationCorrectness} onChange={event => setPublicationCorrectness(event.target.value)}><option value="">Choose review</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option><option value="uncertain">Uncertain</option></select>{!publicationCorrectness && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Review publication date extraction.</span>}</label>
              {publicationCorrectness === "incorrect" && <label className="text-sm">Correct source-supported publication date<input aria-invalid={!/^\d{4}-\d{2}-\d{2}$/.test(correctedPublication)} className={`${inputClass} mt-1`} type="date" value={correctedPublication} onChange={event => setCorrectedPublication(event.target.value)} />{!/^\d{4}-\d{2}-\d{2}$/.test(correctedPublication) && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Enter the corrected publication date.</span>}</label>}
            </div>
          </section>

          <section className="glass-panel space-y-4 rounded-2xl p-5">
            <h2 className="font-semibold">Predicted event classifications</h2>
            <p className="text-xs text-slate-500">Choose one action for every prediction. Evidence edits must remain exact text from the saved article.</p>
            {selected.event_classifications.map(prediction => <div key={prediction.category} className="space-y-2 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
              <p className="font-medium">{prediction.category} <span className="text-xs text-slate-500">· unvalidated prediction</span></p>
              {prediction.evidence?.map(item => <blockquote key={item.text} className="border-l-2 border-cyan-500 pl-3 text-xs">“{item.text}”</blockquote>)}
              <div className="flex flex-wrap gap-2">{(["approved", "rejected", "unsupported", "corrected"] as const).map(action => <button key={action} type="button" aria-pressed={decisions[prediction.category] === action} className={`${buttonClass} ${decisions[prediction.category] === action ? "border-cyan-500 bg-cyan-500/10" : ""}`} onClick={() => markPrediction(prediction, action)}>{action[0].toUpperCase() + action.slice(1)}</button>)}</div>
              {!decisions[prediction.category] && <p className="text-xs text-amber-700 dark:text-amber-300">Choose an action for this prediction.</p>}
              {decisions[prediction.category] === "corrected" && <label className="block text-sm">Correct category<select className={`${inputClass} mt-1`} value={correctedCategories[prediction.category] || ""} onChange={event => { const value = event.target.value; setCorrectedCategories(current => ({ ...current, [prediction.category]: value })); setEvents(current => current.map(item => item.source_prediction_category === prediction.category ? { ...item, category: value } : item)); }}><option value="">Choose category</option>{taxonomy.map(category => <option key={category} value={category}>{category}</option>)}</select></label>}
            </div>)}
            {selected.event_classifications.length === 0 && <p className="text-sm text-slate-500">No event categories were predicted; your article-level decision still needs review.</p>}
          </section>

          <section className="glass-panel space-y-3 rounded-2xl p-5">
            <h2 className="font-semibold">Predicted date mentions · reference only</h2>
            {selected.date_mentions?.length ? selected.date_mentions.map((mention, index) => <div key={`${mention.role}-${index}`} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700"><p>{mention.text} · predicted role: {mention.role}</p><p className="text-xs text-slate-500">Normalized date: {mention.normalized_date || "not normalized"}</p></div>) : <p className="text-sm text-slate-500">No date mentions were predicted. Publication date and event effective dates must be reviewed separately.</p>}
          </section>

          <section className="glass-panel space-y-4 rounded-2xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Reviewed event evidence and dates</h2><button type="button" className={buttonClass} onClick={() => setEvents(current => [...current, { category: "", decision: "added", evidence: [{ quote: "" }], dates: [] }])}>Add event</button></div>
            {events.map((event, index) => <div key={`${event.source_prediction_category || "added"}-${index}`} className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
              <label className="block text-sm">Reviewed category<select aria-invalid={!event.category} className={`${inputClass} mt-1`} value={event.category} onChange={change => updateEvent(index, { category: change.target.value })}><option value="">Choose category</option>{taxonomy.map(category => <option key={category} value={category}>{category}</option>)}</select>{!event.category && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Choose the reviewed event category.</span>}</label>
              {event.evidence.map((evidence, evidenceIndex) => <label key={evidenceIndex} className="block text-sm">Exact supporting passage<textarea aria-invalid={!evidence.quote.trim() || !selected.article_text?.includes(evidence.quote)} className={`${inputClass} mt-1 min-h-20`} value={evidence.quote} onChange={change => updateEvent(index, { evidence: event.evidence.map((item, n) => n === evidenceIndex ? { quote: change.target.value } : item) })} />{!evidence.quote.trim() ? <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">This passage is required.</span> : !selected.article_text?.includes(evidence.quote) ? <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Use an exact passage from the saved article text; headline-only text is not accepted.</span> : null}</label>)}
              <button type="button" className={buttonClass} onClick={() => updateEvent(index, { evidence: [...event.evidence, { quote: "" }] })}>Add evidence passage</button>
              <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">{event.dates.map((date, dateIndex) => <div key={dateIndex} className="contents"><label className="text-sm">Source-supported date<input aria-invalid={!/^\d{4}-\d{2}-\d{2}$/.test(date.date) || Number.isNaN(Date.parse(`${date.date}T00:00:00Z`))} className={`${inputClass} mt-1`} type="date" value={date.date} onChange={change => updateEvent(index, { dates: event.dates.map((item, n) => n === dateIndex ? { ...item, date: change.target.value } : item) })} />{(!/^\d{4}-\d{2}-\d{2}$/.test(date.date) || Number.isNaN(Date.parse(`${date.date}T00:00:00Z`))) && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Enter a valid YYYY-MM-DD date.</span>}</label><label className="text-sm">Date role<input aria-invalid={!date.role.trim()} className={`${inputClass} mt-1`} value={date.role} onChange={change => updateEvent(index, { dates: event.dates.map((item, n) => n === dateIndex ? { ...item, role: change.target.value } : item) })} placeholder="effective_date" />{!date.role.trim() && <span className="mt-1 block text-xs text-amber-700 dark:text-amber-300">Enter what this date represents.</span>}</label><button className={buttonClass} type="button" aria-label="Remove reviewed date" onClick={() => updateEvent(index, { dates: event.dates.filter((_, n) => n !== dateIndex) })}>Remove date</button></div>)}</div>
              <button type="button" className={buttonClass} onClick={() => updateEvent(index, { dates: [...event.dates, { date: "", role: "" }] })}>Add date mention</button>
              <button type="button" className="ml-2 rounded-xl px-3 py-2 text-sm text-rose-700 hover:bg-rose-500/10 dark:text-rose-300" onClick={() => setEvents(current => current.filter((_, n) => n !== index))}>Remove event</button>
            </div>)}
            <label className="block text-sm">Reviewer notes<textarea className={`${inputClass} mt-1 min-h-20`} value={notes} onChange={event => setNotes(event.target.value)} /></label>
            {!!validationMessages.length && <ul className="space-y-1 text-xs text-amber-700 dark:text-amber-300" aria-label="Review form validation">{validationMessages.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}
            {error && <p className="rounded-xl border border-rose-400/50 p-3 text-sm text-rose-700 dark:text-rose-300" role="alert">{message ? `Review was saved, but the refreshed queue could not be loaded: ${error}` : `Review was not saved: ${error}`}</p>}
            {message && <p className="rounded-xl border border-emerald-400/50 p-3 text-sm text-emerald-700 dark:text-emerald-300" role="status">{message}</p>}
            <button type="button" className="rounded-xl bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50" disabled={!canSave || busy} onClick={() => void save()}>{busy ? "Saving review…" : latest(selected) ? "Save correction as new history entry" : "Save explicit human review"}</button>
          </section>

          </>}

          <section className="glass-panel space-y-2 rounded-2xl p-5">
            <h2 className="font-semibold">Append-only review history</h2>
            {selected.review_history.length ? selected.review_history.map(review => <div key={review.review_id} className="border-l-2 border-cyan-500 pl-3 text-xs"><p>{review.reviewer_id} · {review.reviewed_at_utc} · {review.review_id}</p><p>Capture: {review.capture_id} · Supersedes: {String(review.supersedes_review_id || "none (first review)")}</p><p>Source revision: {String(review.payload.source_content_sha256 || "unknown")}</p></div>) : <p className="text-sm text-slate-500">No human review has been recorded for this article.</p>}
          </section>
        </article> : <section className="glass-panel rounded-2xl p-6"><p>Select an article when the review queue loads.</p></section>}
      </div>
    </div>
  </main>;
}
