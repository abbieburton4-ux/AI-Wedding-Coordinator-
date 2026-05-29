import { useNavigate } from "react-router";
import { Icon } from "../Icon";
import { usePlannerClients, statusProgress, formatWeddingDate, daysUntil } from "../usePlannerClients";
import { setStoredActiveWeddingId } from "../../wedding/WeddingProvider";

export function Clients() {
  const navigate = useNavigate();
  const { clients, loading } = usePlannerClients();

  // Open a client's wedding in the (shared) couple workspace.
  function open(id: string) {
    setStoredActiveWeddingId(id);
    navigate("/wedding");
  }

  return (
    <div className="px-margin-mobile md:px-margin-desktop py-12">
      <div className="max-w-[1120px] mx-auto">
        <div className="mb-12">
          <h2 className="font-display-lg text-display-lg text-on-surface mb-2">Your clients</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant">
            {loading
              ? "Loading your weddings…"
              : `${clients.length} ${clients.length === 1 ? "wedding" : "weddings"} you manage.`}
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-64 bg-surface-container-low rounded-[3rem] animate-pulse" />
            ))}
          </div>
        ) : clients.length === 0 ? (
          <div className="bg-wedding-white rounded-[3rem] p-10 border border-outline-variant/20 text-center">
            <Icon name="celebration" size={40} className="text-primary mb-3" />
            <h3 className="font-headline-sm text-headline-sm text-on-surface mb-1">No clients yet</h3>
            <p className="text-body-md text-on-surface-variant">Couples you manage will appear here.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {clients.map((c) => {
              const p = statusProgress(c.status);
              const countdown = daysUntil(c.wedding_date);
              return (
                <div
                  key={c.id}
                  className="bg-wedding-white rounded-[3rem] p-6 border border-outline-variant/20 group hover:shadow-[0px_4px_20px_rgba(142,103,73,0.08)] transition-shadow duration-300"
                >
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <h3 className="font-headline-sm text-headline-sm text-on-surface mb-1">
                        {c.region} • {c.ceremony_type}
                      </h3>
                      <p className="font-body-md text-body-md text-on-surface-variant flex items-center gap-1">
                        <Icon name="group" size={16} /> {c.guest_count_estimate} guests • €{c.budget_total.toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-label-caps text-label-caps text-primary">{formatWeddingDate(c.wedding_date)}</p>
                      {countdown && <p className="font-body-md text-[12px] text-on-surface-variant mt-1">{countdown}</p>}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between font-label-caps text-label-caps text-on-surface-variant mb-2">
                        <span>{p.phase}</span>
                        <span className="text-primary font-bold">{p.pct}%</span>
                      </div>
                      <div className="w-full bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
                        <div className="bg-primary-container h-full rounded-full" style={{ width: `${p.pct}%` }} />
                      </div>
                    </div>
                    <span className="inline-block bg-primary/10 text-primary font-label-caps text-[10px] px-2 py-1 rounded-full uppercase tracking-wider">
                      {c.status}
                    </span>
                  </div>

                  <div className="mt-6 pt-4 border-t border-outline-variant/20 flex justify-end">
                    <button
                      type="button"
                      onClick={() => open(c.id)}
                      className="text-primary font-button-text text-button-text flex items-center gap-1 group-hover:underline decoration-1 underline-offset-4"
                    >
                      Open workspace <Icon name="arrow_forward" size={16} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
