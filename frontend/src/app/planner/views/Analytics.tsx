import { Icon } from "../Icon";

const METRICS: {
  label: string;
  value: string;
  caption: string;
  icon: string;
  trendIcon: string;
  trendClass: string;
}[] = [
  {
    label: "Total Revenue",
    value: "$248,500",
    caption: "+14.2% vs last year",
    icon: "account_balance",
    trendIcon: "trending_up",
    trendClass: "text-secondary",
  },
  {
    label: "Active Clients",
    value: "34",
    caption: "+4 new this month",
    icon: "favorite",
    trendIcon: "trending_up",
    trendClass: "text-secondary",
  },
  {
    label: "Conversion Rate",
    value: "68%",
    caption: "Steady trend",
    icon: "donut_large",
    trendIcon: "trending_flat",
    trendClass: "text-on-surface-variant",
  },
];

const LEAD_SOURCES: { name: string; pct: number; bar: string }[] = [
  { name: "Instagram", pct: 42, bar: "bg-primary-container" },
  { name: "Referrals", pct: 35, bar: "bg-secondary-fixed-dim" },
  { name: "Vendor Network", pct: 15, bar: "bg-outline-variant" },
  { name: "Organic Search", pct: 8, bar: "bg-outline" },
];

export function Analytics() {
  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="mb-10 flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4">
          <div>
            <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight mb-2">Performance Overview</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">Tracking your growth and client engagement.</p>
          </div>
          <div className="flex gap-4">
            <button
              type="button"
              className="border border-outline-variant/50 rounded-full px-6 py-2 font-button-text text-button-text text-secondary hover:bg-surface-container-low transition-colors flex items-center gap-2"
            >
              <Icon name="calendar_today" size={18} />
              This Year
            </button>
            <button
              type="button"
              className="bg-primary-container text-on-primary-container rounded-full px-6 py-2 font-button-text text-button-text hover:opacity-90 transition-opacity flex items-center gap-2"
            >
              <Icon name="download" size={18} />
              Export
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {METRICS.map((metric) => (
            <div
              key={metric.label}
              className="bg-wedding-white rounded-[1rem] border border-outline-variant/20 p-6 flex flex-col justify-between h-40 hover:border-outline-variant/50 transition-colors"
            >
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-label-caps text-on-surface-variant tracking-wider">{metric.label}</span>
                <div className="bg-surface-container-low p-2 rounded-full">
                  <Icon name={metric.icon} size={20} className="text-primary" />
                </div>
              </div>
              <div>
                <div className="font-headline-md text-headline-md text-on-surface mb-1">{metric.value}</div>
                <div className={"flex items-center gap-1 font-button-text text-button-text " + metric.trendClass}>
                  <Icon name={metric.trendIcon} size={16} />
                  <span>{metric.caption}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 bg-wedding-white rounded-[1rem] border border-outline-variant/20 p-8 flex flex-col">
            <div className="flex justify-between items-center mb-8">
              <h3 className="font-title-lg text-title-lg text-on-surface">Revenue Trends</h3>
              <button type="button" aria-label="More options" className="text-on-surface-variant hover:text-primary transition-colors">
                <Icon name="more_horiz" />
              </button>
            </div>
            <div className="flex-1 relative chart-grid border-b border-l border-outline-variant/20 min-h-[300px] flex items-end pt-4 pr-4">
              <div className="absolute -left-12 top-0 h-full flex flex-col justify-between text-label-caps font-label-caps text-outline pb-6">
                <span>$60k</span>
                <span>$40k</span>
                <span>$20k</span>
                <span>$0</span>
              </div>
              <div className="w-full h-full relative">
                <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 800 250">
                  <defs>
                    <linearGradient id="lineGrad" x1="0%" x2="0%" y1="0%" y2="100%">
                      <stop offset="0%" stopColor="#d4af37" stopOpacity="0.2" />
                      <stop offset="100%" stopColor="#d4af37" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <path
                    d="M0,200 C100,180 200,220 300,150 C400,80 500,120 600,60 C700,0 800,40 800,40 L800,250 L0,250 Z"
                    fill="url(#lineGrad)"
                  />
                  <path
                    d="M0,200 C100,180 200,220 300,150 C400,80 500,120 600,60 C700,0 800,40 800,40"
                    fill="none"
                    stroke="#d4af37"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="3"
                  />
                  <circle cx="300" cy="150" fill="#faf9f6" r="5" stroke="#d4af37" strokeWidth="2" />
                  <circle cx="600" cy="60" fill="#faf9f6" r="5" stroke="#d4af37" strokeWidth="2" />
                  <circle cx="800" cy="40" fill="#faf9f6" r="5" stroke="#d4af37" strokeWidth="2" />
                </svg>
              </div>
              <div className="absolute -bottom-8 left-0 w-full flex justify-between text-label-caps font-label-caps text-outline pl-2 pr-2">
                <span>Jan</span>
                <span>Mar</span>
                <span>May</span>
                <span>Jul</span>
                <span>Sep</span>
                <span>Nov</span>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 bg-wedding-white rounded-[1rem] border border-outline-variant/20 p-8 flex flex-col">
            <h3 className="font-title-lg text-title-lg text-on-surface mb-8">Top Lead Sources</h3>
            <div className="flex flex-col gap-6 flex-1">
              {LEAD_SOURCES.map((source) => (
                <div key={source.name}>
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-body-md text-body-md font-medium text-on-surface">{source.name}</span>
                    <span className="font-label-caps text-label-caps text-on-surface-variant">{source.pct}%</span>
                  </div>
                  <div className="w-full bg-surface-container-high rounded-full h-2 overflow-hidden">
                    <div className={source.bar + " h-full rounded-full"} style={{ width: `${source.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="mt-8 text-secondary font-button-text text-button-text flex items-center gap-1 hover:opacity-80 transition-opacity"
            >
              View detailed report
              <Icon name="arrow_forward" size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
