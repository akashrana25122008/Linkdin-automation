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
  performance: {
    state: string;
    message: string;
    published_total: number;
    published_this_week: number;
  };
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

export type ContentType =
  | "educational"
  | "technical"
  | "project_showcase"
  | "personal_learning"
  | "hackathon"
  | "career"
  | "ai_tech_commentary"
  | "storytelling"
  | "tutorial"
  | "opinion"
  | "achievement_update";

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  educational: "Educational",
  technical: "Technical",
  project_showcase: "Project Showcase",
  personal_learning: "Personal Learning",
  hackathon: "Hackathon",
  career: "Career",
  ai_tech_commentary: "AI/Tech Commentary",
  storytelling: "Storytelling",
  tutorial: "Tutorial",
  opinion: "Opinion",
  achievement_update: "Achievement/Update",
};

export type StudioStatus = "idea" | "draft" | "approved";

export interface StudioItem {
  id: number;
  title: string;
  body: string;
  content_type: string;
  status: string;
  scheduled_at: string | null;
  scheduled_tz: string | null;
  linkedin_post_id: string | null;
  published_at: string | null;
  publish_error: string;
  mock?: boolean;
  updated_at: string | null;
}

export interface StudioItemSummary {
  id: number;
  title: string;
  preview: string;
  content_type: string;
  status: string;
  linkedin_post_id: string | null;
  published_at: string | null;
  publish_error: string;
  created_at: string | null;
  updated_at: string | null;
}

export type AiAction =
  | "generate"
  | "improve_hook"
  | "shorten"
  | "expand"
  | "simplify"
  | "tone_technical"
  | "tone_personal"
  | "tone_professional"
  | "improve_cta"
  | "improve_hashtags"
  | "alternatives";

export const REWRITE_ACTIONS: { key: AiAction; label: string }[] = [
  { key: "improve_hook", label: "Improve Hook" },
  { key: "shorten", label: "Shorten" },
  { key: "expand", label: "Expand" },
  { key: "simplify", label: "Simplify" },
  { key: "tone_technical", label: "Technical Tone" },
  { key: "tone_personal", label: "Personal Tone" },
  { key: "tone_professional", label: "Professional Tone" },
  { key: "improve_cta", label: "Improve CTA" },
  { key: "improve_hashtags", label: "Improve Hashtags" },
  { key: "alternatives", label: "Generate Alternatives" },
];

export interface AiResult {
  action: string;
  mock: boolean;
  text?: string;
  texts?: string[];
}

export interface ReviewDimension {
  key: string;
  label: string;
  status: "strong" | "good" | "needs_work";
  detail: string;
}

export interface ReviewResult {
  score: number;
  method: string;
  mock: boolean;
  summary: string;
  dimensions: ReviewDimension[];
  factual_note: string;
}

function studioError(res: Response): Error {
  if (res.status === 401)
    return new Error("Session expired — please log in again.");
  return new Error(`Backend responded with HTTP ${res.status}`);
}

export async function listStudioItems(): Promise<StudioItemSummary[]> {
  const res = await fetch(`${API_URL}/api/studio/items`, {
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return ((await res.json()) as { items: StudioItemSummary[] }).items;
}

export async function getStudioItem(id: number): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}`, {
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as StudioItem;
}

export async function createStudioItem(input: {
  title: string;
  body: string;
  content_type: string;
  status: string;
}): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as StudioItem;
}

export async function updateStudioItem(
  id: number,
  input: { title?: string; body?: string; content_type?: string; status?: string },
): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as StudioItem;
}

export async function duplicateStudioItem(id: number): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}/duplicate`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as StudioItem;
}

export async function deleteStudioItem(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
}

export const PUBLISH_ERROR_MESSAGES: Record<string, string> = {
  already_published: "This post is already published.",
  not_approved: "Approve this post before publishing.",
  invalid_content: "The post text is empty or too long to publish.",
  linkedin_not_connected: "Connect LinkedIn in Settings before publishing.",
  missing_scope:
    "The LinkedIn connection lacks publishing permission. Reconnect with the share scope.",
  linkedin_token_error: "The stored LinkedIn credential failed. Reconnect LinkedIn.",
  linkedin_rate_limited: "LinkedIn rate-limited the request. Try again later.",
  linkedin_timeout_unknown:
    "LinkedIn did not answer in time — the outcome is unknown. Check LinkedIn before retrying.",
  linkedin_missing_post_id:
    "LinkedIn answered without a post ID, so this was not marked published.",
  linkedin_network_error: "Could not reach LinkedIn. Try again later.",
};

export function publishErrorMessage(code: string): string {
  if (code.startsWith("linkedin_upstream_")) {
    return `LinkedIn rejected the request (${code.replace("linkedin_upstream_", "HTTP ")}). Nothing was marked published.`;
  }
  return (
    PUBLISH_ERROR_MESSAGES[code] ??
    (code.startsWith("Session expired")
      ? code
      : "Publishing failed. Nothing was marked published.")
  );
}

