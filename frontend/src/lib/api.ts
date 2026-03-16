const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Token storage ────────────────────────────────────────────────────────────
// After OAuth, the backend redirects to /?token=<signed_token>. The frontend
// stores it here and attaches it as Authorization: Bearer on every request,
// avoiding cross-domain cookie issues entirely.

let _token: string | null = null;

export function setToken(token: string) {
  _token = token;
  localStorage.setItem("auth_token", token);
}

export function loadToken(): string | null {
  if (!_token) _token = localStorage.getItem("auth_token");
  return _token;
}

export function clearToken() {
  _token = null;
  localStorage.removeItem("auth_token");
}

// ─── Fetch wrapper ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = loadToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "API error");
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const getMe = () => apiFetch<User>("/auth/me");
export const logout = () => {
  clearToken();
  return apiFetch<void>("/auth/logout", { method: "POST" });
};
export const loginUrl = () => `${API_BASE}/auth/google`;
export const youtubeConnectUrl = () => `${API_BASE}/auth/youtube/connect`;
export const patchMe = (display_name: string) =>
  apiFetch<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ display_name }) });
export const deleteMe = () => apiFetch<void>("/auth/me", { method: "DELETE" });
export const updateEmailNotifications = (email_notifications: boolean) =>
  apiFetch<User>("/auth/me/notifications", {
    method: "PATCH",
    body: JSON.stringify({ email_notifications }),
  });

export const updateProfile = (profile: string, goal: string[], equipment?: string[]) =>
  apiFetch<User>("/auth/me/profile", {
    method: "PATCH",
    body: JSON.stringify({ profile, goal, ...(equipment !== undefined && { equipment }) }),
  });

// ─── Channels ────────────────────────────────────────────────────────────────

export const getChannels = () => apiFetch<ChannelResponse[]>("/channels");

export const searchChannels = (q: string) =>
  apiFetch<ChannelSearchResult[]>(`/channels/search?q=${encodeURIComponent(q)}`);

export const addChannel = (data: ChannelCreate) =>
  apiFetch<ChannelResponse>("/channels", { method: "POST", body: JSON.stringify(data) });

export const deleteChannel = (id: string) =>
  apiFetch<void>(`/channels/${id}`, { method: "DELETE" });

export const getSuggestions = (profile?: string, goals?: string[]) => {
  const params = new URLSearchParams();
  if (profile) params.set("profile", profile);
  if (goals?.length) params.set("goals", goals.join(","));
  const q = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<ChannelSearchResult[]>(`/channels/suggestions${q}`);
};

// ─── Schedule ────────────────────────────────────────────────────────────────

export const getSchedule = () => apiFetch<ScheduleResponse>("/schedule");

export const updateSchedule = (schedule: ScheduleSlot[], profile?: string, goal?: string[], equipment?: string[]) =>
  apiFetch<ScheduleResponse>("/schedule", {
    method: "PUT",
    body: JSON.stringify({
      schedule,
      ...(profile !== undefined && { profile }),
      ...(goal !== undefined && { goal }),
      ...(equipment !== undefined && { equipment }),
    }),
  });

// ─── Plan ────────────────────────────────────────────────────────────────────

export const getUpcomingPlan = () => apiFetch<PlanResponse>("/plan/upcoming");

export const generatePlan = () => apiFetch<PlanResponse>("/plan/generate", { method: "POST" });

export const swapPlanDay = (day: string, videoId: string) =>
  apiFetch<PlanDay>(`/plan/${day}`, {
    method: "PATCH",
    body: JSON.stringify({ video_id: videoId }),
  });

export const publishPlan = () =>
  apiFetch<{ message: string }>("/plan/publish", { method: "POST" });

export const getPublishStatus = () =>
  apiFetch<PublishStatus>("/plan/publish/status");

// ─── Library ─────────────────────────────────────────────────────────────────

export const getLibrary = (params: {
  workout_type?: string;
  body_focus?: string;
  difficulty?: string;
  channel_id?: string;
  page?: number;
  limit?: number;
}) => {
  const q = new URLSearchParams();
  if (params.workout_type) q.set("workout_type", params.workout_type);
  if (params.body_focus) q.set("body_focus", params.body_focus);
  if (params.difficulty) q.set("difficulty", params.difficulty);
  if (params.channel_id) q.set("channel_id", params.channel_id);
  if (params.page) q.set("page", String(params.page));
  if (params.limit) q.set("limit", String(params.limit));
  return apiFetch<LibraryResponse>(`/library?${q}`);
};

// ─── Jobs ────────────────────────────────────────────────────────────────────

export const triggerScan = () => apiFetch<JobResponse>("/jobs/scan", { method: "POST" });
export const getJobStatus = () => apiFetch<{ stage: string | null; total: number | null; done: number | null; error: string | null; background_classifying?: boolean }>("/jobs/status");

// ─── Announcements ───────────────────────────────────────────────────────────

export const getActiveAnnouncement = () =>
  apiFetch<{ id: number; message: string } | null>("/announcements/active");

// ─── Types ───────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  youtube_connected: boolean;
  credentials_valid: boolean;
  is_admin: boolean;
  email_notifications: boolean;
  profile: string | null;
  goal: string[] | null;
  equipment: string[] | null;
  created_at: string | null;
}

export interface ChannelCreate {
  name: string;
  youtube_url: string;
  youtube_channel_id?: string;
  description?: string;
  thumbnail_url?: string;
}

export interface ChannelResponse {
  id: string;
  name: string;
  youtube_url: string;
  youtube_channel_id: string | null;
  thumbnail_url: string | null;
  added_at: string;
}

export interface ChannelSearchResult {
  youtube_channel_id: string;
  name: string;
  description: string;
  thumbnail_url: string | null;
}

export interface ScheduleSlot {
  day: string;
  workout_type: string | null;
  body_focus: string | null;
  duration_min: number | null;
  duration_max: number | null;
  difficulty: string;
}

export interface ScheduleResponse {
  schedule: ScheduleSlot[];
}

export interface VideoSummary {
  id: string;
  title: string;
  url: string;
  channel_name: string;
  duration_sec: number | null;
  workout_type: string | null;
  body_focus: string | null;
  difficulty: string | null;
}

export interface PlanDay {
  day: string;
  video: VideoSummary | null;
  scheduled_workout_type?: string | null;
}

export interface PlanResponse {
  week_start: string;
  days: PlanDay[];
}

export interface LibraryResponse {
  videos: VideoSummary[];
  total: number;
  page: number;
  pages: number;
}

export interface JobResponse {
  message: string;
}

export interface PublishResponse {
  playlist_url: string;
  video_count: number;
}

export interface PublishStatus {
  status: "idle" | "publishing" | "done" | "failed";
  playlist_url?: string | null;
  video_count?: number | null;
  error?: string | null;
}

// ─── Admin charts ─────────────────────────────────────────────────────────────

export type ChartPoint = {
  date: string;
  [key: string]: number | string;
};

export interface ChartsResponse {
  signups: ChartPoint[];
  active_users: ChartPoint[];
  ai_usage: ChartPoint[];
  scans: ChartPoint[];
}

export const getAdminCharts = (days = 30) =>
  apiFetch<ChartsResponse>(`/admin/charts?days=${days}`);

export const adminResetOnboarding = (userId: string) =>
  apiFetch<void>(`/admin/users/${userId}/reset-onboarding`, { method: "POST" });

// ─── Feedback ─────────────────────────────────────────────────────────────────

export const submitFeedback = (category: string, message: string) =>
  apiFetch<void>("/feedback", {
    method: "POST",
    body: JSON.stringify({ category, message }),
  });
