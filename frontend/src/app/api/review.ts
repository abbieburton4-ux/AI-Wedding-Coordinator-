import { createContext, useCallback, useContext } from "react";
import { useApi } from "./useApi";

/**
 * Check-before-send for every AI action (PD-008): the first request returns the exact
 * text that would go to the AI and sends nothing. The person reads it and clicks to
 * send, which repeats the request with that same text as `approved_prompt`.
 */
export interface NeedsReview {
  needs_review: true;
  preview: string;
  changed?: boolean;
}

export interface ReviewRequest {
  preview: string;
  changed: boolean;
}

/** Shows the text and resolves true once the person clicks send, false if they go back. */
export type ConfirmSend = (review: ReviewRequest) => Promise<boolean>;

export const ReviewContext = createContext<ConfirmSend>(async () => {
  throw new Error("This screen can't show you the text first, so nothing was sent.");
});

function isReview(value: unknown): value is NeedsReview {
  return (
    !!value &&
    typeof value === "object" &&
    (value as { needs_review?: unknown }).needs_review === true &&
    typeof (value as { preview?: unknown }).preview === "string"
  );
}

// If the text keeps changing between the check and the click, stop rather than loop.
const MAX_CHECKS = 3;

export interface ReviewHooks {
  /** The text is on screen and nothing is being sent (e.g. hide a "working" state). */
  onReview?: () => void;
  /** The person clicked send; the approved text is about to go. */
  onSend?: () => void;
}

/**
 * POSTs an AI action. Returns the result once the person has approved the text, or
 * null if they went back without sending.
 */
export function useReviewedRequest() {
  const { request } = useApi();
  const confirm = useContext(ReviewContext);

  return useCallback(
    async <T>(
      path: string,
      body: Record<string, unknown> = {},
      hooks: ReviewHooks = {},
    ): Promise<T | null> => {
      let approved: string | undefined;
      for (let i = 0; i < MAX_CHECKS; i++) {
        const payload = approved === undefined ? body : { ...body, approved_prompt: approved };
        const res = await request<T | NeedsReview>(path, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (!isReview(res)) return res as T;
        hooks.onReview?.();
        const send = await confirm({ preview: res.preview, changed: !!res.changed });
        if (!send) return null;
        hooks.onSend?.();
        // Send back exactly the text that was shown, never a re-typed copy.
        approved = res.preview;
      }
      throw new Error("The text kept changing, so nothing was sent. Please try again.");
    },
    [request, confirm],
  );
}