async function throwPublishError(res: Response): Promise<never> {
  if (res.status === 401)
    throw new Error("Session expired — please log in again.");
  let detail = "";
  try {
    detail = ((await res.json()) as { detail?: string }).detail ?? "";
  } catch {
    detail = "";
  }
  throw new Error(detail || `Backend responded with HTTP ${res.status}`);
}

export async function publishItem(id: number): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}/publish`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) await throwPublishError(res);
  return (await res.json()) as StudioItem;
}

export async function updateStudioItemStatus(
  id: number,
  status: string,
): Promise<StudioItem> {
  const res = await fetch(`${API_URL}/api/studio/items/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as StudioItem;
}

export interface ScheduledItem {
  id: number;
  title: string;
  content_type: string;
  status: string;
  scheduled_at: string | null;
  scheduled_tz: string | null;
}

export const SCHEDULE_ERROR_MESSAGES: Record<string, string> = {
  approval_required: "Approve this post before scheduling.",
  not_scheduled: "This post is not scheduled.",
  unschedule_first: "Unschedule this post before changing its status.",
  scheduled_at_required: "Choose a date and time.",
  timezone_required: "Choose a timezone.",
  invalid_timezone: "That timezone is not recognized.",
  malformed_schedule: "That date or time is not valid.",
  past_time: "That time is in the past. Choose a future time.",
  malformed_range: "That date range is not valid.",
  range_too_large: "That date range is too large.",
  not_found: "That post was not found.",
};

async function scheduleRequest(
  url: string,
  body?: { scheduled_at: string; timezone: string },
): Promise<StudioItem> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    if (res.status === 401)
      throw new Error("Session expired — please log in again.");
    let detail = "";
    try {
      detail = ((await res.json()) as { detail?: string }).detail ?? "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `Backend responded with HTTP ${res.status}`);
  }
  return (await res.json()) as StudioItem;
}

export async function fetchScheduledRange(
  startIso: string,
  endIso: string,
  signal?: AbortSignal,
): Promise<ScheduledItem[]> {
  const res = await fetch(
    `${API_URL}/api/studio/scheduled?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(endIso)}`,
    { credentials: "include", signal },
  );
  if (!res.ok) throw studioError(res);
  return ((await res.json()) as { items: ScheduledItem[] }).items;
}

export async function scheduleItem(
  id: number,
  scheduled_at: string,
  timezone: string,
): Promise<StudioItem> {
  return scheduleRequest(`${API_URL}/api/studio/items/${id}/schedule`, {
    scheduled_at,
    timezone,
  });
}

export async function rescheduleItem(
  id: number,
  scheduled_at: string,
  timezone: string,
): Promise<StudioItem> {
  return scheduleRequest(`${API_URL}/api/studio/items/${id}/reschedule`, {
    scheduled_at,
    timezone,
  });
}

export async function unscheduleItem(id: number): Promise<StudioItem> {
  return scheduleRequest(`${API_URL}/api/studio/items/${id}/unschedule`);
}

export function scheduleErrorMessage(codeOrError: string): string {
  return (
    SCHEDULE_ERROR_MESSAGES[codeOrError] ??
    (codeOrError.startsWith("Session expired")
      ? codeOrError
      : "Could not save the schedule. Please try again.")
  );
}

