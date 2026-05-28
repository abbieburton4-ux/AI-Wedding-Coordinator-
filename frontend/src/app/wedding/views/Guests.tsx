import { useState } from "react";
import { Icon } from "../../planner/Icon";

const GUESTS = [
  { name: "Eleanor Vance", detail: "Table 4 • Vegan", icon: "check_circle" },
  { name: "James Sunderland", detail: "Unassigned", icon: "schedule" },
];

const TABLE_ONE = ["Sarah Jenkins", "James Sunderland", "Elena Rostova"];

export function Guests() {
  const [showPanel, setShowPanel] = useState(false);

  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8 text-center">
        <h2 className="font-headline-md text-headline-md text-on-surface">Guests & Seating</h2>
        <p className="text-on-surface-variant">Manage RSVPs and arrangements with ease.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-8">
        <div className="bg-wedding-white p-6 rounded-[3rem] border border-outline-variant/20 flex flex-col items-center justify-center">
          <span className="font-display-lg-mobile text-display-lg-mobile text-primary">142</span>
          <span className="font-label-caps text-[10px] text-on-surface-variant">Attending</span>
        </div>
        <div className="grid grid-rows-2 gap-4">
          <div className="bg-wedding-white p-4 rounded-[3rem] border border-outline-variant/20 flex justify-between items-center">
            <span className="font-label-caps text-[10px] text-on-surface-variant">Pending</span>
            <span className="font-bold">28</span>
          </div>
          <div className="bg-wedding-white p-4 rounded-[3rem] border border-outline-variant/20 flex justify-between items-center">
            <span className="font-label-caps text-[10px] text-on-surface-variant">Declined</span>
            <span className="font-bold text-outline">15</span>
          </div>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 p-6 mb-8">
        <h3 className="font-title-lg text-title-lg mb-4">Floor Plan</h3>
        <div
          className="h-[300px] bg-surface-bright/50 rounded-[2rem] flex items-center justify-center relative cursor-pointer"
          onClick={() => setShowPanel(true)}
        >
          <div className="w-24 h-24 rounded-full border-2 border-primary-container bg-white flex flex-col items-center justify-center shadow-lg">
            <span className="text-xl font-headline-sm text-primary">Table 1</span>
            <span className="text-[10px] text-on-surface-variant">8/8 Guests</span>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {GUESTS.map((guest) => (
          <div
            key={guest.name}
            className="bg-wedding-white p-4 rounded-[3rem] border border-outline-variant/20 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary">
                <Icon name={guest.icon} filled={guest.icon === "check_circle"} />
              </div>
              <div>
                <p className="font-bold">{guest.name}</p>
                <p className="text-xs text-on-surface-variant">{guest.detail}</p>
              </div>
            </div>
            <button type="button" aria-label="Guest options" className="text-outline">
              <Icon name="more_vert" />
            </button>
          </div>
        ))}
      </div>

      {showPanel && (
        <div className="fixed inset-0 z-[100] flex items-end md:items-center justify-center p-0 md:p-6">
          <div className="absolute inset-0 bg-charcoal-ink/40" onClick={() => setShowPanel(false)} />
          <div className="relative w-full md:max-w-md bg-surface-container-lowest rounded-t-3xl md:rounded-3xl p-6 shadow-2xl animate-slide-up">
            <div className="flex justify-between items-center mb-6">
              <h2 className="font-headline-sm text-headline-sm">Table 1 Guests</h2>
              <button type="button" aria-label="Close" onClick={() => setShowPanel(false)}>
                <Icon name="close" />
              </button>
            </div>
            <div className="space-y-4 max-h-[530px] overflow-y-auto pr-2">
              {TABLE_ONE.map((name) => (
                <div key={name} className="flex items-center gap-4 p-3 hover:bg-surface-container-low rounded-[3rem]">
                  <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center">{name[0]}</div>
                  <span className="font-medium">{name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
