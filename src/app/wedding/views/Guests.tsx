import { useMemo, useState } from "react";
import { Link } from "react-router";
import { cn } from "../../design-system/cn";
import { Icon } from "../../planner/Icon";

type Status = "Attending" | "Pending" | "Declined";
type Guest = { id: string; name: string; status: Status; table?: string; head?: boolean; dietary: string[] };

const GUESTS: Guest[] = [
  { id: "1", name: "Eleanor Vance", status: "Attending", table: "Table 4", dietary: ["Vegan"] },
  { id: "2", name: "Julian Crain", status: "Pending", dietary: [] },
  { id: "3", name: "Sarah Jenkins", status: "Attending", table: "Table 1", head: true, dietary: ["GF", "Nut Allergy"] },
  { id: "4", name: "Marcus Cole", status: "Declined", dietary: [] },
  { id: "5", name: "James Sunderland", status: "Attending", table: "Table 1", dietary: [] },
  { id: "6", name: "Elena Rostova", status: "Attending", table: "Table 4", dietary: ["Vegan"] },
  { id: "7", name: "Priya Patel", status: "Attending", table: "Table 2", dietary: ["Dairy-Free"] },
  { id: "8", name: "Tom Wright", status: "Pending", dietary: [] },
  { id: "9", name: "Aoife Byrne", status: "Attending", table: "Table 4", dietary: [] },
  { id: "10", name: "Liam O'Connor", status: "Attending", table: "Table 3", dietary: ["Nut Allergy"] },
  { id: "11", name: "Hannah Schmidt", status: "Pending", dietary: ["Vegan"] },
  { id: "12", name: "Grace Murphy", status: "Attending", table: "Table 2", dietary: ["Vegan"] },
  { id: "13", name: "David Kim", status: "Pending", dietary: [] },
];

const STATS = [
  { label: "Attending", value: 142, icon: "check_circle", valueClass: "text-primary", iconOpacity: "opacity-10 group-hover:opacity-20", iconClass: "text-primary" },
  { label: "Pending", value: 28, icon: "hourglass_empty", valueClass: "text-secondary", iconOpacity: "opacity-10 group-hover:opacity-20", iconClass: "text-secondary" },
  { label: "Declined", value: 15, icon: "cancel", valueClass: "text-on-surface-variant/60", iconOpacity: "opacity-5 group-hover:opacity-10", iconClass: "text-on-surface-variant" },
];

const FILTERS = ["All Guests", "Needs Seat", "Dietary"] as const;
type Filter = (typeof FILTERS)[number];

const PAGE_SIZE = 6;

const statusBadge: Record<Status, string> = {
  Attending: "bg-secondary-container/30 text-on-secondary-container",
  Pending: "bg-surface-variant/50 text-on-surface-variant",
  Declined: "bg-surface-variant text-on-surface-variant",
};
const statusDot: Record<Status, string> = {
  Attending: "bg-secondary",
  Pending: "bg-outline-variant",
  Declined: "",
};

