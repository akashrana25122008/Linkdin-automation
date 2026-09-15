import { useEffect, useMemo, useRef, useState } from "react";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { NAV_ITEMS } from "../nav";

export default function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      inputRef.current?.focus();
    }
  }, [open ]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q
      ? NAV_ITEMS.filter((item) => item.label.toLowerCase().includes(q))
      : NAV_ITEMS;
  }, [query]);

  useEffect(() => setActive(0), [results.length]);

  if (!open) return null;

  const run = (path: string | null) => {
    if (path === null) {
      void logout().then(() => navigate("/login"));
    } else {
      navigate(path);
    }
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (a + 1) % (results.length + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a - 1 + results.length + 1) % (results.length + 1));
    } else if (e.key === "Enter") {
      const item = results[active];
      run(item ? item.path : null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]">
      <button
        aria-label="Close command menu"
        className="absolute inset-0 cursor-default bg-slate-900/20"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command menu"
        onKeyDown={onKeyDown}
        className="float-enter relative w-full max-w-md overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Jump to a section…"
          aria-label="Jump to a section"
          className="w-full border-b border-slate-100 px-4 py-3 text-sm outline-none placeholder:text-slate-400"
        />
        <ul role="listbox" aria-label="Sections" className="max-h-72 overflow-y-auto p-1.5">
          {results.map((item, i) => {
            const Icon = item.icon;
            return (
              <li key={item.path}>
                <button
                  role="option"
                  aria-selected={i === active}
                  onClick={() => run(item.path)}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                    i === active
                      ? "bg-slate-100 text-slate-900"
                      : "text-slate-600"
                  }`}
                >
                  <Icon size={15} className="shrink-0 text-slate-400" />
                  {item.label}
                </button>
              </li>
            );
          })}
          <li>
            <button
              role="option"
              aria-selected={active === results.length}
              onClick={() => run(null)}
              onMouseEnter={() => setActive(results.length)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                active === results.length
                  ? "bg-slate-100 text-slate-900"
                  : "text-slate-600"
              }`}
            >
              <LogOut size={15} className="shrink-0 text-slate-400" />
              Log out
            </button>
          </li>
          {results.length === 0 && (
            <li className="px-3 py-4 text-center text-sm text-slate-400">
              No matching sections.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
