import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../shared/Icon";
import { useApi } from "../../api";
import { useActiveWedding } from "../WeddingProvider";
import { VoiceCall } from "../VoiceCall";

type Message = { role: "ai" | "user"; text: string };

const SEED: Message[] = [
  {
    role: "ai",
    text: "Hi, I'm Aurelia — your AI wedding coordinator. Ask me anything about your budget, checklist, or vendors and I'll answer from your real plan.",
  },
];

const SUGGESTIONS = ["Can we afford a live band?", "Are we on budget?", "What should I do next?"];

export function Concierge() {
  const navigate = useNavigate();
  const { request } = useApi();
  const { activeWedding } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;

  const [messages, setMessages] = useState<Message[]>(SEED);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const scroll = () =>
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
    setDraft("");
    scroll();

    if (!weddingId) {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Start your wedding plan first and I'll have your budget and checklist to work from." },
      ]);
      return;
    }

    setSending(true);
    try {
      const res = await request<{ reply: string }>(`/weddings/${weddingId}/concierge`, {
        method: "POST",
        body: JSON.stringify({ message: trimmed }),
      });
      setMessages((prev) => [...prev, { role: "ai", text: res.reply || "…" }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "I had trouble reaching my tools just now — please try again in a moment." },
      ]);
    } finally {
      setSending(false);
      scroll();
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="fixed top-0 w-full z-50 bg-surface border-b border-outline-variant/20 h-16 flex items-center px-4">
        <button type="button" onClick={() => navigate(-1)} aria-label="Back" className="text-primary p-2">
          <Icon name="arrow_back" />
        </button>
        <h1 className="font-headline-sm text-headline-sm text-center flex-1">Aurelia</h1>
        <button
          type="button"
          onClick={() => setVoiceOpen(true)}
          aria-label="Talk to Aurelia by voice"
          className="text-primary p-2"
        >
          <Icon name="call" />
        </button>
      </header>

      <main className="pt-20 pb-24 px-4 max-w-2xl mx-auto w-full flex flex-col gap-6">
        {messages.map((msg, i) =>
          msg.role === "ai" ? (
            <div key={i} className="flex flex-col items-start max-w-[85%]">
              <span className="text-[10px] font-bold text-primary mb-1 uppercase tracking-widest">Aurelia</span>
              <div className="bg-surface-container-low rounded-2xl rounded-tl-none p-4 border border-outline-variant/20">
                <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
              </div>
            </div>
          ) : (
            <div key={i} className="flex flex-col items-end max-w-[85%] self-end">
              <div className="bg-primary text-white rounded-2xl rounded-tr-none p-4">
                <p className="text-sm">{msg.text}</p>
              </div>
            </div>
          ),
        )}

        {sending && (
          <div className="flex flex-col items-start max-w-[85%]">
            <span className="text-[10px] font-bold text-primary mb-1 uppercase tracking-widest">Aurelia</span>
            <div className="bg-surface-container-low rounded-2xl rounded-tl-none p-4 border border-outline-variant/20 flex items-center gap-1">
              <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce [animation-delay:-0.3s]" />
              <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce [animation-delay:-0.15s]" />
              <span className="w-2 h-2 bg-primary/50 rounded-full animate-bounce" />
            </div>
          </div>
        )}

        {!sending && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((btn) => (
              <button
                key={btn}
                type="button"
                onClick={() => send(btn)}
                className="bg-soft-clay/10 text-soft-clay text-[10px] font-bold px-4 py-2 rounded-full border border-soft-clay/20"
              >
                {btn}
              </button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </main>

      <div className="fixed bottom-0 w-full p-4 bg-background">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
          className="max-w-2xl mx-auto relative flex items-center bg-white border border-outline-variant/30 rounded-full p-1 shadow-lg"
        >
          <button type="button" aria-label="Suggestions" className="p-3 text-primary">
            <Icon name="auto_awesome" />
          </button>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
            className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-sm px-2 disabled:opacity-60"
            placeholder="Ask Aurelia anything..."
          />
          <button type="submit" aria-label="Send" disabled={sending} className="p-3 bg-primary text-white rounded-full disabled:opacity-50">
            <Icon name="send" size={20} />
          </button>
        </form>
      </div>

      {voiceOpen && <VoiceCall onClose={() => setVoiceOpen(false)} />}
    </div>
  );
}
