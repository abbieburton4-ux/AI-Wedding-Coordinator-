import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../planner/Icon";

type Message = { role: "ai" | "user"; text: string };

const SEED: Message[] = [
  { role: "ai", text: "Hello! I'm Aurelia, your wedding concierge. How can I help you refine your special day today?" },
  { role: "user", text: "I'm worried about the floral budget." },
  {
    role: "ai",
    text: "Based on your budget of $4,000, we've spent $3,100. I can find seasonal greenery options that save up to 15%.",
  },
];

const SUGGESTIONS = ["Show portfolios", "Check budget", "See moodboard"];

export function Concierge() {
  const navigate = useNavigate();
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
        text: "Lovely — I'm looking into that now. (Preview build: connect the agent backend for live answers.)",
      },
    ]);
    setDraft("");
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="fixed top-0 w-full z-50 bg-surface border-b border-outline-variant/20 h-16 flex items-center px-4">
        <button type="button" onClick={() => navigate(-1)} aria-label="Back" className="text-primary p-2">
          <Icon name="arrow_back" />
        </button>
        <h1 className="font-headline-sm text-headline-sm text-center flex-1 pr-10">Aurelia</h1>
      </header>

      <main className="pt-20 pb-24 px-4 max-w-2xl mx-auto w-full flex flex-col gap-6">
        {messages.map((msg, i) =>
          msg.role === "ai" ? (
            <div key={i} className="flex flex-col items-start max-w-[85%]">
              <span className="text-[10px] font-bold text-primary mb-1 uppercase tracking-widest">Aurelia</span>
              <div className="bg-surface-container-low rounded-2xl rounded-tl-none p-4 border border-outline-variant/20">
                <p className="text-sm">{msg.text}</p>
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
            className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-sm px-2"
            placeholder="Ask Aurelia anything..."
          />
          <button type="submit" aria-label="Send" className="p-3 bg-primary text-white rounded-full">
            <Icon name="send" size={20} />
          </button>
        </form>
      </div>
    </div>
  );
}
