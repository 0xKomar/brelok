const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cyberswipe_token");
}

export function setToken(token: string) {
  localStorage.setItem("cyberswipe_token", token);
}

export function setNick(nick: string) {
  localStorage.setItem("cyberswipe_nick", nick);
}

export function getNick(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cyberswipe_nick");
}

export function clearSession() {
  localStorage.removeItem("cyberswipe_token");
  localStorage.removeItem("cyberswipe_nick");
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { "X-Token": token } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Błąd serwera" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── API functions ───────────────────────────────────────────────

export interface LoginResponse {
  token: string;
  nick: string;
}

export async function apiLogin(nick: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/login", {
    method: "POST",
    body: JSON.stringify({ nick }),
  });
}

export interface Task {
  id: number;
  type: string;
  title: string;
  description: string;
  hint: string;
  category: string;
  location: string;
  risk_level: string;
  images?: string[];
}

export async function apiGetTasks(): Promise<Task[]> {
  return apiFetch<Task[]>("/api/tasks");
}

export interface SwipeResult {
  correct: boolean;
  points_earned: number;
  total_score: number;
  combo: number;
  explanation: string;
}

export async function apiSwipe(
  taskId: number,
  action: "scan" | "ignore" | "image_1" | "image_2" | "image_3" | "image_4" | "skip"
): Promise<SwipeResult> {
  return apiFetch<SwipeResult>("/api/swipe", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId, action }),
  });
}

export interface LeaderboardEntry {
  rank: number;
  nick: string;
  score: number;
  is_current_user: boolean;
}

export async function apiGetLeaderboard(): Promise<LeaderboardEntry[]> {
  return apiFetch<LeaderboardEntry[]>("/api/leaderboard");
}

export interface Stats {
  nick: string;
  score: number;
  combo: number;
  answered: number;
  total_tasks: number;
  progress_pct: number;
}

export async function apiGetStats(): Promise<Stats> {
  return apiFetch<Stats>("/api/stats");
}
