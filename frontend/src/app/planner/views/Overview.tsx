import { Link } from "react-router";
import { Icon } from "../Icon";

type Note = {
  variant: "alert" | "suggestion" | "ontrack";
  icon: string;
  label: string;
  text: string;
};

const STATS = [
  { label: "Portfolio Value", value: "$248,500", caption: "+12% this quarter", icon: "payments" },
  { label: "Active Files", value: "14", caption: "Weddings in progress", icon: "folder_open" },
];

const CLIENTS: {
  names: string;
  date: string;
  days: string;
  daysAccent: boolean;
  progress: number;
  phase: string;
  note: Note;
}[] = [
  {
    names: "Elena & Julian",
    date: "Oct 12, 2024",
    days: "45 Days",
    daysAccent: true,
    progress: 75,
    phase: "Planning Phase",
    note: {
      variant: "alert",
      icon: "warning",
      label: "AI Alert",
      text: "Catering contracts need review before Friday.",
    },
  },
  {
    names: "Marcus & Sarah",
    date: "Dec 05, 2024",
    days: "98 Days",
    daysAccent: false,
    progress: 40,
    phase: "Vendor Selection",
    note: {
      variant: "suggestion",
      icon: "auto_awesome",
      label: "AI Suggestion",
      text: "Budget alert: Floral estimates exceed allocation by 15%.",
    },
  },
  {
    names: "Chloe & James",
    date: "Mar 15, 2025",
    days: "198 Days",
    daysAccent: false,
    progress: 15,
    phase: "Onboarding",
    note: {
      variant: "ontrack",
      icon: "check_circle",
      label: "On Track",
      text: "Venue secured. Next task: finalize guest list.",
    },
  },
];

export function Overview() {
  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <header className="mb-12">
          <h2 className="font-headline-md text-headline-md text-on-background mb-8">Book of Business</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {STATS.map((stat) => (
              <div
                key={stat.label}
                className="bg-wedding-white p-6 rounded-[3rem] border border-outline/10 flex flex-col justify-between"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="font-label-caps text-label-caps text-on-surface-variant">{stat.label}</span>
                  <Icon name={stat.icon} className="text-primary" />
                </div>
                <div>
                  <span className="font-display-lg text-display-lg text-on-background block">{stat.value}</span>
                  <span className="font-body-md text-body-md text-secondary mt-1 block">{stat.caption}</span>
                </div>
              </div>
            ))}

            <div className="bg-surface-container-low p-6 rounded-[3rem] border border-primary/20 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute -right-4 -top-4 opacity-5 pointer-events-none">
                <Icon name="auto_awesome" size={120} />
              </div>
              <div className="flex items-center justify-between mb-4 relative z-10">
                <span className="font-label-caps text-label-caps text-primary">Pending AI Actions</span>
                <Icon name="auto_awesome" className="text-primary" />
              </div>
              <div className="relative z-10">
                <span className="font-display-lg text-display-lg text-primary block">5</span>
                <span className="font-body-md text-body-md text-on-surface-variant mt-1 block">Requires your attention</span>
              </div>
            </div>
          </div>
        </header>

        <section>
          <div className="flex justify-between items-center mb-6 border-b border-outline/20 pb-4">
            <h3 className="font-title-lg text-title-lg text-on-background">Active Weddings</h3>
            <Link
              to="/planner/clients"
              className="bg-primary-container text-on-primary-container px-4 py-2 rounded-full font-button-text text-button-text flex items-center hover:opacity-90 transition-opacity"
            >
              <Icon name="add" className="mr-2" size={18} /> New Client
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {CLIENTS.map((client) => (
              <div
                key={client.names}
                className="bg-wedding-white rounded-[2rem] border border-outline/20 p-5 hover:shadow-[0px_4px_20px_rgba(142,103,73,0.08)] transition-shadow"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h4 className="font-headline-sm text-headline-sm text-on-background mb-1">{client.names}</h4>
                    <p className="font-body-md text-body-md text-on-surface-variant flex items-center">
                      <Icon name="calendar_today" className="mr-1" size={16} /> {client.date}
                    </p>
                  </div>
                  <div
                    className={
                      client.daysAccent
                        ? "bg-secondary-container text-on-secondary-container font-label-caps text-label-caps px-2 py-1 rounded-full border border-secondary/20"
                        : "bg-surface-container-high text-on-surface-variant font-label-caps text-label-caps px-2 py-1 rounded-full border border-outline/20"
                    }
                  >
                    {client.days}
                  </div>
                </div>

                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-full bg-surface-container-high rounded-full h-1.5">
                      <div className="bg-primary h-1.5 rounded-full" style={{ width: `${client.progress}%` }} />
                    </div>
                    <span className="font-label-caps text-label-caps text-on-surface-variant">{client.progress}%</span>
                  </div>
                  <p className="font-label-caps text-label-caps text-secondary">{client.phase}</p>
                </div>

                <div className="bg-surface-container-low p-3 rounded-[1rem] border border-outline/10">
                  <div className="flex items-start gap-2">
                    <Icon
                      name={client.note.icon}
                      size={18}
                      className={client.note.variant === "alert" ? "text-error" : "text-primary"}
                    />
                    <div>
                      <p
                        className={
                          "font-label-caps text-label-caps mb-1 " +
                          (client.note.variant === "alert" ? "text-error" : "text-primary")
                        }
                      >
                        {client.note.label}
                      </p>
                      <p className="font-body-md text-body-md text-on-surface-variant">{client.note.text}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
