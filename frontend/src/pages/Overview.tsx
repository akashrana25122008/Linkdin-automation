import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchDashboard,
  type DashboardData,
} from "../api";
import { useAuth } from "../auth";

const STAGES = [
  { key: "idea", label: "Ideas", href: "/drafts" },
  { key: "draft", label: "Drafts", href: "/drafts" },
  { key: "approved", label: "Approved", href: "/drafts" },
  { key: "scheduled", label: "Scheduled", href: "/calendar" },
  { key: "published", label: "Published", href: "/published" },
] as const;

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function MockTag() {
  return (
    <span className="ml-2 inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 align-middle text-[10px] font-semibold tracking-wide text-amber-700">
      MOCK
    </span>
  );
}

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={title}>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Skeleton() {
  return (
    <div className="max-w-5xl" aria-label="Loading dashboard" role="status">
      <div className="skeleton h-7 w-56 rounded-lg" />
      <div className="skeleton mt-2 h-4 w-80 rounded" />
      <div className="skeleton mt-8 h-28 rounded-xl" />
      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="skeleton h-40 rounded-xl" />
          <div className="skeleton mt-4 h-32 rounded-xl" />
        </div>
        <div className="lg:col-span-2">
          <div className="skeleton h-28 rounded-xl" />
          <div className="skeleton mt-4 h-44 rounded-xl" />
        </div>
      </div>
    </div>
  );
}

export default function Overview() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDashboard(controller.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((err: unknown) => {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Backend unreachable");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => load(), [load]);

  if (loading && !data) return <Skeleton />;

  if (error && !data) {
    return (
      <div className="max-w-xl" role="alert">
        <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-4 text-sm text-red-600">
          Couldn&apos;t load the dashboard: {error}
        </p>
        <button
          onClick={load}
          className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 active:bg-slate-800"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const name = user?.name ?? data.user.name ?? data.user.email ?? "there";
  const total = Object.values(data.pipeline).reduce((a, b) => a + b, 0);
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="max-w-5xl">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-xl font-semibold tracking-tight">
          {greeting()}, {name.split(" ")[0]}
        </h1>
        {data.mock && <MockTag />}
      </div>
      <p className="mt-1 text-sm text-slate-500">{today} · Here&apos;s your workspace.</p>

      {/* Today's brief */}
      <div className="mt-6 border-y border-slate-200 py-5">
        <Section title="Today's brief">
          <p className="max-w-3xl text-[15px] leading-relaxed text-slate-800">
            {data.brief.text}
          </p>
          {data.brief.mock && (
            <p className="mt-2 text-xs text-slate-400">
              Development preview — phrased by the mock AI provider, no key required.
            </p>
          )}
        </Section>
      </div>

      {/* Content pipeline */}
      <div className="mt-8">
        <Section
          title="Content pipeline"
          action={
            <Link
              to="/drafts"
              className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              Open drafts →
            </Link>
          }
        >
          <ol className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-5">
            {STAGES.map((stage) => (
              <li key={stage.key} className="bg-white">
                <Link
                  to={stage.href}
                  className="block px-4 py-3.5 transition-colors hover:bg-slate-50 active:bg-slate-100"
                >
                  <span className="block text-2xl font-semibold tracking-tight tabular-nums">
                    {data.pipeline[stage.key] ?? 0}
                  </span>
                  <span className="mt-0.5 block text-xs font-medium text-slate-500">
                    {stage.label}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
          {total === 0 && (
            <p className="mt-3 text-sm text-slate-500">
              Nothing in the pipeline yet.{" "}
              <Link to="/studio" className="font-medium text-slate-900 underline underline-offset-2 hover:text-slate-600">
                Create your first draft
              </Link>
              .
            </p>
          )}
        </Section>
      </div>

      <div className="mt-8 grid gap-x-8 gap-y-10 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col gap-10 lg:col-span-3">
          {/* Research signals */}
          <Section
            title="Research signals"
            action={
              <Link
                to="/research"
                className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                Open research →
              </Link>
            }
          >
            {data.signals.length === 0 ? (
              <p className="text-sm text-slate-500">
                No signals right now. The full research workspace arrives in M5.
              </p>
            ) : (
              <ul className="divide-y divide-slate-100 border-y border-slate-200">
                {data.signals.map((signal, i) => (
                  <li key={i} className="group py-3.5">
                    <p className="text-sm font-medium text-slate-900">
                      {signal.title}
                      {signal.mock && <MockTag />}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-slate-500">
                      {signal.summary}
                    </p>
                    <p className="mt-1.5 text-xs text-slate-400">
                      Relevance {Math.round(signal.relevance_score * 100)}% ·{" "}
                      {signal.freshness} · {signal.potential_angle}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {/* Upcoming */}
          <Section
            title="Upcoming posts"
            action={
              <Link
                to="/calendar"
                className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                Open calendar →
              </Link>
            }
          >
            {data.upcoming.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 px-5 py-6 text-center">
                <p className="text-sm font-medium text-slate-700">
                  Nothing scheduled
                </p>
                <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
                  Scheduled posts will appear here. Plan your next post in the
                  calendar workflow.
                </p>
                <Link
                  to="/calendar"
                  className="mt-3 inline-block rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                >
                  Plan in Calendar
                </Link>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100 border-y border-slate-200">
                {data.upcoming.map((item) => (
                  <li key={item.id} className="flex items-baseline justify-between gap-4 py-3">
                    <span className="truncate text-sm font-medium text-slate-900">
                      {item.title || "(untitled)"}
                    </span>
                    <time className="shrink-0 text-xs text-slate-400">
                      {item.scheduled_at
                        ? new Date(item.scheduled_at).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          })
                        : "Unscheduled"}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div className="flex min-w-0 flex-col gap-10 lg:col-span-2">
          {/* Performance */}
          <Section title="Performance">
            <div className="rounded-xl border border-slate-200 bg-white px-5 py-5">
              <p className="text-sm font-medium text-slate-700">
                Analytics not connected
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-slate-500">
                {data.performance.message}
              </p>
            </div>
          </Section>

          {/* AI recommendations */}
          <Section title="AI recommendations">
            <ul className="flex flex-col gap-2.5">
              {data.recommendations.map((rec, i) => (
                <li key={i}>
                  <Link
                    to={rec.href}
                    className="group block rounded-xl border border-slate-200 bg-white px-4 py-3.5 transition-colors hover:border-slate-300 hover:bg-slate-50 active:bg-slate-100"
                  >
                    <p className="text-sm font-medium text-slate-900">
                      <span aria-hidden="true" className="mr-2 text-slate-300">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      {rec.title}
                      {rec.mock && <MockTag />}
                    </p>
                    <p className="mt-1 pl-8 text-[13px] text-slate-500">
                      {rec.detail}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </div>
  );
}
