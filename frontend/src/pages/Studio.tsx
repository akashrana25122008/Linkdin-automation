import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useBlocker, useLocation, useSearchParams } from "react-router-dom";
import {
  CONTENT_TYPE_LABELS,
  REWRITE_ACTIONS,
  createStudioItem,
  getResearchItem,
  getStudioItem,
  listStudioItems,
  publishErrorMessage,
  publishItem,
  reviewDraft,
  runAiAction,
  unscheduleItem,
  updateStudioItem,
  type AiAction,
  type AiResult,
  type ContentType,
  type ReviewResult,
  type SavedResearch,
  type StudioItemSummary,
  type StudioStatus,
} from "../api";
import ScheduleModal from "../components/ScheduleModal";
import { formatDateTime } from "../time";

type SaveState =
  | { kind: "saved" }
  | { kind: "dirty" }
  | { kind: "saving" }
  | { kind: "error"; message: string };

type AiState =
  | { phase: "idle" }
  | { phase: "loading"; label: string }
  | {
      phase: "result";
      label: string;
      mock: boolean;
      text?: string;
      texts?: string[];
      selected: number;
    }
  | { phase: "error"; label: string; message: string };

type ReviewState =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "result"; result: ReviewResult }
  | { phase: "error"; message: string };

const OBJECTIVES = [
  "Teach something useful",
  "Share a project update",
  "Start a discussion",
  "Document a lesson learned",
];

const STATUS_LABELS: Record<StudioStatus, string> = {
  idea: "Idea",
  draft: "Draft",
  approved: "Approved",
};

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

