import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A refusal shown by the form or button that caused it, not at the top of the page
 * (B96). ``at`` says which row of a list it belongs to, when one hook serves several.
 * ``n`` counts up on every new message, so the same refusal twice is announced twice.
 */
export type FormErrorState = { text: string; n: number; at?: string } | null;

export function useFormError() {
  const [error, setState] = useState<FormErrorState>(null);
  const seq = useRef(0);
  /** Shows a message (or clears it with null). Fits the `setError` the amount helpers take. */
  const setError = useCallback((text: string | null, at?: string) => {
    if (text === null) setState(null);
    else setState({ text, n: ++seq.current, at });
  }, []);
  const clear = useCallback(() => setState(null), []);
  return { error, setError, clear };
}

/**
 * The message, by its form. Announced as an alert, and scrolled into view if it's off
 * screen (on a phone it can sit below the fold or under the tab bar, hence the bottom
 * margin). Focus stays where it is.
 */
export function FormError({
  error, at, className = "w-full",
}: { error: FormErrorState; at?: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const shown = error && error.at === at ? error : null;
  useEffect(() => {
    if (!shown) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    ref.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
  }, [shown?.n]);
  if (!shown) return null;
  // A new key for each message, so a screen reader hears a repeat of the same text.
  return (
    <p key={shown.n} ref={ref} role="alert" className={`${className} text-sm text-error scroll-mt-48 scroll-mb-24 md:scroll-mb-6`}>
      {shown.text}
    </p>
  );
}
