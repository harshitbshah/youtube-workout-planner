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
export const patchMe = (display_name: string) =>
  apiFetch<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ display_name }) });
export const deleteMe = () => apiFetch<void>("/auth/me", { method: "DELETE" });

// ─── Channels ────────────────────────────────────────────────────────────────

export const getChannels = () => apiFetch<ChannelResponse[]>("/channels");

export const searchChannels = (q: string) =>
  apiFetch<ChannelSearchResult[]>(`/channels/search?q=${encodeURIComponent(q)}`);

export const addChannel = (data: ChannelCreate) =>
  apiFetch<ChannelResponse>("/channels", { method: "POST", body: JSON.stringify(data) });

export const deleteChannel = (id: string) =>
  apiFetch<void>(`/channels/${id}`, { method: "DELETE" });

// ─── Schedule ────────────────────────────────────────────────────────────────

export const getSchedule = () => apiFetch<ScheduleResponse>("/schedule");

export const updateSchedule = (schedule: ScheduleSlot[]) =>
  apiFetch<ScheduleResponse>("/schedule", {
    method: "PUT",
    body: JSON.stringify({ schedule }),
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
  apiFetch<PublishResponse>("/plan/publish", { method: "POST" });

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

// ─── Types ───────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  youtube_connected: boolean;
  credentials_valid: boolean;
}

export interface ChannelCreate {
  name: string;
  youtube_url: string;
  youtube_channel_id?: string;
}

export interface ChannelResponse {
  id: string;
  name: string;
  youtube_url: string;
  youtube_channel_id: string | null;
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
