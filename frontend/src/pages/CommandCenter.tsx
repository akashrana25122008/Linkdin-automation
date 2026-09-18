import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { runCommand, type CommandResponse } from "../api";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

const EXAMPLES = [
  "Create a LinkedIn post about my latest project.",
  "Give me three post ideas based on my strategy.",
  "Find recent AI topics I can post about.",
  "Review my latest draft.",
  "Repurpose my last published post.",
  "Schedule this draft for Friday at 7 PM.",
  "Show me what I have scheduled.",
  "Why did the AI reject this post?",
];

interface Exchange {
  id: number;
  command: string;
  response: CommandResponse | null;
  error: string | null;
  pendingProposal: Record<string, unknown> | null;
}

const HISTORY_KEY = "li-ai-command-history";
let nextId = 1;

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string").slice(0, 10) : [];
  } catch {
    return [];
  }
}

export default function CommandCenter() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [history, setHistory] = useState<string[]>(loadHistory);
  const [sessionExpired, setSessionExpired] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [exchanges.length, busy]);

  const remember = (text: string) => {
    setHistory((prev) => {
      const next = [text, ...prev.filter((h) => h !== text)].slice(0, 10);
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable — history simply won't persist */
      }
      return next;
    });
  };

  const submit = async (text: string, confirmed = false, proposal?: Record<string, unknown>) => {
    const command = text.trim();
    if (!command || busy) return;
    setBusy(true);
    const id = nextId++;
    setExchanges((list) => [...list, { id, command, response: null, error: null, pendingProposal: null }]);
    try {
      const response = await runCommand(command, { confirmed, proposal });
      setExchanges((list) =>
        list.map((ex) =>
          ex.id === id
            ? {
                ...ex,
                response,
                pendingProposal: response.needs_confirmation ? (response.proposal ?? null) : null,
              }
            : ex,
        ),
      );
      remember(command);
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      setExchanges((list) =>
        list.map((ex) =>
          ex.id === id
            ? { ...ex, error: err instanceof Error ? err.message : "Command failed" }
            : ex,
        ),
      );
    } finally {
      setBusy(false);
    }
  };

  const confirm = (ex: Exchange) => {
    if (!ex.pendingProposal) return;
    setExchanges((list) => list.filter((e) => e.id !== ex.id));
    void submit(ex.command, true, ex.pendingProposal);
  };

  const openAction = (ex: Exchange) => {
    const action = ex.response?.action;
    if (!action) return;
    if (action.kind === "navigate" && action.href) {
      navigate(action.href);
    } else if (action.kind === "studio_prefill") {
      navigate("/studio", {
        state: {
          importResult: {
            topic: action.topic ?? "",
            notes: action.notes ?? "",
            body: action.body ?? "",
          },
        },
      });
    }
  };

  const actionable = (ex: Exchange) => {
    const action = ex.response?.action;
    if (!action || action.kind === "none") return null;
    if (action.kind === "navigate") return action.href ? "Open" : null;
    return "Open in Studio";
  };

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col">
      <p className="text-sm text-slate-500">
        Control your workspace in plain language. Commands run your real
        drafts, research, calendar, and settings — publishing and deletion
        always stay in their approval UI.
      </p>

      {sessionExpired && (
        <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          Session expired —{" "}
          <Link to="/login" className="font-medium underline">
            please log in again
          </Link>
          .
        </p>
      )}

      <div className="mt-4 flex flex-col gap-3" aria-live="polite">
        {exchanges.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <p className="text-sm font-medium text-slate-700">Try one of these</p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {EXAMPLES.map((example) => (
                <li key={example}>
                  <button
                    onClick={() => void submit(example)}
                    disabled={busy}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50"
                  >
                    {example}
                  </button>
                </li>
              ))}
            </ul>
            {history.length > 0 && (
              <>
                <p className="mt-4 text-sm font-medium text-slate-700">Recent</p>
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {history.map((h) => (
                    <li key={h}>
                      <button
                        onClick={() => void submit(h)}
                        disabled={busy}
                        className="rounded-full bg-slate-100 px-3 py-1.5 text-left text-xs text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-800 disabled:opacity-50"
                      >
                        {h}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        {exchanges.map((ex) => (
          <div key={ex.id} className="rounded-xl border border-slate-200 bg-white">
            <p className="border-b border-slate-100 px-4 py-2.5 text-sm font-medium text-slate-900">
              {ex.command}
            </p>
            <div className="px-4 py-3">
              {ex.error ? (
                <p className="text-sm text-red-600" role="alert">{ex.error}</p>
              ) : !ex.response ? (
                <p className="text-sm text-slate-400" role="status">Working…</p>
              ) : (
                <>
                  <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
                    {ex.response.intent.replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-slate-700">
                    {ex.response.message}
                  </p>
                  {ex.response.mock && (
                    <span className="mt-1.5 inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
                      MOCK
                    </span>
                  )}
                  {ex.response.ideas && ex.response.ideas.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1.5">
                      {ex.response.ideas.map((idea, i) => (
                        <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-[13px] text-slate-700">
                          <span className="font-medium text-slate-900">{idea.topic}</span>
                          <span className="text-slate-400"> · {idea.content_type}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {ex.response.results && ex.response.results.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1.5">
                      {ex.response.results.map((r, i) => (
                        <li key={i} className="rounded-lg bg-slate-50 px-3 py-2 text-[13px]">
                          <span className="font-medium text-slate-900">{r.title}</span>
                          {r.angle && <span className="block text-slate-500">{r.angle}</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                  {ex.response.review && (
                    <p className="mt-2 text-[13px] text-slate-600">
                      Quality {ex.response.review.score}/100 ·{" "}
                      {ex.response.review.dimensions
                        .filter((d) => d.status === "needs_work")
                        .map((d) => d.label)
                        .join(", ") || "no major issues"}
                    </p>
                  )}
                  {ex.response.items && ex.response.items.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1">
                      {ex.response.items.map((item) => (
                        <li key={item.id} className="text-[13px] text-slate-600">
                          #{item.id} · {item.title || "(untitled)"}
                          {item.status ? ` · ${item.status}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                  {ex.response.recommendations && ex.response.recommendations.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1">
                      {ex.response.recommendations.map((rec, i) => (
                        <li key={i} className="text-[13px] text-slate-600">
                          <span className="font-medium text-slate-800">{rec.title}</span>
                          {" — "}
                          {rec.reason}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {ex.pendingProposal && (
                      <button
                        onClick={() => confirm(ex)}
                        disabled={busy}
                        className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                      >
                        Confirm
                      </button>
                    )}
                    {actionable(ex) && (
                      <button
                        onClick={() => openAction(ex)}
                        className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                      >
                        {actionable(ex)}
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form
        className="sticky bottom-0 mt-4 flex gap-2 bg-slate-50 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          setInput("");
          void submit(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder='Try "Review my latest draft"…'
          aria-label="Command input"
          autoFocus
          className="w-full min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400"
        />
        <button
          type="submit"
          disabled={!input.trim() || busy}
          className="shrink-0 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
