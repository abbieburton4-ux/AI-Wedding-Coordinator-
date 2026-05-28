import { useMemo, useState } from "react";
import { Link } from "react-router";
import { cn } from "../../design-system/cn";
import { Icon } from "../../planner/Icon";

type Tier = "Premium" | "Studio" | "Trial";
type Planner = { id: string; name: string; agency: string; tier: Tier; weddings: number; status: "Active" | "Trial"; lastActive: string };

const PLANNERS: Planner[] = [
  { id: "1", name: "Aoife Gallagher", agency: "Aura Wedding Studio", tier: "Premium", weddings: 18, status: "Active", lastActive: "2m ago" },
  { id: "2", name: "Conor Walsh", agency: "Lúnasa Events", tier: "Studio", weddings: 9, status: "Active", lastActive: "1h ago" },
  { id: "3", name: "Niamh Doyle", agency: "Bloom & Vine Co.", tier: "Premium", weddings: 24, status: "Active", lastActive: "Yesterday" },
  { id: "4", name: "Seán Murphy", agency: "Coast & Clover", tier: "Trial", weddings: 2, status: "Trial", lastActive: "3d ago" },
  { id: "5", name: "Orla Byrne", agency: "The Stardust Planner", tier: "Studio", weddings: 11, status: "Active", lastActive: "5h ago" },
  { id: "6", name: "Cillian Ryan", agency: "Atlantic Weddings", tier: "Trial", weddings: 1, status: "Trial", lastActive: "1w ago" },
];

const tierBadge: Record<Tier, string> = {
  Premium: "bg-primary-container/20 text-on-primary-container",
  Studio: "bg-secondary-container/40 text-on-secondary-container",
  Trial: "bg-surface-variant text-on-surface-variant",
};

export function Planners() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return PLANNERS.filter((p) => !q || p.name.toLowerCase().includes(q) || p.agency.toLowerCase().includes(q));
  }, [query]);

  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-10">
          <div>
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight mb-2">Planners</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">The planner accounts you oversee. Open one to drop into their workspace.</p>
          </div>
          <button
            type="button"
            className="px-6 py-2 rounded-full bg-primary-container text-on-primary-container font-button-text text-button-text flex items-center gap-2 hover:opacity-90 transition-opacity shrink-0"
          >
            <Icon name="person_add" size={18} />
            Invite Planner
          </button>
        </div>

        <div className="relative w-full sm:w-72 mb-6">
          <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search planners…"
            className="w-full bg-wedding-white border border-outline-variant/30 rounded-full py-2 pl-10 pr-4 font-body-md text-body-md text-on-surface focus:ring-1 focus:ring-primary/30 outline-none placeholder:text-on-surface-variant/50"
            type="text"
          />
        </div>

        <div className="bg-wedding-white rounded-[1rem] border border-outline-variant/20 overflow-hidden">
          <div className="hidden md:grid grid-cols-12 gap-4 p-4 border-b border-outline-variant/10 bg-surface/50 font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">
            <div className="col-span-4 pl-4">Planner</div>
            <div className="col-span-2">Tier</div>
            <div className="col-span-2">Weddings</div>
            <div className="col-span-2">Last Active</div>
            <div className="col-span-2 text-right pr-4">Workspace</div>
          </div>
          <div className="divide-y divide-outline-variant/10">
            {filtered.length === 0 && (
              <p className="p-8 text-center font-body-md text-body-md text-on-surface-variant">No planners match your search.</p>
            )}
            {filtered.map((p) => (
              <div key={p.id} className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 p-4 items-center hover:bg-surface-container-lowest transition-colors">
                <div className="col-span-1 md:col-span-4 flex items-center gap-4 md:pl-4">
                  <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center font-title-lg text-title-lg text-on-surface-variant shrink-0">
                    {p.name.charAt(0)}
                  </div>
                  <div className="min-w-0">
                    <p className="font-body-lg text-body-lg font-medium text-on-surface truncate">{p.name}</p>
                    <p className="font-body-md text-body-md text-on-surface-variant truncate">{p.agency}</p>
                  </div>
                </div>
                <div className="hidden md:block col-span-2">
                  <span className={cn("inline-block px-2.5 py-0.5 rounded-full font-label-caps text-label-caps", tierBadge[p.tier])}>{p.tier}</span>
                </div>
                <div className="hidden md:block col-span-2 font-body-md text-body-md text-on-surface">{p.weddings}</div>
                <div className="hidden md:block col-span-2 font-body-md text-body-md text-on-surface-variant">{p.lastActive}</div>
                <div className="col-span-1 md:col-span-2 md:text-right md:pr-4">
                  <Link
                    to="/planner"
                    className="inline-flex items-center gap-1 text-primary font-button-text text-button-text hover:underline underline-offset-4"
                  >
                    Open workspace <Icon name="arrow_forward" size={16} />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
