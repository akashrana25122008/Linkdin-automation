import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "../api";

export default function Overview() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((data) => {
        setHealth(data);
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

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
      <p className="mt-1 text-sm text-slate-500">
        M0 foundation. Full dashboard arrives in M3 — no placeholder metrics here.
      </p>
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-medium text-slate-700">Backend health</h2>
        {loading && <p className="mt-2 text-sm text-slate-500">Checking…</p>}
        {error && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            Backend unreachable: {error}. Start it with{" "}
            <code>uvicorn app.main:app --reload</code> in backend/.
          </p>
        )}
        {health && (
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
            <dt className="text-slate-500">status</dt>
            <dd className="font-medium">{health.status}</dd>
            <dt className="text-slate-500">mock_mode</dt>
            <dd className="font-medium">{String(health.mock_mode)}</dd>
          </dl>
        )}
      </div>
    </div>
  );
}
