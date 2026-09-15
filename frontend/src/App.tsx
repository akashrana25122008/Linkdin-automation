import { useEffect, useState } from "react";
import { ChevronsLeft, ChevronsRight, Linkedin } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { fetchStatus } from "./api";
import Topbar from "./components/Topbar";
import { NAV_ITEMS, type NavItem } from "./nav";

const COLLAPSE_KEY = "li-ai-sidebar-collapsed";

function linkClass({ isActive }: { isActive: boolean }) {
  return `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
    isActive
      ? "bg-slate-900 text-white"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;
}

function SidebarLinks({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5">
      {NAV_ITEMS.map((item: NavItem) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            aria-label={collapsed ? item.label : undefined}
            className={linkClass}
          >
            <Icon size={16} className="shrink-0" />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function App() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSE_KEY) === "1",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [status, setStatus] = useState<Record<string, string> | null>(null);
  const location = useLocation();

  useEffect(() => {
    const controller = new AbortController();
    fetchStatus(controller.signal)
      .then(setStatus)
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, []);

  useEffect(() => setMobileOpen(false), [location.pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });
  };

  const active =
    NAV_ITEMS.find((n) => n.path === location.pathname) ?? NAV_ITEMS[0];
  const linkedinRaw = status?.linkedin_oauth ?? null;
  const linkedinLabel =
    linkedinRaw === null
      ? null
      : linkedinRaw === "READY"
        ? "LinkedIn ready"
        : "LinkedIn not connected";

  const linkedinRow = (mini: boolean) => (
    <div
      className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2"
      title="LinkedIn connection arrives in a later milestone"
    >
      <Linkedin size={14} className="shrink-0 text-slate-400" />
      {mini ? (
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-slate-400" />
      ) : (
        <span className="truncate text-xs text-slate-500">
          {linkedinLabel ?? "LinkedIn status…"}
        </span>
      )}
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:shadow-lg"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside
        className={`sticky top-0 hidden h-screen shrink-0 flex-col gap-1 overflow-y-auto border-r border-slate-200 bg-white p-3 transition-[width] duration-200 ease-out lg:flex ${
          collapsed ? "w-[68px]" : "w-60"
        }`}
      >
        <div
          className={`mb-3 flex items-center gap-2 px-1 pt-1 ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <span
            aria-hidden="true"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-[11px] font-bold text-white"
          >
            Li
          </span>
          {!collapsed && (
            <span className="truncate text-sm font-semibold tracking-tight">
              LinkedIn AI
            </span>
          )}
        </div>

        <div className="flex-1">
          <SidebarLinks collapsed={collapsed} />
        </div>

        <div className="flex flex-col gap-2">
          {linkedinRow(collapsed)}
          <button
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            className="flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            {collapsed ? <ChevronsRight size={15} /> : <ChevronsLeft size={15} />}
            {!collapsed && "Collapse"}
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 cursor-default bg-slate-900/20"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="float-enter absolute inset-y-0 left-0 flex w-72 flex-col gap-1 overflow-y-auto border-r border-slate-200 bg-white p-3">
            <div className="mb-3 flex items-center gap-2 px-1 pt-1">
              <span
                aria-hidden="true"
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900 text-[11px] font-bold text-white"
              >
                Li
              </span>
              <span className="text-sm font-semibold tracking-tight">
                LinkedIn AI
              </span>
            </div>
            <div className="flex-1">
              <SidebarLinks
                collapsed={false}
                onNavigate={() => setMobileOpen(false)}
              />
            </div>
            <div className="mt-2">{linkedinRow(false)}</div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          title={active.label}
          description={active.description}
          linkedinLabel={linkedinLabel}
          onMenu={() => setMobileOpen(true)}
        />
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
          <div key={location.pathname} className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
