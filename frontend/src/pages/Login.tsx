import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { API_URL, fetchStatus } from "../api";
import { useAuth } from "../auth";

const ERROR_MESSAGES: Record<string, string> = {
  cancelled: "Login was cancelled before completing Google authorization.",
  state: "Login could not be verified. Please try again.",
  exchange_failed: "Google did not complete the login. Please try again.",
  auth_failed: "Google identity could not be verified. Please try again.",
};

export default function Login() {
  const { user, loading, error, refresh } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [googleOAuth, setGoogleOAuth] = useState<string | null>(null);
  const [completing, setCompleting] = useState(
    params.get("login") === "success",
  );

  useEffect(() => {
    fetchStatus()
      .then((s) => setGoogleOAuth(s.google_auth ?? null))
      .catch(() => setGoogleOAuth(null));
  }, []);

  useEffect(() => {
    if (params.get("login") !== "success") return;
    refresh().finally(() => {
      setCompleting(false);
      navigate("/", { replace: true });
    });
  }, [params, refresh, navigate]);

  useEffect(() => {
    if (user && !completing) navigate("/", { replace: true });
  }, [user, completing, navigate]);

  const errorCode = params.get("error");
  const configured = googleOAuth !== "NOT CONFIGURED";

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold tracking-tight">LinkedIn AI</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your AI content team for LinkedIn.
        </p>
        <div className="mt-6">
          {loading || completing ? (
            <p className="text-sm text-slate-500" role="status">
              {completing ? "Completing sign-in…" : "Checking session…"}
            </p>
          ) : errorCode ? (
            <p className="text-sm text-red-600" role="alert">
              {ERROR_MESSAGES[errorCode] ?? "Login failed. Please try again."}
            </p>
          ) : error ? (
            <p className="text-sm text-red-600" role="alert">
              Backend unreachable: {error}
            </p>
          ) : configured ? (
            <a
              href={`${API_URL}/api/auth/google/login`}
              className="block rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700"
            >
              Continue with Google
            </a>
          ) : (
            <p className="rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-800" role="status">
              GOOGLE OAUTH: NOT CONFIGURED — sign-in is unavailable until
              server credentials are added.
            </p>
          )}
        </div>
        <p className="mt-6 text-xs text-slate-400">
          <Link to="/terms" className="underline hover:text-slate-600">
            Terms
          </Link>
          {" · "}
          <Link to="/privacy" className="underline hover:text-slate-600">
            Privacy
          </Link>
        </p>
      </div>
    </div>
  );
}
