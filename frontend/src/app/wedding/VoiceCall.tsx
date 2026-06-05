import { useCallback, useEffect, useRef, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { Icon } from "../shared/Icon";
import { useApi } from "../api/useApi";
import { useActiveWedding, type WeddingSummary } from "./WeddingProvider";

/**
 * Live voice call with Aurelia (the ElevenLabs Conversational AI agent), running
 * in parallel to the text concierge. The WebRTC token is minted server-side at
 * /voice/token so the ElevenLabs API key never reaches the browser.
 *
 * useConversation requires a ConversationProvider ancestor, so VoiceCall wraps
 * the actual call UI (VoiceCallInner) in one.
 */

// Grounds the voice agent in the couple's real plan. Sent as a contextual update
// once connected, so Aurelia speaks to their actual budget/date/guests without us
// having to pre-configure dynamic variables on the ElevenLabs side.
function buildContext(w: WeddingSummary | null): string {
  if (!w) return "";
  const euro = (n: number) => `€${Math.round(n).toLocaleString()}`;
  const facts = [
    `Region: ${w.region}`,
    `Ceremony type: ${w.ceremony_type}`,
    `Estimated guests: ${w.guest_count_estimate}`,
    `Total budget: ${euro(w.budget_total)}`,
    w.wedding_date ? `Wedding date: ${w.wedding_date}` : null,
    `Planning status: ${w.status}`,
  ].filter(Boolean);
  return `You are speaking with a couple planning their wedding. Use these facts about their plan when relevant: ${facts.join(
    "; ",
  )}.`;
}

function VoiceCallInner({ onClose }: { onClose: () => void }) {
  const { request } = useApi();
  const { activeWedding } = useActiveWedding();
  const [error, setError] = useState<string | null>(null);

  // onConnect needs the latest context + the conversation handle, both of which
  // aren't available at the time useConversation() is called — read them via refs.
  const contextRef = useRef("");
  contextRef.current = buildContext(activeWedding);
  const conversationRef = useRef<ReturnType<typeof useConversation> | null>(null);

  const conversation = useConversation({
    onConnect: () => {
      const context = contextRef.current;
      if (context) conversationRef.current?.sendContextualUpdate(context);
    },
    onError: (e: unknown) =>
      setError(typeof e === "string" ? e : "Voice connection error — please try again."),
  });
  conversationRef.current = conversation;

  const { status, isSpeaking } = conversation;
  const connected = status === "connected";
  const connecting = status === "connecting";
  const live = connected || connecting;

  // End any live session if the panel unmounts (e.g. route change) so we never
  // leave a dangling call holding the mic.
  useEffect(() => {
    return () => conversationRef.current?.endSession();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access is needed to talk to Aurelia.");
      return;
    }
    try {
      const { token } = await request<{ token: string }>("/voice/token");
      // startSession resolves nothing synchronously; connection errors surface
      // via the onError callback, success via onConnect.
      conversation.startSession({ conversationToken: token, connectionType: "webrtc" });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't start the voice session.");
    }
  }, [request, conversation]);

  const hangUp = useCallback(() => {
    conversation.endSession();
    onClose();
  }, [conversation, onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex flex-col items-center justify-center bg-background/95 backdrop-blur-sm px-6">
      <button
        type="button"
        onClick={hangUp}
        aria-label="Close voice call"
        className="absolute top-4 right-4 text-on-surface-variant p-2"
      >
        <Icon name="close" />
      </button>

      <div
        className={
          "flex items-center justify-center w-32 h-32 rounded-full bg-primary/10 text-primary mb-6 transition-transform " +
          (isSpeaking ? "scale-110" : connected ? "animate-pulse" : "")
        }
      >
        <Icon name="auto_awesome" filled size={56} />
      </div>

      <h2 className="font-headline-sm text-headline-sm text-on-surface">Aurelia</h2>
      <p className="text-sm text-on-surface-variant mt-1 mb-8 h-5">
        {connecting
          ? "Connecting…"
          : connected
            ? isSpeaking
              ? "Speaking…"
              : "Listening…"
            : "Tap to start a voice call"}
      </p>

      {error && <p className="text-sm text-error mb-6 text-center max-w-xs">{error}</p>}

      {live ? (
        <button
          type="button"
          onClick={hangUp}
          className="flex items-center gap-2 bg-error text-on-error rounded-full px-6 py-3.5 shadow-lg active:scale-95 transition-transform"
        >
          <Icon name="call_end" filled />
          <span className="font-button-text text-button-text">End call</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={start}
          className="flex items-center gap-2 bg-primary text-on-primary rounded-full px-6 py-3.5 shadow-lg active:scale-95 transition-transform"
        >
          <Icon name="mic" filled />
          <span className="font-button-text text-button-text">Start call</span>
        </button>
      )}
    </div>
  );
}

export function VoiceCall({ onClose }: { onClose: () => void }) {
  return (
    <ConversationProvider>
      <VoiceCallInner onClose={onClose} />
    </ConversationProvider>
  );
}
