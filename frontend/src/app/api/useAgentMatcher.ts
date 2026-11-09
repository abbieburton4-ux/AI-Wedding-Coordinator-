import { useState, useRef, useCallback } from "react";
import { useApi } from "./useApi";
import { useReviewedRequest } from "./review";
import { POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from "./config";

export type AgentStatus =
  | "idle"
  | "running"
  | "success"
  | "blocked"
  | "error"
  | "timeout";

interface DecisionLog {
  agent_id: string;
  status: string;
  rationale_summary?: string;
  error_message?: string;
  confidence_score?: number;
}

/**
 * Reusable hook for dispatching an AI agent task and polling until completion.
 *
 * Handles the full lifecycle:
 *   idle → running (POST dispatch) → polling decisions → success | blocked | error | timeout
 *
 * Usage:
 *   const { trigger, status, rationale, errorMsg } = useAgentMatcher(weddingId);
 *   <button onClick={() => trigger("venue")} disabled={status === "running"}>
 */
export function useAgentMatcher(weddingId: string) {
  const { request } = useApi();
  const sendReviewed = useReviewedRequest();
  const [status, setStatus] = useState<AgentStatus>("idle");
  const [rationale, setRationale] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [confidence, setConfidence] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const triggerVenueMatch = useCallback(async () => {
    cleanup();
    setStatus("running");
    setRationale("Initializing venue matching agent...");
    setErrorMsg("");
    setConfidence(null);
    startTimeRef.current = Date.now();

    try {
      // Shows the couple what goes to the AI first; nothing is sent until they click (PD-008).
      const sent = await sendReviewed(`/weddings/${weddingId}/match`);
      if (sent === null) {
        setStatus("idle");
        setRationale("");
        return;
      }
      // On Replit the agent runs inside that request, so the time limit only
      // starts once it has returned.
      startTimeRef.current = Date.now();

      pollRef.current = setInterval(async () => {
        // Timeout guard
        if (Date.now() - startTimeRef.current > POLL_TIMEOUT_MS) {
          cleanup();
          setStatus("timeout");
          setRationale(
            "Matching is taking longer than expected. Results will appear when complete."
          );
          return;
        }

        try {
          const logs: DecisionLog[] = await request(
            `/weddings/${weddingId}/decisions`
          );
          const latest = logs.find((l) => l.agent_id === "venue_matcher");

          if (latest) {
            setRationale(
              latest.rationale_summary || "Analyzing venue options..."
            );

            if (latest.status === "success") {
              setStatus("success");
              setConfidence(latest.confidence_score ?? null);
              cleanup();
            } else if (latest.status === "blocked_by_guardrail") {
              setStatus("blocked");
              setRationale(
                latest.error_message || "AI guardrail safety block triggered."
              );
              cleanup();
            } else if (latest.status === "error") {
              setStatus("error");
              setErrorMsg(
                latest.error_message || "Agent execution encountered an error."
              );
              cleanup();
            }
          }
        } catch {
          cleanup();
          setStatus("error");
          setErrorMsg("Lost connection while polling agent status.");
        }
      }, POLL_INTERVAL_MS);
    } catch (err: any) {
      setStatus("error");
      setErrorMsg(err.message);
    }
  }, [weddingId, request, sendReviewed, cleanup]);

  const triggerSupplierMatch = useCallback(
    async (category: string) => {
      cleanup();
      setStatus("running");
      setRationale(`Searching for ${category} suppliers...`);
      setErrorMsg("");
      setConfidence(null);
      startTimeRef.current = Date.now();

      try {
        const sent = await sendReviewed(`/weddings/${weddingId}/suppliers`, { category });
        if (sent === null) {
          setStatus("idle");
          setRationale("");
          return;
        }
        startTimeRef.current = Date.now();

        pollRef.current = setInterval(async () => {
          if (Date.now() - startTimeRef.current > POLL_TIMEOUT_MS) {
            cleanup();
            setStatus("timeout");
            setRationale(
              "Supplier matching is taking longer than expected. Results will appear when complete."
            );
            return;
          }

          try {
            const logs: DecisionLog[] = await request(
              `/weddings/${weddingId}/decisions`
            );
            const latest = logs.find(
              (l) => l.agent_id === "supplier_matcher"
            );

            if (latest) {
              setRationale(
                latest.rationale_summary ||
                  `Evaluating ${category} suppliers...`
              );

              if (latest.status === "success") {
                setStatus("success");
                setConfidence(latest.confidence_score ?? null);
                cleanup();
              } else if (latest.status === "blocked_by_guardrail") {
                setStatus("blocked");
                setRationale(
                  latest.error_message ||
                    "Supplier matching blocked by safety guardrail."
                );
                cleanup();
              } else if (latest.status === "error") {
                setStatus("error");
                setErrorMsg(
                  latest.error_message || "Supplier matching agent failed."
                );
                cleanup();
              }
            }
          } catch {
            cleanup();
            setStatus("error");
            setErrorMsg("Lost connection while polling supplier match status.");
          }
        }, POLL_INTERVAL_MS);
      } catch (err: any) {
        setStatus("error");
        setErrorMsg(err.message);
      }
    },
    [weddingId, request, sendReviewed, cleanup]
  );

  const reset = useCallback(() => {
    cleanup();
    setStatus("idle");
    setRationale("");
    setErrorMsg("");
    setConfidence(null);
  }, [cleanup]);

  return {
    triggerVenueMatch,
    triggerSupplierMatch,
    status,
    rationale,
    errorMsg,
    confidence,
    reset,
  };
}
