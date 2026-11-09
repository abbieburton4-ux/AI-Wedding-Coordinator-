import { useCallback, useRef, useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { ReviewContext, type ReviewRequest } from "../api/review";

/**
 * Shows the person the exact text an AI action would send (PD-008). Nothing is sent
 * until they click "Send to the AI"; "Go back", Escape or closing sends nothing.
 */
export function PromptReviewProvider({ children }: { children: ReactNode }) {
  const [review, setReview] = useState<ReviewRequest | null>(null);
  const resolver = useRef<((send: boolean) => void) | null>(null);
  const textRef = useRef<HTMLPreElement>(null);

  const confirm = useCallback((next: ReviewRequest) => {
    // A second request replaces the first, which counts as going back.
    resolver.current?.(false);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
      setReview(next);
    });
  }, []);

  const finish = (send: boolean) => {
    resolver.current?.(send);
    resolver.current = null;
    setReview(null);
  };

  return (
    <ReviewContext.Provider value={confirm}>
      {children}
      <Dialog open={review !== null} onOpenChange={(open) => !open && finish(false)}>
        <DialogContent
          className="wedding flex max-h-[90vh] flex-col gap-4 rounded-3xl bg-background text-on-surface sm:max-w-2xl"
          onOpenAutoFocus={(e) => {
            // Start on the text, not the send button, so Enter can't send it unread.
            e.preventDefault();
            textRef.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle className="font-headline-sm text-on-surface">
              Check this before it goes to the AI
            </DialogTitle>
            <DialogDescription className="text-on-surface-variant text-sm leading-relaxed">
              This is exactly what will be sent to Google's AI, Gemini. Names, emails and phone
              numbers the app already knows are taken out, and show as [name], [email] or
              [phone].
            </DialogDescription>
          </DialogHeader>

          {review?.changed && (
            <p role="status" className="rounded-2xl bg-primary/10 px-4 py-3 text-sm text-on-surface">
              Something changed since you last looked, so this is the updated text.
            </p>
          )}

          <pre
            ref={textRef}
            tabIndex={0}
            aria-label="The text that will be sent to the AI"
            className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-outline-variant/40 bg-surface-container-low p-4 font-body-md text-sm text-on-surface focus:border-primary focus:outline-none"
          >
            {review?.preview}
          </pre>

          <p className="text-sm text-on-surface-variant">
            If you see someone's name or a private detail we missed, choose Go back and change it
            where it was written: your message, the pasted email, a checklist task or your
            wedding details. Nothing is sent until you click Send.
          </p>

          <DialogFooter className="gap-3">
            <button
              type="button"
              onClick={() => finish(false)}
              className="rounded-full px-6 py-3 font-button-text text-sm text-on-surface-variant hover:bg-surface-container-low focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              Go back
            </button>
            <button
              type="button"
              onClick={() => finish(true)}
              className="rounded-full bg-primary px-6 py-3 font-button-text text-sm uppercase tracking-wider text-on-primary hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              Send to the AI
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ReviewContext.Provider>
  );
}
