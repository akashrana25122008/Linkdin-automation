import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CONTENT_TYPE_LABELS,
  listStudioItems,
  type StudioItemSummary,
} from "../api";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

function formatDate(iso: string | null): string {
  if (!iso) return "Unknown date";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown date";
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function Published() {
  const [items, setItems] = useState<StudioItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);
    listStudioItems(controller.signal)
      .then((list) => setItems(list.filter((i) => i.status === "published")))
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        if (isSessionError(err)) setSessionExpired(true);
        else setLoadError(err instanceof Error ? err.message : "Failed to load published posts");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => load(), [load]);

  return (
    <div className="mx-auto w-full max-w-4xl">
      {sessionExpired && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          Session expired —{" "}
          <Link to="/login" className="font-medium underline">
            please log in again
          </Link>
          .
        </p>
      )}

      <p className="text-sm text-slate-500">
        Posts this workspace published. Engagement metrics are unavailable
        through the LinkedIn integration — see Analytics for what is measured.
      </p>

      <div className="mt-4">
        {loading ? (
          <ul className="flex flex-col gap-2" aria-label="Loading published posts" role="status">
            {[0, 1, 2].map((i) => (
              <li key={i} className="rounded-xl border border-slate-200 bg-white px-4 py-3.5">
                <div className="skeleton h-4 w-1/3 rounded" />
                <div className="skeleton mt-2 h-3.5 w-2/3 rounded" />
              </li>
            ))}
          </ul>
        ) : loadError ? (
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center" role="alert">
            <p className="text-sm font-medium text-slate-700">Couldn&apos;t load published posts</p>
            <p className="mt-1 text-[13px] text-slate-500">{loadError}</p>
            <button
              onClick={load}
              className="mt-3 rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-5 py-12 text-center">
            <p className="text-sm font-medium text-slate-700">Nothing published yet</p>
            <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
              Approve a draft and publish it to see it here.
            </p>
            <Link
              to="/drafts"
              className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
            >
              Open drafts
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {items.map((item) => (
              <li key={item.id} className="px-4 py-3.5 transition-colors hover:bg-slate-50/60">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/studio?id=${item.id}`}
                    className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900 hover:underline"
                  >
                    {item.title || "(untitled)"}
                  </Link>
                  <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                    {(item.linkedin_post_id ?? "").startsWith("mock:")
                      ? "Published · mock"
                      : "Published"}
                  </span>
                </div>
                {item.preview && (
                  <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-slate-500">
                    {item.preview}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  <span className="text-xs text-slate-400">
                    {CONTENT_TYPE_LABELS[item.content_type as keyof typeof CONTENT_TYPE_LABELS] ??
                      item.content_type}
                    {" · Published "}
                    {formatDate(item.published_at)}
                  </span>
                  {item.linkedin_post_id && (
                    <span className="truncate font-mono text-[11px] text-slate-400" title="LinkedIn post identifier">
                      {item.linkedin_post_id}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
