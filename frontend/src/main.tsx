import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  ArrowLeft,
  Bookmark,
  X,
  EyeOff,
  SlidersHorizontal,
  RotateCcw,
  Check,
  Plus,
  Minus,
} from "lucide-react";
import "./style.css";

type Item = {
  id: string;
  category: string;
  title: string;
  abstract: string;
  body: string;
  reason?: string;
  recommendation_id?: string;
};
type Feed = {
  items: Item[];
  recommendation_id: string;
  fallback: string | null;
  method: string;
  research_ready: boolean;
  model_version: string;
};
type Mode = "popular" | "content" | "personalized";
type Page = "Discover" | "Saved" | "Evaluation";
type Metric = Record<string, { mean: number | null; groups: number }>;
type Evaluation = {
  status: string;
  message?: string;
  protocol: string;
  selected?: string;
  groups?: number;
  holdout?: Record<string, Metric>;
  ci?: { ci95: number[]; mean_difference: number };
};
type Read = { item: Item; rid: string; opened: boolean };
const names: Record<string, string> = {
  science: "Science",
  health: "Health",
  finance: "Money",
  sports: "Sport",
  foodanddrink: "Food & drink",
  travel: "Travel",
  news: "Community",
  lifestyle: "Life",
};
const modeNames: Record<Mode, string> = {
  popular: "Popular",
  content: "Content-based",
  personalized: "Personalized",
};
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-FeedRank": "1",
      ...(new URLSearchParams(location.search).has("qa")
        ? { "X-FeedRank-QA": "1" }
        : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Something went wrong. Please try again.");
  }
  return response.json();
}
function App() {
  const [page, setPage] = useState<Page>("Discover");
  const [mode, setMode] = useState<Mode>("personalized");
  const [interests, setInterests] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [saved, setSaved] = useState<Item[]>([]);
  const [savedIds, setSavedIds] = useState<string[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [reading, setReading] = useState<Read | null>(null);
  const [mobileReader, setMobileReader] = useState(false);
  const [topicsOpen, setTopicsOpen] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
  const [expanded, setExpanded] = useState<string | null>("protocol");
  const [toast, setToast] = useState<{
    text: string;
    item?: Item;
    rid?: string;
    undo?: "unsave" | "unhide";
  } | null>(null);
  const generation = useRef(0);
  const dialogClose = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const readerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const session = await api<{ interests: string[] }>("/api/sessions", {
          method: "POST",
        });
        const [info, state] = await Promise.all([
          api<{ categories: string[] }>("/api/catalog-info"),
          api<{ saved: string[] }>("/api/session"),
        ]);
        if (live) {
          setInterests(session.interests);
          setCategories(info.categories);
          setSavedIds(state.saved);
          setStarted(true);
        }
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    })();
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (!started) return;
    const n = ++generation.current;
    const control = new AbortController();
    setLoading(true);
    setError("");
    (async () => {
      try {
        if (page === "Discover") {
          const data = await api<Feed>(`/api/recommendations?mode=${mode}`, {
            signal: control.signal,
          });
          if (n === generation.current) setFeed(data);
        }
        if (page === "Saved") {
          const data = await api<{ items: Item[] }>("/api/saved", {
            signal: control.signal,
          });
          if (n === generation.current) setSaved(data.items);
        }
        if (page === "Evaluation") {
          const data = await api<Evaluation>("/api/evaluation", {
            signal: control.signal,
          });
          if (n === generation.current) setEvaluation(data);
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError" && n === generation.current)
          setError((e as Error).message);
      } finally {
        if (n === generation.current) setLoading(false);
      }
    })();
    return () => control.abort();
  }, [started, page, mode, revision]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (!resetDialog) return;
    previousFocus.current = document.activeElement as HTMLElement;
    dialogClose.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") setResetDialog(false);
      if (e.key === "Tab") {
        const elements = Array.from(
          document.querySelectorAll<HTMLButtonElement>(
            '[role="dialog"] button',
          ),
        );
        const first = elements[0],
          last = elements[elements.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      previousFocus.current?.focus();
    };
  }, [resetDialog]);
  useEffect(() => {
    if (mobileReader) readerRef.current?.focus();
  }, [mobileReader]);
  async function preferences(cat: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    const next = interests.includes(cat)
      ? interests.filter((x) => x !== cat)
      : [...interests, cat];
    try {
      await api("/api/session/preferences", {
        method: "PUT",
        body: JSON.stringify({ interests: next }),
      });
      setInterests(next);
      setRevision((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function event(
    item: Item,
    type: "open" | "save" | "hide" | "unsave" | "unhide",
    rid: string,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    const payload = JSON.stringify({
      event_id: crypto.randomUUID(),
      item_id: item.id,
      event_type: type,
      recommendation_id: rid,
    });
    try {
      try {
        await api("/api/events", { method: "POST", body: payload });
      } catch (e) {
        if (e instanceof TypeError)
          await api("/api/events", { method: "POST", body: payload });
        else throw e;
      }
      if (type === "open") {
        setReading({ item, rid, opened: true });
        setMobileReader(true);
      }
      if (type === "save")
        setSavedIds((ids) => [...new Set([...ids, item.id])]);
      if (type === "unsave")
        setSavedIds((ids) => ids.filter((id) => id !== item.id));
      if (type === "save" || type === "hide")
        setToast({
          text: type === "save" ? "Added to saved" : "Hidden from your feed",
          item,
          rid,
          undo: type === "save" ? "unsave" : "unhide",
        });
      if (type === "unsave" || type === "unhide")
        setToast({
          text: type === "unsave" ? "Removed from saved" : "Back in your feed",
        });
      setRevision((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reset() {
    setBusy(true);
    setError("");
    try {
      await api("/api/session/history", { method: "DELETE" });
      setInterests([]);
      setSavedIds([]);
      setSaved([]);
      setReading(null);
      setMobileReader(false);
      setToast(null);
      setResetDialog(false);
      setRevision((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function navigate(next: Page) {
    setPage(next);
    setReading(null);
    setMobileReader(false);
    setTopicsOpen(false);
    setError("");
  }
  const rows = page === "Saved" ? saved : feed?.items || [];
  const lead =
    reading ||
    (rows[0]
      ? {
          item: rows[0],
          rid: rows[0].recommendation_id || feed?.recommendation_id || "",
          opened: false,
        }
      : null);
  const isSaved = lead ? savedIds.includes(lead.item.id) : false;
  return (
    <div className="shell">
      <a href="#main" className="skip">
        Skip to content
      </a>
      <header className="masthead">
        <button
          className="wordmark"
          onClick={() => navigate("Discover")}
          aria-label="FeedRank home"
        >
          feedrank
          <span className="brand-square" />
        </button>
        <nav aria-label="Main navigation">
          {(["Discover", "Saved", "Evaluation"] as Page[]).map((p) => (
            <button
              key={p}
              className={page === p ? "nav-link current" : "nav-link"}
              aria-current={page === p ? "page" : undefined}
              onClick={() => navigate(p)}
            >
              {p}
              {p === "Saved" && savedIds.length > 0 && (
                <span className="nav-count">{savedIds.length}</span>
              )}
            </button>
          ))}
        </nav>
        <button
          className="session-reset"
          onClick={() => setResetDialog(true)}
          aria-label="Reset session"
        >
          <RotateCcw size={14} />
          <span>Reset session</span>
        </button>
      </header>
      <main
        id="main"
        className={mobileReader ? "main reader-visible" : "main"}
        tabIndex={-1}
      >
        <div className="page-top">
          <div className="page-title">
            <h1>
              {page === "Discover"
                ? "Discover."
                : page === "Saved"
                  ? "Saved."
                  : "Evaluation."}
            </h1>
            <span>
              {page === "Discover"
                ? "48 demo reads across eight subjects."
                : page === "Saved"
                  ? "Keep something for later."
                  : "Methods, results and limitations."}
            </span>
          </div>
          {page === "Discover" && (
            <div className="feed-controls">
              <div className="select-field">
                <label htmlFor="method">Sort by</label>
                <select
                  id="method"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as Mode)}
                >
                  {Object.entries(modeNames).map(([key, name]) => (
                    <option key={key} value={key}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className={
                  topicsOpen ? "interest-toggle is-open" : "interest-toggle"
                }
                onClick={() => setTopicsOpen(!topicsOpen)}
                aria-expanded={topicsOpen}
                aria-controls="topic-panel"
              >
                <SlidersHorizontal size={16} />
                Interests
                {interests.length > 0 && <span>{interests.length}</span>}
              </button>
            </div>
          )}
        </div>
        {page === "Discover" && topicsOpen && (
          <section
            className="topic-panel"
            id="topic-panel"
            aria-label="Choose interests"
          >
            <div>
              <h2>Choose your interests.</h2>
              <p>
                Pick the subjects you want more of. Leave all unchecked to
                explore everything.
              </p>
            </div>
            <div className="topic-options">
              {categories.map((c) => (
                <label key={c}>
                  <input
                    type="checkbox"
                    checked={interests.includes(c)}
                    disabled={busy}
                    onChange={() => preferences(c)}
                  />
                  <span>{names[c] || c}</span>
                </label>
              ))}
            </div>
            <button
              className="text-action"
              onClick={() => setTopicsOpen(false)}
            >
              Done <Check size={15} />
            </button>
          </section>
        )}
        {error && (
          <div role="alert" className="error-line">
            <span>{error}</span>
            <button
              onClick={() =>
                started ? setRevision((v) => v + 1) : location.reload()
              }
            >
              Try again
            </button>
          </div>
        )}
        {page === "Discover" && feed?.fallback && (
          <div role="status" className="fallback-line">
            <span>
              {!feed.research_ready
                ? "Research model unavailable. Content matching is active."
                : feed.fallback}
            </span>
            <button onClick={() => navigate("Evaluation")}>
              Details <ArrowUpRight size={12} />
            </button>
          </div>
        )}
        {page !== "Evaluation" && (
          <div className="reading-layout">
            <section
              className="queue"
              aria-label={
                page === "Saved" ? "Saved reads" : "Recommended reads"
              }
              aria-busy={loading}
            >
              <div className="queue-caption">
                <span>
                  {page === "Saved"
                    ? `${saved.length} saved ${saved.length === 1 ? "read" : "reads"}`
                    : "Your next reads"}
                </span>
                <span>
                  {loading
                    ? "Updating…"
                    : page === "Discover"
                      ? feed?.fallback
                        ? `${feed.method === "content" ? "Content-based" : feed.method === "popular" ? "Popular" : modeNames[mode]} fallback`
                        : `${modeNames[mode]} order`
                      : ""}
                </span>
              </div>
              {!started || (loading && !rows.length) ? (
                <div className="loading-state" role="status">
                  Loading your reads<span>…</span>
                </div>
              ) : rows.length ? (
                rows.map((item, index) => {
                  const rid =
                    item.recommendation_id || feed?.recommendation_id || "";
                  const saved = savedIds.includes(item.id);
                  return (
                    <article className="story-row" key={item.id}>
                      <span className="story-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div className="story-copy">
                        <div className="story-meta">
                          <span>{names[item.category] || item.category}</span>
                          {item.reason && (
                            <span className="story-reason">
                              {item.reason === "Balanced demo selection"
                                ? "From the collection"
                                : item.reason}
                            </span>
                          )}
                        </div>
                        <h2>
                          <button
                            disabled={busy || loading}
                            onClick={() => event(item, "open", rid)}
                          >
                            {item.title}
                          </button>
                        </h2>
                        <p>{item.abstract}</p>
                        <div className="story-actions">
                          <button
                            className="read-link"
                            disabled={busy || loading}
                            onClick={() => event(item, "open", rid)}
                          >
                            Read <ArrowRight size={14} />
                          </button>
                          <div>
                            <button
                              className={saved ? "row-icon saved" : "row-icon"}
                              title={saved ? "Remove from saved" : "Save read"}
                              aria-label={`${saved ? "Unsave" : "Save"} ${item.title}`}
                              disabled={busy || loading}
                              onClick={() =>
                                event(item, saved ? "unsave" : "save", rid)
                              }
                            >
                              <Bookmark
                                size={16}
                                fill={saved ? "currentColor" : "none"}
                              />
                            </button>
                            {page === "Discover" && (
                              <button
                                className="row-icon"
                                aria-label={`Hide ${item.title}`}
                                disabled={busy || loading}
                                onClick={() => event(item, "hide", rid)}
                              >
                                <EyeOff size={16} />
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })
              ) : (
                <div className="empty-state">
                  <span className="empty-dash">—</span>
                  <h2>
                    {page === "Saved"
                      ? "Your reading list is empty."
                      : "You’ve reached the end."}
                  </h2>
                  <p>
                    {page === "Saved"
                      ? "Use the bookmark beside a read to keep it here."
                      : "Reset your session to start again with this collection."}
                  </p>
                  <button
                    className="solid-button"
                    onClick={() =>
                      page === "Saved"
                        ? navigate("Discover")
                        : setResetDialog(true)
                    }
                  >
                    {page === "Saved" ? "Find a read" : "Start again"}
                    <ArrowRight size={15} />
                  </button>
                </div>
              )}
            </section>
            <aside
              ref={readerRef}
              tabIndex={-1}
              className={lead?.opened ? "reader is-reading" : "reader"}
              aria-label="Reading pane"
            >
              <button
                className="reader-back"
                onClick={() => setMobileReader(false)}
              >
                <ArrowLeft size={16} />
                Back to the feed
              </button>
              {lead ? (
                <>
                  <div className="reader-label">
                    <span>{lead.opened ? "NOW READING" : "READ NEXT"}</span>
                    <span>
                      {names[lead.item.category] || lead.item.category}
                    </span>
                  </div>
                  <h2>{lead.item.title}</h2>
                  <p className="reader-abstract">{lead.item.abstract}</p>
                  {lead.opened ? (
                    <>
                      <div className="reader-rule" />
                      <p className="reader-body">{lead.item.body}</p>
                      <div className="reading-end">
                        <span />
                        End of demo read
                      </div>
                      <button
                        className="reader-save"
                        disabled={busy}
                        onClick={() =>
                          event(
                            lead.item,
                            isSaved ? "unsave" : "save",
                            lead.rid,
                          )
                        }
                      >
                        <Bookmark
                          size={16}
                          fill={isSaved ? "currentColor" : "none"}
                        />
                        {isSaved ? "Saved. Remove?" : "Save for later"}
                      </button>
                    </>
                  ) : (
                    <button
                      className="solid-button"
                      disabled={busy || loading}
                      onClick={() => event(lead.item, "open", lead.rid)}
                    >
                      Open this read <ArrowUpRight size={17} />
                    </button>
                  )}
                </>
              ) : (
                <div className="reader-placeholder">
                  <span className="placeholder-bracket">[ ]</span>
                  <p>Select a read from the feed.</p>
                </div>
              )}
              <div className="collection-note">
                <span>THE COLLECTION</span>
                <p>
                  Original demo summaries.
                  <br />
                  Evergreen ideas, not live news.
                </p>
                <button onClick={() => navigate("Evaluation")}>
                  About the recommendations <ArrowUpRight size={12} />
                </button>
              </div>
            </aside>
          </div>
        )}
        {page === "Evaluation" && (
          <div className="evaluation-layout">
            <section className="evaluation-main">
              <div className="evaluation-summary">
                <span className="section-label">RESEARCH STATUS</span>
                <h2>
                  {evaluation?.status === "measured"
                    ? "The results are in."
                    : "Research evaluation pending."}
                </h2>
                <p>
                  {evaluation?.status === "measured"
                    ? "Complete logged candidate sets. Official validation is used as the final holdout, not an official test."
                    : "The app works. The MIND benchmark still needs dataset access. Until then, there are no research quality scores to report."}
                </p>
              </div>
              {evaluation?.holdout && (
                <>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Method</th>
                          <th>NDCG@10</th>
                          <th>MRR</th>
                          <th>AUC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(evaluation.holdout).map(([name, m]) => (
                          <tr key={name}>
                            <th>{name.replaceAll("_", " ")}</th>
                            {["ndcg10", "mrr", "auc"].map((k) => (
                              <td key={k}>{m[k]?.mean?.toFixed(4) ?? "—"}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="evaluation-footnote">
                    {evaluation.groups?.toLocaleString()} groups. Selected on C:{" "}
                    {evaluation.selected}.
                  </p>
                  {evaluation.ci && (
                    <p className="evaluation-footnote">
                      Ranker minus content NDCG@10:{" "}
                      {evaluation.ci.mean_difference.toFixed(4)}. User-cluster
                      95% interval:{" "}
                      {evaluation.ci.ci95.map((v) => v.toFixed(4)).join(" to ")}
                      .
                    </p>
                  )}
                </>
              )}
              {[
                {
                  id: "protocol",
                  label: "01",
                  title: "Separate learning from the final check",
                  body: "Earlier data trains the content encoder. A later window trains the ranker with that encoder frozen. Another window selects the method. Official validation is reserved for the final holdout.",
                },
                {
                  id: "methods",
                  label: "02",
                  title: "Compare against useful baselines",
                  body: "Popularity and content matching are compared with the two-tower retriever, the separate ranker, and the final diversity policy. Every method sees the same logged candidates. A ranking score is not a click probability.",
                },
                {
                  id: "limits",
                  label: "03",
                  title: "Know where the evidence stops",
                  body: "Offline clicks do not establish gains in satisfaction or retention. Non-clicks do not prove dislike. The public collection uses original demo summaries; research quality would not establish transfer quality here.",
                },
                {
                  id: "session",
                  label: "04",
                  title: "Your session changes the features",
                  body: "Opening and saving reads updates your history. Hiding removes a read from the queue. These actions change session features, not the trained model weights. Sessions are separate and can be reset.",
                },
              ].map((section) => (
                <section className="explanation" key={section.id}>
                  <button
                    aria-expanded={expanded === section.id}
                    aria-controls={`section-${section.id}`}
                    onClick={() =>
                      setExpanded(expanded === section.id ? null : section.id)
                    }
                  >
                    <span>{section.label}</span>
                    <h3>{section.title}</h3>
                    {expanded === section.id ? (
                      <Minus size={18} />
                    ) : (
                      <Plus size={18} />
                    )}
                  </button>
                  {expanded === section.id && (
                    <p id={`section-${section.id}`}>{section.body}</p>
                  )}
                </section>
              ))}
            </section>
            <aside className="evaluation-aside">
              <span className="section-label">A SMALL, OPEN SYSTEM</span>
              <h3>
                Read the method.
                <br />
                Inspect the code.
              </h3>
              <p>
                The protocol, training code, checks and current limitations are
                in the repository.
              </p>
              <a
                href="https://github.com/EshkirenokCode/FeedRank"
                target="_blank"
                rel="noreferrer"
              >
                Open repository <ArrowUpRight size={16} />
              </a>
              <div className="aside-divider" />
              <span className="section-label">IN THIS DEMO</span>
              <p>
                48 original summaries.
                <br />
                Eight subjects.
                <br />
                One private session.
              </p>
            </aside>
          </div>
        )}
      </main>
      <footer className="site-footer">
        <span>FeedRank / A recommendation study</span>
        <span>Original demo content. No account required.</span>
        <a
          href="https://github.com/EshkirenokCode/FeedRank"
          target="_blank"
          rel="noreferrer"
        >
          Source <ArrowUpRight size={12} />
        </a>
      </footer>
      {toast && (
        <div className="toast" role="status">
          <span>{toast.text}</span>
          {toast.undo && toast.item && toast.rid && (
            <button
              disabled={busy}
              onClick={() => event(toast.item!, toast.undo!, toast.rid!)}
            >
              Undo
            </button>
          )}
          <button
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {resetDialog && (
        <div className="overlay" onClick={() => setResetDialog(false)}>
          <section
            className="reset-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              ref={dialogClose}
              className="close-dialog"
              aria-label="Close dialog"
              onClick={() => setResetDialog(false)}
            >
              <X size={20} />
            </button>
            <span className="section-label">YOUR SESSION</span>
            <h2 id="reset-title">Start fresh?</h2>
            <p>This clears your interests, saved reads and reading history.</p>
            <div>
              <button className="solid-button" disabled={busy} onClick={reset}>
                Reset session <ArrowRight size={15} />
              </button>
              <button
                className="text-action"
                onClick={() => setResetDialog(false)}
              >
                Keep my reads
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
