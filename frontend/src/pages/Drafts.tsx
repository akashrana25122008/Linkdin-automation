import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CONTENT_TYPE_LABELS,
  deleteStudioItem,
  duplicateStudioItem,
  listStudioItems,
  publishErrorMessage,
  publishItem,
  updateStudioItemStatus,
  type StudioItemSummary,
} from "../api";
import ScheduleModal from "../components/ScheduleModal";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

type StatusFilter = "all" | "idea" | "draft" | "approved";

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "idea", label: "Ideas" },
  { value: "draft", label: "Drafts" },
  { value: "approved", label: "Approved" },
];

const ROW_STATUSES = ["idea", "draft", "approved"] as const;

function relativeTime(iso: string | null): string {
  if (!iso) return "Unknown time";
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return "Unknown time";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

const pillClass = (status: string) =>
  `shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${
    status === "approved" || status === "published"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : status === "failed"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : status === "idea"
          ? "border-slate-200 bg-slate-50 text-slate-500"
          : "border-slate-200 bg-white text-slate-600"
  }`;

const pillLabel = (item: StudioItemSummary): string => {
  if (item.status === "published") {
    return (item.linkedin_post_id ?? "").startsWith("mock:")
      ? "Published · mock"
      : "Published";
  }
  return item.status;
};

const LOCKED_STATUSES = ["scheduled", "published", "failed"];

const btnGhost =
  "rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50";

export default function Drafts() {
  const [items, setItems] = useState<StudioItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [schedItem, setSchedItem] = useState<{ id: number; title: string } | null>(null);
  const [confirmPublishId, setConfirmPublishId] = useState<number | null>(null);

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);
    listStudioItems(controller.signal)
      .then((list) => setItems(list))
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        if (isSessionError(err)) setSessionExpired(true);
        else setLoadError(err instanceof Error ? err.message : "Failed to load drafts");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => load(), [load]);

  const fail = (err: unknown, fallback: string) => {
    if (isSessionError(err)) setSessionExpired(true);
    else setNotice({ kind: "error", text: err instanceof Error ? err.message : fallback });
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (typeFilter !== "all" && item.content_type !== typeFilter) return false;
      if (!q) return true;
      const typeLabel =
        CONTENT_TYPE_LABELS[item.content_type as keyof typeof CONTENT_TYPE_LABELS] ?? "";
      return (
        item.title.toLowerCase().includes(q) ||
        item.preview.toLowerCase().includes(q) ||
        typeLabel.toLowerCase().includes(q)
      );
    });
  }, [items, search, statusFilter, typeFilter]);

  const handleStatus = async (id: number, next: string) => {
    setBusyId(id);
    try {
      const updated = await updateStudioItemStatus(id, next);
      setItems((list) => list.map((i) => (i.id === id ? { ...i, ...updated } : i)));
      setNotice({ kind: "ok", text: `Moved to ${next}.` });
    } catch (err) {
      fail(err, "Status update failed");
    } finally {
      setBusyId(null);
    }
  };

  const handleDuplicate = async (id: number) => {
    setBusyId(id);
    try {
      const copy = await duplicateStudioItem(id);
      setItems((list) => [
        {
          id: copy.id,
          title: copy.title,
          preview: (copy.body || "").slice(0, 160),
          content_type: copy.content_type,
          status: copy.status,
          linkedin_post_id: null,
          published_at: null,
          publish_error: "",
          created_at: null,
          updated_at: copy.updated_at,
        },
        ...list,
      ]);
      setNotice({ kind: "ok", text: `Duplicated as “${copy.title}”.` });
    } catch (err) {
      fail(err, "Duplicate failed");
    } finally {
      setBusyId(null);
    }
  };

  const handlePublish = async (id: number) => {
    setBusyId(id);
    try {
      const published = await publishItem(id);
      setItems((list) =>
        list.map((i) =>
          i.id === id
            ? {
                ...i,
                status: published.status,
                linkedin_post_id: published.linkedin_post_id,
                published_at: published.published_at,
                publish_error: published.publish_error || "",
                updated_at: published.updated_at,
              }
            : i,
        ),
      );
      setConfirmPublishId(null);
      const mock = (published.linkedin_post_id ?? "").startsWith("mock:");
      setNotice({
        kind: "ok",
        text: mock ? "Published — Mock LinkedIn." : "Published to LinkedIn.",
      });
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else {
        const code = err instanceof Error ? err.message : "";
        setNotice({ kind: "error", text: publishErrorMessage(code) });
      }
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (id: number, title: string) => {
    setBusyId(id);
    try {
      await deleteStudioItem(id);
      setItems((list) => list.filter((i) => i.id !== id));
      setConfirmDeleteId(null);
      setNotice({ kind: "ok", text: `Deleted “${title || "(untitled)"}”.` });
    } catch (err) {
      fail(err, "Delete failed");
    } finally {
      setBusyId(null);
    }
  };

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

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search title, content, or type…"
          aria-label="Search drafts"
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          aria-label="Filter by content type"
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-sm text-slate-600 outline-none transition-colors hover:border-slate-300 focus:border-slate-400"
        >
          <option value="all">All types</option>
          {(Object.keys(CONTENT_TYPE_LABELS) as (keyof typeof CONTENT_TYPE_LABELS)[]).map(
            (ct) => (
              <option key={ct} value={ct}>
                {CONTENT_TYPE_LABELS[ct]}
              </option>
            ),
          )}
        </select>
        <Link
          to="/studio"
          className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
        >
          Create post
        </Link>
      </div>

      <div className="mt-3 flex rounded-lg border border-slate-200 bg-white p-0.5" role="tablist" aria-label="Filter by status">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            role="tab"
            aria-selected={statusFilter === opt.value}
            onClick={() => setStatusFilter(opt.value)}
            className={`rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
              statusFilter === opt.value
                ? "bg-slate-900 text-white"
                : "text-slate-500 hover:text-slate-900"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {notice && (
        <p
          aria-live="polite"
          className={`mt-3 rounded-lg border px-3 py-2 text-[13px] ${
            notice.kind === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {notice.text}
        </p>
      )}

      <div className="mt-4">
        {loading ? (
          <ul className="flex flex-col gap-2" aria-label="Loading drafts" role="status">
            {[0, 1, 2].map((i) => (
              <li key={i} className="rounded-xl border border-slate-200 bg-white px-4 py-3.5">
                <div className="skeleton h-4 w-1/3 rounded" />
                <div className="skeleton mt-2 h-3.5 w-2/3 rounded" />
              </li>
            ))}
          </ul>
        ) : loadError ? (
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center" role="alert">
            <p className="text-sm font-medium text-slate-700">Couldn&apos;t load drafts</p>
            <p className="mt-1 text-[13px] text-slate-500">{loadError}</p>
            <button onClick={load} className={`${btnGhost} mt-3 border border-slate-200`}>
              Retry
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-5 py-12 text-center">
            <p className="text-sm font-medium text-slate-700">No drafts yet</p>
            <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
              Everything you save in Content Studio will appear here.
            </p>
            <Link
              to="/studio"
              className="mt-4 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
            >
              Create a post
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">
              {search.trim()
                ? "No content matches your search."
                : "No content matches this filter."}
            </p>
            <button
              onClick={() => {
                setSearch("");
                setStatusFilter("all");
                setTypeFilter("all");
              }}
              className={`${btnGhost} mt-3 border border-slate-200`}
            >
              Clear search and filters
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {filtered.map((item) => (
              <li key={item.id} className="px-4 py-3.5 transition-colors hover:bg-slate-50/60">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/studio?id=${item.id}`}
                    className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900 hover:underline"
                  >
                    {item.title || "(untitled)"}
                  </Link>
                    <span className={pillClass(item.status)}>{pillLabel(item)}</span>
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
                    {" · Updated "}
                    {relativeTime(item.updated_at)}
                  </span>
                  <span className="ml-auto flex flex-wrap items-center gap-1">
                    <select
                      value={ROW_STATUSES.includes(item.status as (typeof ROW_STATUSES)[number]) ? item.status : "draft"}
                      onChange={(e) => void handleStatus(item.id, e.target.value)}
                      disabled={busyId === item.id || LOCKED_STATUSES.includes(item.status)}
                      title={LOCKED_STATUSES.includes(item.status) ? "Scheduled or published items keep their status here" : undefined}
                      aria-label={`Status for ${item.title || "untitled"}`}
                      className="rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs text-slate-600 outline-none transition-colors hover:border-slate-300 disabled:opacity-50"
                    >
                      {ROW_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => void handleDuplicate(item.id)}
                      disabled={busyId === item.id}
                      className={btnGhost}
                    >
                      {busyId === item.id ? "Working…" : "Duplicate"}
                    </button>
                    {item.status === "approved" && (
                      <button
                        onClick={() => setSchedItem({ id: item.id, title: item.title })}
                        disabled={busyId === item.id}
                        className={btnGhost}
                      >
                        Schedule
                      </button>
                    )}
                    {item.status === "scheduled" && (
                      <Link to="/calendar" className={btnGhost}>
                        Calendar →
                      </Link>
                    )}
                    {(item.status === "approved" ||
                      item.status === "scheduled" ||
                      item.status === "failed") && (
                      <button
                        onClick={() => setConfirmPublishId(item.id)}
                        disabled={busyId === item.id}
                        className={btnGhost}
                      >
                        {item.status === "failed" ? "Retry" : "Publish"}
                      </button>
                    )}
                    <Link to={`/studio?id=${item.id}`} className={btnGhost}>
                      Open
                    </Link>
                    <button
                      onClick={() => setConfirmDeleteId(item.id)}
                      disabled={busyId === item.id}
                      className={`${btnGhost} hover:!bg-red-50 hover:!text-red-700`}
                    >
                      Delete
                    </button>
                  </span>
                </div>
                {confirmDeleteId === item.id && (
                  <div
                    className="float-enter mt-2.5 flex flex-wrap items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5"
                    role="alertdialog"
                    aria-label={`Delete ${item.title || "untitled"}?`}
                  >
                    <p className="min-w-0 flex-1 text-[13px] text-red-800">
                      Delete “{item.title || "(untitled)"}”? This cannot be undone.
                    </p>
                    <button
                      autoFocus
                      onClick={() => void handleDelete(item.id, item.title)}
                      disabled={busyId === item.id}
                      className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                    >
                      {busyId === item.id ? "Deleting…" : "Delete"}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-700 transition-colors hover:bg-red-100/50"
                    >
                      Cancel
                    </button>
                  </div>
                )}
                {confirmPublishId === item.id && (
                  <div
                    className="float-enter mt-2.5 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5"
                    role="alertdialog"
                    aria-label={`Publish ${item.title || "untitled"}?`}
                  >
                    <p className="min-w-0 flex-1 text-[13px] text-slate-700">
                      Publish “{item.title || "(untitled)"}”? In live mode this
                      creates a real LinkedIn post.
                    </p>
                    <button
                      autoFocus
                      onClick={() => void handlePublish(item.id)}
                      disabled={busyId === item.id}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                    >
                      {busyId === item.id ? "Publishing…" : "Publish"}
                    </button>
                    <button
                      onClick={() => setConfirmPublishId(null)}
                      className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {schedItem && (
        <ScheduleModal
          itemId={schedItem.id}
          itemTitle={schedItem.title}
          mode="schedule"
          onClose={() => setSchedItem(null)}
          onSaved={() => {
            setSchedItem(null);
            setNotice({ kind: "ok", text: "Scheduled. See it on the Calendar." });
            load();
          }}
        />
      )}
    </div>
  );
}
