import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  Bookmark,
  BookOpen,
  Check,
  ChevronRight,
  BarChart3,
  Layers,
  RotateCcw,
  X,
  Menu,
  EyeOff,
  ArrowLeft,
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
type Metric = Record<string, { mean: number | null; groups: number }>;
type Evaluation = {
  status: string;
  message?: string;
  protocol: string;
  selected?: string;
  groups?: number;
  holdout?: Record<string, Metric>;
  C?: Record<string, Metric>;
  ci?: { ci95: number[]; mean_difference: number };
  retrieval?: Record<
    string,
    { recall50: number; pipeline_ndcg10: number; groups: number }
  >;
};
const names: Record<string, string> = {
  foodanddrink: "Food & drink",
  news: "Community",
  science: "Science",
  health: "Wellbeing",
  finance: "Money",
  sports: "Sport",
  travel: "Travel",
  lifestyle: "Everyday life",
};
const modes: Record<Mode, string> = {
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
    throw new Error(
      data.detail || "Could not complete this request. Try again.",
    );
  }
  return response.json();
}
function App() {
  const [page, setPage] = useState("Feed");
  const [mode, setMode] = useState<Mode>("personalized");
  const [interests, setInterests] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [saved, setSaved] = useState<Item[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [started, setStarted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [opened, setOpened] = useState<Item | null>(null);
  const [toast, setToast] = useState<{
    text: string;
    item?: Item;
    rid?: string;
    undo?: "unhide" | "unsave";
  } | null>(null);
  const [sidebar, setSidebar] = useState(false);
  const [resetDialog, setResetDialog] = useState(false);
  const generation = useRef(0);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const session = await api<{ interests: string[] }>("/api/sessions", {
          method: "POST",
        });
        const info = await api<{ categories: string[] }>("/api/catalog-info");
        if (live) {
          setInterests(session.interests);
          setCategories(info.categories);
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
        if (page === "Feed") {
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
    const id = setTimeout(() => setToast(null), 9000);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    if (!opened && !resetDialog) return;
    previousFocus.current = document.activeElement as HTMLElement;
    closeRef.current?.focus();
    function key(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpened(null);
        setResetDialog(false);
      }
      if (e.key === "Tab") {
        const nodes = Array.from(
          document.querySelectorAll<HTMLElement>(
            '[role="dialog"] button,[role="dialog"] a,[role="dialog"] [tabindex="0"]',
          ),
        );
        if (!nodes.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      previousFocus.current?.focus();
    };
  }, [opened, resetDialog]);
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
    rid?: string,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    const recommendation =
      rid || item.recommendation_id || feed?.recommendation_id;
    // A retry reuses this immutable event ID instead of adding another interaction.
    const payload = JSON.stringify({
      event_id: crypto.randomUUID(),
      item_id: item.id,
      event_type: type,
      recommendation_id: recommendation,
    });
    try {
      try {
        await api("/api/events", { method: "POST", body: payload });
      } catch (e) {
        if (e instanceof TypeError)
          await api("/api/events", { method: "POST", body: payload });
        else throw e;
      }
      if (type === "open") setOpened(item);
      if (type === "hide" || type === "save")
        setToast({
          text: type === "hide" ? "Read hidden" : "Saved to your reading list",
          item,
          rid: recommendation,
          undo: type === "hide" ? "unhide" : "unsave",
        });
      if (type === "unsave" || type === "unhide")
        setToast({
          text:
            type === "unsave" ? "Removed from saved reads" : "Read restored",
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
    try {
      await api("/api/session/history", { method: "DELETE" });
      setInterests([]);
      setOpened(null);
      setToast(null);
      setResetDialog(false);
      setRevision((v) => v + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function navigate(value: string) {
    setPage(value);
    setSidebar(false);
    setError("");
  }
  const rows = page === "Saved" ? saved : feed?.items || [];
  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside className={sidebar ? "sidebar shown" : "sidebar"}>
        <a className="brand" href="/" aria-label="FeedRank home">
          <span className="mark">
            <Layers size={20} />
          </span>
          FeedRank<span className="brand-dot">.</span>
        </a>
        <div className="nav-label">YOUR SPACE</div>
        <nav aria-label="Main navigation">
          {[
            ["Feed", BookOpen],
            ["Saved", Bookmark],
            ["Evaluation", BarChart3],
          ].map(([name, Icon]) => (
            <button
              key={name as string}
              className={page === name ? "nav active" : "nav"}
              onClick={() => navigate(name as string)}
              aria-current={page === name ? "page" : undefined}
            >
              <Icon size={18} />
              {name as string}
              {page === name && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="small-rule" />
          <span className="eyebrow">A feed that responds</span>
          <p>
            Choose a few interests.
            <br />
            Open something good.
            <br />
            See what comes next.
          </p>
        </div>
        <div className="session">
          <span className="session-dot" />
          Your private demo session
          <p>No account needed. Your reading history stays in this session.</p>
          <button className="text-button" onClick={() => setResetDialog(true)}>
            <RotateCcw size={14} />
            Reset session
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="mobile-menu icon-button"
            aria-label="Toggle navigation"
            onClick={() => setSidebar(!sidebar)}
          >
            <Menu size={20} />
          </button>
          <span className="breadcrumb">
            Your space <ChevronRight size={13} /> <strong>{page}</strong>
          </span>
          <span className="demo-label">DEMO COLLECTION</span>
        </header>
        <main id="main" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {page === "Feed"
                  ? "DISCOVER AT YOUR OWN PACE"
                  : page === "Saved"
                    ? "KEEP FOR A QUIET MOMENT"
                    : "BEHIND THE RECOMMENDATIONS"}
              </span>
              <h1>
                {page === "Feed"
                  ? "Your reading space"
                  : page === "Saved"
                    ? "Saved reads"
                    : "Measured, not assumed"}
              </h1>
              <p>
                {page === "Feed"
                  ? "A small collection. A feed shaped by what you explore."
                  : page === "Saved"
                    ? "Something worth coming back to."
                    : "Compare the methods, the evidence, and the limits."}
              </p>
            </div>
            <span className="heading-icon">
              {page === "Evaluation" ? (
                <BarChart3 size={26} />
              ) : page === "Saved" ? (
                <Bookmark size={26} />
              ) : (
                <BookOpen size={26} />
              )}
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
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
          {page === "Feed" && (
            <>
              <section className="interests" aria-labelledby="interest-title">
                <div className="section-top">
                  <h2 id="interest-title">What are you curious about?</h2>
                  <span>Choose a few, or explore everything</span>
                </div>
                <div className="chips">
                  {categories.map((c) => (
                    <button
                      disabled={busy}
                      key={c}
                      aria-pressed={interests.includes(c)}
                      className={interests.includes(c) ? "chip chosen" : "chip"}
                      onClick={() => preferences(c)}
                    >
                      {interests.includes(c) && <Check size={12} />}{" "}
                      {names[c] || c}
                    </button>
                  ))}
                </div>
              </section>
              <div className="feed-toolbar">
                <div
                  className="tabs"
                  role="group"
                  aria-label="Recommendation method"
                >
                  {(Object.keys(modes) as Mode[]).map((m) => (
                    <button
                      key={m}
                      className={mode === m ? "selected" : ""}
                      aria-pressed={mode === m}
                      onClick={() => setMode(m)}
                    >
                      {modes[m]}
                    </button>
                  ))}
                </div>
                <span className="count">
                  {loading
                    ? "Refreshing your feed…"
                    : `${rows.length} reads to explore`}
                </span>
              </div>
              <div className="method-note">
                {mode === "popular"
                  ? "A balanced starting point. Demo reads have no measured audience popularity."
                  : mode === "content"
                    ? "Text similarity and category matches use your interests and reading history."
                    : "Retrieves content, then ranks it using the selected research method."}
              </div>
              {feed?.fallback && (
                <div className="notice" role="status">
                  <span className="notice-dot" />
                  <span>{feed.fallback}</span>
                </div>
              )}
            </>
          )}
          {page !== "Evaluation" && (
            <>
              <div
                className={loading ? "cards refreshing" : "cards"}
                aria-busy={loading}
              >
                {rows.map((item, i) => (
                  <article className="card" key={item.id}>
                    <div className="card-top">
                      <span className={`category cat-${item.category}`}>
                        <span />
                        {names[item.category] || item.category}
                      </span>
                      <span className="read-number">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                    </div>
                    <h2>
                      <button
                        disabled={busy || loading}
                        onClick={() => event(item, "open")}
                      >
                        {item.title}
                        <ArrowUpRight size={18} />
                      </button>
                    </h2>
                    <p className="abstract">{item.abstract}</p>
                    <div className="card-bottom">
                      <span className="reason">
                        {page === "Saved"
                          ? "In your reading list"
                          : item.reason}
                      </span>
                      <div className="actions">
                        <button
                          className="icon-button"
                          disabled={busy || loading}
                          title={
                            page === "Saved" ? "Remove from saved" : "Save read"
                          }
                          aria-label={`${page === "Saved" ? "Remove" : "Save"} ${item.title}`}
                          onClick={() =>
                            event(item, page === "Saved" ? "unsave" : "save")
                          }
                        >
                          <Bookmark
                            size={17}
                            fill={page === "Saved" ? "currentColor" : "none"}
                          />
                        </button>
                        {page === "Feed" && (
                          <button
                            className="icon-button"
                            disabled={busy || loading}
                            title="Hide read"
                            aria-label={`Hide ${item.title}`}
                            onClick={() => event(item, "hide")}
                          >
                            <EyeOff size={17} />
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
              {!rows.length && !loading && started && (
                <div className="empty">
                  <Bookmark size={30} />
                  <h2>
                    {page === "Saved"
                      ? "Your reading list starts here"
                      : "You have explored this collection"}
                  </h2>
                  <p>
                    {page === "Saved"
                      ? "Save a read from your feed. Find it here whenever you like."
                      : "Reset your session to explore the demo collection again."}
                  </p>
                  <button
                    className="primary"
                    onClick={() =>
                      page === "Saved" ? navigate("Feed") : setResetDialog(true)
                    }
                  >
                    {page === "Saved" ? "Explore the feed" : "Reset session"}
                  </button>
                </div>
              )}
              {loading && !rows.length && (
                <div className="loading" role="status">
                  Opening your reading space…
                </div>
              )}
              <footer>
                <span>
                  48 original demo summaries · Evergreen reading, not live news
                </span>
                <button
                  className="text-button"
                  onClick={() => navigate("Evaluation")}
                >
                  How this works <ArrowUpRight size={13} />
                </button>
              </footer>
            </>
          )}
          {page === "Evaluation" && (
            <section className="evaluation">
              <div className="eval-intro">
                <span className="eyebrow">TWO DIFFERENT QUESTIONS</span>
                <h2>
                  Does it rank well?
                  <br />
                  Does it respond to you?
                </h2>
                <p>
                  Research quality is measured on MIND-small. This interactive
                  collection uses original demo summaries. Quality on this
                  collection has not been established.
                </p>
              </div>
              {evaluation?.status === "awaiting_data" ? (
                <div className="eval-status">
                  <span className="eyebrow">RESEARCH STATUS</span>
                  <h3>Benchmark results are not available yet</h3>
                  <p>{evaluation.message}</p>
                </div>
              ) : (
                evaluation?.holdout && (
                  <>
                    <h3>Official validation used as final holdout</h3>
                    <p>
                      {evaluation.groups?.toLocaleString()} complete impression
                      groups. The official validation set is not an official
                      test.
                    </p>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Method</th>
                            <th>NDCG@10</th>
                            <th>MRR</th>
                            <th>Group AUC</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(evaluation.holdout).map(
                            ([name, m]) => (
                              <tr key={name}>
                                <th>{name.replaceAll("_", " ")}</th>
                                {["ndcg10", "mrr", "auc"].map((k) => (
                                  <td key={k}>
                                    {m[k]?.mean?.toFixed(4) ?? "—"}
                                  </td>
                                ))}
                              </tr>
                            ),
                          )}
                        </tbody>
                      </table>
                    </div>
                    <p className="fine">
                      Selected on C: {evaluation.selected}. Scores are ranking
                      signals, not click probabilities. Category policy is
                      reported separately.
                    </p>
                    {evaluation.ci && (
                      <p>
                        Ranker minus content NDCG@10:{" "}
                        {evaluation.ci.mean_difference.toFixed(4)}. User-cluster
                        95% interval:{" "}
                        {evaluation.ci.ci95
                          .map((v) => v.toFixed(4))
                          .join(" to ")}
                        .
                      </p>
                    )}
                  </>
                )
              )}
              <div className="steps">
                {[
                  [
                    "01",
                    "Learn from the past",
                    "An item encoder learns from titles, summaries and categories. A user encoder combines earlier reading history.",
                  ],
                  [
                    "02",
                    "Find, then rank",
                    "Exact vector search finds candidates. A separate ranker is trained on a later time window with frozen representations.",
                  ],
                  [
                    "03",
                    "Keep the final check separate",
                    "A later window selects the method. Official validation is reserved for the final holdout. Demo events never enter those metrics.",
                  ],
                ].map(([n, title, text]) => (
                  <div key={n}>
                    <span>{n}</span>
                    <div>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="limitations">
                <h3>Where the evidence stops</h3>
                <p>
                  Offline clicks do not establish a gain in satisfaction or
                  retention. Historical candidate order was shuffled. Non-clicks
                  are observations, not proof of dislike. Live actions update
                  session features; model weights stay fixed.
                </p>
                <p>
                  New sessions use a balanced fallback. Selected interests add
                  an explicit category signal. Every session is independent, and
                  you can reset yours at any time.
                </p>
              </div>
              <a
                className="repo-link"
                href="https://github.com/EshkirenokCode/FeedRank"
                target="_blank"
                rel="noreferrer"
              >
                Explore the code and protocol <ArrowUpRight size={15} />
              </a>
            </section>
          )}
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          <span>{toast.text}</span>
          {toast.undo && toast.item && (
            <button
              disabled={busy}
              onClick={() => event(toast.item!, toast.undo!, toast.rid)}
            >
              Undo
            </button>
          )}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {(opened || resetDialog) && (
        <div
          className="overlay"
          onClick={() => {
            setOpened(null);
            setResetDialog(false);
          }}
        >
          <section
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              ref={closeRef}
              className="dialog-close icon-button"
              aria-label="Close dialog"
              onClick={() => {
                setOpened(null);
                setResetDialog(false);
              }}
            >
              <X size={21} />
            </button>
            {opened ? (
              <>
                <span className="eyebrow">
                  {names[opened.category]} · DEMO READ
                </span>
                <h2 id="dialog-title">{opened.title}</h2>
                <p className="standfirst">{opened.abstract}</p>
                <p>{opened.body}</p>
                <div className="dialog-footer">
                  Original demo summary. This is the complete demo text.
                </div>
                <button className="text-button" onClick={() => setOpened(null)}>
                  <ArrowLeft size={15} />
                  Back to your reads
                </button>
              </>
            ) : (
              <>
                <span className="eyebrow">A FRESH START</span>
                <h2 id="dialog-title">Reset your session?</h2>
                <p>
                  This clears your interests, saved reads and reading history
                  for this session.
                </p>
                <div className="dialog-actions">
                  <button className="primary" disabled={busy} onClick={reset}>
                    Reset session
                  </button>
                  <button
                    className="secondary"
                    onClick={() => setResetDialog(false)}
                  >
                    Keep my reads
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
