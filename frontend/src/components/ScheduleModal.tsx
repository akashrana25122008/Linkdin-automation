import { useEffect, useMemo, useState } from "react";
import {
  rescheduleItem,
  scheduleErrorMessage,
  scheduleItem,
} from "../api";
import { COMMON_TIMEZONES, browserTimeZone, zonedTimeToUtc } from "../time";

const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition-colors hover:border-slate-300 focus:border-slate-400 disabled:opacity-50";

/** Wall-clock parts of a UTC instant in the given zone, for prefilling. */
function utcToWall(
  iso: string,
  timeZone: string,
): { date: string; time: string } | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).formatToParts(d);
    const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
    return {
      date: `${get("year")}-${get("month")}-${get("day")}`,
      time: `${get("hour")}:${get("minute")}`,
    };
  } catch {
    return null;
  }
}

export default function ScheduleModal({
  itemId,
  itemTitle,
  mode,
  initial,
  onClose,
  onSaved,
}: {
  itemId: number;
  itemTitle: string;
  mode: "schedule" | "reschedule";
  initial?: { scheduled_at: string | null; scheduled_tz: string | null };
  onClose: () => void;
  onSaved: () => void;
}) {
  const browserTz = useMemo(browserTimeZone, []);
  const zones = useMemo(() => {
    const extra = [initial?.scheduled_tz, browserTz].filter(
      (z): z is string => !!z && !COMMON_TIMEZONES.includes(z),
    );
    return [...COMMON_TIMEZONES, ...extra];
  }, [initial?.scheduled_tz, browserTz]);

  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [tz, setTz] = useState(initial?.scheduled_tz ?? browserTz);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial?.scheduled_at && initial?.scheduled_tz) {
      const wall = utcToWall(initial.scheduled_at, initial.scheduled_tz);
      if (wall) {
        setDate(wall.date);
        setTime(wall.time);
        setTz(initial.scheduled_tz);
      }
    }
  }, [initial?.scheduled_at, initial?.scheduled_tz]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const instant = useMemo(
    () => (date && time ? zonedTimeToUtc(date, time, tz) : null),
    [date, time, tz],
  );

  const submit = async () => {
    if (!instant) {
      setError("That date or time is not valid.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const call = mode === "schedule" ? scheduleItem : rescheduleItem;
      await call(itemId, instant.toISOString(), tz);
      onSaved();
      onClose();
    } catch (err) {
      setError(
        scheduleErrorMessage(err instanceof Error ? err.message : ""),
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-label="Close scheduling dialog"
        className="absolute inset-0 cursor-default bg-slate-900/20"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={mode === "schedule" ? "Schedule post" : "Reschedule post"}
        className="float-enter relative w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
      >
        <h2 className="text-sm font-semibold text-slate-900">
          {mode === "schedule" ? "Schedule post" : "Reschedule post"}
        </h2>
        <p className="mt-0.5 truncate text-xs text-slate-500">
          {itemTitle || "(untitled)"} · local app schedule, not LinkedIn publishing
        </p>

        <div className="mt-4 flex flex-col gap-3">
          <label className="grid grid-cols-2 gap-2">
            <span className="col-span-2 text-xs font-medium text-slate-600">Date</span>
            <input
              autoFocus
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              aria-label="Scheduled date"
              className={`${inputClass} col-span-2`}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600">Time</span>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              aria-label="Scheduled time"
              className={inputClass}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600">Timezone</span>
            <select
              value={tz}
              onChange={(e) => setTz(e.target.value)}
              aria-label="Timezone"
              className={inputClass}
            >
              {zones.map((z) => (
                <option key={z} value={z}>
                  {z}
                  {z === browserTz ? " (browser)" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="mt-3 text-xs text-slate-500" aria-live="polite">
          {instant
            ? `Saves as ${instant.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })} in ${tz}.`
            : "Enter a date, time, and timezone."}
        </p>

        {error && (
          <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
            {error}
          </p>
        )}

        <div className="mt-4 flex gap-2">
          <button
            onClick={() => void submit()}
            disabled={saving || !instant}
            className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {saving
              ? "Saving…"
              : mode === "schedule"
                ? "Schedule"
                : "Save changes"}
          </button>
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
