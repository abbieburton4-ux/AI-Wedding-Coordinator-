import { useNavigate } from "react-router";
import { Icon } from "../../planner/Icon";
import { IMG } from "../../design-system/assets";

const VENUES = [
  { name: "The Glasshouse", img: IMG.showroom, price: "$150/HEAD" },
  { name: "Meadow Retreat", img: IMG.aisleOutdoors, price: "$125/HEAD" },
];

export function Dashboard() {
  const navigate = useNavigate();
  return (
    <main className="pt-24 pb-32 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop max-w-[1120px] mx-auto">
      <section className="mb-12">
        <header className="flex items-center justify-between mb-6">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">AI Decision Feed</h2>
          <span className="bg-soft-clay/10 text-soft-clay font-label-caps text-[10px] px-2 py-1 rounded-full uppercase tracking-tighter">
            Live Insight
          </span>
        </header>
        <div className="bg-wedding-white custom-shadow rounded-[3rem] p-6 mb-8 border border-outline-variant/10">
          <div className="flex items-center gap-3 mb-4">
            <Icon name="priority_high" filled className="text-primary-container" />
            <h3 className="font-title-lg text-title-lg text-on-surface">Approve Venue Shortlist</h3>
          </div>
          <p className="font-body-md text-on-surface-variant mb-6">
            Based on your vision, I've curated three venues that align with your aesthetic.
          </p>

          <div className="space-y-6">
            {VENUES.map((venue) => (
              <div key={venue.name} className="group cursor-pointer">
                <div className="relative h-48 w-full overflow-hidden mb-3 rounded-[2rem]">
                  <img
                    src={venue.img}
                    alt={venue.name}
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                  <div className="absolute top-4 right-4 bg-wedding-white/90 px-3 py-1 text-label-caps font-label-caps text-primary shadow-sm rounded-full">
                    {venue.price}
                  </div>
                </div>
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-headline-sm text-headline-sm">{venue.name}</h4>
                    <div className="flex items-center gap-2 mt-1 text-soft-clay">
                      <Icon name="auto_awesome" filled size={16} />
                      <p className="font-body-md italic text-xs">Matches your floral aesthetic.</p>
                    </div>
                  </div>
                  <button type="button" aria-label="View venue" className="text-primary hover:bg-primary/5 p-2 rounded-full">
                    <Icon name="chevron_right" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-8 flex gap-3">
            <button
              type="button"
              onClick={() => navigate("/wedding/vendors")}
              className="flex-1 bg-primary text-on-primary py-4 rounded-full font-button-text tracking-widest uppercase hover:opacity-90 transition-opacity"
            >
              Review All
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
