export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  mock_mode?: boolean;
  [key: string]: unknown;
}

export interface AuthUser {
  id: number;
  email: string | null;
  name: string | null;
  profile_picture: string | null;
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/api/health`, { signal });
  if (!res.ok) throw new Error(`Backend responded with HTTP ${res.status}`);
  return (await res.json()) as HealthResponse;
}

export async function fetchStatus(
  signal?: AbortSignal,
): Promise<Record<string, string>> {
  const res = await fetch(`${API_URL}/api/status`, { signal });
  if (!res.ok) throw new Error(`Backend responded with HTTP ${res.status}`);
  return (await res.json()) as Record<string, string>;
}

export async function fetchMe(signal?: AbortSignal): Promise<AuthUser | null> {
  const res = await fetch(`${API_URL}/api/auth/me`, {
    credentials: "include",
    signal,
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`Backend responded with HTTP ${res.status}`);
  return (await res.json()) as AuthUser;
}

export async function requestLogout(): Promise<void> {
  const res = await fetch(`${API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error(`Backend responded with HTTP ${res.status}`);
}

export interface DashboardBrief {
  text: string;
  mock: boolean;
}

export interface ResearchSignal {
  title: string;
  source: string;
  url: string;
  summary: string;
  relevance_score: number;
  freshness: string;
  potential_angle: string;
  mock: boolean;
}

export interface UpcomingItem {
  id: number;
  title: string;
  status: string;
  scheduled_at: string | null;
}

export interface Recommendation {
  title: string;
  detail: string;
  href: string;
  mock: boolean;
}

export interface DashboardData {
  user: { name: string | null; email: string | null };
  brief: DashboardBrief;
  pipeline: Record<string, number>;
  signals: ResearchSignal[];
  upcoming: UpcomingItem[];
  performance: { state: string; message: string };
  recommendations: Recommendation[];
  mock: boolean;
}

export async function fetchDashboard(
  signal?: AbortSignal,
): Promise<DashboardData> {
  const res = await fetch(`${API_URL}/api/dashboard`, {
    credentials: "include",
    signal,
  });
  if (res.status === 401)
    throw new Error("Session expired — please log in again.");
  if (!res.ok) throw new Error(`Backend responded with HTTP ${res.status}`);
  return (await res.json()) as DashboardData;
}