export async function runAiAction(input: {
  action: AiAction;
  content: string;
  topic: string;
  content_type: string;
  context: string;
}): Promise<AiResult> {
  const res = await fetch(`${API_URL}/api/studio/ai`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as AiResult;
}

export async function reviewDraft(content: string): Promise<ReviewResult> {
  const res = await fetch(`${API_URL}/api/studio/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as ReviewResult;
}

export interface ResearchResult {
  title: string;
  summary: string;
  source_name: string;
  source_url: string;
  published_at: string | null;
  topic: string;
  relevance_score: number;
  freshness_score: number;
  linkedin_angle: string;
  mock: boolean;
}

export interface SavedResearch extends ResearchResult {
  id: number;
  status: string;
}

export interface ResearchSearchResponse {
  query: string;
  results: ResearchResult[];
  mock: boolean;
  scoring: { method: string; note: string };
}

export async function searchResearch(query: string): Promise<ResearchSearchResponse> {
  const res = await fetch(`${API_URL}/api/research/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as ResearchSearchResponse;
}

export async function listResearch(status = "saved"): Promise<SavedResearch[]> {
  const res = await fetch(`${API_URL}/api/research/items?item_status=${status}`, {
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return ((await res.json()) as { items: SavedResearch[] }).items;
}

export async function getResearchItem(id: number): Promise<SavedResearch> {
  const res = await fetch(`${API_URL}/api/research/items/${id}`, {
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as SavedResearch;
}

export async function saveResearch(
  input: Omit<SavedResearch, "id" | "status">,
): Promise<SavedResearch> {
  const res = await fetch(`${API_URL}/api/research/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as SavedResearch;
}

export async function ignoreResearch(id: number): Promise<SavedResearch> {
  const res = await fetch(`${API_URL}/api/research/items/${id}/ignore`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as SavedResearch;
}

export async function requestAngle(input: {
  title: string;
  summary: string;
  topic: string;
}): Promise<{ angle: string; mock: boolean }> {
  const res = await fetch(`${API_URL}/api/research/angle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as { angle: string; mock: boolean };
}

export interface Strategy {
  display_name: string;
  headline: string;
  bio: string;
  skills: string[];
  projects: string[];
  technologies: string[];
  interests: string[];
  target_audience: string;
  professional_goals: string[];
  content_goals: string[];
  preferred_topics: string[];
  forbidden_topics: string[];
  writing_style: string;
  content_types: string[];
  posting_frequency: string;
  preferred_days: string[];
  preferred_times: string[];
  timezone: string;
}

export async function fetchStrategy(): Promise<Strategy> {
  const res = await fetch(`${API_URL}/api/strategy`, {
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as Strategy;
}

export interface LearningInsight {
  type: string;
  title: string;
  evidence: string;
  confidence: "INSUFFICIENT_DATA" | "EARLY_SIGNAL" | "SUPPORTED_PATTERN";
  source: string;
  recommendation: string | null;
}

export interface LearningData {
  source: string;
  state: string;
  coverage: {
    published_total: number;
    application_history: boolean;
    linkedin_engagement: string;
    performance_learning: string;
    minimum_for_patterns: number;
  };
  insights: LearningInsight[];
  recommendations: { title: string; reason: string; confidence: string }[];
  strategy_alignment: LearningInsight[];
  learning_context: {
    recent_content: string[];
    strategy_priorities: string[];
    validated_learnings: string[];
  };
  ai_summary: { text: string; mock: boolean } | null;
  performance_note: string;
  message?: string;
}

export async function fetchLearning(
  signal?: AbortSignal,
): Promise<LearningData> {
  const res = await fetch(`${API_URL}/api/learning/insights`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as LearningData;
}

export type AnalyticsRange = "7" | "30" | "90" | "all";

export interface AnalyticsBucket {
  label: string;
  start: string;
  count: number;
}

export interface AnalyticsOverview {
  source: "APPLICATION_DATA";
  range: string;
  timezone: string;
  status_counts: Record<string, number>;
  published_in_range: number;
  posts_per_week: number | null;
  by_content_type: Record<string, number>;
  weekly_activity: AnalyticsBucket[];
  linkedin: {
    connected: boolean;
    mock: boolean;
    engagement: { state: string; message: string };
  };
}

export interface AnalyticsPost {
  id: number;
  title: string;
  content_type: string;
  status: string;
  published_at: string | null;
  scheduled_at: string | null;
  linkedin_post_id: string | null;
}

export async function fetchAnalyticsOverview(
  range: AnalyticsRange,
  signal?: AbortSignal,
): Promise<AnalyticsOverview> {
  const res = await fetch(`${API_URL}/api/analytics/overview?days=${range}`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as AnalyticsOverview;
}

export async function fetchAnalyticsPosts(
  range: AnalyticsRange,
  postStatus: string,
  signal?: AbortSignal,
): Promise<AnalyticsPost[]> {
  const params = new URLSearchParams({ days: range });
  if (postStatus) params.set("post_status", postStatus);
  const res = await fetch(`${API_URL}/api/analytics/posts?${params}`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) throw studioError(res);
  return ((await res.json()) as { items: AnalyticsPost[] }).items;
}

export interface LinkedInStatus {
  connected: boolean;
  mode: "mock" | "live";
  mock: boolean;
  configured?: boolean;
  member_name?: string;
  member_id?: string;
  connected_at?: string | null;
  scopes: string[];
}

export async function fetchLinkedInStatus(
  signal?: AbortSignal,
): Promise<LinkedInStatus> {
  const res = await fetch(`${API_URL}/api/linkedin/status`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as LinkedInStatus;
}

export async function mockLinkedInConnect(): Promise<LinkedInStatus> {
  const res = await fetch(`${API_URL}/api/linkedin/mock/connect`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
  return (await res.json()) as LinkedInStatus;
}

export async function disconnectLinkedIn(): Promise<void> {
  const res = await fetch(`${API_URL}/api/linkedin/connection`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw studioError(res);
}

export async function saveStrategy(input: Strategy): Promise<Strategy> {
  const res = await fetch(`${API_URL}/api/strategy`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    if (res.status === 400) {
      let detail = "";
      try {
        detail = ((await res.json()) as { detail?: string }).detail ?? "";
      } catch {
        detail = "";
      }
      throw new Error(detail || "Invalid strategy data.");
    }
    throw studioError(res);
  }
  return (await res.json()) as Strategy;
}
