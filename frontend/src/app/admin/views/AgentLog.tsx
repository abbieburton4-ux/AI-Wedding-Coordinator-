import { useMemo, useState } from "react";
import { cn } from "../../design-system/cn";
import { Icon } from "../../planner/Icon";

type Category = "Sourcing" | "Budget" | "Timeline" | "Comms" | "Seating";
type Outcome = "Auto-approved" | "Executed" | "Needs review";
type Entry = {
  id: string;
  time: string;
  workspace: string;
  category: Category;
  action: string;
  outcome: Outcome;
  confidence: number;
};

const ENTRIES: Entry[] = [
  { id: "1", time: "10:42", workspace: "Smith Wedding", category: "Sourcing", action: "Shortlisted 3 venues matching floral aesthetic", outcome: "Needs review", confidence: 88 },
  { id: "2", time: "10:31", workspace: "Vance Wedding", category: "Budget", action: "Rebalanced florals −15% to seasonal blooms", outcome: "Auto-approved", confidence: 94 },
  { id: "3", time: "09:58", workspace: "Aura Studio", category: "Comms", action: "Drafted revised-quote email to Bloom & Co", outcome: "Needs review", confidence: 91 },
  { id: "4", time: "09:40", workspace: "O'Brien Wedding", category: "Seating", action: "Grouped 3 vegan guests at Table 4", outcome: "Executed", confidence: 96 },
  { id: "5", time: "09:12", workspace: "Smith Wedding", category: "Timeline", action: "Flagged dress-fitting confirmation past due", outcome: "Needs review", confidence: 99 },
  { id: "6", time: "08:55", workspace: "Lúnasa Events", category: "Sourcing", action: "Matched photographer to couple style profile", outcome: "Auto-approved", confidence: 90 },
  { id: "7", time: "08:30", workspace: "Vance Wedding", category: "Comms", action: "Sent RSVP reminder to 28 pending guests", outcome: "Executed", confidence: 97 },
  { id: "8", time: "Yesterday", workspace: "Coast & Clover", category: "Budget", action: "Alerted catering 12% over allocation", outcome: "Needs review", confidence: 92 },
  { id: "9", time: "Yesterday", workspace: "Smith Wedding", category: "Timeline", action: "Drafted day-of run-of-show v2", outcome: "Auto-approved", confidence: 89 },
  { id: "10", time: "Yesterday", workspace: "O'Brien Wedding", category: "Seating", action: "Resolved table-capacity conflict on Table 2", outcome: "Executed", confidence: 95 },
  { id: "11", time: "2d ago", workspace: "Aura Studio", category: "Sourcing", action: "Compiled preferred-vendor list for autumn season", outcome: "Auto-approved", confidence: 87 },
  { id: "12", time: "2d ago", workspace: "Vance Wedding", category: "Comms", action: "Negotiated revised florist deposit terms", outcome: "Needs review", confidence: 84 },
];

const CATEGORIES = ["All", "Sourcing", "Budget", "Timeline", "Comms", "Seating"] as const;
type Filter = (typeof CATEGORIES)[number];

const outcomeBadge: Record<Outcome, string> = {
  "Auto-approved": "bg-secondary-container/40 text-on-secondary-container",
  Executed: "bg-primary-container/20 text-on-primary-container",
  "Needs review": "bg-error-container/40 text-on-error-container",
};

const categoryIcon: Record<Category, string> = {
  Sourcing: "storefront",
  Budget: "payments",
  Timeline: "auto_schedule",
  Comms: "mail",
  Seating: "table_restaurant",
};

export function AgentLog() {
  const [filter, setFilter] = useState<Filter>("All");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const q = query.toLowerCase();
    return ENTRIES.filter((e) => {
      if (filter !== "All" && e.category !== filter) return false;
      if (q && !(e.action.toLowerCase().includes(q) || e.workspace.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [filter, query]);

  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-8">
          <div>
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight mb-2">Agent Decision Log</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">
              Every autonomous agent action — the evidence backbone of the XPRIZE submission.
            </p>
          </div>
          <button
            type="button"
            className="px-6 py-2 rounded-full bg-primary-container text-on-primary-container font-button-text text-button-text flex items-center gap-2 hover:opacity-90 transition-opacity shrink-0"
          >
            <Icon name="download" size={18} />
            Export evidence
          </button>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch sm:items-center mb-6">
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setFilter(c)}
                className={cn(
                  "whitespace-nowrap px-4 py-1.5 rounded-full font-label-caps text-label-caps border transition-colors",
                  filter === c
                    ? "bg-primary-container/20 text-on-primary-container border-primary-container/30"
                    : "bg-wedding-white text-on-surface-variant border-outline-variant/30 hover:bg-surface-container-low",
                )}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="relative w-full sm:w-64 shrink-0">
            <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search actions…"
              className="w-full bg-wedding-white border border-outline-variant/30 rounded-full py-2 pl-10 pr-4 font-body-md text-body-md text-on-surface focus:ring-1 focus:ring-primary/30 outline-none placeholder:text-on-surface-variant/50"
              type="text"
            />
          </div>
        </div>

        <div className="bg-wedding-white rounded-[1rem] border border-outline-variant/20 overflow-hidden">
          <div className="hidden md:grid grid-cols-12 gap-4 p-4 border-b border-outline-variant/10 bg-surface/50 font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">
            <div className="col-span-1 pl-4">Time</div>
            <div className="col-span-3">Workspace</div>
            <div className="col-span-4">Action</div>
            <div className="col-span-2">Outcome</div>
            <div className="col-span-2 text-right pr-4">Confidence</div>
          </div>
          <div className="divide-y divide-outline-variant/10">
            {rows.length === 0 && (
              <p className="p-8 text-center font-body-md text-body-md text-on-surface-variant">No actions match these filters.</p>
            )}
            {rows.map((e) => (
              <div key={e.id} className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 p-4 items-center hover:bg-surface-container-lowest transition-colors">
                <div className="hidden md:block col-span-1 pl-4 font-label-caps text-label-caps text-on-surface-variant">{e.time}</div>
                <div className="col-span-1 md:col-span-3 flex items-center gap-3">
                  <div className="bg-surface-container-low p-1.5 rounded-full shrink-0">
                    <Icon name={categoryIcon[e.category]} size={16} className="text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-body-md text-body-md text-on-surface truncate">{e.workspace}</p>
                    <p className="font-label-caps text-label-caps text-on-surface-variant md:hidden">{e.category} · {e.time}</p>
                  </div>
                </div>
                <div className="col-span-1 md:col-span-4 font-body-md text-body-md text-on-surface">{e.action}</div>
                <div className="col-span-1 md:col-span-2">
                  <span className={cn("inline-block px-2.5 py-0.5 rounded-full font-label-caps text-label-caps", outcomeBadge[e.outcome])}>
                    {e.outcome}
                  </span>
                </div>
                <div className="col-span-1 md:col-span-2 md:text-right md:pr-4 flex md:block items-center gap-2">
                  <div className="w-full max-w-[80px] md:ml-auto bg-surface-container-high h-1.5 rounded-full overflow-hidden">
                    <div className="bg-primary h-full rounded-full" style={{ width: `${e.confidence}%` }} />
                  </div>
                  <span className="font-label-caps text-label-caps text-on-surface-variant">{e.confidence}%</span>
                </div>
              </div>
            ))}
          </div>
          <div className="p-4 border-t border-outline-variant/10 bg-surface-bright font-body-md text-body-md text-on-surface-variant">
            {rows.length} action{rows.length === 1 ? "" : "s"} shown
          </div>
        </div>
      </div>
    </div>
  );
}
