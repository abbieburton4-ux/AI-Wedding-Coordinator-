import { Icon } from "../../planner/Icon";

const CATEGORIES = [
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

export function Budget() {
  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8">
        <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary mb-2">
          Budget Health
        </h1>
        <p className="text-on-surface-variant">Stay on track with your wedding finances.</p>
      </div>
      <div className="flex flex-col items-center mb-12">
        <div className="chart-donut shadow-sm">
          <div className="absolute flex flex-col items-center justify-center z-10">
            <span className="font-body-md text-on-surface-variant text-xs">Total Spent</span>
            <span className="font-headline-sm text-headline-sm text-on-surface">$24,500</span>
            <span className="font-label-caps text-[10px] text-outline">OF $35,000</span>
          </div>
        </div>
      </div>
      <div className="space-y-6">
        {CATEGORIES.map((cat) => (
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
                  </p>
                </div>
              </div>
              <span className="text-primary font-bold">{cat.pct}</span>
            </div>
            <div className="w-full bg-surface-container-low h-2 rounded-full mb-4">
              <div className="bg-primary-container h-2 rounded-full" style={{ width: cat.pct }} />
            </div>
            <div className="bg-secondary-fixed/20 p-3 rounded-[2rem] flex items-start gap-2 border border-secondary-fixed/50">
              <Icon name="lightbulb" size={18} className="text-secondary" />
              <p className="text-sm text-on-secondary-container">
                <strong className="font-button-text">AI Tip:</strong> {cat.tip}
              </p>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
