import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router";
import { useAuth } from "../AuthProvider";
import { AuthShell, authInputClass } from "../AuthShell";
import { Button } from "../../design-system/primitives";
import { ConfirmEmail } from "./ConfirmEmail";

/** Generate a throwaway couple uid for dev-auth signup ("couple" in the id makes
 *  the backend assign the couple role for the mock- token). */
function newDevCoupleUid() {
  return `couple_${Math.random().toString(36).slice(2, 8)}`;
}

export function Signup() {
  const { user, signUpEmail, signInGoogle, devSignIn, firebaseEnabled, accessMessage, unconfirmedEmail } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) navigate("/app", { replace: true });
  }, [user, navigate]);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  const onEmail = (e: FormEvent) => {
    e.preventDefault();
    run(() => signUpEmail(email, password));
  };

  return (
    <AuthShell
      eyebrow="Welcome"
      title={<>Create your <span className="italic">account</span></>}
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline">Sign in</Link>
        </>
      }
    >
      {accessMessage && <p className="mb-4 text-sm text-destructive">{accessMessage}</p>}
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {unconfirmedEmail ? (
        <ConfirmEmail email={unconfirmedEmail} />
      ) : firebaseEnabled ? (
        <>
          <form onSubmit={onEmail} className="flex flex-col gap-4">
            <input className={authInputClass} type="email" placeholder="Email" value={email}
              onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            <input className={authInputClass} type="password" placeholder="Password (min 6 characters)" value={password}
              onChange={(e) => setPassword(e.target.value)} required minLength={6} autoComplete="new-password" />
            <Button type="submit" variant="solid" disabled={busy} className="w-full">
              {busy ? "Creating account…" : "Create account"}
            </Button>
          </form>
          <Button type="button" variant="outline" disabled={busy} className="w-full mt-3"
            onClick={() => run(signInGoogle)}>
            Continue with Google
          </Button>
        </>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground mb-1">Dev mode — no Firebase required:</p>
          <Button type="button" variant="solid" disabled={busy} className="w-full"
            onClick={() => run(() => devSignIn(newDevCoupleUid()))}>
            Create a new couple account
          </Button>
        </div>
      )}
    </AuthShell>
  );
}
