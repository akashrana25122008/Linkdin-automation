import { Activity, LayoutDashboard } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? "bg-slate-900 text-white"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="flex w-60 shrink-0 flex-col gap-1 border-r border-slate-200 bg-white p-4">
        <div className="mb-4 px-1">
          <p className="text-base font-semibold tracking-tight">LinkedIn AI</p>
          <p className="text-xs text-slate-500">M0 foundation</p>
        </div>
        <nav className="flex flex-col gap-1">
          <NavLink to="/" className={linkClass} end>
            <LayoutDashboard size={16} /> Overview
          </NavLink>
          <NavLink to="/status" className={linkClass}>
            <Activity size={16} /> Backend status
          </NavLink>
        </nav>
        <div className="mt-auto rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          DEVELOPMENT MODE — mock providers, no real publishing.
        </div>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
