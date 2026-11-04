import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useLocation, Link } from "react-router";
import { useAuth } from "../AuthProvider";
import { AuthShell, authInputClass } from "../AuthShell";
import { Button } from "../../design-system/primitives";

export function Login() {
  const { user, signInEmail, signInGoogle, devSignIn, firebaseEnabled } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect once the session is established (handles Firebase's async listener).
  useEffect(() => {
    if (user) navigate(from ?? "/app", { replace: true });
  }, [user, from, navigate]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  const onEmail = (e: FormEvent) => {
    e.preventDefault();
    run(() => signInEmail(email, password));
  };

  return (
    <AuthShell
      eyebrow="Welcome back"
      title={<>Sign in to your <span className="italic">plans</span></>}
      footer={
        <>
          New to VenueFlow?{" "}
          <Link to="/signup" className="text-primary hover:underline">Create your wedding</Link>
        </>
      }
    >
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {firebaseEnabled ? (
        <>
          <form onSubmit={onEmail} className="flex flex-col gap-4">
            <input className={authInputClass} type="email" placeholder="Email" value={email}
              onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            <input className={authInputClass} type="password" placeholder="Password" value={password}
              onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            <Button type="submit" variant="solid" disabled={busy} className="w-full">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          <Button type="button" variant="outline" disabled={busy} className="w-full mt-3"
            onClick={() => run(signInGoogle)}>
            Continue with Google
          </Button>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground mb-1">Dev mode — choose an identity:</p>
          <Button type="button" variant="solid" disabled={busy} className="w-full"
            onClick={() => run(() => devSignIn("couple_2"))}>
            Continue as a couple
          </Button>
          <Button type="button" variant="outline" disabled={busy} className="w-full"
            onClick={() => run(() => devSignIn("planner_1"))}>
            Continue as a planner
          </Button>
        </div>
      )}
    </AuthShell>
  );
}
