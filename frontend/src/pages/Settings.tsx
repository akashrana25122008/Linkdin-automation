import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  API_URL,
  disconnectLinkedIn,
  fetchLinkedInStatus,
  mockLinkedInConnect,
  type LinkedInStatus,
} from "../api";
import { useAuth } from "../auth";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

const CALLBACK_MESSAGES: Record<string, { kind: "ok" | "error"; text: string }> = {
  connected: { kind: "ok", text: "LinkedIn account connected." },
  cancelled: { kind: "error", text: "LinkedIn authorization was cancelled. No connection was created." },
  state: { kind: "error", text: "LinkedIn authorization could not be verified. Please try again." },
  session: { kind: "error", text: "Your session expired during LinkedIn authorization. Please log in and try again." },
  error: { kind: "error", text: "LinkedIn authorization failed. Please try again." },
};

export default function Settings() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<LinkedInStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  const callbackKey = params.get("linkedin");

  const load = useCallback(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchLinkedInStatus(controller.signal)
      .then((s) => {
        setStatus(s);
        setError(null);
      })
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        if (isSessionError(err)) setSessionExpired(true);
        else setError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => load(), [load]);

  useEffect(() => {
    if (callbackKey) {
      load();
      navigate("/settings", { replace: true });
    }
  }, [callbackKey, load, navigate]);

  const handleDisconnect = async () => {
    setBusy(true);
    try {
      await disconnectLinkedIn();
      setConfirmDisconnect(false);
      load();
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusy(false);
    }
  };

  const handleMockConnect = async () => {
    setBusy(true);
    try {
      setStatus(await mockLinkedInConnect());
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else setError(err instanceof Error ? err.message : "Mock connect failed");
    } finally {
      setBusy(false);
    }
  };

  const feedback = callbackKey ? CALLBACK_MESSAGES[callbackKey] : null;

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

      {feedback && (
        <p
          role={feedback.kind === "ok" ? "status" : "alert"}
          className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
            feedback.kind === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {feedback.text}
        </p>
      )}

      <section aria-label="Account" className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
          Account
        </h2>
        <div className="mt-3 flex items-center gap-3">
          {user?.profile_picture ? (
            <img
              src={user.profile_picture}
              alt=""
              className="h-10 w-10 rounded-full"
              referrerPolicy="no-referrer"
            />
          ) : (
            <span aria-hidden="true" className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-500">
              {(user?.name ?? user?.email ?? "?").charAt(0).toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">
              {user?.name ?? "Account"}
            </p>
            <p className="truncate text-[13px] text-slate-500">{user?.email ?? ""}</p>
          </div>
          <span className="ml-auto shrink-0 rounded-full border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-500">
            Google sign-in
          </span>
        </div>
      </section>

      <section aria-label="LinkedIn connection" className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2">
          <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
            LinkedIn
          </h2>
          {status?.mock && (
            <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
              DEVELOPMENT MOCK
            </span>
          )}
        </div>
        <p className="mt-1 text-[13px] text-slate-500">
          LinkedIn authorization is separate from your Google sign-in. Connecting
          lets the app act on your LinkedIn account when you publish — nothing
          is published by connecting.
        </p>

        <div className="mt-4">
          {loading ? (
            <p className="text-sm text-slate-400" role="status">Checking LinkedIn status…</p>
          ) : error ? (
            <div role="alert">
              <p className="text-sm text-red-600">Couldn&apos;t load LinkedIn status: {error}</p>
              <button onClick={load} className="mt-2 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50">
                Retry
              </button>
            </div>
          ) : status && !status.connected && status.mode === "live" && status.configured === false ? (
            <div className="rounded-lg bg-slate-50 px-4 py-3">
              <p className="text-sm font-medium text-slate-700">LinkedIn OAuth: NOT CONFIGURED</p>
              <p className="mt-1 text-[13px] text-slate-500">
                Add LinkedIn credentials to the server configuration to enable
                real account connection. No connection is faked in the meantime.
              </p>
            </div>
          ) : status && !status.connected ? (
            <div>
              <p className="text-sm text-slate-600">
                {status.mock
                  ? "Not connected. Mock mode is active for development — no real LinkedIn account is involved."
                  : "Not connected."}
              </p>
              {status.mock ? (
                <button
                  onClick={() => void handleMockConnect()}
                  disabled={busy}
                  className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                >
                  {busy ? "Connecting…" : "Mock connect (development only)"}
                </button>
              ) : (
                <a
                  href={`${API_URL}/api/linkedin/connect`}
                  className="mt-3 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
                >
                  Connect LinkedIn
                </a>
              )}
            </div>
          ) : status ? (
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Connected{status.mock ? " (mock)" : ""}
                </span>
                <p className="text-sm font-medium text-slate-900">{status.member_name}</p>
              </div>
              <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
                {status.connected_at && (
                  <>
                    <dt className="text-slate-400">Connected</dt>
                    <dd className="text-slate-600">
                      {new Date(status.connected_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </dd>
                  </>
                )}
                {status.scopes.length > 0 && (
                  <>
                    <dt className="text-slate-400">Scopes</dt>
                    <dd className="flex flex-wrap gap-1">
                      {status.scopes.map((s) => (
                        <code key={s} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                          {s}
                        </code>
                      ))}
                    </dd>
                  </>
                )}
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {!status.mock && (
                  <a
                    href={`${API_URL}/api/linkedin/connect`}
                    className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50"
                  >
                    Reconnect
                  </a>
                )}
                <button
                  onClick={() => setConfirmDisconnect(true)}
                  disabled={busy}
                  className="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
                >
                  Disconnect
                </button>
              </div>
              {confirmDisconnect && (
                <div
                  className="float-enter mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
                  role="alertdialog"
                  aria-label="Disconnect LinkedIn?"
                >
                  <p className="text-[13px] text-amber-800">
                    Disconnect {status.member_name ?? "this account"}? Stored
                    credentials are removed. Your posts, drafts, and settings
                    are unaffected.
                  </p>
                  <div className="mt-2.5 flex gap-2">
                    <button
                      autoFocus
                      onClick={() => void handleDisconnect()}
                      disabled={busy}
                      className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50"
                    >
                      {busy ? "Working…" : "Disconnect"}
                    </button>
                    <button
                      onClick={() => setConfirmDisconnect(false)}
                      className="rounded-lg border border-amber-200 bg-white px-3.5 py-1.5 text-xs font-medium text-amber-800 transition-colors hover:bg-amber-100/50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
