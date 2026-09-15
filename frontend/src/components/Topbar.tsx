import { useEffect, useState } from "react";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import CommandPalette from "./CommandPalette";
import StatusBadge from "./StatusBadge";

function useDismiss(onDismiss: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onDismiss]);
}

export default function Topbar({
  title,
  description,
  linkedinLabel,
  onMenu,
}: {
  title: string;
  description: string;
  linkedinLabel: string | null;
  onMenu: () => void;
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [openPanel, setOpenPanel] = useState<"bell" | "user" | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useDismiss(() => setOpenPanel(null));

  const toggle = (panel: "bell" | "user") =>
    setOpenPanel((p) => (p === panel ? null : panel));

  const handleLogout = async () => {
    setOpenPanel(null);
    await logout();
    navigate("/login");
  };

  const initial = (user?.name ?? user?.email ?? "?").charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
      <button
        onClick={onMenu}
        aria-label="Open navigation"
        className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 lg:hidden"
      >
        <Menu size={18} />
      </button>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold tracking-tight text-slate-900">
          {title}
        </h1>
        <p className="hidden truncate text-xs text-slate-500 sm:block">
          {description}
        </p>
      </div>

      <button
        onClick={() => setPaletteOpen(true)}
        className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-700 md:flex"
        aria-label="Search or jump to a section"
      >
        <Search size={13} />
        <span className="hidden xl:inline">Search or jump to…</span>
        <kbd className="rounded border border-slate-200 bg-white px-1 font-sans text-[10px] text-slate-400">
          ⌘K
        </kbd>
      </button>

      {linkedinLabel && (
        <span className="hidden sm:inline-flex">
          <StatusBadge
            label={linkedinLabel}
            title="LinkedIn connection arrives in a later milestone"
          />
        </span>
      )}

      <div className="relative">
        <button
          onClick={() => toggle("bell")}
          aria-label="Notifications"
          aria-expanded={openPanel === "bell"}
          className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
        >
          <Bell size={17} />
        </button>
        {openPanel === "bell" && (
          <>
            <button
              aria-label="Close notifications"
              className="fixed inset-0 z-40 cursor-default"
              onClick={() => setOpenPanel(null)}
            />
            <div className="float-enter absolute right-0 z-50 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
              <p className="text-xs font-medium text-slate-700">Notifications</p>
              <p className="mt-1 text-xs text-slate-500">
                You&apos;re all caught up. Notifications arrive with later
                milestones.
              </p>
            </div>
          </>
        )}
      </div>

      <div className="relative">
        <button
          onClick={() => toggle("user")}
          aria-label="Account menu"
          aria-expanded={openPanel === "user"}
          className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full border border-slate-200 bg-slate-100 text-xs font-semibold text-slate-600 transition-colors hover:border-slate-300"
        >
          {user?.profile_picture ? (
            <img
              src={user.profile_picture}
              alt=""
              className="h-full w-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            initial
          )}
        </button>
        {openPanel === "user" && (
          <>
            <button
              aria-label="Close account menu"
              className="fixed inset-0 z-40 cursor-default"
              onClick={() => setOpenPanel(null)}
            />
            <div className="float-enter absolute right-0 z-50 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
              <p className="truncate px-3 pb-1 pt-2 text-xs font-medium text-slate-900">
                {user?.name ?? "Account"}
              </p>
              <p className="truncate px-3 pb-2 text-xs text-slate-500">
                {user?.email ?? ""}
              </p>
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                <LogOut size={13} /> Log out
              </button>
            </div>
          </>
        )}
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </header>
  );
}
