import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
} from "firebase/auth";
import { firebaseAuth, firebaseEnabled } from "./firebase";
import { API_BASE_URL } from "../api/config";

export type Role = "couple" | "planner" | "admin";

export interface AuthUser {
  id: string;
  role: Role | string;
  name: string;
  email: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  role: string | null;
  loading: boolean;
  /** Whether real Firebase auth is configured (vs dev-auth mode). */
  firebaseEnabled: boolean;
  signUpEmail: (email: string, password: string) => Promise<void>;
  signInEmail: (email: string, password: string) => Promise<void>;
  signInGoogle: () => Promise<void>;
  /** Dev-auth: sign in as a seeded/synthetic identity using a mock- token. */
  devSignIn: (uid: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Returns the current bearer token (Firebase ID token, or dev mock token). */
  getToken: () => Promise<string | null>;
}

const DEV_UID_KEY = "vf_dev_uid";
// Kept in sync for backward-compat with views that still read it directly.
const LEGACY_TOKEN_KEY = "vf_planner_token";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Fetch the authenticated user's profile/role. Done with a bare fetch (not
 *  useApi) to avoid a circular dependency on this provider. */
async function fetchMe(token: string): Promise<AuthUser | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    return (await res.json()) as AuthUser;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const getToken = useCallback(async (): Promise<string | null> => {
    if (firebaseEnabled && firebaseAuth) {
      return firebaseAuth.currentUser
        ? await firebaseAuth.currentUser.getIdToken()
        : null;
    }
    const uid = localStorage.getItem(DEV_UID_KEY);
    return uid ? `mock-${uid}` : null;
  }, []);

  // Resolve the session on mount (and on Firebase auth-state changes).
  useEffect(() => {
    let active = true;

    if (firebaseEnabled && firebaseAuth) {
      const unsub = onAuthStateChanged(firebaseAuth, async (fbUser) => {
        if (!active) return;
        if (fbUser) {
          const token = await fbUser.getIdToken();
          const me = await fetchMe(token);
          if (active) setUser(me);
        } else {
          setUser(null);
        }
        if (active) setLoading(false);
      });
      return () => {
        active = false;
        unsub();
      };
    }

    // Dev-auth mode: restore the stored identity if present.
    const uid = localStorage.getItem(DEV_UID_KEY);
    (async () => {
      const me = uid ? await fetchMe(`mock-${uid}`) : null;
      if (active) {
        setUser(me);
        setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const signUpEmail = useCallback(async (email: string, password: string) => {
    if (!firebaseAuth) throw new Error("Firebase is not configured.");
    await createUserWithEmailAndPassword(firebaseAuth, email, password);
    // onAuthStateChanged handles state + /auth/me (auto-creates a couple).
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
    if (!firebaseAuth) throw new Error("Firebase is not configured.");
    await signInWithEmailAndPassword(firebaseAuth, email, password);
  }, []);

  const signInGoogle = useCallback(async () => {
    if (!firebaseAuth) throw new Error("Firebase is not configured.");
    await signInWithPopup(firebaseAuth, new GoogleAuthProvider());
  }, []);

  const devSignIn = useCallback(async (uid: string) => {
    localStorage.setItem(DEV_UID_KEY, uid);
    localStorage.setItem(LEGACY_TOKEN_KEY, `mock-${uid}`);
    setLoading(true);
    const me = await fetchMe(`mock-${uid}`);
    setUser(me);
    setLoading(false);
  }, []);

  const signOut = useCallback(async () => {
    if (firebaseEnabled && firebaseAuth) {
      await firebaseSignOut(firebaseAuth);
    }
    localStorage.removeItem(DEV_UID_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    role: user?.role ?? null,
    loading,
    firebaseEnabled,
    signUpEmail,
    signInEmail,
    signInGoogle,
    devSignIn,
    signOut,
    getToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

/** Where to send a user after login, based on role. */
export function homeForRole(role: string | null | undefined): string {
  if (role === "planner") return "/planner";
  if (role === "admin") return "/admin";
  return "/wedding";
}
