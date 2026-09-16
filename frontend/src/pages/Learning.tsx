import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchLearning, type LearningData, type LearningInsight } from "../api";

const CONFIDENCE_LABELS: Record<string, string> = {
  INSUFFICIENT_DATA: "Insufficient data",
  EARLY_SIGNAL: "Early signal",
  SUPPORTED_PATTERN: "Supported pattern",
};

function ConfidencePill({ value }: { value: string }) {
  const tone =
    value === "SUPPORTED_PATTERN"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : value === "EARLY_SIGNAL"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-500";
  return (
    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}>
      {CONFIDENCE_LABELS[value] ?? value}
    </span>
  );
}

function InsightCard({ insight }: { insight: LearningInsight }) {
  return (
    <li className="rounded-xl border border-slate-200 bg-white px-5 py-4">
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-slate-900">
          {insight.title}
        </p>
        <ConfidencePill value={insight.confidence} />
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">
        <span className="font-medium text-slate-700">Evidence: </span>
        {insight.evidence}
      </p>
      <p className="mt-1 text-xs text-slate-400">Source: {insight.source}</p>
      {insight.recommendation && (
        <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-[13px] text-slate-600">
          {insight.recommendation}
        </p>
      )}
    </li>
  );
}

export default function Learning() {
  const [data, setData] = useState<LearningData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchLearning(controller.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load learning");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => load(), [load]);

  const sessionExpired = error?.startsWith("Session expired") ?? false;

  return (
    <div className="mx-auto w-full max-w-3xl">
      {loading ? (
        <div role="status" aria-label="Loading learning">
          <div className="skeleton h-7 w-56 rounded-lg" />
          <div className="skeleton mt-4 h-36 rounded-xl" />
          <div className="skeleton mt-4 h-36 rounded-xl" />
        </div>
      ) : error ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center" role="alert">
          <p className="text-sm font-medium text-slate-700">Couldn&apos;t load learning</p>
          <p className="mt-1 text-[13px] text-slate-500">{error}</p>
          <div className="mt-3 flex items-center justify-center gap-2">
            <button
              onClick={load}
              className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              Retry
            </button>
            {sessionExpired && (
              <Link
                to="/login"
                className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700"
              >
                Log in
              </Link>
            )}
          </div>
        </div>
      ) : data && (data.state === "INSUFFICIENT_DATA" && data.coverage.published_total === 0) ? (
        <div className="rounded-xl border border-dashed border-slate-300 px-5 py-12 text-center">
          <p className="text-sm font-medium text-slate-700">Learning hasn&apos;t started yet.</p>
          <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
            Publish more content to build enough history for meaningful patterns.
          </p>
          <Link
            to="/studio"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
          >
            Create a post
          </Link>
        </div>
      ) : data ? (
        <div className="flex flex-col gap-8">
          <section aria-label="Current understanding" className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
              Current understanding
            </h2>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-4">
              <div>
                <dt className="text-slate-400">Published posts</dt>
                <dd className="mt-0.5 text-lg font-semibold tabular-nums">
                  {data.coverage.published_total}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">App history</dt>
                <dd className="mt-0.5 text-lg font-semibold">
                  {data.coverage.application_history ? "Available" : "None yet"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">LinkedIn engagement</dt>
                <dd className="mt-0.5 text-lg font-semibold">Unavailable</dd>
              </div>
              <div>
                <dt className="text-slate-400">Pattern gate</dt>
                <dd className="mt-0.5 text-lg font-semibold tabular-nums">
                  {data.coverage.minimum_for_patterns}+ posts
                </dd>
              </div>
            </dl>
            {data.state === "INSUFFICIENT_DATA" && data.message && (
              <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-[13px] text-slate-600">
                {data.message}
              </p>
            )}
            {data.ai_summary && (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-3">
                <p className="text-[13px] leading-relaxed text-slate-700">
                  {data.ai_summary.text}
                  {data.ai_summary.mock && (
                    <span className="ml-2 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 align-middle text-[10px] font-semibold tracking-wide text-amber-700">
                      MOCK
                    </span>
                  )}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  AI phrasing of the validated facts above — no new claims.
                </p>
              </div>
            )}
          </section>

          {data.insights.length > 0 && (
            <section aria-label="Validated insights">
              <h2 className="mb-3 text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                Validated insights
              </h2>
              <ul className="flex flex-col gap-3">
                {data.insights.map((insight) => (
                  <InsightCard key={`${insight.type}-${insight.title}`} insight={insight} />
                ))}
              </ul>
            </section>
          )}

          {data.strategy_alignment.length > 0 && (
            <section aria-label="Strategy alignment">
              <h2 className="mb-3 text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                Strategy alignment
              </h2>
              <ul className="flex flex-col gap-3">
                {data.strategy_alignment.map((insight) => (
                  <InsightCard key={`${insight.type}-${insight.title}`} insight={insight} />
                ))}
              </ul>
            </section>
          )}

          {data.recommendations.length > 0 && (
            <section aria-label="Recommendations" className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                Recommendations
              </h2>
              <ul className="mt-3 flex flex-col gap-2.5">
                {data.recommendations.map((rec) => (
                  <li key={rec.title} className="flex items-start gap-2.5">
                    <ConfidencePill value={rec.confidence} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900">{rec.title}</p>
                      <p className="mt-0.5 text-[13px] text-slate-500">{rec.reason}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-400">
                Suggestions only — your strategy is never changed automatically.
              </p>
            </section>
          )}

          <section aria-label="Data limitations" className="rounded-xl border border-dashed border-slate-300 px-5 py-4">
            <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
              Data limitations
            </h2>
            <p className="mt-2 text-[13px] leading-relaxed text-slate-500">
              {data.performance_note} Patterns need at least{" "}
              {data.coverage.minimum_for_patterns} published posts; nothing is
              concluded below that. No content is generated or published from
              these insights.
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
