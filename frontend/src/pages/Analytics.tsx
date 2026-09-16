import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchAnalyticsOverview,
  fetchAnalyticsPosts,
  type AnalyticsOverview,
  type AnalyticsPost,
  type AnalyticsRange,
} from "../api";

const RANGES: { value: AnalyticsRange; label: string }[] = [
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
  { value: "all", label: "All time" },
];

function formatCount(n: number): string {
  return n.toLocaleString();
}

function Bars({
  buckets,
  ariaLabel,
}: {
  buckets: { label: string; count: number }[];
  ariaLabel: string;
}) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const total = buckets.reduce((sum, b) => sum + b.count, 0);
  return (
    <div role="img" aria-label={`${ariaLabel}: ${total} total`}>
      <div className="flex h-28 items-end gap-1.5">
        {buckets.map((b) => (
          <div key={b.label} className="flex min-w-0 flex-1 flex-col items-center gap-1" title={`${b.label}: ${b.count}`}>
            <span className="text-[11px] text-slate-500 tabular-nums">
              {b.count > 0 ? b.count : ""}
            </span>
            <div
              className={`w-full rounded-sm ${b.count > 0 ? "bg-slate-800" : "bg-slate-100"}`}
              style={{ height: `${Math.max(4, (b.count / max) * 88)}px` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5">
        {buckets.map((b) => (
          <span key={b.label} className="min-w-0 flex-1 truncate text-center text-[10px] text-slate-400">
            {b.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function Distribution({ entries }: { entries: [string, number][] }) {
  const max = Math.max(1, ...entries.map(([, n]) => n));
  if (entries.length === 0) {
    return <p className="text-[13px] text-slate-400">No data yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {entries.map(([label, count]) => (
        <li key={label} className="flex items-center gap-3">
          <span className="w-32 shrink-0 truncate text-[13px] text-slate-600">
            {label}
          </span>
          <div
            className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-100"
            role="img"
            aria-label={`${label}: ${count}`}
          >
            <div
              className="h-full rounded-full bg-slate-700"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <span className="w-8 shrink-0 text-right text-[13px] text-slate-600 tabular-nums">
            {count}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function Analytics() {
  const [range, setRange] = useState<AnalyticsRange>("30");
  const [historyStatus, setHistoryStatus] = useState("");
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [posts, setPosts] = useState<AnalyticsPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      fetchAnalyticsOverview(range, controller.signal),
      fetchAnalyticsPosts(range, historyStatus, controller.signal),
    ])
      .then(([o, p]) => {
        setOverview(o);
        setPosts(p);
        setError(null);
      })
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Failed to load analytics");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [range, historyStatus]);

  useEffect(() => load(), [load]);

  const sessionExpired = error?.startsWith("Session expired") ?? false;
  const empty =
    !loading &&
    !error &&
    overview &&
    Object.values(overview.status_counts).reduce((a, b) => a + b, 0) === 0;

  return (
    <div className="mx-auto w-full max-w-4xl">
      <div className="flex flex-wrap items-center gap-2">
        <div
          className="flex rounded-lg border border-slate-200 bg-white p-0.5"
          role="tablist"
          aria-label="Time range"
        >
          {RANGES.map((r) => (
            <button
              key={r.value}
              role="tab"
              aria-selected={range === r.value}
              onClick={() => setRange(r.value)}
              className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
                range === r.value
                  ? "bg-slate-900 text-white"
                  : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <p className="ml-auto text-xs text-slate-400">
          Source: application publishing data
        </p>
      </div>

      {loading ? (
        <div className="mt-4" role="status" aria-label="Loading analytics">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-20 rounded-xl" />
            ))}
          </div>
          <div className="skeleton mt-4 h-44 rounded-xl" />
          <div className="skeleton mt-4 h-32 rounded-xl" />
        </div>
      ) : error ? (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white px-5 py-10 text-center" role="alert">
          <p className="text-sm font-medium text-slate-700">
            Couldn&apos;t load analytics
          </p>
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
      ) : empty || !overview ? (
        <div className="mt-4 rounded-xl border border-dashed border-slate-300 px-5 py-12 text-center">
          <p className="text-sm font-medium text-slate-700">No publishing data yet.</p>
          <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
            Publish your first post to start building analytics history.
          </p>
          <Link
            to="/studio"
            className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
          >
            Create a post
          </Link>
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(
              [
                ["Published", overview.published_in_range],
                ["Scheduled", overview.status_counts.scheduled ?? 0],
                ["Drafts", overview.status_counts.draft ?? 0],
                ["Failed", overview.status_counts.failed ?? 0],
              ] as [string, number][]
            ).map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-white px-4 py-3.5">
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="mt-0.5 text-2xl font-semibold tracking-tight tabular-nums">
                  {formatCount(value)}
                </dd>
              </div>
            ))}
          </dl>
          {overview.posts_per_week !== null && (
            <p className="text-[13px] text-slate-500">
              {overview.posts_per_week} posts per week over the last {overview.range} days
              {overview.published_in_range === 0 ? " — no posts published in this range." : "."}
            </p>
          )}

          <section aria-label="Publishing activity" className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
              Publishing activity
            </h2>
            <div className="mt-3">
              <Bars buckets={overview.weekly_activity} ariaLabel="Posts published over time" />
            </div>
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <section aria-label="Posts by content type" className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                By content type
              </h2>
              <div className="mt-3">
                <Distribution entries={Object.entries(overview.by_content_type)} />
              </div>
            </section>
            <section aria-label="LinkedIn engagement" className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                LinkedIn engagement
              </h2>
              <p className="mt-3 text-sm font-medium text-slate-700">
                {overview.linkedin.connected
                  ? "Connected — metrics unavailable"
                  : "Not available"}
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-slate-500">
                {overview.linkedin.engagement.message}
              </p>
            </section>
          </div>

          <section aria-label="Published history" className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                History
              </h2>
              <select
                value={historyStatus}
                onChange={(e) => setHistoryStatus(e.target.value)}
                aria-label="Filter history by status"
                className="ml-auto rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 outline-none transition-colors hover:border-slate-300"
              >
                <option value="">All statuses</option>
                <option value="published">Published</option>
                <option value="scheduled">Scheduled</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            {posts.length === 0 ? (
              <p className="mt-3 text-[13px] text-slate-400">
                No posts match this filter.
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-slate-100">
                {posts.map((post) => (
                  <li key={post.id} className="flex items-baseline gap-3 py-2.5">
                    <Link
                      to={`/studio?id=${post.id}`}
                      className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900 hover:underline"
                    >
                      {post.title || "(untitled)"}
                    </Link>
                    <span className="hidden shrink-0 rounded-full border border-slate-200 px-2 py-0.5 text-[11px] text-slate-500 sm:inline">
                      {post.status}
                    </span>
                    <time className="shrink-0 text-xs text-slate-400 tabular-nums">
                      {(post.published_at ?? post.scheduled_at)
                        ? new Date(
                            (post.published_at ?? post.scheduled_at) as string,
                          ).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                          })
                        : "—"}
                    </time>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-slate-400">
              A published post ID proves publication — not engagement.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
