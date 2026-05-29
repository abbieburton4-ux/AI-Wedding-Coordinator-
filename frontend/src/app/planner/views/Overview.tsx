import { useNavigate, Link } from "react-router";
import { Icon } from "../Icon";
import { usePlannerClients, statusProgress, formatWeddingDate } from "../usePlannerClients";
import { setStoredActiveWeddingId } from "../../wedding/WeddingProvider";

export function Overview() {
  const navigate = useNavigate();
  const { clients, loading } = usePlannerClients();

  const portfolio = clients.reduce((s, c) => s + (c.budget_total || 0), 0);
  const inPlanning = clients.filter((c) => c.status === "planning").length;
  const inIntake = clients.filter((c) => c.status === "intake").length;

  function open(id: string) {
    setStoredActiveWeddingId(id);
    navigate("/wedding");
  }

  const stats = [
    { label: "Active files", value: loading ? "—" : String(clients.length), caption: "Weddings you manage", icon: "folder_open" },
    { label: "Portfolio value", value: loading ? "—" : `€${portfolio.toLocaleString()}`, caption: "Total managed budget", icon: "payments" },
    { label: "In planning", value: loading ? "—" : String(inPlanning), caption: `${inIntake} in intake`, icon: "event" },
  ];

  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <header className="mb-12">
          <h2 className="font-headline-md text-headline-md text-on-background mb-8">Book of business</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {stats.map((stat) => (
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
          </div>
        </header>

        <section>
          <div className="flex justify-between items-center mb-6 border-b border-outline/20 pb-4">
            <h3 className="font-title-lg text-title-lg text-on-background">Active weddings</h3>
            <Link
              to="/planner/clients"
              className="text-primary font-button-text text-button-text flex items-center gap-1 hover:underline"
            >
              View all <Icon name="arrow_forward" size={16} />
            </Link>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-44 bg-surface-container-low rounded-[2rem] animate-pulse" />
              ))}
            </div>
          ) : clients.length === 0 ? (
            <div className="bg-wedding-white rounded-[2rem] p-8 border border-outline/20 text-center text-on-surface-variant">
              No managed weddings yet. Couples assigned to you will appear here.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {clients.slice(0, 6).map((c) => {
                const p = statusProgress(c.status);
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => open(c.id)}
                    className="text-left bg-wedding-white rounded-[2rem] border border-outline/20 p-5 hover:shadow-[0px_4px_20px_rgba(142,103,73,0.08)] transition-shadow"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h4 className="font-headline-sm text-headline-sm text-on-background mb-1">
                          {c.region} • {c.ceremony_type}
                        </h4>
                        <p className="font-body-md text-body-md text-on-surface-variant flex items-center">
                          <Icon name="calendar_today" className="mr-1" size={16} /> {formatWeddingDate(c.wedding_date)}
                        </p>
                      </div>
                      <span className="bg-surface-container-high text-on-surface-variant font-label-caps text-label-caps px-2 py-1 rounded-full border border-outline/20 uppercase">
                        {c.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-full bg-surface-container-high rounded-full h-1.5">
                        <div className="bg-primary h-1.5 rounded-full" style={{ width: `${p.pct}%` }} />
                      </div>
                      <span className="font-label-caps text-label-caps text-on-surface-variant">{p.pct}%</span>
                    </div>
                    <p className="font-label-caps text-label-caps text-secondary mt-2">{p.phase}</p>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
