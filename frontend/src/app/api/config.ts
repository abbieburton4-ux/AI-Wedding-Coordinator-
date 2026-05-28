/**
 * VenueFlow API Configuration
 *
 * Central configuration for backend connectivity.
 * Set USE_FASTAPI_BACKEND to false to instantly fall back to static mock data
 * (emergency rollback — no redeploy needed beyond toggling this flag).
 */

export const USE_FASTAPI_BACKEND = true;

/**
 * Base URL of the deployed FastAPI backend.
 * - Production (Railway): https://venueflow-backend.up.railway.app
 * - Local dev: http://localhost:8000
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Polling interval in milliseconds for agent status checks.
 * 2000ms balances responsiveness against SQLite read load.
 */
export const POLL_INTERVAL_MS = 2000;

/**
 * Maximum polling duration before showing a timeout fallback message (ms).
 */
export const POLL_TIMEOUT_MS = 60000;
