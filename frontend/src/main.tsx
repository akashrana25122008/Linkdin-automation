import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App";
import { AuthProvider, RequireAuth } from "./auth";
import ComingSoon from "./components/ComingSoon";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Privacy from "./pages/Privacy";
import Research from "./pages/Research";
import Status from "./pages/Status";
import Studio from "./pages/Studio";
import Terms from "./pages/Terms";
import { NAV_ITEMS } from "./nav";
import "./index.css";

const soonRoutes = NAV_ITEMS.filter(
  (item) => item.path !== "/" && item.path !== "/studio" && item.path !== "/research",
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
