import { useState, useCallback } from "react";
import { API_BASE_URL } from "./config";

/**
 * Lightweight fetch wrapper with automatic auth header injection,
 * JSON parsing, and error state management.
 *
 * Usage:
 *   const { request, loading, error } = useApi();
 *   const data = await request("/weddings", { method: "GET" });
 */
export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(
    async <T = any>(path: string, options: RequestInit = {}): Promise<T> => {
      setLoading(true);
      setError(null);

      try {
        const token = localStorage.getItem("vf_planner_token");
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
            errData.detail || `Request failed with status ${response.status}`
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
    []
  );

  const clearError = useCallback(() => setError(null), []);

  return { request, loading, error, clearError };
}
