import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ignoreResearch,
  listResearch,
  requestAngle,
  saveResearch,
  searchResearch,
  type ResearchResult,
  type SavedResearch,
} from "../api";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

function MockTag() {
  return (
    <span className="ml-2 inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 align-middle text-[10px] font-semibold tracking-wide text-amber-700">
      MOCK
    </span>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
      {label} {pct}
      <span
        role="img"
        aria-label={`${label} ${pct} out of 100, heuristic estimate`}
        className="inline-block h-1 w-14 overflow-hidden rounded-full bg-slate-200"
      >
        <span className="block h-full rounded-full bg-slate-500" style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

const btnSecondary =
  "rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 active:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50";

export default function Research() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"discover" | "saved">("discover");
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [results, setResults] = useState<ResearchResult[]>([]);
  const [isMock, setIsMock] = useState(true);
  const [scoringNote, setScoringNote] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set());
  const [angles, setAngles] = useState<Record<string, { phase: string; text?: string }>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const [saved, setSaved] = useState<SavedResearch[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  const fail = (err: unknown) => {
    if (isSessionError(err)) setSessionExpired(true);
    else setActionError(err instanceof Error ? err.message : "Request failed");
  };

  const refreshSaved = useCallback(() => {
    setSavedLoading(true);
    listResearch("saved")
      .then((items) => {
        setSaved(items);
        setSavedKeys(
          new Set(items.map((i) => `${i.title}||${i.topic}`)),
        );
      })
      .catch(fail)
      .finally(() => setSavedLoading(false));
  }, []);

  useEffect(() => {
    if (tab === "saved") refreshSaved();
  }, [tab, refreshSaved]);

  const runSearch = async () => {
    if (!query.trim() || searching) return;
    setSearching(true);
    setSearchError(null);
    try {
      const res = await searchResearch(query.trim());
      setResults(res.results);
      setIsMock(res.mock);
      setScoringNote(res.scoring.note);
      setSearched(true);
      setHidden(new Set());
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else
        setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const keyOf = (r: ResearchResult, i: number) => `${r.title}||${r.topic}||${i}`;

  const handleAngle = async (r: ResearchResult, key: string) => {
    setAngles((a) => ({ ...a, [key]: { phase: "loading" } }));
    try {
      const res = await requestAngle({
        title: r.title,
        summary: r.summary,
        topic: r.topic,
      });
      setAngles((a) => ({ ...a, [key]: { phase: "done", text: res.angle } }));
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      setAngles((a) => ({ ...a, [key]: { phase: "error" } }));
    }
  };

  const handleSave = async (r: ResearchResult, key: string) => {
    setBusyId(key);
    setActionError(null);
    try {
      await saveResearch({
        title: r.title,
        summary: r.summary,
        source_name: r.source_name,
        source_url: r.source_url,
        published_at: r.published_at,
        topic: r.topic,
        relevance_score: r.relevance_score,
        freshness_score: r.freshness_score,
        linkedin_angle: angles[key]?.text ?? r.linkedin_angle,
        mock: r.mock,
      });
      setSavedKeys((s) => new Set(s).add(`${r.title}||${r.topic}`));
    } catch (err) {
      fail(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleUseInStudio = async (r: ResearchResult, key: string) => {
    setBusyId(key);
    try {
      const savedItem = await saveResearch({
        title: r.title,
        summary: r.summary,
        source_name: r.source_name,
        source_url: r.source_url,
        published_at: r.published_at,
        topic: r.topic,
        relevance_score: r.relevance_score,
        freshness_score: r.freshness_score,
        linkedin_angle: angles[key]?.text ?? r.linkedin_angle,
        mock: r.mock,
      });
      navigate("/studio", { state: { researchId: savedItem.id } });
    } catch (err) {
      fail(err);
    } finally {
      setBusyId(null);
    }
  };

  const handleIgnoreSaved = async (id: number) => {
    setBusyId(`saved-${id}`);
    try {
      await ignoreResearch(id);
      setSaved((s) => s.filter((i) => i.id !== id));
    } catch (err) {
      fail(err);
    } finally {
      setBusyId(null);
    }
  };

  const renderCard = (
    r: ResearchResult,
    key: string,
    opts: { saved: boolean; id?: number },
  ) => {
    const angle = angles[key];
    const isSaved = opts.saved || savedKeys.has(`${r.title}||${r.topic}`);
    return (
      <li
        key={key}
        className="rounded-xl border border-slate-200 bg-white px-5 py-4"
      >
        <p className="text-[15px] font-medium text-slate-900">
          {r.title}
          {r.mock && <MockTag />}
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{r.summary}</p>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5">
          <span className="text-xs text-slate-400">Source: {r.source_name}</span>
          {r.source_url ? (
            <a
              href={r.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-slate-700 underline underline-offset-2 hover:text-slate-900"
            >
              View source
            </a>
          ) : (
            <span className="text-xs text-slate-400">No source link (mock)</span>
          )}
          <Score label="Relevance" value={r.relevance_score} />
          <Score label="Freshness" value={r.freshness_score} />
        </div>
        {(angle?.text || r.linkedin_angle) && (
          <p className="mt-2.5 rounded-lg bg-slate-50 px-3 py-2 text-[13px] leading-relaxed text-slate-600">
            <span className="font-medium text-slate-700">LinkedIn angle: </span>
            {angle?.phase === "loading" ? "Generating angle…" : (angle?.text ?? r.linkedin_angle)}
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => void handleAngle(r, key)}
            disabled={angle?.phase === "loading"}
            className={btnSecondary}
          >
            {angle?.phase === "loading" ? "Generating…" : angle ? "Regenerate angle" : "Generate angle"}
          </button>
          {!opts.saved && !isSaved && (
            <button
              onClick={() => void handleSave(r, key)}
              disabled={busyId === key}
              className={btnSecondary}
            >
              {busyId === key ? "Saving…" : "Save"}
            </button>
          )}
          {!opts.saved && !isSaved && (
            <button
              onClick={() => setHidden((h) => new Set(h).add(key))}
              className={btnSecondary}
            >
              Ignore
            </button>
          )}
          {isSaved && !opts.saved && (
            <span className="inline-flex items-center px-1 py-1.5 text-xs font-medium text-emerald-700">
              Saved
            </span>
          )}
          <button
            onClick={() =>
              opts.id
                ? navigate("/studio", { state: { researchId: opts.id } })
                : void handleUseInStudio(r, key)
            }
            disabled={busyId === key}
            className={btnSecondary}
          >
            Use in Content Studio →
          </button>
          {opts.id && (
            <button
              onClick={() => void handleIgnoreSaved(opts.id as number)}
              disabled={busyId === `saved-${opts.id}`}
              className={btnSecondary}
            >
              Ignore
            </button>
          )}
        </div>
      </li>
    );
  };

  const visible = results.filter((r, i) => !hidden.has(keyOf(r, i)));

  return (
    <div className="mx-auto w-full max-w-3xl">
      {sessionExpired && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          Session expired —{" "}
          <Link to="/login" className="font-medium underline">
            please log in again
          </Link>
          .
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5" role="tablist" aria-label="Research views">
          {(["discover", "saved"] as const).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1.5 text-[13px] font-medium capitalize transition-colors ${
                tab === t ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {t === "discover" ? "Discover" : "Saved"}
            </button>
          ))}
        </div>
        {isMock && (
          <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
            DEVELOPMENT RESEARCH · MOCK PROVIDER
          </span>
        )}
      </div>

      {tab === "discover" && (
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void runSearch();
          }}
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Try "AI coding agents" or "developer tools"…'
            aria-label="Research topic"
            maxLength={200}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400"
          />
          <button
            type="submit"
            disabled={!query.trim() || searching}
            className="shrink-0 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
      )}

      {actionError && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
          {actionError}
        </p>
      )}

      <div className="mt-5">
        {tab === "discover" && (
          <>
            {searching && (
              <ul className="flex flex-col gap-3" aria-label="Loading results" role="status">
                {[0, 1, 2].map((i) => (
                  <li key={i} className="rounded-xl border border-slate-200 bg-white px-5 py-4">
                    <div className="skeleton h-5 w-2/3 rounded" />
                    <div className="skeleton mt-2 h-4 w-full rounded" />
                    <div className="skeleton mt-1.5 h-4 w-1/2 rounded" />
                  </li>
                ))}
              </ul>
            )}
            {!searching && searchError && (
              <div className="rounded-xl border border-slate-200 bg-white px-5 py-8 text-center" role="alert">
                <p className="text-sm font-medium text-slate-700">Search failed</p>
                <p className="mt-1 text-[13px] text-slate-500">{searchError}</p>
                <button onClick={() => void runSearch()} className={`${btnSecondary} mt-3`}>
                  Retry
                </button>
              </div>
            )}
            {!searching && !searchError && !searched && (
              <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center">
                <p className="text-sm font-medium text-slate-700">Discover research signals</p>
                <p className="mx-auto mt-1 max-w-sm text-[13px] text-slate-500">
                  Enter a professional topic above. Results are development
                  mock data until a real provider is configured.
                </p>
              </div>
            )}
            {!searching && !searchError && searched && visible.length === 0 && (
              <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center">
                <p className="text-sm font-medium text-slate-700">No signals found</p>
                <p className="mx-auto mt-1 max-w-sm text-[13px] text-slate-500">
                  Try a different topic. Ignored results are hidden from this list.
                </p>
              </div>
            )}
            {!searching && !searchError && visible.length > 0 && (
              <>
                <p className="mb-3 text-xs text-slate-400">{scoringNote}</p>
                <ul className="flex flex-col gap-3">
                  {results.map((r, i) =>
                    hidden.has(keyOf(r, i)) ? null : renderCard(r, keyOf(r, i), { saved: false }),
                  )}
                </ul>
              </>
            )}
          </>
        )}

        {tab === "saved" && (
          <>
            {savedLoading ? (
              <p className="text-sm text-slate-400" role="status">Loading saved research…</p>
            ) : saved.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center">
                <p className="text-sm font-medium text-slate-700">Nothing saved yet</p>
                <p className="mx-auto mt-1 max-w-sm text-[13px] text-slate-500">
                  Save signals from Discover to build your research library.
                </p>
              </div>
            ) : (
              <ul className="flex flex-col gap-3">
                {saved.map((r) => renderCard(r, `saved-${r.id}`, { saved: true, id: r.id }))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}
