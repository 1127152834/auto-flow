export type Action = { t: string; [key: string]: string | number };
export type Device = {
  name: string;
  width: number;
  height: number;
  socketPresent: boolean;
  managed: boolean;
  exitCode?: number | null;
  error?: string;
};
export type State = {
  token: string;
  devices: Device[];
  environment: {
    root: string;
    freeGiB: number;
    canAttemptLaunch: boolean;
    note: string;
    checks: Record<string, { ok: boolean | null; text: string }>;
  };
};
export type Frame = {
  image: string;
  width: number;
  height: number;
  message: string;
};
export async function request<T>(
  path: string,
  token?: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Demo-Token": token ?? "",
          },
          body: JSON.stringify(body),
        }
      : {},
  );
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? `HTTP ${response.status}`);
  return result as T;
}
export function position(
  clientX: number,
  clientY: number,
  rect: Pick<DOMRect, "left" | "top" | "width" | "height">,
) {
  if (rect.width <= 0 || rect.height <= 0) return null;
  const x = (clientX - rect.left) / rect.width,
    y = (clientY - rect.top) / rect.height;
  return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x, y } : null;
}