export function Guests() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("All Guests");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    return GUESTS.filter((g) => {
      if (query && !g.name.toLowerCase().includes(query.toLowerCase())) return false;
      if (filter === "Needs Seat") return !g.table && g.status !== "Declined";
      if (filter === "Dietary") return g.dietary.length > 0;
      return true;
    });
  }, [query, filter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageItems = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);
  const start = filtered.length === 0 ? 0 : safePage * PAGE_SIZE + 1;
  const end = safePage * PAGE_SIZE + pageItems.length;

  function applyFilter(f: Filter) {
    setFilter(f);
    setPage(0);
  }

  return (
    <main className="pt-20 md:pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-28 md:pb-12 relative overflow-hidden min-h-screen">
      <div className="absolute top-0 right-0 w-96 h-96 bg-primary-container/5 rounded-full blur-3xl pointer-events-none -z-10 -translate-y-1/2 translate-x-1/4" />

      <header className="mb-12 flex flex-col md:flex-row md:justify-between md:items-end gap-4">
        <div>
          <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-on-surface mb-2">
            Guests & Seating
          </h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">
            Manage your attendees and orchestrate the perfect table arrangements.
          </p>
        </div>
        <div className="hidden lg:flex gap-4">
          <button
            type="button"
            className="bg-surface text-secondary border border-outline/20 font-button-text text-button-text py-2 px-6 rounded-full hover:bg-surface-variant/20 transition-colors"
          >
            Import List
          </button>
          <button
            type="button"
            className="bg-primary-container text-on-primary-container font-button-text text-button-text py-2 px-6 rounded-full hover:opacity-90 transition-opacity flex items-center"
          >
            <Icon name="person_add" size={16} className="mr-2" /> Add Guest
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {STATS.map((s) => (
          <div key={s.label} className="glass-card rounded-[3rem] p-6 flex flex-col justify-between h-32 relative overflow-hidden group">
            <div className={cn("absolute top-0 right-0 p-4 transition-opacity", s.iconOpacity)}>
              <Icon name={s.icon} size={60} className={s.iconClass} />
            </div>
            <p className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-widest">{s.label}</p>
            <p className={cn("font-display-lg text-display-lg", s.valueClass)}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-12">
        <div className="xl:col-span-2 space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-wedding-white p-4 rounded-[2rem] shadow-[0px_4px_20px_rgba(142,103,73,0.03)] border border-outline/10">
            <div className="relative w-full sm:w-64">
              <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
              <input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(0);
                }}
                placeholder="Search guests..."
                className="w-full bg-surface-container-low border-none rounded-full py-2 pl-10 pr-4 font-body-md text-body-md text-on-surface focus:ring-1 focus:ring-primary/30 outline-none placeholder:text-on-surface-variant/50"
                type="text"
              />
            </div>
            <div className="flex gap-2 overflow-x-auto pb-2 sm:pb-0 w-full sm:w-auto scrollbar-hide">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => applyFilter(f)}
                  className={cn(
                    "whitespace-nowrap px-4 py-1.5 rounded-full font-label-caps text-label-caps border transition-colors",
                    filter === f
                      ? "bg-primary-container/20 text-on-primary-container border-primary-container/30"
                      : "bg-surface text-on-surface-variant border-outline/20 hover:bg-surface-variant/30",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-wedding-white rounded-[2rem] shadow-[0px_4px_20px_rgba(142,103,73,0.05)] border border-outline/10 overflow-hidden">
            <div className="hidden md:grid grid-cols-12 gap-4 p-4 border-b border-outline/10 bg-surface/50 font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">
              <div className="col-span-4 pl-4">Guest Name</div>
              <div className="col-span-3">Status</div>
              <div className="col-span-2">Table</div>
              <div className="col-span-3">Dietary Info</div>
            </div>

            <div className="divide-y divide-outline/10">
              {pageItems.length === 0 && (
                <p className="p-8 text-center font-body-md text-body-md text-on-surface-variant">No guests match your search.</p>
              )}
              {pageItems.map((g) => {
                const declined = g.status === "Declined";
                return (
                  <div
                    key={g.id}
                    className={cn(
                      "grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-4 p-4 items-center hover:bg-surface-container-lowest transition-colors cursor-pointer group",
                      declined && "opacity-60",
                    )}
                  >
                    <div className="col-span-1 md:col-span-4 flex items-center gap-4 md:pl-4">
                      <div className="w-10 h-10 rounded-full bg-surface-variant flex items-center justify-center text-on-surface-variant font-title-lg text-title-lg shrink-0">
                        {g.name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <p className={cn("font-body-lg text-body-lg font-medium text-on-surface group-hover:text-primary transition-colors", declined && "line-through")}>
                          {g.name}
                        </p>
                        <p className="font-body-md text-body-md text-on-surface-variant md:hidden">
                          {g.table ? `${g.table}${g.head ? " (Head)" : ""}` : "Unassigned"}
                          {g.dietary.length > 0 && ` • ${g.dietary.join(", ")}`}
                        </p>
                      </div>
                    </div>

                    <div className="hidden md:block col-span-3">
                      <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", statusBadge[g.status])}>
                        {declined ? (
                          <Icon name="close" size={10} className="mr-1" />
                        ) : (
                          <span className={cn("w-1.5 h-1.5 rounded-full mr-1.5", statusDot[g.status])} />
                        )}
                        {g.status}
                      </span>
                    </div>

                    <div className="hidden md:block col-span-2">
                      {g.table ? (
                        <span className={cn("font-body-md text-body-md", g.head ? "text-primary font-medium" : "text-on-surface")}>
                          {g.table}
                          {g.head && " (Head)"}
                        </span>
                      ) : declined ? (
                        <span className="font-body-md text-body-md text-on-surface-variant/50">—</span>
                      ) : (
                        <span className="font-body-md text-body-md text-error flex items-center">
                          <Icon name="warning" size={14} className="mr-1" /> Unassigned
                        </span>
                      )}
                    </div>

                    <div className="hidden md:flex col-span-3 items-center flex-wrap gap-2">
                      {g.dietary.length > 0 ? (
                        g.dietary.map((d) => (
                          <span key={d} className="bg-soft-clay/10 text-tertiary font-label-caps text-label-caps px-2 py-1 rounded-full">
                            {d}
                          </span>
                        ))
                      ) : (
                        <span className="text-on-surface-variant/50 font-body-md text-body-md">—</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="p-4 border-t border-outline/10 flex justify-between items-center bg-surface-bright">
              <span className="font-body-md text-body-md text-on-surface-variant">
                Showing {start}–{end} of {filtered.length}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={safePage === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  className="p-1 rounded text-on-surface-variant hover:bg-surface-variant/50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Icon name="chevron_left" />
                </button>
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={safePage >= pageCount - 1}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  className="p-1 rounded text-on-surface-variant hover:bg-surface-variant/50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Icon name="chevron_right" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="xl:col-span-1">
          <div className="sticky top-8 bg-wedding-white rounded-[2rem] shadow-[0px_8px_30px_rgba(142,103,73,0.06)] border border-primary-container/30 overflow-hidden flex flex-col min-h-[400px]">
            <div className="p-6 bg-gradient-to-br from-surface-bright to-surface-container relative overflow-hidden border-b border-outline/10">
              <div className="absolute top-0 right-0 -mr-8 -mt-8 text-primary-container/20">
                <Icon name="auto_awesome" size={140} />
              </div>
              <div className="relative z-10 flex items-center gap-2 mb-2">
                <Icon name="auto_awesome" filled className="text-primary" />
                <h3 className="font-headline-sm text-headline-sm text-on-surface">Smart Seating</h3>
              </div>
              <p className="font-body-md text-body-md text-on-surface-variant relative z-10">
                Let Aurelia orchestrate harmony — AI-driven seating based on relationships, ages, and dietary needs.
              </p>
            </div>

            <div className="p-6 flex-1 flex flex-col gap-6">
              <div className="space-y-4">
                <h4 className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Current Insights</h4>
                <div className="flex items-start gap-3 bg-secondary-container/10 p-3 rounded-[1rem] border border-secondary-container/30">
                  <Icon name="group_work" size={16} className="text-secondary mt-0.5" />
                  <div>
                    <p className="font-body-md font-medium text-on-surface text-sm">Family clustering optimal</p>
                    <p className="font-body-md text-on-surface-variant text-xs mt-0.5">
                      The Smith and Vance families have balanced numbers for 8-top tables.
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 bg-error-container/20 p-3 rounded-[1rem] border border-error/10">
                  <Icon name="restaurant" size={16} className="text-error mt-0.5" />
                  <div>
                    <p className="font-body-md font-medium text-on-surface text-sm">Dietary isolation risk</p>
                    <p className="font-body-md text-on-surface-variant text-xs mt-0.5">
                      3 vegans are seated alone. Consider grouping at Table 4 for service ease.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex-1" />

              <div className="pt-4 border-t border-outline/10">
                <Link
                  to="/wedding/seating"
                  className="w-full bg-primary-container text-on-primary-container font-button-text text-button-text py-3.5 px-6 rounded-full hover:opacity-90 transition-all hover:scale-[1.02] shadow-[0_4px_14px_rgba(212,175,55,0.25)] flex items-center justify-center gap-2"
                >
                  <Icon name="auto_fix_high" />
                  Generate Seating Plan
                </Link>
                <p className="text-center font-body-md text-[11px] text-on-surface-variant/60 mt-3">
                  This will create a draft. Your current layout will be saved as a version.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
