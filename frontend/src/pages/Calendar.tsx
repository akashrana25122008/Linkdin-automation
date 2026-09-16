import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  fetchScheduledRange,
  unscheduleItem,
  type ScheduledItem,
} from "../api";
import ScheduleModal from "../components/ScheduleModal";
import {
  addDays,
  addMonths,
  formatDateTime,
  formatTime,
  monthCells,
  sameDay,
  toISODate,
  weekCells,
} from "../time";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function dayKey(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : toISODate(d);
}

export default function Calendar() {
  const navigate = useNavigate();
  const [view, setView] = useState<"month" | "week">("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [items, setItems] = useState<ScheduledItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDay, setExpandedDay] = useState<string | null>(null);
  const [modalItem, setModalItem] = useState<ScheduledItem | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  const cells = useMemo(
    () => (view === "month" ? monthCells(cursor) : weekCells(cursor)),
    [view, cursor],
  );

  const load = useCallback(
    (range: Date[]) => {
      const controller = new AbortController();
      setLoading(true);
      setError(null);
      const start = range[0].toISOString();
      const end = addDays(range[range.length - 1], 1).toISOString();
      fetchScheduledRange(start, end, controller.signal)
        .then(setItems)
        .catch((err: unknown) => {
          if ((err as Error).name === "AbortError") return;
          if (isSessionError(err)) setSessionExpired(true);
          else setError(err instanceof Error ? err.message : "Failed to load calendar");
        })
        .finally(() => setLoading(false));
      return () => controller.abort();
    },
    [],
  );

  useEffect(() => load(cells), [load, cells]);
  useEffect(() => setExpandedDay(null), [view, cursor]);

  const byDay = useMemo(() => {
    const map = new Map<string, ScheduledItem[]>();
    for (const item of items) {
      const key = dayKey(item.scheduled_at);
      if (!key) continue;
      const list = map.get(key) ?? [];
      list.push(item);
      map.set(key, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) =>
        (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""),
      );
    }
    return map;
  }, [items]);

  const upcoming = useMemo(() => {
    const now = new Date();
    return items
      .filter((i) => i.scheduled_at && new Date(i.scheduled_at) >= now)
      .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""));
  }, [items]);

  const title =
    view === "month"
      ? cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })
      : `${cells[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${cells[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  const shift = (n: number) =>
    setCursor((c) => (view === "month" ? addMonths(c, n) : addDays(c, n * 7)));

  const handleUnscheduled = async (id: number) => {
    setBusy(true);
    try {
      await unscheduleItem(id);
      setItems((list) => list.filter((i) => i.id !== id));
      setConfirmId(null);
      setNotice("Unschedule confirmed — the post is back to approved.");
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else setNotice(err instanceof Error ? err.message : "Unschedule failed.");
    } finally {
      setBusy(false);
    }
  };

  const chip = (item: ScheduledItem) => (
    <button
      key={item.id}
      onClick={() => navigate(`/studio?id=${item.id}`)}
      title={`${item.title || "(untitled)"} · ${formatDateTime(item.scheduled_at)}`}
      className="block w-full truncate rounded-md border border-slate-200 bg-white px-1.5 py-1 text-left text-[11px] leading-tight transition-colors hover:border-slate-400"
    >
      <span className="font-medium text-slate-700">
        {formatTime(item.scheduled_at)}
      </span>{" "}
      <span className="text-slate-600">{item.title || "(untitled)"}</span>
    </button>
  );

  const agenda = (
    <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
      {[...cells.map((d) => toISODate(d))]
        .filter((v, i, a) => a.indexOf(v) === i)
        .map((key) => {
          const dayItems = byDay.get(key) ?? [];
          if (dayItems.length === 0) return null;
          const d = new Date(`${key}T12:00:00`);
          return (
            <li key={key} className="px-4 py-3">
              <p className="text-xs font-semibold text-slate-500">
                {d.toLocaleDateString(undefined, {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
              </p>
              <div className="mt-1.5 flex flex-col gap-1.5">
                {dayItems.map(chip)}
              </div>
            </li>
          );
        })}
    </ul>
  );

  return (
    <div className="mx-auto w-full max-w-6xl">
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
        <div className="flex items-center gap-1">
          <button
            onClick={() => shift(-1)}
            aria-label={view === "month" ? "Previous month" : "Previous week"}
            className="rounded-lg px-2.5 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            ←
          </button>
          <button
            onClick={() => setCursor(new Date())}
            className="rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            Today
          </button>
          <button
            onClick={() => shift(1)}
            aria-label={view === "month" ? "Next month" : "Next week"}
            className="rounded-lg px-2.5 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            →
          </button>
        </div>
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900 sm:text-base">
          {title}
        </h2>
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5" role="tablist" aria-label="Calendar view">
          {(["month", "week"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1.5 text-[13px] font-medium capitalize transition-colors ${
                view === v ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <Link
          to="/studio"
          className="rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
        >
          Create post
        </Link>
      </div>

      {notice && (
        <p aria-live="polite" className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-[13px] text-emerald-700">
          {notice}
        </p>
      )}

      <div className="mt-4" key={`${view}-${toISODate(cells[0])}`}>
        {loading ? (
          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200" aria-label="Loading calendar" role="status">
            {Array.from({ length: view === "month" ? 42 : 7 }, (_, i) => (
              <div key={i} className="min-h-20 bg-white p-2 sm:min-h-24">
                <div className="skeleton h-3 w-6 rounded" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-10 text-center" role="alert">
            <p className="text-sm font-medium text-slate-700">Couldn&apos;t load the calendar</p>
            <p className="mt-1 text-[13px] text-slate-500">{error}</p>
            <button
              onClick={() => load(cells)}
              className="mt-3 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {/* Desktop grid */}
            <div className="hidden md:block">
              <div className="grid grid-cols-7 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200">
                {DOW.map((d) => (
                  <div key={d} className="bg-slate-50 px-2 py-1.5 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                    {d}
                  </div>
                ))}
                {cells.map((day) => {
                  const key = toISODate(day);
                  const dayItems = byDay.get(key) ?? [];
                  const isToday = sameDay(day, new Date());
                  const inMonth =
                    view === "week" || day.getMonth() === cursor.getMonth();
                  const expanded = expandedDay === key;
                  const shown = expanded ? dayItems : dayItems.slice(0, 3);
                  return (
                    <div
                      key={key}
                      className={`min-h-20 bg-white p-1.5 sm:min-h-24 ${inMonth ? "" : "bg-slate-50/70"}`}
                    >
                      <span
                        className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs tabular-nums ${
                          isToday
                            ? "bg-slate-900 font-semibold text-white"
                            : inMonth
                              ? "text-slate-600"
                              : "text-slate-300"
                        }`}
                        aria-label={isToday ? `${day.toDateString()}, today` : undefined}
                      >
                        {day.getDate()}
                      </span>
                      <div className="mt-1 flex flex-col gap-1">
                        {shown.map(chip)}
                        {!expanded && dayItems.length > 3 && (
                          <button
                            onClick={() => setExpandedDay(key)}
                            className="rounded-md px-1.5 py-0.5 text-left text-[11px] font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                            aria-expanded="false"
                          >
                            +{dayItems.length - 3} more
                          </button>
                        )}
                        {expanded && (
                          <button
                            onClick={() => setExpandedDay(null)}
                            className="rounded-md px-1.5 py-0.5 text-left text-[11px] font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                            aria-expanded="true"
                          >
                            Show less
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            {/* Mobile agenda fallback */}
            <div className="md:hidden">
              {items.length === 0 ? null : agenda}
            </div>

            {items.length === 0 ? (
              <div className="mt-4 rounded-xl border border-dashed border-slate-300 px-5 py-8 text-center">
                <p className="text-sm font-medium text-slate-700">No scheduled posts yet.</p>
                <p className="mx-auto mt-1 max-w-xs text-[13px] text-slate-500">
                  Approve a post, then schedule it to see it here. Local
                  scheduling only — nothing is published.
                </p>
                <Link
                  to="/drafts"
                  className="mt-3 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
                >
                  Schedule a post
                </Link>
              </div>
            ) : (
              <div className="mt-6">
                <h3 className="mb-2 text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
                  Upcoming
                </h3>
                <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                  {upcoming.map((item) => (
                    <li key={item.id} className="px-4 py-3">
                      <div className="flex items-baseline gap-3">
                        <button
                          onClick={() => navigate(`/studio?id=${item.id}`)}
                          className="min-w-0 flex-1 truncate text-left text-sm font-medium text-slate-900 hover:underline"
                        >
                          {item.title || "(untitled)"}
                        </button>
                        <time className="shrink-0 text-xs text-slate-500 tabular-nums">
                          {formatDateTime(item.scheduled_at)}
                        </time>
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        <button
                          onClick={() => setModalItem(item)}
                          className="rounded-lg px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                        >
                          Reschedule
                        </button>
                        <button
                          onClick={() => setConfirmId(item.id)}
                          className="rounded-lg px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
                        >
                          Unschedule
                        </button>
                      </div>
                      {confirmId === item.id && (
                        <div
                          className="float-enter mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2"
                          role="alertdialog"
                          aria-label={`Unschedule ${item.title || "untitled"}?`}
                        >
                          <p className="min-w-0 flex-1 text-[13px] text-amber-800">
                            Remove the schedule? The post returns to approved.
                          </p>
                          <button
                            autoFocus
                            onClick={() => void handleUnscheduled(item.id)}
                            disabled={busy}
                            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                          >
                            {busy ? "Working…" : "Unschedule"}
                          </button>
                          <button
                            onClick={() => setConfirmId(null)}
                            className="rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-100/50"
                          >
                            Cancel
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {items.length > 0 && upcoming.length === 0 && (
              <p className="mt-4 text-[13px] text-slate-500">
                All scheduled times are in the past. Reschedule a post to see it under Upcoming.
              </p>
            )}
          </>
        )}
      </div>

      {modalItem && (
        <ScheduleModal
          itemId={modalItem.id}
          itemTitle={modalItem.title}
          mode="reschedule"
          initial={{
            scheduled_at: modalItem.scheduled_at,
            scheduled_tz: modalItem.scheduled_tz,
          }}
          onClose={() => setModalItem(null)}
          onSaved={() => {
            setModalItem(null);
            setNotice("Schedule updated.");
            load(cells);
          }}
        />
      )}
    </div>
  );
}
