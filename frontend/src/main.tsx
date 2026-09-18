import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import { AuthProvider, RequireAuth } from "./auth";
import Analytics from "./pages/Analytics";
import ComingSoon from "./components/ComingSoon";
import Calendar from "./pages/Calendar";
import CommandCenter from "./pages/CommandCenter";
import Drafts from "./pages/Drafts";
import Learning from "./pages/Learning";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Privacy from "./pages/Privacy";
import Published from "./pages/Published";
import Research from "./pages/Research";
import Settings from "./pages/Settings";
import Status from "./pages/Status";
import Strategy from "./pages/Strategy";
import Studio from "./pages/Studio";
import Terms from "./pages/Terms";
import { NAV_ITEMS } from "./nav";
import "./index.css";

const soonRoutes = NAV_ITEMS.filter(
  (item) =>
    item.path !== "/" &&
    item.path !== "/studio" &&
    item.path !== "/research" &&
    item.path !== "/drafts" &&
    item.path !== "/calendar" &&
    item.path !== "/strategy" &&
    item.path !== "/settings" &&
    item.path !== "/analytics" &&
    item.path !== "/learning" &&
    item.path !== "/published" &&
    item.path !== "/command",
).map((item) => ({
  path: item.path.slice(1),
  element: (
    <ComingSoon
      title={item.label}
      description={item.description}
      milestone={item.milestone}
    />
  ),
}));

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  { path: "/terms", element: <Terms /> },
  { path: "/privacy", element: <Privacy /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <App />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Overview /> },
      { path: "status", element: <Status /> },
      { path: "studio", element: <Studio /> },
      { path: "research", element: <Research /> },
      { path: "drafts", element: <Drafts /> },
      { path: "calendar", element: <Calendar /> },
      { path: "strategy", element: <Strategy /> },
      { path: "settings", element: <Settings /> },
      { path: "analytics", element: <Analytics /> },
      { path: "learning", element: <Learning /> },
      { path: "published", element: <Published /> },
      { path: "command", element: <CommandCenter /> },
      ...soonRoutes,
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </React.StrictMode>,
);
