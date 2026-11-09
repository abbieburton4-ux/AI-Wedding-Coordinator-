import { Icon } from "../../shared/Icon";

interface CoupleVendor {
  name: string;
  website?: string;
  /** Only what the couple have said. Never "booked" or "paid" unless they set it (rule 4). */
  note?: string;
}

interface VendorSection {
  id: string;
  title: string;
  icon: string;
  vendors: CoupleVendor[];
}

/**
 * The couple's own vendor sections (PD-012). Static for now because this app
 * plans one wedding; it's the single place to swap for backend data once the
 * couple can add vendors themselves.
 */
const COUPLE_VENDOR_SECTIONS: VendorSection[] = [
  {
    id: "venue",
    title: "Venue",
    icon: "location_city",
    vendors: [
      {
        name: "Wildman BT",
        website: "https://www.wildmanbt.com/",
        note: "Chosen",
      },
    ],
  },
  { id: "food-drink", title: "Food & drink", icon: "restaurant", vendors: [] },
  { id: "flowers-decoration", title: "Flowers & decoration", icon: "local_florist", vendors: [] },
  { id: "photo-video", title: "Photographer & videographer", icon: "photo_camera", vendors: [] },
  { id: "entertainment", title: "Entertainment", icon: "music_note", vendors: [] },
  { id: "hair-makeup", title: "Hair & makeup", icon: "brush", vendors: [] },
  { id: "transportation", title: "Transportation", icon: "directions_car", vendors: [] },
];

function VendorRow({ vendor }: { vendor: CoupleVendor }) {
  return (
    <li className="flex flex-col gap-1">
      <p className="font-title-lg text-title-lg text-on-surface leading-tight">{vendor.name}</p>
      {vendor.website && (
        <a
          href={vendor.website}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 self-start text-sm font-button-text text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary rounded-sm"
        >
          {vendor.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
          <Icon name="open_in_new" size={14} />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      )}
      {vendor.note && <p className="text-sm text-on-surface-variant">{vendor.note}</p>}
    </li>
  );
}

function SectionCard({ section }: { section: VendorSection }) {
  const headingId = `vendor-section-${section.id}`;
  return (
    <section
      aria-labelledby={headingId}
      className="bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-gutter flex flex-col gap-4"
    >
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 shrink-0 rounded-full bg-primary/10 flex items-center justify-center">
          <Icon name={section.icon} size={20} className="text-primary" />
        </span>
        <h3 id={headingId} className="font-headline-sm text-headline-sm text-on-surface">
          {section.title}
        </h3>
      </div>
      {section.vendors.length > 0 ? (
        <ul className="flex flex-col gap-4">
          {section.vendors.map((v) => (
            <VendorRow key={v.name} vendor={v} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-on-surface-variant">Nothing added yet</p>
      )}
    </section>
  );
}

export function Vendors() {
  return (
    <main className="pt-16 md:pl-72 pb-20 md:pb-8">
      <section className="px-margin-mobile md:px-margin-desktop py-8 md:py-12 bg-surface">
        <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary">
          Vendors
        </h2>
        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-2">
          The people and places you choose for the day, by section.
        </p>
      </section>

      <div className="px-margin-mobile md:px-margin-desktop py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
        {COUPLE_VENDOR_SECTIONS.map((s) => (
          <SectionCard key={s.id} section={s} />
        ))}
      </div>
    </main>
  );
}
