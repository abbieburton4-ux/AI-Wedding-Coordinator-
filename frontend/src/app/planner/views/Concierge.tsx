import { useRef, useState } from "react";
import { Icon } from "../Icon";
import { Avatar } from "../Avatar";
import { cn } from "../../design-system/cn";

type Message = { role: "ai" | "user"; text: string };

const SEED: Message[] = [
  {
    role: "ai",
    text: "Good morning. I've reviewed your three active weddings overnight. Elena & Julian's catering contract still needs sign-off before Friday, and Marcus & Sarah's floral estimate is 15% over budget. Where would you like to start?",
  },
  {
    role: "user",
    text: "Draft a polite note to Marcus & Sarah's florist asking for a revised quote.",
  },
  {
    role: "ai",
    text: "Done — I've drafted a message proposing a 15% reduction by swapping the imported peonies for seasonal garden roses, keeping the palette intact. It's saved to their file as a draft for your approval. Want me to send it, or adjust the tone first?",
  },
];

const SUGGESTIONS = [
  "Summarize this week's priorities",
  "Draft a timeline for Elena & Julian",
  "Which clients are over budget?",
  "Prepare a vendor shortlist",
];

export function Concierge() {
  const [messages, setMessages] = useState<Message[]>(SEED);
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: trimmed },
      {
        role: "ai",
        text: "I'm on it. (This is a preview build — connect the agent backend to generate live responses and log them to the AgentDecisionLog.)",
      },
    ]);
    setDraft("");
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <header className="shrink-0 border-b border-outline-variant/20 px-margin-mobile md:px-margin-desktop py-5 flex items-center gap-4 bg-surface-bright/80 backdrop-blur-md">
        <div className="w-10 h-10 rounded-full bg-primary-container flex items-center justify-center">
          <Icon name="auto_awesome" filled className="text-on-primary-container" />
        </div>
        <div className="flex-1">
          <h2 className="font-headline-sm text-headline-sm text-on-surface leading-tight">VenueFlow Concierge</h2>
          <p className="font-label-caps text-label-caps text-on-surface-variant flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary inline-block" />
            AI wedding coordinator · always on
          </p>
        </div>
        <button
          type="button"
          aria-label="New conversation"
          className="text-on-surface-variant hover:text-primary transition-colors"
          onClick={() => setMessages(SEED)}
        >
          <Icon name="restart_alt" />
        </button>
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto px-margin-mobile md:px-margin-desktop py-8">
        <div className="max-w-3xl mx-auto flex flex-col gap-6">
          {messages.map((msg, i) =>
            msg.role === "ai" ? (
              <div key={i} className="flex items-start gap-3">
                <div className="w-8 h-8 shrink-0 rounded-full bg-primary-container flex items-center justify-center mt-1">
                  <Icon name="auto_awesome" filled size={18} className="text-on-primary-container" />
                </div>
                <div className="bg-wedding-white border border-outline-variant/20 rounded-[1.5rem] rounded-tl-md p-4 font-body-md text-body-md text-on-surface max-w-[85%]">
                  {msg.text}
                </div>
              </div>
            ) : (
              <div key={i} className="flex items-start gap-3 flex-row-reverse">
                <Avatar initials="AM" className="w-8 h-8 text-[10px] mt-1 shrink-0" />
                <div className="bg-primary text-on-primary rounded-[1.5rem] rounded-tr-md p-4 font-body-md text-body-md max-w-[85%]">
                  {msg.text}
                </div>
              </div>
            ),
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-outline-variant/20 px-margin-mobile md:px-margin-desktop py-5 bg-surface-bright">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-2 flex-wrap mb-4">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="font-label-caps text-label-caps text-on-surface-variant border border-outline-variant/40 rounded-full px-3 py-1.5 hover:bg-surface-container-low hover:text-primary transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
            className="flex items-center gap-2 bg-surface-container-low border border-outline-variant/30 rounded-full pl-5 pr-2 py-2 focus-within:border-primary transition-colors"
          >
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask the concierge to draft, plan, or review…"
              className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-body-md text-on-surface placeholder:text-on-surface-variant/60 p-0"
            />
            <button
              type="submit"
              aria-label="Send message"
              disabled={!draft.trim()}
              className={cn(
                "w-9 h-9 rounded-full flex items-center justify-center transition-opacity",
                draft.trim()
                  ? "bg-primary text-on-primary hover:opacity-90"
                  : "bg-surface-container-high text-on-surface-variant/50",
              )}
            >
              <Icon name="arrow_upward" size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
