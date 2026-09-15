import { useEffect, useState } from "react";
import { fetchStatus } from "../api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; entries: [string, string][] };

export default function Status() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetchStatus(controller.signal)
      .then((data) => setState({ kind: "ready", entries: Object.entries(data) }))
      .catch((err: unknown) =>
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Backend unreachable",
        }),
      );
    return () => controller.abort();
  }, []);

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Backend status</h1>
      <p className="mt-1 text-sm text-slate-500">
        Honest capability flags from <code>/api/status</code>.
      </p>
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        {state.kind === "loading" && (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
        {state.kind === "error" && (
          <p className="text-sm text-red-600" role="alert">
            Backend unreachable: {state.message}
          </p>
        )}
        {state.kind === "ready" && (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            {state.entries.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-slate-500">{key}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  );
}
