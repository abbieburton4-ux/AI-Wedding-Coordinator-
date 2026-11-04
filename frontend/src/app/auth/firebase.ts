/**
 * Firebase initialization.
 *
 * If the VITE_FIREBASE_* env vars are not configured, `firebaseAuth` is null and
 * the app runs in DEV-AUTH mode (mock tokens via AuthProvider) — so local
 * development never requires real Firebase credentials. In production, set the
 * VITE_FIREBASE_* vars (see frontend/.env.example) to enable real auth.
 */
import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
};

/** True when real Firebase config is present; otherwise the app uses dev-auth. */
export const firebaseEnabled = Boolean(config.apiKey && config.projectId);

let app: FirebaseApp | null = null;
export const firebaseAuth: Auth | null = firebaseEnabled
  ? getAuth((app = initializeApp(config as Record<string, string>)))
  : null;
