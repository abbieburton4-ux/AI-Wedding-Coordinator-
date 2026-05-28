import { Icon } from "../../planner/Icon";

const ITEMS: {
  date: string;
  title: string;
  time: string;
  status: string;
  icon: string;
  type: "standard" | "primary" | "error";
}[] = [
  { date: "Oct 12, 2024", title: "Engagement Shoot", time: "10:00 AM • Botanical Gardens", status: "Upcoming", icon: "photo_camera", type: "standard" },
  { date: "Nov 05, 2024", title: "Cake Tasting", time: "2:00 PM • Sweet Elegance", status: "Next Up", icon: "cake", type: "primary" },
  { date: "Nov 18, 2024", title: "Dress Fitting", time: "4:30 PM • L'Amour Bridal", status: "Behind", icon: "styler", type: "error" },
];

const circleClass: Record<string, string> = {
  primary: "border-primary bg-primary/10 text-primary",
  error: "border-error text-error",
  standard: "border-outline-variant text-outline",
};

const badgeClass: Record<string, string> = {
  primary: "bg-primary/20 text-primary",
  error: "bg-error/10 text-error",
  standard: "bg-surface-container-high text-outline",
};

export function Timeline() {
  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8">
        <h1 className="font-display-lg-mobile text-display-lg-mobile text-on-surface mb-2">Timeline</h1>
        <p className="text-on-surface-variant">Your upcoming milestones and planning schedule.</p>
      </div>

      <div className="bg-error-container/10 border border-error/20 rounded-[3rem] p-4 mb-8 flex gap-4">
        <div className="w-10 h-10 rounded-full bg-error/10 flex items-center justify-center shrink-0">
          <Icon name="error" filled className="text-error" />
        </div>
        <div>
          <h3 className="font-bold text-error">Attention Needed</h3>
          <p className="text-sm text-on-surface-variant mb-3">Dress fitting confirmation is past due.</p>
          <button type="button" className="bg-error text-white px-4 py-2 rounded-full text-xs font-bold">
            Contact Boutique
          </button>
        </div>
      </div>

      <div className="space-y-8 relative">
        {ITEMS.map((item) => (
          <div key={item.title} className="timeline-item relative flex gap-6">
            <div className="timeline-line shrink-0 relative">
              <div
                className={
                  "w-12 h-12 rounded-full border flex items-center justify-center z-10 relative bg-white " +
                  circleClass[item.type]
                }
              >
                <Icon name={item.icon} filled={item.type === "primary"} />
              </div>
            </div>
            <div className="flex-grow pb-8">
              <div className="flex justify-between items-start mb-1">
                <span
                  className={
                    "text-[10px] font-bold tracking-widest uppercase " +
                    (item.type === "error" ? "text-error" : "text-primary")
                  }
                >
                  {item.date}
                </span>
                <span className={"px-2 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider " + badgeClass[item.type]}>
                  {item.status}
                </span>
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface">{item.title}</h3>
              <p className="text-sm text-on-surface-variant">{item.time}</p>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