export default function Studio() {
  const [items, setItems] = useState<StudioItemSummary[]>([]);
  const [itemsLoading, setItemsLoading] = useState(true);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<string>("");

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [contentType, setContentType] = useState<ContentType>("educational");
  const [statusSel, setStatusSel] = useState<StudioStatus>("draft");
  const [topic, setTopic] = useState("");
  const [objective, setObjective] = useState(OBJECTIVES[0]);
  const [notes, setNotes] = useState("");

  const [saveState, setSaveState] = useState<SaveState>({ kind: "saved" });
  const [opening, setOpening] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [ai, setAi] = useState<AiState>({ phase: "idle" });
  const [review, setReview] = useState<ReviewState>({ phase: "idle" });
  const [sessionExpired, setSessionExpired] = useState(false);
  const [research, setResearch] = useState<SavedResearch | null>(null);
  const [schedule, setSchedule] = useState<{
    at: string | null;
    tz: string | null;
  } | null>(null);
  const [schedModal, setSchedModal] = useState<"schedule" | "reschedule" | null>(null);
  const [confirmUnsched, setConfirmUnsched] = useState(false);
  const [schedBusy, setSchedBusy] = useState(false);
  const [pubInfo, setPubInfo] = useState<{
    status: string;
    postId: string | null;
    publishedAt: string | null;
    error: string;
    mock: boolean;
  } | null>(null);
  const [confirmPublish, setConfirmPublish] = useState(false);
  const [pubBusy, setPubBusy] = useState(false);
  const [pubError, setPubError] = useState<string | null>(null);
  const location = useLocation() as { state?: { researchId?: number } };
  const [params] = useSearchParams();
  const openedParam = useRef<string | null>(null);

  const fingerprint = useMemo(
    () => JSON.stringify([title, body, contentType, statusSel]),
    [title, body, contentType, statusSel],
  );
  const dirty = fingerprint !== snapshot;

  useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!dirty) return;
    const onUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [dirty]);

  const refreshItems = useCallback(() => {
    setItemsLoading(true);
    listStudioItems()
      .then(setItems)
      .catch((err: unknown) => {
        if (isSessionError(err)) setSessionExpired(true);
      })
      .finally(() => setItemsLoading(false));
  }, []);

  useEffect(() => refreshItems(), [refreshItems]);

  useEffect(() => {
    const researchId = location.state?.researchId;
    if (!researchId) return;
    window.history.replaceState({}, "");
    getResearchItem(researchId)
      .then((item) => {
        setResearch(item);
        setTopic((t) => t || item.topic || "");
        setNotes((n) =>
          n ||
          `Research: ${item.title}\n${item.summary}\nAngle: ${item.linkedin_angle}`,
        );
      })
      .catch((err: unknown) => {
        if (isSessionError(err)) setSessionExpired(true);
      });
  }, [location.state]);

  useEffect(() => {
    setSaveState((prev) => {
      if (dirty) return prev.kind === "error" ? prev : { kind: "dirty" };
      return { kind: "saved" };
    });
  }, [dirty]);

  const confirmDiscard = () =>
    !dirty ||
    window.confirm("Discard unsaved changes in the editor?");

  const applySnapshot = (
    id: number | null,
    t: string,
    b: string,
    ct: string,
    st: string,
  ) => {
    setActiveId(id);
    setSnapshot(JSON.stringify([t, b, ct, st]));
    setSaveState({ kind: "saved" });
    setNotFound(false);
  };

  const newPost = () => {
    if (!confirmDiscard()) return;
    setTitle("");
    setBody("");
    setContentType("educational");
    setStatusSel("draft");
    setAi({ phase: "idle" });
    setReview({ phase: "idle" });
    setSchedule(null);
    setConfirmUnsched(false);
    setPubInfo(null);
    setConfirmPublish(false);
    setPubError(null);
    setActiveId(null);
    setSnapshot(JSON.stringify(["", "", "educational", "draft"]));
    setSaveState({ kind: "saved" });
    setNotFound(false);
  };

  const openItem = (id: number) => {
    if (id === activeId || !confirmDiscard()) return;
    setOpening(true);
    getStudioItem(id)
      .then((item) => {
        const scheduled = item.status === "scheduled";
        const terminal =
          scheduled || item.status === "published" || item.status === "failed";
        setTitle(item.title);
        setBody(item.body);
        setContentType(item.content_type as ContentType);
        setStatusSel(terminal ? "approved" : (item.status as StudioStatus));
        setSchedule(
          scheduled
            ? { at: item.scheduled_at, tz: item.scheduled_tz }
            : null,
        );
        setPubInfo(
          item.status === "published" || item.status === "failed"
            ? {
                status: item.status,
                postId: item.linkedin_post_id,
                publishedAt: item.published_at,
                error: item.publish_error || "",
                mock: (item.linkedin_post_id ?? "").startsWith("mock:"),
              }
            : null,
        );
        setConfirmPublish(false);
        setPubError(null);
        setAi({ phase: "idle" });
        setReview({ phase: "idle" });
        setConfirmUnsched(false);
        setConfirmPublish(false);
        setPubError(null);
        applySnapshot(
          item.id,
          item.title,
          item.body,
          item.content_type,
          terminal ? "approved" : item.status,
        );
      })
      .catch((err: unknown) => {
        if (isSessionError(err)) setSessionExpired(true);
        else setNotFound(true);
      })
      .finally(() => setOpening(false));
  };

  useEffect(() => {
    const idParam = params.get("id");
    if (!idParam || openedParam.current === idParam) return;
    const id = Number(idParam);
    if (!Number.isInteger(id)) {
      setNotFound(true);
      return;
    }
    openedParam.current = idParam;
    openItem(id);
  }, [params]);

  const save = useCallback(async () => {
    setSaveState({ kind: "saving" });
    try {
      if (!activeId) {
        const created = await createStudioItem({
          title,
          body,
          content_type: contentType,
          status: statusSel,
        });
        setActiveId(created.id);
        setSchedule(null);
      } else {
        const [snapTitle, snapBody, snapCt, snapStatus] = JSON.parse(
          snapshot || '["","","educational","draft"]',
        ) as string[];
        const patch: Record<string, string> = {};
        if (title !== snapTitle) patch.title = title;
        if (body !== snapBody) patch.body = body;
        if (contentType !== snapCt) patch.content_type = contentType;
        if (statusSel !== snapStatus) patch.status = statusSel;
        if (Object.keys(patch).length > 0) {
          const updated = await updateStudioItem(activeId, patch);
          setSchedule(
            updated.status === "scheduled"
              ? { at: updated.scheduled_at, tz: updated.scheduled_tz }
              : null,
          );
          setPubInfo(
            updated.status === "published" || updated.status === "failed"
              ? {
                  status: updated.status,
                  postId: updated.linkedin_post_id,
                  publishedAt: updated.published_at,
                  error: updated.publish_error || "",
                  mock: (updated.linkedin_post_id ?? "").startsWith("mock:"),
                }
              : pubInfo,
          );
        }
      }
      setSnapshot(fingerprint);
      setSaveState({ kind: "saved" });
      refreshItems();
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      setSaveState({
        kind: "error",
        message: err instanceof Error ? err.message : "Save failed",
      });
    }
  }, [title, body, contentType, statusSel, activeId, fingerprint, snapshot, refreshItems, pubInfo]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty) void save();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [dirty, save]);

  const handlePublish = async () => {
    if (!activeId) return;
    setPubBusy(true);
    setPubError(null);
    try {
      const published = await publishItem(activeId);
      setPubInfo({
        status: published.status,
        postId: published.linkedin_post_id,
        publishedAt: published.published_at,
        error: published.publish_error || "",
        mock: published.mock === true,
      });
      setConfirmPublish(false);
      refreshItems();
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else {
        const code = err instanceof Error ? err.message : "";
        setPubError(publishErrorMessage(code));
        if (code === "already_published" && activeId) {
          getStudioItem(activeId)
            .then((item) =>
              setPubInfo({
                status: item.status,
                postId: item.linkedin_post_id,
                publishedAt: item.published_at,
                error: item.publish_error || "",
                mock: (item.linkedin_post_id ?? "").startsWith("mock:"),
              }),
            )
            .catch(() => undefined);
        }
      }
    } finally {
      setPubBusy(false);
    }
  };

  const handleUnschedule = async () => {
    if (!activeId) return;
    setSchedBusy(true);
    try {
      await unscheduleItem(activeId);
      setSchedule(null);
      setConfirmUnsched(false);
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else
        setSaveState({
          kind: "error",
          message: err instanceof Error ? err.message : "Unschedule failed",
        });
    } finally {
      setSchedBusy(false);
    }
  };

  const refreshSchedule = async () => {
    if (!activeId) return;
    try {
      const item = await getStudioItem(activeId);
      setSchedule(
        item.status === "scheduled"
          ? { at: item.scheduled_at, tz: item.scheduled_tz }
          : null,
      );
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
    }
  };

  const contextText = useMemo(() => {
    const parts = [`Objective: ${objective}.`];
    if (notes.trim()) parts.push(`Notes: ${notes.trim()}`);
    return parts.join(" ");
  }, [objective, notes]);

  const runAction = async (action: AiAction, label: string) => {
    setAi({ phase: "loading", label });
    try {
      const result: AiResult = await runAiAction({
        action,
        content: body,
        topic: topic.trim(),
        content_type: contentType,
        context: contextText,
      });
      setAi({
        phase: "result",
        label,
        mock: result.mock,
        text: result.text,
        texts: result.texts,
        selected: 0,
      });
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      setAi({
        phase: "error",
        label,
        message: err instanceof Error ? err.message : "AI action failed",
      });
    }
  };

  const applyAiResult = () => {
    if (ai.phase !== "result") return;
    const text = ai.texts ? ai.texts[ai.selected] : (ai.text ?? "");
    setBody(text);
    setAi({ phase: "idle" });
  };

  const analyze = async () => {
    setReview({ phase: "loading" });
    try {
      setReview({ phase: "result", result: await reviewDraft(body) });
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      setReview({
        phase: "error",
        message: err instanceof Error ? err.message : "Analysis failed",
      });
    }
  };

  const words = body.trim() ? body.trim().split(/\s+/).length : 0;
  const hasBody = body.trim().length > 0;
  const hasTopic = topic.trim().length > 0;

  const pristine = activeId === null && !title && !body;
  const saveLabel =
    saveState.kind === "saving"
      ? "Saving…"
      : saveState.kind === "error"
        ? "Save failed — retry"
        : dirty || pristine
          ? "Save"
          : "Saved";

  return (
    <div className="mx-auto w-full max-w-[1400px]">
      {sessionExpired && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          Session expired —{" "}
          <Link to="/login" className="font-medium underline">
            please log in again
          </Link>
          .
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
            pubInfo?.status === "published"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : pubInfo?.status === "failed"
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : statusSel === "approved"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-slate-200 bg-white text-slate-600"
          }`}
        >
          {pubInfo?.status === "published"
            ? "Published"
            : pubInfo?.status === "failed"
              ? "Failed"
              : STATUS_LABELS[statusSel]}
        </span>
        <span aria-live="polite" className="text-xs text-slate-500">
          {saveState.kind === "error"
            ? saveState.message
            : saveState.kind === "saving"
              ? "Saving…"
              : dirty
                ? "Unsaved changes"
                : "All changes saved"}
        </span>
        <span className="text-xs text-slate-400 tabular-nums">
          {words} words · {body.length} chars
        </span>
        <div className="ml-auto">
          <button
            onClick={() => void save()}
            disabled={!dirty || saveState.kind === "saving"}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 active:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {saveLabel}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4 xl:grid xl:grid-cols-[250px_minmax(0,1fr)_320px] xl:items-start">
        {/* LEFT — context */}
        <aside className="order-2 flex flex-col gap-4 xl:order-none" aria-label="Context">
          <Panel title="Post">
            <button
              onClick={newPost}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 active:bg-slate-100"
            >
              + New post
            </button>
            <div className="mt-3 flex flex-col gap-3">
              <Field label="Topic">
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="What is this post about?"
                  className={inputClass}
                />
              </Field>
              <Field label="Content type">
                <select
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value as ContentType)}
                  className={inputClass}
                >
                  {(Object.keys(CONTENT_TYPE_LABELS) as ContentType[]).map(
                    (ct) => (
                      <option key={ct} value={ct}>
                        {CONTENT_TYPE_LABELS[ct]}
                      </option>
                    ),
                  )}
                </select>
              </Field>
              <Field label="Objective">
                <select
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  className={inputClass}
                >
                  {OBJECTIVES.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Notes">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Angles, examples, constraints…"
                  rows={3}
                  className={`${inputClass} resize-y`}
                />
              </Field>
            </div>
          </Panel>

          <Panel title="Schedule">
            {schedule ? (
              <div>
                <p className="text-[13px] text-slate-600">
                  Scheduled:{" "}
                  <span className="font-medium text-slate-900">
                    {formatDateTime(schedule.at)}
                  </span>
                  {schedule.tz && (
                    <span className="text-slate-400"> · {schedule.tz}</span>
                  )}
                </p>
                <div className="mt-2.5 flex gap-2">
                  <button
                    onClick={() => setSchedModal("reschedule")}
                    className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                  >
                    Reschedule
                  </button>
                  <button
                    onClick={() => setConfirmUnsched(true)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                  >
                    Unschedule
                  </button>
                </div>
                {confirmUnsched && (
                  <div
                    className="float-enter mt-2.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5"
                    role="alertdialog"
                    aria-label="Unschedule this post?"
                  >
                    <p className="text-xs text-amber-800">
                      Remove the schedule? The post returns to approved.
                    </p>
                    <div className="mt-2 flex gap-2">
                      <button
                        autoFocus
                        onClick={() => void handleUnschedule()}
                        disabled={schedBusy}
                        className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                      >
                        {schedBusy ? "Working…" : "Unschedule"}
                      </button>
                      <button
                        onClick={() => setConfirmUnsched(false)}
                        className="rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-100/50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : !activeId || dirty ? (
              <p className="text-[13px] leading-relaxed text-slate-500">
                Save the post before scheduling.
              </p>
            ) : statusSel !== "approved" ? (
              <p className="text-[13px] leading-relaxed text-slate-500">
                Approve this post before scheduling.
              </p>
            ) : (
              <button
                onClick={() => setSchedModal("schedule")}
                className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
              >
                Schedule post
              </button>
            )}
          </Panel>

          <Panel title="Publish">
            {pubInfo?.status === "published" ? (
              <div>
                <p className="text-[13px] font-medium text-slate-800">
                  {pubInfo.mock ? "Published — Mock LinkedIn" : "Published to LinkedIn"}
                </p>
                {pubInfo.publishedAt && (
                  <p className="mt-1 text-xs text-slate-500">
                    {new Date(pubInfo.publishedAt).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </p>
                )}
                {pubInfo.postId && (
                  <p className="mt-1.5 break-all font-mono text-[11px] text-slate-400">
                    {pubInfo.postId}
                  </p>
                )}
                <p className="mt-2 text-xs text-slate-400">
                  Further edits won&apos;t unpublish this post.
                </p>
              </div>
            ) : !activeId || dirty ? (
              <p className="text-[13px] leading-relaxed text-slate-500">
                Save the post before publishing.
              </p>
            ) : statusSel !== "approved" ? (
              <p className="text-[13px] leading-relaxed text-slate-500">
                Approve this post before publishing.
              </p>
            ) : (
              <div>
                {pubInfo?.status === "failed" && (
                  <p className="mb-2.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800" role="alert">
                    Last attempt failed: {publishErrorMessage(pubInfo.error)}
                  </p>
                )}
                {!confirmPublish ? (
                  <button
                    onClick={() => {
                      setPubError(null);
                      setConfirmPublish(true);
                    }}
                    className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
                  >
                    {pubInfo?.status === "failed" ? "Retry publish" : "Publish post"}
                  </button>
                ) : (
                  <div className="float-enter rounded-lg border border-slate-200 bg-slate-50 p-3" role="alertdialog" aria-label="Confirm publishing">
                    <p className="text-[13px] text-slate-700">
                      Publish this post? In live mode this creates a real
                      LinkedIn post.
                    </p>
                    <div className="mt-2.5 flex gap-2">
                      <button
                        autoFocus
                        onClick={() => void handlePublish()}
                        disabled={pubBusy}
                        className="flex-1 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                      >
                        {pubBusy ? "Publishing…" : "Publish"}
                      </button>
                      <button
                        onClick={() => setConfirmPublish(false)}
                        className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                {pubError && (
                  <p className="mt-2.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs leading-relaxed text-red-700" role="alert">
                    {pubError}
                  </p>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Research">
            {research ? (
              <div>
                <p className="text-[13px] font-medium text-slate-800">
                  {research.title}
                </p>
                <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-500">
                  {research.summary}
                </p>
                <button
                  onClick={() => setResearch(null)}
                  className="mt-2 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
                >
                  Remove context
                </button>
              </div>
            ) : (
              <p className="text-[13px] leading-relaxed text-slate-500">
                No research selected yet. Choose “Use in Content Studio” on
                the{" "}
                <Link to="/research" className="font-medium text-slate-700 underline underline-offset-2 hover:text-slate-900">
                  Research page
                </Link>{" "}
                to attach context here.
              </p>
            )}
          </Panel>

          <Panel title="Your posts">
            {itemsLoading ? (
              <p className="text-[13px] text-slate-400">Loading…</p>
            ) : items.length === 0 ? (
              <p className="text-[13px] text-slate-500">
                No posts yet. Your saved work will appear here.
              </p>
            ) : (
              <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto">
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => openItem(item.id)}
                      disabled={opening}
                      className={`w-full truncate rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors disabled:opacity-50 ${
                        item.id === activeId
                          ? "bg-slate-900 font-medium text-white"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      }`}
                    >
                      {item.title || "(untitled)"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </aside>

        {/* CENTER — editor */}
        <section className="order-1 min-w-0 xl:order-none" aria-label="Editor">
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5">
            {notFound ? (
              <div className="py-10 text-center" role="alert">
                <p className="text-sm font-medium text-slate-700">Post not found</p>
                <p className="mt-1 text-[13px] text-slate-500">
                  It may have been deleted or belong to another account.
                </p>
                <button
                  onClick={newPost}
                  className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
                >
                  Start a new post
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <Field label="Working title">
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Internal title (not published)"
                    maxLength={255}
                    className={`${inputClass} text-[15px] font-medium`}
                  />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Content type">
                    <select
                      value={contentType}
                      onChange={(e) => setContentType(e.target.value as ContentType)}
                      className={inputClass}
                    >
                      {(Object.keys(CONTENT_TYPE_LABELS) as ContentType[]).map(
                        (ct) => (
                          <option key={ct} value={ct}>
                            {CONTENT_TYPE_LABELS[ct]}
                          </option>
                        ),
                      )}
                    </select>
                  </Field>
                  <Field label="Status">
                    <select
                      value={statusSel}
                      onChange={(e) => setStatusSel(e.target.value as StudioStatus)}
                      className={inputClass}
                    >
                      {(Object.keys(STATUS_LABELS) as StudioStatus[]).map((s) => (
                        <option key={s} value={s}>
                          {STATUS_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
                <Field label="Post content">
                  <textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder="Write your LinkedIn post here…"
                    rows={18}
                    maxLength={20000}
                    aria-label="Post content"
                    className={`${inputClass} resize-y leading-relaxed`}
                  />
                </Field>
              </div>
            )}
          </div>
        </section>

        {/* RIGHT — AI assistant + quality */}
        <aside className="order-3 flex flex-col gap-4 xl:order-none" aria-label="AI assistant">
          <Panel title="AI Assistant">
            <button
              onClick={() => void runAction("generate", "Generate")}
              disabled={!hasTopic || ai.phase === "loading"}
              title={hasTopic ? "Generate a draft from the topic" : "Enter a topic first"}
              className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 active:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {ai.phase === "loading" && ai.label === "Generate"
                ? "Generating…"
                : "Generate draft"}
            </button>
            {!hasTopic && (
              <p className="mt-2 text-xs text-slate-400">
                Enter a topic on the left to enable generation.
              </p>
            )}
            <div className="mt-3 grid grid-cols-2 gap-1.5">
              {REWRITE_ACTIONS.map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => void runAction(key, label)}
                  disabled={!hasBody || ai.phase === "loading"}
                  title={hasBody ? label : "Write something first"}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 active:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {ai.phase === "loading" && ai.label === label ? "Working…" : label}
                </button>
              ))}
            </div>
            {!hasBody && (
              <p className="mt-2 text-xs text-slate-400">
                Rewrite tools activate once the editor has content.
              </p>
            )}

            {ai.phase === "error" && (
              <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
                {ai.label} failed: {ai.message}
              </p>
            )}

            {ai.phase === "result" && (
              <div className="float-enter mt-3 rounded-lg border border-slate-300 bg-slate-50 p-3" aria-live="polite">
                <p className="mb-2 flex items-center text-xs font-semibold text-slate-600">
                  {ai.label} result
                  {ai.mock && (
                    <span className="ml-2 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
                      MOCK
                    </span>
                  )}
                </p>
                {ai.texts ? (
                  <div className="flex flex-col gap-2" role="radiogroup" aria-label="Alternatives">
                    {ai.texts.map((t, i) => (
                      <button
                        key={i}
                        role="radio"
                        aria-checked={ai.selected === i}
                        onClick={() => setAi({ ...ai, selected: i })}
                        className={`max-h-36 overflow-y-auto whitespace-pre-wrap rounded-lg border p-2.5 text-left text-[13px] leading-relaxed transition-colors ${
                          ai.selected === i
                            ? "border-slate-900 bg-white"
                            : "border-slate-200 bg-white text-slate-600 hover:border-slate-400"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="max-h-64 overflow-y-auto whitespace-pre-wrap text-[13px] leading-relaxed text-slate-700">
                    {ai.text}
                  </p>
                )}
                <div className="mt-2.5 flex gap-2">
                  <button
                    onClick={applyAiResult}
                    className="flex-1 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700"
                  >
                    Apply to editor
                  </button>
                  <button
                    onClick={() => setAi({ phase: "idle" })}
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-white"
                  >
                    Dismiss
                  </button>
                </div>
                <p className="mt-2 text-[11px] text-slate-400">
                  Applying replaces the editor content — save afterward to keep it.
                </p>
              </div>
            )}
          </Panel>

          <Panel title="Quality Review">
            {!hasBody ? (
              <p className="text-[13px] text-slate-500">
                Write or generate content first, then run an analysis.
              </p>
            ) : (
              <button
                onClick={() => void analyze()}
                disabled={review.phase === "loading"}
                className="w-full rounded-lg border border-slate-900 bg-white px-3 py-2 text-sm font-medium text-slate-900 transition-colors hover:bg-slate-900 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {review.phase === "loading" ? "Analyzing…" : "Analyze quality"}
              </button>
            )}

            {review.phase === "error" && (
              <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
                Analysis failed: {review.message}
              </p>
            )}

            {review.phase === "result" && (
              <div className="float-enter mt-3" aria-live="polite">
                <p className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tracking-tight tabular-nums">
                    {review.result.score}
                  </span>
                  <span className="text-xs text-slate-400">/100 · heuristic</span>
                  {review.result.mock && (
                    <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
                      MOCK
                    </span>
                  )}
                </p>
                <ul className="mt-2 divide-y divide-slate-100">
                  {review.result.dimensions.map((d) => (
                    <li key={d.key} className="py-2">
                      <p className="flex items-center justify-between gap-2 text-[13px]">
                        <span className="font-medium text-slate-700">{d.label}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            d.status === "strong"
                              ? "bg-emerald-50 text-emerald-700"
                              : d.status === "good"
                                ? "bg-slate-100 text-slate-600"
                                : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {d.status === "strong"
                            ? "Strong"
                            : d.status === "good"
                              ? "Good"
                              : "Needs work"}
                        </span>
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">{d.detail}</p>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
                  {review.result.factual_note}
                </p>
              </div>
            )}
          </Panel>
        </aside>
      </div>

      {schedModal && activeId && (
        <ScheduleModal
          itemId={activeId}
          itemTitle={title}
          mode={schedModal}
          initial={
            schedModal === "reschedule" && schedule
              ? { scheduled_at: schedule.at, scheduled_tz: schedule.tz }
              : undefined
          }
          onClose={() => setSchedModal(null)}
          onSaved={() => {
            setSchedModal(null);
            void refreshSchedule();
          }}
        />
      )}
    </div>
  );
}
