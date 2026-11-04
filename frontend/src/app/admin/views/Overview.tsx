import { Link } from "react-router";
import { Icon } from "../../planner/Icon";

const KPIS = [
  { label: "Active Planners", value: "12", caption: "+2 this month", icon: "business_center", trend: "trending_up" },
  { label: "Active Weddings", value: "148", caption: "+19 this month", icon: "celebration", trend: "trending_up" },
  { label: "Agent Actions (30d)", value: "3,402", caption: "94% auto-approved", icon: "smart_toy", trend: "bolt" },
  { label: "Submission Readiness", value: "78%", caption: "On track for deadline", icon: "verified", trend: "trending_up" },
];

const ACTIVITY = [
  { icon: "smart_toy", title: "Agent sourced 3 venues", meta: "Smith Wedding · 2m ago", tint: "text-primary" },
  { icon: "person_add", title: "New planner onboarded — Lúnasa Events", meta: "Admin · 1h ago", tint: "text-secondary" },
  { icon: "payments", title: "Budget rebalanced automatically", meta: "Vance Wedding · 3h ago", tint: "text-primary" },
  { icon: "warning", title: "Dietary conflict flagged for review", meta: "O'Brien Wedding · 5h ago", tint: "text-error" },
];

const READINESS = [
  { label: "Category selected — Professional Services Access", done: true },
  { label: "Agent Decision Log capturing actions", done: true },
  { label: "Narrative sections drafted", done: true },
  { label: "Evidence metrics exported", done: false },
  { label: "Final review & sign-off", done: false },
];

export function Overview() {
  const doneCount = READINESS.filter((r) => r.done).length;

  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="mb-10">
          <h2 className="font-display-lg text-display-lg text-on-surface tracking-tight mb-2">Operations</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">Platform health and XPRIZE submission progress.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {KPIS.map((k) => (
            <div key={k.label} className="bg-wedding-white rounded-[1rem] border border-outline-variant/20 p-6 flex flex-col justify-between h-40">
              <div className="flex justify-between items-start">
                <span className="font-label-caps text-label-caps text-on-surface-variant tracking-wider">{k.label}</span>
                <div className="bg-surface-container-low p-2 rounded-full">
                  <Icon name={k.icon} size={20} className="text-primary" />
                </div>
              </div>
              <div>
                <div className="font-headline-md text-headline-md text-on-surface mb-1">{k.value}</div>
                <div className="flex items-center gap-1 font-button-text text-button-text text-secondary">
                  <Icon name={k.trend} size={16} />
                  <span>{k.caption}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-7 bg-wedding-white rounded-[1rem] border border-outline-variant/20 p-8">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-title-lg text-title-lg text-on-surface">Platform Activity</h3>
              <Link to="/admin/agent-log" className="text-primary font-button-text text-button-text hover:underline">
                View agent log
              </Link>
            </div>
            <div className="flex flex-col">
              {ACTIVITY.map((a, i) => (
                <div key={i} className="flex items-start gap-4 py-4 border-b border-outline-variant/10 last:border-0">
                  <div className="bg-surface-container-low p-2 rounded-full shrink-0">
                    <Icon name={a.icon} size={20} className={a.tint} />
                  </div>
                  <div className="min-w-0">
                    <p className="font-body-md text-body-md text-on-surface">{a.title}</p>
                    <p className="font-label-caps text-label-caps text-on-surface-variant mt-0.5">{a.meta}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-5 bg-surface-container-low rounded-[1rem] border border-primary/20 p-8 relative overflow-hidden">
            <div className="absolute -right-6 -top-6 opacity-5 pointer-events-none">
              <Icon name="workspace_premium" size={140} />
            </div>
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-1">
                <Icon name="workspace_premium" filled className="text-primary" />
                <h3 className="font-title-lg text-title-lg text-on-surface">XPRIZE Submission</h3>
              </div>
              <p className="font-body-md text-body-md text-on-surface-variant mb-6">
                Build with Gemini — {doneCount} of {READINESS.length} requirements complete.
              </p>
              <div className="w-full bg-surface-container-high h-2 rounded-full overflow-hidden mb-6">
                <div className="bg-primary h-full rounded-full" style={{ width: `${(doneCount / READINESS.length) * 100}%` }} />
              </div>
              <ul className="flex flex-col gap-3">
                {READINESS.map((r) => (
                  <li key={r.label} className="flex items-start gap-3">
                    <Icon
                      name={r.done ? "check_circle" : "radio_button_unchecked"}
                      filled={r.done}
                      size={20}
                      className={r.done ? "text-primary" : "text-outline-variant"}
                    />
                    <span className={"font-body-md text-body-md " + (r.done ? "text-on-surface" : "text-on-surface-variant")}>
                      {r.label}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
