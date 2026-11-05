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
  sendEmailVerification,
  signOut as firebaseSignOut,
  type User as FirebaseUser,
} from "firebase/auth";
import { firebaseAuth, firebaseEnabled } from "./firebase";
import { API_BASE_URL } from "../api/config";

export type Role = "couple";

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
  /** Set when the account signed in but isn't on the wedding's access list. */
  accessMessage: string | null;
  /**
   * The email of someone signed in with a password whose address isn't confirmed
   * yet. They stay signed in to Firebase (not to the app) so they can ask for a
   * confirmation email.
   */
  unconfirmedEmail: string | null;
  /** Asks Firebase to send one confirmation email. Only ever called from the person's own click. */
  sendConfirmationEmail: () => Promise<void>;
  /** Re-checks the address after they've opened the link; resolves false if it's still unconfirmed. */
  checkEmailConfirmed: () => Promise<boolean>;
}

/** A password account whose address hasn't been confirmed. Google accounts are confirmed already. */
function needsConfirmation(fbUser: FirebaseUser): boolean {
  return (
    !fbUser.emailVerified && fbUser.providerData.some((p) => p.providerId === "password")
  );
}

const DEV_UID_KEY = "vf_dev_uid";
// Kept in sync for backward-compat with views that still read it directly.
const LEGACY_TOKEN_KEY = "vf_planner_token";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Fetch the authenticated user's profile/role. Done with a bare fetch (not
 *  useApi) to avoid a circular dependency on this provider. */
async function fetchMe(token: string): Promise<AuthUser | null> {
  const { user } = await fetchMeWithStatus(token);
  return user;
}

const NOT_ON_LIST =
  "This account isn't on the wedding's access list yet. Ask the couple to add you, " +
  "then sign in again.";

async function fetchMeWithStatus(
  token: string,
): Promise<{ user: AuthUser | null; denied: string | null }> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 403) {
      // The backend says why: not on the list, or email not confirmed yet.
      const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
      const detail = typeof body?.detail === "string" ? body.detail : NOT_ON_LIST;
      return { user: null, denied: detail };
    }
    if (!res.ok) return { user: null, denied: null };
    return { user: (await res.json()) as AuthUser, denied: null };
  } catch {
    return { user: null, denied: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessMessage, setAccessMessage] = useState<string | null>(null);
  const [unconfirmedEmail, setUnconfirmedEmail] = useState<string | null>(null);

  /** Ask the backend who this Firebase account is; sign out of Firebase if refused. */
  const resolveFirebaseUser = useCallback(async (fbUser: FirebaseUser, forceRefresh = false) => {
    const token = await fbUser.getIdToken(forceRefresh);
    const { user: me, denied } = await fetchMeWithStatus(token);
    setUser(me);
    setAccessMessage(denied);
    // Not on the list: sign out of Google too, so they can try another account.
    if (denied && firebaseAuth) await firebaseSignOut(firebaseAuth);
  }, []);

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
        if (fbUser && needsConfirmation(fbUser)) {
          // The backend refuses unconfirmed addresses, so don't ask it yet.
          setUser(null);
          setAccessMessage(null);
          setUnconfirmedEmail(fbUser.email);
        } else if (fbUser) {
          setUnconfirmedEmail(null);
          await resolveFirebaseUser(fbUser);
        } else {
          setUser(null);
          setUnconfirmedEmail(null);
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
    // onAuthStateChanged handles state + /auth/me (only listed emails get an account).
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

  const sendConfirmationEmail = useCallback(async () => {
    const fbUser = firebaseAuth?.currentUser;
    if (!fbUser) throw new Error("Please sign in again first.");
    // Firebase sends the one email, to the person's own address, because they asked.
    await sendEmailVerification(fbUser);
  }, []);

  const checkEmailConfirmed = useCallback(async () => {
    const fbUser = firebaseAuth?.currentUser;
    if (!fbUser) throw new Error("Please sign in again first.");
    await fbUser.reload();
    if (!fbUser.emailVerified) return false;
    setUnconfirmedEmail(null);
    setLoading(true);
    try {
      // A fresh token carries the confirmed address to the backend.
      await resolveFirebaseUser(fbUser, true);
    } finally {
      setLoading(false);
    }
    return true;
  }, [resolveFirebaseUser]);

  const signOut = useCallback(async () => {
    if (firebaseEnabled && firebaseAuth) {
      await firebaseSignOut(firebaseAuth);
    }
    localStorage.removeItem(DEV_UID_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    setUser(null);
    setUnconfirmedEmail(null);
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
    accessMessage,
    unconfirmedEmail,
    sendConfirmationEmail,
    checkEmailConfirmed,
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
  return "/wedding";
}
