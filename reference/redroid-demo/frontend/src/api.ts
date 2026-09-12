/** Mirrors the deliberately small demo contract in ../API.md. */
export interface Instance {
  id: string; name: string; image: string; image_id: string; docker_status: string;
  android_status: 'starting' | 'ready' | 'stopped' | 'failed' | 'unknown';
  android_version: string | null;
  width: number; height: number; dpi: number; cpu: number; memory_mb: number;
  adb_address: string | null; busy: boolean; error: string | null;
}
export interface Environment {
  docker_available: boolean; ready: boolean;
  checks: { name: string; status: 'pass' | 'fail' | 'unknown'; message: string }[];
  daemon: Record<string, unknown> | null;
  images: { ref: string; cached: boolean; id: string | null }[];
  limits: { max_instances: number; concurrency: number };
}
export interface Job {
  id: string; action: string; status: 'queued' | 'running' | 'done' | 'failed'; total: number; done: number;
  results: { instance_id: string | null; name: string; status: 'success' | 'error'; message: string; data?: Record<string, unknown> }[];
}
export interface Apk { id: string; name: string; size_bytes: number }
export type Input = { action: 'tap'; x: number; y: number } | { action: 'swipe'; x1: number; y1: number; x2: number; y2: number } | { action: 'key'; code: number } | { action: 'text'; text: string };
export type CreateConfig = { name: string; image: string; width: number; height: number; dpi: number; cpu: number; memory_mb: number; count: number };
export type BatchAction = 'start' | 'stop' | 'restart' | 'delete' | 'install' | 'open_settings';
export type InstanceAction = Exclude<BatchAction, 'install'> | 'clone' | 'launch' | 'root_check';
export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string) { super(message); }
}
export async function responseError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null) as { error?: { message?: string; code?: string } } | null;
  return new ApiError(body?.error?.message || `请求失败（HTTP ${response.status}）`, response.status, body?.error?.code || 'http_error');
}
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, signal: init.signal ?? AbortSignal.timeout(init.method === 'POST' ? 150_000 : 35_000) });
  if (!response.ok) throw await responseError(response);
  return response.json() as Promise<T>;
}
export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}
export function instancePath(id: string): string { return `/instances/${encodeURIComponent(id)}`; }
