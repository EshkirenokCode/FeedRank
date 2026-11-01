import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowRight,
  ArrowLeft,
  Bookmark,
  X,
  SlidersHorizontal,
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
  const [readerOpen, setReaderOpen] = useState(false);
  const [topicsOpen, setTopicsOpen] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
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
    if (readerOpen) readerRef.current?.focus();
  }, [readerOpen]);
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
        setReaderOpen(true);
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
      setReaderOpen(false);
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
    requestAnimationFrame(() => {
      document.getElementById("main")?.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    });
    setPage(next);
    setReading(null);
    setReaderOpen(false);
    setTopicsOpen(false);
    setError("");
  }
  const rows = page === "Saved" ? saved : feed?.items || [];
  const activeMode = feed?.fallback
    ? feed.method === "content"
      ? "Content-based fallback"
      : feed.method === "popular"
        ? "Popular fallback"
        : modeNames[mode]
    : modeNames[mode];
  function backToList() {
    setReaderOpen(false);
    requestAnimationFrame(() => document.getElementById("main")?.focus());
  }
  return (
    <div className="application">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="app-header">
        <div className="header-content">
          <button
            className="brand"
            aria-label="FeedRank home"
            onClick={() => navigate("Discover")}
          >
            FeedRank
          </button>
          <nav aria-label="Main navigation">
            <button
              aria-current={page === "Discover" ? "page" : undefined}
              onClick={() => navigate("Discover")}
            >
              Feed
            </button>
            <button
              aria-current={page === "Saved" ? "page" : undefined}
              onClick={() => navigate("Saved")}
            >
              Saved{savedIds.length > 0 && <span>{savedIds.length}</span>}
            </button>
          </nav>
          <button
            className="settings-button"
            aria-label="Settings"
            aria-expanded={topicsOpen}
            aria-controls="feed-settings"
            onClick={() => setTopicsOpen(!topicsOpen)}
          >
            <SlidersHorizontal size={16} />
            <span>Settings</span>
          </button>
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className={
          readerOpen && reading ? "content reading-content" : "content"
        }
      >
        {topicsOpen && (
          <section
            className="settings"
            id="feed-settings"
            aria-labelledby="settings-heading"
          >
            <div className="settings-top">
              <h2 id="settings-heading">Feed settings</h2>
              <button
                aria-label="Close settings"
                onClick={() => setTopicsOpen(false)}
              >
                <X size={17} />
              </button>
            </div>
            <div className="settings-fields">
              <div>
                <label className="field-label" htmlFor="method">
                  Recommendation method
                </label>
                <select
                  id="method"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as Mode)}
                >
                  {Object.entries(modeNames).map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
                <p>Changing the method updates the feed.</p>
              </div>
              <fieldset>
                <legend>Interests</legend>
                <div className="interest-options">
                  {categories.map((c) => (
                    <label key={c}>
                      <input
                        type="checkbox"
                        disabled={busy}
                        checked={interests.includes(c)}
                        onChange={() => preferences(c)}
                      />
                      {names[c] || c}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
            <div className="settings-bottom">
              <button
                className="quiet-button"
                onClick={() => setResetDialog(true)}
              >
                Reset session
              </button>
              <button
                className="primary-button"
                onClick={() => setTopicsOpen(false)}
              >
                Done
              </button>
            </div>
          </section>
        )}
        {error && (
          <div role="alert" className="error">
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
        {readerOpen && reading ? (
          <article
            className="full-read"
            ref={readerRef}
            tabIndex={-1}
            aria-label="Article"
          >
            <div className="reader-toolbar">
              <button onClick={backToList}>
                <ArrowLeft size={16} />
                Back to {page === "Saved" ? "saved" : "feed"}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  event(
                    reading.item,
                    savedIds.includes(reading.item.id) ? "unsave" : "save",
                    reading.rid,
                  )
                }
              >
                <Bookmark
                  size={16}
                  fill={
                    savedIds.includes(reading.item.id) ? "currentColor" : "none"
                  }
                />
                {savedIds.includes(reading.item.id) ? "Saved" : "Save"}
              </button>
            </div>
            <header className="article-heading">
              <span>
                {names[reading.item.category] || reading.item.category}{" "}
                <span className="separator">/</span> Demo collection
              </span>
              <h1>{reading.item.title}</h1>
              <p>{reading.item.abstract}</p>
            </header>
            <div className="article-body">
              <p>{reading.item.body}</p>
            </div>
            <div className="article-end">
              <span>End of demo read</span>
              <button onClick={backToList}>
                Return to {page === "Saved" ? "saved" : "feed"}{" "}
                <ArrowRight size={14} />
              </button>
            </div>
          </article>
        ) : page === "Evaluation" ? (
          <section className="research-page">
            <button className="back-link" onClick={() => navigate("Discover")}>
              <ArrowLeft size={15} />
              Back to feed
            </button>
            <h1>How recommendations work</h1>
            <p className="research-intro">
              The feed compares popularity, content matching and a learned
              retrieval-and-ranking pipeline.
            </p>
            <section className="research-status">
              <h2>Research evaluation</h2>
              <p>
                {evaluation?.status === "measured"
                  ? "Official validation is used as the final holdout, not an official test. All logged candidates are kept."
                  : "MIND benchmark training and evaluation are pending dataset access. The app currently uses a content-based fallback. No research scores are claimed."}
              </p>
            </section>
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
                <p className="note">
                  {evaluation.groups?.toLocaleString()} groups. Selected on C:{" "}
                  {evaluation.selected}.
                </p>
                {evaluation.ci && (
                  <p className="note">
                    Ranker minus content NDCG@10:{" "}
                    {evaluation.ci.mean_difference.toFixed(4)}. User-cluster 95%
                    interval:{" "}
                    {evaluation.ci.ci95.map((v) => v.toFixed(4)).join(" to ")}.
                  </p>
                )}
              </>
            )}
            <h2>Learning and evaluation use different time windows</h2>
            <p>
              Earlier data trains the content encoder. A later window trains the
              ranker with that encoder frozen. Another window selects the
              method. Official validation stays separate for the final check.
            </p>
            <h2>Your actions update your session</h2>
            <p>
              Opening and saving reads changes the history used for matching.
              Hiding a read removes it from your feed. These actions update
              features, not model weights. Each session is independent.
            </p>
            <h2>What the demo can show</h2>
            <p>
              The collection contains 48 original summaries. It is not a live
              news service. Offline quality on MIND would not prove quality on
              this collection, or establish gains in satisfaction or retention.
            </p>
            <a
              className="source-link"
              href="https://github.com/EshkirenokCode/FeedRank"
              target="_blank"
              rel="noreferrer"
            >
              Code and evaluation protocol <ArrowUpRight size={14} />
            </a>
          </section>
        ) : (
          <section className="feed-page" aria-busy={loading}>
            <div className="feed-heading">
              <div>
                <h1>{page === "Saved" ? "Saved reads" : "Your feed"}</h1>
                <p>
                  {page === "Saved"
                    ? "Reads you kept for later."
                    : interests.length
                      ? interests.map((c) => names[c] || c).join(", ")
                      : "All subjects"}
                </p>
              </div>
              {page === "Discover" && (
                <button
                  className="feed-method"
                  onClick={() => setTopicsOpen(!topicsOpen)}
                >
                  {activeMode}
                  <SlidersHorizontal size={13} />
                </button>
              )}
            </div>
            {page === "Discover" && feed?.fallback && (
              <p className="model-note">
                {feed.research_ready
                  ? feed.fallback
                  : "Research model unavailable; content matching is active."}
                <button onClick={() => navigate("Evaluation")}>
                  About this
                </button>
              </p>
            )}
            {(loading && !rows.length) || !started ? (
              <p className="loading" role="status">
                Loading reads…
              </p>
            ) : rows.length ? (
              <div className="feed-list">
                {rows.map((item) => {
                  const rid =
                    item.recommendation_id || feed?.recommendation_id || "";
                  const isSaved = savedIds.includes(item.id);
                  return (
                    <article className="feed-item" key={item.id}>
                      <div className="item-category">
                        {names[item.category] || item.category}
                      </div>
                      <div className="item-main">
                        <h2>
                          <button
                            disabled={busy || loading}
                            onClick={() => event(item, "open", rid)}
                          >
                            {item.title}
                          </button>
                        </h2>
                        <p>{item.abstract}</p>
                        <div className="item-bottom">
                          <span>
                            {item.reason === "Matches a selected interest"
                              ? "Matches your interests"
                              : item.reason === "Based on your reading history"
                                ? "From your reading history"
                                : "Demo collection"}
                          </span>
                          <div>
                            <button
                              disabled={busy || loading}
                              aria-label={`${isSaved ? "Unsave" : "Save"} ${item.title}`}
                              className={
                                isSaved ? "item-action is-saved" : "item-action"
                              }
                              onClick={() =>
                                event(item, isSaved ? "unsave" : "save", rid)
                              }
                            >
                              <Bookmark
                                size={14}
                                fill={isSaved ? "currentColor" : "none"}
                              />
                              {isSaved ? "Saved" : "Save"}
                            </button>
                            {page === "Discover" && (
                              <button
                                disabled={busy || loading}
                                className="item-action"
                                aria-label={`Hide ${item.title}`}
                                onClick={() => event(item, "hide", rid)}
                              >
                                <X size={14} />
                                Hide
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="empty">
                <h2>
                  {page === "Saved"
                    ? "No saved reads"
                    : "No more reads in this session"}
                </h2>
                <p>
                  {page === "Saved"
                    ? "Use Save beside a read to keep it here."
                    : "Reset the session to browse the collection again."}
                </p>
                <button
                  className="primary-button"
                  onClick={() =>
                    page === "Saved"
                      ? navigate("Discover")
                      : setResetDialog(true)
                  }
                >
                  {page === "Saved" ? "Back to feed" : "Reset session"}
                </button>
              </div>
            )}
          </section>
        )}
        <footer className="app-footer">
          <button onClick={() => navigate("Evaluation")}>
            How recommendations work
          </button>
          <span aria-hidden="true">·</span>
          <a
            href="https://github.com/EshkirenokCode/FeedRank"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <span className="footer-description">Original demo content</span>
        </footer>
      </main>
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
            <X size={15} />
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
              <X size={19} />
            </button>
            <h2 id="reset-title">Reset this session?</h2>
            <p>
              Your interests, saved reads and reading history will be cleared.
            </p>
            {error && <p role="alert">{error}</p>}
            <div>
              <button
                className="quiet-button"
                onClick={() => setResetDialog(false)}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                disabled={busy}
                onClick={reset}
              >
                Reset session
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
