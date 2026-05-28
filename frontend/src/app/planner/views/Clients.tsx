import { Link } from "react-router";
import { Icon } from "../Icon";

const CLIENTS: {
  names: string;
  venue: string;
  date: string;
  days: string;
  progress: number;
  tags: string[];
  initials: [string, string];
  actionNeeded?: boolean;
}[] = [
  {
    names: "Eleanor & James",
    venue: "The Botanical Glasshouse",
    date: "SEP 14, 2024",
    days: "42 Days",
    progress: 85,
    tags: ["FLORIST DUE", "SEATING CHART"],
    initials: ["E", "J"],
    actionNeeded: true,
  },
  {
    names: "Sophia & Michael",
    venue: "Villa Bella Estate",
    date: "OCT 05, 2024",
    days: "63 Days",
    progress: 60,
    tags: ["MENU TASTING"],
    initials: ["S", "M"],
  },
  {
    names: "Chloe & David",
    venue: "The Grand Hotel",
    date: "NOV 12, 2024",
    days: "101 Days",
    progress: 35,
    tags: ["INVITATIONS", "BAND DEPOSIT"],
    initials: ["C", "D"],
  },
];

export function Clients() {
  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="flex justify-between items-end mb-12">
          <div>
            <h2 className="font-display-lg text-display-lg text-on-surface mb-2">Active Projects</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant">Manage your upcoming celebrations.</p>
          </div>
          <button
            type="button"
            className="bg-primary-container text-on-primary-container py-2 px-6 rounded-full font-button-text text-button-text flex items-center gap-2 hover:opacity-90 transition-opacity shadow-[0px_4px_20px_rgba(142,103,73,0.08)]"
          >
            <Icon name="add" />
            New Client
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {CLIENTS.map((client) => (
            <div
              key={client.names}
              className="bg-wedding-white rounded-[3rem] p-6 border border-outline-variant/20 relative group hover:shadow-[0px_4px_20px_rgba(142,103,73,0.08)] transition-shadow duration-300"
            >
              {client.actionNeeded && (
                <div className="absolute -top-3 -right-3 bg-error-container text-on-error-container font-label-caps text-[10px] px-3 py-1 rounded-full shadow-sm flex items-center gap-1 border border-error/20">
                  <Icon name="priority_high" size={14} />
                  ACTION NEEDED
                </div>
              )}

              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="font-headline-sm text-headline-sm text-on-surface mb-1">{client.names}</h3>
                  <p className="font-body-md text-body-md text-on-surface-variant flex items-center gap-1">
                    <Icon name="location_on" size={16} />
                    {client.venue}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-label-caps text-label-caps text-primary">{client.date}</p>
                  <p className="font-body-md text-body-md text-on-surface-variant text-[12px] mt-1">{client.days}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between font-label-caps text-label-caps text-on-surface-variant mb-2">
                    <span>Planning Progress</span>
                    <span className="text-primary font-bold">{client.progress}%</span>
                  </div>
                  <div className="w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
                    <div className="bg-primary-container h-full rounded-full" style={{ width: `${client.progress}%` }} />
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {client.tags.map((tag) => (
                    <span
                      key={tag}
                      className="bg-soft-clay/10 text-secondary font-label-caps text-[10px] px-2 py-1 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline-variant/20 flex justify-between items-center">
                <div className="flex -space-x-2">
                  {client.initials.map((initial, i) => (
                    <div
                      key={i}
                      className="w-8 h-8 rounded-full bg-surface-dim border-2 border-wedding-white flex items-center justify-center text-[10px] font-bold text-on-surface-variant"
                    >
                      {initial}
                    </div>
                  ))}
                </div>
                <Link
                  to="/wedding"
                  className="text-primary font-button-text text-button-text flex items-center gap-1 group-hover:underline decoration-1 underline-offset-4"
                >
                  View Details <Icon name="arrow_forward" size={16} />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
