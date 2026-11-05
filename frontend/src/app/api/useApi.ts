import { useState, useCallback } from "react";
import { API_BASE_URL } from "./config";
import { useAuth } from "../auth/AuthProvider";

/**
 * Lightweight fetch wrapper with automatic auth header injection,
 * JSON parsing, and error state management.
 *
 * Usage:
 *   const { request, loading, error } = useApi();
 *   const data = await request("/weddings", { method: "GET" });
 */
/**
 * FastAPI's `detail` can be a string, an object such as `{ message, error_kind }`
 * (a blocked AI action), or a list of validation errors. Turn each into text a
 * person can read, never "[object Object]".
 */
function errorMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : null))
      .filter((m): m is string => Boolean(m));
    return parts.length ? parts.join("; ") : null;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message: unknown }).message;
    return typeof message === "string" ? message : null;
  }
  return null;
}

export function useApi() {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(
    async <T = any>(path: string, options: RequestInit = {}): Promise<T> => {
      setLoading(true);
      setError(null);

      try {
        const token = await getToken();
        const headers = new Headers(options.headers);

        if (token) {
          headers.set("Authorization", `Bearer ${token}`);
        }

        // Only set Content-Type for requests that carry a body
        if (options.body) {
          headers.set("Content-Type", "application/json");
        }

        const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
          ...options,
          headers,
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(
            errorMessage(errData.detail) ||
              `Request failed with status ${response.status}`
          );
        }

        // Handle empty responses (204 No Content)
        const text = await response.text();
        if (!text) return {} as T;

        return JSON.parse(text) as T;
      } catch (err: any) {
        const msg = err.message || "An unexpected error occurred";
        setError(msg);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [getToken]
  );

  const clearError = useCallback(() => setError(null), []);

  return { request, loading, error, clearError };
}
