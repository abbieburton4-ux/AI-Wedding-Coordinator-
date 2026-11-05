import { useState } from "react";
import { useAuth } from "../AuthProvider";
import { Button } from "../../design-system/primitives";

const FIREBASE_ERRORS: Record<string, string> = {
  "auth/too-many-requests": "We've sent a few already. Please wait a few minutes, then try again.",
  "auth/network-request-failed": "We couldn't connect. Check your internet connection and try again.",
  "auth/user-token-expired": "Please sign in again.",
};

function plainError(err: unknown): string {
  const code = (err as { code?: unknown } | null)?.code;
  if (typeof code === "string" && FIREBASE_ERRORS[code]) return FIREBASE_ERRORS[code];
  if (err instanceof Error && !err.message.startsWith("Firebase:")) return err.message;
  return "Something went wrong. Please try again.";
}

/**
 * Shown to someone who signed up with an email and password but hasn't confirmed
 * the address yet (PD-002, email-confirmation note). The confirmation email goes
 * only when they press the button; nothing is sent automatically.
 */
export function ConfirmEmail({ email }: { email: string }) {
  const { sendConfirmationEmail, checkEmailConfirmed, signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await fn();
    } catch (err) {
      setError(plainError(err));
    } finally {
      setBusy(false);
    }
  }

  const send = () =>
    run(async () => {
      await sendConfirmationEmail();
      setSent(true);
      setMessage(`We've sent a confirmation email to ${email}. Open the link in it, then come back here.`);
    });

  const check = () =>
    run(async () => {
      const confirmed = await checkEmailConfirmed();
      if (!confirmed) {
        setMessage("Your email isn't confirmed yet. Open the link in the email, then try again.");
      }
    });

  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-serif text-2xl font-light">Confirm your email</h2>
      <p className="text-sm text-muted-foreground">
        Before you can get in, we need to check that <strong className="text-foreground">{email}</strong> is
        your email address. Press the button and we'll send you one email with a link to confirm it.
      </p>

      {message && <p role="status" className="text-sm text-foreground">{message}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}

      <Button type="button" variant="solid" disabled={busy} className="w-full" onClick={send}>
        {sent ? "Send it again" : "Send me a confirmation email"}
      </Button>
      <Button type="button" variant="outline" disabled={busy} className="w-full" onClick={check}>
        I've confirmed it, continue
      </Button>
      <Button type="button" variant="link" disabled={busy} className="self-center mt-2" onClick={() => run(signOut)}>
        Use a different account
      </Button>
    </div>
  );
}
