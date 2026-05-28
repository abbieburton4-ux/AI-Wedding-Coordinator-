import { Icon } from "../../planner/Icon";
import { IMG } from "../../design-system/assets";

const VENDORS = [
  { title: "The Glasshouse Estate", cat: "Venue", rating: "4.9", img: IMG.showroom },
  { title: "Ethereal Lens Studio", cat: "Photography", rating: "5.0", img: IMG.weddingConfetti },
  { title: "Culinary Canvas", cat: "Catering", rating: "4.8", img: IMG.fineDining },
];

export function Vendors() {
  return (
    <main className="pt-16 md:pl-72 pb-20 md:pb-8">
      <section className="px-margin-mobile md:px-margin-desktop py-8 md:py-12 bg-surface">
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary">
              Curated Vendors
            </h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-2">
              Discover and manage the professionals bringing your vision to life.
            </p>
          </div>
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Icon name="search" className="absolute left-4 top-1/2 -translate-y-1/2 text-outline" />
              <input
                className="w-full h-12 pl-12 pr-4 bg-surface-container-lowest border-b border-outline-variant/20 rounded-t-[2rem] focus:outline-none"
                placeholder="Search vendors..."
                type="text"
              />
            </div>
            <button
              type="button"
              className="flex items-center gap-2 px-6 h-12 bg-soft-clay/10 rounded-full border border-soft-clay/20 text-tertiary"
            >
              <Icon name="auto_awesome" size={18} />
              <span className="font-button-text">Recommended by AI</span>
            </button>
          </div>
        </div>
      </section>
      <section className="px-margin-mobile md:px-margin-desktop py-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
          {VENDORS.map((v) => (
            <div
              key={v.title}
              className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 overflow-hidden flex flex-col group hover:shadow-lg transition-all"
            >
              <div className="relative h-48 w-full">
                <img src={v.img} alt={v.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                <div className="absolute top-3 right-3 bg-surface-container-lowest/90 px-3 py-1 rounded-full flex items-center gap-1">
                  <Icon name="auto_awesome" filled size={14} className="text-tertiary" />
                  <span className="font-label-caps text-[10px] text-tertiary font-bold">MATCH</span>
                </div>
              </div>
              <div className="p-gutter flex flex-col flex-1 gap-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="font-label-caps text-[10px] text-outline tracking-widest uppercase">{v.cat}</span>
                    <h3 className="font-title-lg text-title-lg text-on-surface mt-1">{v.title}</h3>
                  </div>
                  <div className="flex items-center gap-1">
                    <Icon name="star" filled size={16} className="text-primary" />
                    <span className="font-body-md">{v.rating}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
