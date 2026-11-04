import { Icon } from "../../shared/Icon";
import { useWedding, USE_FASTAPI_BACKEND } from "../../api";
import { useActiveWedding } from "../WeddingProvider";

const STATIC_CATEGORIES = [
  {
    name: "Attire & Beauty",
    spent: "$4,200",
    total: "$5,000",
    pct: "84%",
    icon: "styler",
    tip: "Consider local alterations specialists for a 15% saving.",
  },
  {
    name: "Floral & Decor",
    spent: "$3,100",
    total: "$4,000",
    pct: "77%",
    icon: "local_florist",
    tip: "Opting for seasonal blooms can stretch this budget further.",
  },
];

const ICON_MAP: Record<string, string> = {
  venue: "home",
  catering: "restaurant",
  photography: "photo_camera",
  florals: "local_florist",
  music: "music_note",
  officiant: "person",
  other: "more_horiz",
  attire: "styler",
};

function formatCurrency(amount: number): string {
  return `€${amount.toLocaleString("en-IE", { minimumFractionDigits: 0 })}`;
}

export function Budget() {
  const { activeWedding } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { data, loading } = useWedding(weddingId);

  const useLiveData = USE_FASTAPI_BACKEND && data.budgetLines.length > 0;

  // Compute totals from live data
  const totalAllocated = data.budgetLines.reduce((s, b) => s + b.allocated_amount, 0);
  const totalSpent = data.budgetLines.reduce((s, b) => s + b.spent_amount, 0);

  const liveCategories = data.budgetLines.map((bl) => {
    const pct = bl.allocated_amount > 0
      ? Math.round((bl.spent_amount / bl.allocated_amount) * 100)
      : 0;
    const over = bl.allocated_amount > 0 && bl.spent_amount > bl.allocated_amount;
    return {
      name: bl.category.charAt(0).toUpperCase() + bl.category.slice(1),
      spent: formatCurrency(bl.spent_amount),
      total: formatCurrency(bl.allocated_amount),
      pct: `${pct}%`,
      barPct: `${Math.min(pct, 100)}%`,
      over,
      overBy: over ? formatCurrency(bl.spent_amount - bl.allocated_amount) : "",
      icon: ICON_MAP[bl.category] || "payments",
      tip: "", // Tips will come from AI agent suggestions in the future
    };
  });

  const categories = useLiveData ? liveCategories : STATIC_CATEGORIES;
  const displaySpent = useLiveData ? formatCurrency(totalSpent) : "$24,500";
  const displayTotal = useLiveData ? formatCurrency(totalAllocated) : "$35,000";

  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8">
        <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary mb-2">
          Budget Health
        </h1>
        <p className="text-on-surface-variant">Stay on track with your wedding finances.</p>
      </div>

      {/* Loading skeleton for the donut chart area */}
      {loading ? (
        <div className="flex flex-col items-center mb-12">
          <div className="w-48 h-48 rounded-full bg-surface-container-low animate-pulse" />
        </div>
      ) : (
        <div className="flex flex-col items-center mb-12">
          <div className="chart-donut shadow-sm">
            <div className="absolute flex flex-col items-center justify-center z-10">
              <span className="font-body-md text-on-surface-variant text-xs">Total Spent</span>
              <span className="font-headline-sm text-headline-sm text-on-surface">{displaySpent}</span>
              <span className="font-label-caps text-[10px] text-outline">OF {displayTotal}</span>
            </div>
          </div>
        </div>
      )}

      {useLiveData && totalSpent > totalAllocated && (
        <div className="bg-error-container/15 border border-error-container/40 rounded-[2rem] p-4 mb-6 flex items-start gap-3">
          <Icon name="warning" size={22} className="text-error mt-0.5" />
          <div>
            <p className="font-button-text text-error text-sm">Over budget</p>
            <p className="text-sm text-on-surface-variant">
              Your tracked quotes total {formatCurrency(totalSpent)} — {formatCurrency(totalSpent - totalAllocated)} over
              your {formatCurrency(totalAllocated)} plan. Trim a category or adjust your budget.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-6">
        {loading ? (
          // Skeleton cards
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-surface-container-lowest p-6 rounded-[3rem] border border-outline-variant/20 animate-pulse">
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-surface-container" />
                  <div>
                    <div className="h-4 bg-surface-container-low rounded w-32 mb-1" />
                    <div className="h-3 bg-surface-container-low rounded w-24" />
                  </div>
                </div>
                <div className="h-5 bg-surface-container-low rounded w-10" />
              </div>
              <div className="w-full bg-surface-container-low h-2 rounded-full" />
            </div>
          ))
        ) : (
          categories.map((cat) => (
            <div key={cat.name} className="bg-surface-container-lowest p-6 rounded-[3rem] border border-outline-variant/20">
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center text-primary">
                    <Icon name={cat.icon} />
                  </div>
                  <div>
                    <h3 className="font-button-text text-on-surface">{cat.name}</h3>
                    <p className="text-[12px] text-on-surface-variant">
                      {cat.spent} of {cat.total}
                      {cat.over && <span className="text-error font-bold"> · {cat.overBy} over</span>}
                    </p>
                  </div>
                </div>
                <span className={`font-bold ${cat.over ? "text-error" : "text-primary"}`}>{cat.pct}</span>
              </div>
              <div className="w-full bg-surface-container-low h-2 rounded-full mb-4">
                <div
                  className={`h-2 rounded-full ${cat.over ? "bg-error" : "bg-primary-container"}`}
                  style={{ width: cat.barPct || cat.pct }}
                />
              </div>
              {cat.tip && (
                <div className="bg-secondary-fixed/20 p-3 rounded-[2rem] flex items-start gap-2 border border-secondary-fixed/50">
                  <Icon name="lightbulb" size={18} className="text-secondary" />
                  <p className="text-sm text-on-secondary-container">
                    <strong className="font-button-text">AI Tip:</strong> {cat.tip}
                  </p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </main>
  );
}
