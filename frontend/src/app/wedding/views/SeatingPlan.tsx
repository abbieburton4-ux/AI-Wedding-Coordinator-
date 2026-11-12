import { useMemo, useState } from "react";
import { DndProvider, useDrag, useDrop } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { cn } from "../../design-system/cn";
import { Icon } from "../../shared/Icon";
import { SampleDataNotice } from "../../shared/SampleDataNotice";

const DRAG_TYPE = "GUEST";

type Diet = "GF" | "VEGAN" | "DF" | "NUT-FREE";
type Guest = { id: string; name: string; role: string; diet?: Diet };
type Table = { id: string; name: string; subtitle: string; capacity: number; x: number; y: number; guestIds: string[] };

const GUESTS: Record<string, Guest> = {
  g1: { id: "g1", name: "Sarah Jenkins", role: "Mother of Bride", diet: "GF" },
  g2: { id: "g2", name: "James Sunderland", role: "Father of Bride" },
  g3: { id: "g3", name: "Elena Rostova", role: "Aunt", diet: "VEGAN" },
  g4: { id: "g4", name: "Michael Chen", role: "College Friend" },
  g5: { id: "g5", name: "Priya Patel", role: "College Friend", diet: "DF" },
  g6: { id: "g6", name: "Tom Wright", role: "Colleague" },
  g7: { id: "g7", name: "Aoife Byrne", role: "Cousin" },
  g8: { id: "g8", name: "Liam O'Connor", role: "Cousin", diet: "NUT-FREE" },
  g9: { id: "g9", name: "Hannah Schmidt", role: "Friend of Couple" },
  g10: { id: "g10", name: "David Kim", role: "Plus One" },
  g11: { id: "g11", name: "Grace Murphy", role: "Friend of Couple", diet: "VEGAN" },
};

const INITIAL_TABLES: Table[] = [
  { id: "t1", name: "Table 1", subtitle: "Immediate Family", capacity: 8, x: 32, y: 38, guestIds: ["g1", "g2", "g3"] },
  { id: "t2", name: "Table 2", subtitle: "College Friends", capacity: 8, x: 68, y: 34, guestIds: ["g4", "g5"] },
  { id: "t3", name: "Table 3", subtitle: "Colleagues", capacity: 6, x: 30, y: 72, guestIds: ["g6"] },
  { id: "t4", name: "Table 4", subtitle: "Extended Family", capacity: 6, x: 70, y: 72, guestIds: ["g7", "g8"] },
];

const dietColor: Record<Diet, string> = {
  GF: "bg-soft-clay/10 text-soft-clay",
  VEGAN: "bg-primary-container/15 text-on-primary-container",
  DF: "bg-tertiary/10 text-tertiary",
  "NUT-FREE": "bg-secondary/10 text-secondary",
};

function initials(name: string) {
  return name.charAt(0).toUpperCase();
}

/* ---------- Draggable guest ---------- */

function GuestDragItem({
  guest,
  onSend,
  variant,
}: {
  guest: Guest;
  onSend?: () => void;
  variant: "row" | "chip";
}) {
  const [{ isDragging }, drag] = useDrag(
    () => ({ type: DRAG_TYPE, item: { guestId: guest.id }, collect: (m) => ({ isDragging: m.isDragging() }) }),
    [guest.id],
  );

  if (variant === "chip") {
    return (
      <div
        ref={drag}
        className={cn(
          "shrink-0 w-44 flex items-center gap-3 p-3 rounded-[1.5rem] bg-wedding-white border border-outline-variant/20 cursor-grab active:cursor-grabbing",
          isDragging && "is-dragging",
        )}
      >
        <div className="w-9 h-9 rounded-full bg-surface-container-highest flex items-center justify-center font-title-lg text-title-lg text-on-surface-variant shrink-0">
          {initials(guest.name)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-body-md text-body-md text-on-surface truncate">{guest.name}</p>
          <p className="text-[11px] text-on-surface-variant truncate">{guest.role}</p>
        </div>
        {onSend && (
          <button
            type="button"
            onClick={onSend}
            aria-label="Assign to selected table"
            className="md:hidden text-primary-text shrink-0"
          >
            <Icon name="add_circle" size={22} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      ref={drag}
      className={cn(
        "flex items-center justify-between p-3 rounded-[1.5rem] hover:bg-surface-bright transition-colors border border-transparent hover:border-outline-variant/10 cursor-grab active:cursor-grabbing",
        isDragging && "is-dragging",
      )}
    >
      <div className="flex items-center gap-gutter min-w-0">
        <Icon name="drag_indicator" className="text-outline-variant" />
        <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center font-title-lg text-title-lg text-on-surface-variant shrink-0">
          {initials(guest.name)}
        </div>
        <div className="min-w-0">
          <p className="font-body-lg text-body-lg text-on-surface truncate">{guest.name}</p>
          <p className="font-body-md text-on-surface-variant text-[12px] truncate">{guest.role}</p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {guest.diet && (
          <span className={cn("px-2 py-1 rounded-full font-label-caps text-[10px]", dietColor[guest.diet])}>
            {guest.diet}
          </span>
        )}
        {onSend && (
          <button type="button" onClick={onSend} aria-label="Unassign guest" className="text-outline hover:text-error transition-colors">
            <Icon name="person_remove" size={20} />
          </button>
        )}
      </div>
    </div>
  );
}

/* ---------- Table node (drop target) ---------- */

function TableNode({
  table,
  selected,
  onSelect,
  onDropGuest,
  isFull,
}: {
  table: Table;
  selected: boolean;
  onSelect: () => void;
  onDropGuest: (guestId: string) => void;
  isFull: boolean;
}) {
  const [{ isOver, canDrop }, drop] = useDrop(
    () => ({
      accept: DRAG_TYPE,
      canDrop: (item: { guestId: string }) => table.guestIds.includes(item.guestId) || !isFull,
      drop: (item: { guestId: string }) => onDropGuest(item.guestId),
      collect: (m) => ({ isOver: m.isOver(), canDrop: m.canDrop() }),
    }),
    [table, isFull, onDropGuest],
  );

  const used = table.guestIds.length;
  const seats = Array.from({ length: table.capacity });

  return (
    <div
      ref={drop}
      onClick={onSelect}
      style={{ left: `${table.x}%`, top: `${table.y}%` }}
      className={cn(
        "absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center cursor-pointer transition-transform duration-300",
        selected ? "scale-[1.35] z-20" : "z-10 hover:scale-110",
      )}
    >
      <div
        className={cn(
          "relative w-20 h-20 flex items-center justify-center rounded-full",
          isOver && canDrop && "drop-active",
          isOver && !canDrop && "drop-reject",
        )}
      >
        <div className="absolute w-[112px] h-[112px] rounded-full border border-dashed border-outline-variant/40 animate-spin-slow" />
        {seats.map((_, i) => {
          const angle = (360 / table.capacity) * i;
          const filled = i < used;
          return (
            <span
              key={i}
              className={cn(
                "absolute w-3.5 h-3.5 rounded-full",
                filled ? "bg-primary-container" : "bg-surface-container-highest border border-outline-variant/30",
              )}
              style={{ transform: `rotate(${angle}deg) translateY(-56px)` }}
            />
          );
        })}
        <div
          className={cn(
            "w-20 h-20 rounded-full bg-surface-container-lowest flex flex-col items-center justify-center z-10",
            selected
              ? "border-2 border-primary-container shadow-[0_4px_20px_rgba(142,103,73,0.18)]"
              : "border border-outline-variant/40",
          )}
        >
          <span className="font-headline-sm text-headline-sm text-primary-text leading-none">{table.name.replace("Table ", "")}</span>
          <span className="font-label-caps text-[10px] text-on-surface-variant">
            {used}/{table.capacity}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------- Unassigned tray (drop target) ---------- */

function UnassignedTray({
  guests,
  onUnassign,
  onAssignToSelected,
  canAssign,
}: {
  guests: Guest[];
  onUnassign: (guestId: string) => void;
  onAssignToSelected: (guestId: string) => void;
  canAssign: boolean;
}) {
  const [{ isOver }, drop] = useDrop(
    () => ({
      accept: DRAG_TYPE,
      drop: (item: { guestId: string }) => onUnassign(item.guestId),
      collect: (m) => ({ isOver: m.isOver() }),
    }),
    [onUnassign],
  );

  return (
    <div
      ref={drop}
      className={cn(
        "bg-surface-container-lowest rounded-[2rem] border p-5 transition-colors guest-tray",
        isOver ? "border-primary-container" : "border-outline-variant/20",
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-title-lg text-title-lg text-on-surface flex items-center gap-2">
          <Icon name="chair_alt" className="text-on-surface-variant" />
          Unassigned Guests
          <span className="font-label-caps text-label-caps text-on-surface-variant">({guests.length})</span>
        </h3>
        <span className="hidden md:inline font-label-caps text-[10px] text-on-surface-variant">Drag onto a table · drop here to unassign</span>
      </div>
      {guests.length === 0 ? (
        <p className="font-body-md text-body-md text-on-surface-variant py-4 text-center">Everyone has a seat. 🎉</p>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2 hide-scrollbar">
          {guests.map((g) => (
            <GuestDragItem
              key={g.id}
              guest={g}
              variant="chip"
              onSend={canAssign ? () => onAssignToSelected(g.id) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------- Page ---------- */

function SeatingPlanInner() {
  const [tables, setTables] = useState<Table[]>(INITIAL_TABLES);
  const [selectedId, setSelectedId] = useState<string | null>("t1");
  const [zoom, setZoom] = useState(1);

  const assignedIds = useMemo(() => new Set(tables.flatMap((t) => t.guestIds)), [tables]);
  const unassigned = useMemo(() => Object.values(GUESTS).filter((g) => !assignedIds.has(g.id)), [assignedIds]);
  const selected = tables.find((t) => t.id === selectedId) ?? null;
  const totalSeated = assignedIds.size;

  function assign(guestId: string, tableId: string) {
    setTables((prev) => {
      const target = prev.find((t) => t.id === tableId);
      if (!target) return prev;
      const alreadyHere = target.guestIds.includes(guestId);
      if (!alreadyHere && target.guestIds.length >= target.capacity) return prev; // full
      return prev.map((t) => {
        if (t.id === tableId) return alreadyHere ? t : { ...t, guestIds: [...t.guestIds, guestId] };
        return { ...t, guestIds: t.guestIds.filter((id) => id !== guestId) };
      });
    });
  }

  function unassign(guestId: string) {
    setTables((prev) => prev.map((t) => ({ ...t, guestIds: t.guestIds.filter((id) => id !== guestId) })));
  }

  function addTable() {
    setTables((prev) => {
      const n = prev.length + 1;
      return [
        ...prev,
        {
          id: `t${Date.now()}`,
          name: `Table ${n}`,
          subtitle: "New Table",
          capacity: 8,
          x: 20 + ((n * 17) % 60),
          y: 50 + ((n * 13) % 30),
          guestIds: [],
        },
      ];
    });
  }

  function removeTable(id: string) {
    setTables((prev) => prev.filter((t) => t.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  return (
    <main className="pt-20 md:ml-72 md:pt-24 px-margin-mobile md:px-margin-desktop pb-28 md:pb-12 min-h-screen">
      <div className="mb-8 flex flex-col md:flex-row md:justify-between md:items-end gap-4">
        <div>
          <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary-text mb-2">
            Seating Plan
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Grand Ballroom • {totalSeated} of {Object.keys(GUESTS).length} guests seated
          </p>
          <SampleDataNotice className="mt-4">
            These tables, guests, room and assistant suggestions are made-up examples, not your seating plan. Changes on this screen are not saved.
          </SampleDataNotice>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={addTable}
            className="px-6 py-3 rounded-full border border-outline-variant/20 text-secondary font-button-text text-button-text flex items-center gap-2 hover:bg-surface-container-low transition-colors"
          >
            <Icon name="add" size={18} />
            Add Table
          </button>
          <button
            type="button"
            className="px-6 py-3 rounded-full bg-primary-container text-on-primary-container font-button-text text-button-text flex items-center gap-2 shadow-[0_4px_20px_rgba(142,103,73,0.08)] active:scale-95 transition-transform"
          >
            <Icon name="download" size={18} />
            Export
          </button>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-[2rem] p-6 mb-8 border border-outline-variant/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="bg-surface-container-low p-3 rounded-full text-primary-text shrink-0">
            <Icon name="auto_awesome" filled />
          </div>
          <div>
            <h3 className="font-title-lg text-title-lg text-on-surface mb-1">AI Seating Assistant Active</h3>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-xl">
              Aurelia has grouped family members and balanced dietary requirements across service stations. Drag a guest onto any
              table to override.
            </p>
          </div>
        </div>
        <button
          type="button"
          className="px-4 py-2 rounded-full border border-outline-variant/20 text-secondary font-button-text text-button-text hover:bg-surface-container-low transition-colors shrink-0"
        >
          View Suggestions
        </button>
      </div>

      <div className="bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-6 relative overflow-hidden flex flex-col">
        <div className="flex gap-3 pb-4 mb-2 overflow-x-auto hide-scrollbar">
          {tables.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelectedId(t.id)}
              className={cn(
                "px-6 py-2 rounded-full font-headline-sm text-[16px] whitespace-nowrap border transition-all active:scale-95",
                selectedId === t.id
                  ? "bg-primary-container text-on-primary-container border-primary-container shadow-sm"
                  : "bg-surface-container-low text-on-surface-variant border-outline-variant/20 hover:border-primary-container/30",
              )}
            >
              {t.name}
            </button>
          ))}
        </div>

        <div className="flex justify-between items-center mb-4 z-10 relative">
          <div className="font-label-caps text-label-caps text-on-surface-variant flex gap-4">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-surface-container-highest border border-outline-variant/20" /> Empty Seat
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-primary-container" /> Assigned Seat
            </span>
          </div>
          <div className="flex gap-2 bg-surface-bright rounded-full p-1 border border-outline-variant/20">
            <button
              type="button"
              aria-label="Zoom out"
              onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.2).toFixed(2)))}
              className="p-2 rounded-full hover:bg-surface-container-low text-on-surface-variant transition-colors"
            >
              <Icon name="zoom_out" size={20} />
            </button>
            <button
              type="button"
              aria-label="Zoom in"
              onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.2).toFixed(2)))}
              className="p-2 rounded-full hover:bg-surface-container-low text-on-surface-variant transition-colors"
            >
              <Icon name="zoom_in" size={20} />
            </button>
          </div>
        </div>

        <div className="relative h-[56vh] bg-surface-bright/50 rounded-[1.5rem] border border-outline-variant/10 overflow-hidden">
          <div
            className="absolute inset-0 transition-transform duration-300"
            style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
          >
            {tables.map((t) => (
              <TableNode
                key={t.id}
                table={t}
                selected={selectedId === t.id}
                isFull={t.guestIds.length >= t.capacity}
                onSelect={() => setSelectedId(t.id)}
                onDropGuest={(guestId) => assign(guestId, t.id)}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8">
        <UnassignedTray
          guests={unassigned}
          onUnassign={unassign}
          onAssignToSelected={(guestId) => selected && assign(guestId, selected.id)}
          canAssign={!!selected && selected.guestIds.length < selected.capacity}
        />
      </div>

      {/* Table details panel */}
      {selected && (
        <>
          <div
            className="fixed inset-0 bg-charcoal-ink/20 z-[55] md:hidden"
            onClick={() => setSelectedId(null)}
          />
          <aside className="fixed z-[60] bg-surface-container-lowest border-outline-variant/20 flex flex-col animate-slide-up inset-x-0 bottom-0 rounded-t-3xl border-t max-h-[72%] md:inset-auto md:top-24 md:right-6 md:bottom-6 md:w-[380px] md:rounded-[2rem] md:border md:max-h-none md:animate-none">
            <div className="md:hidden flex flex-col items-center pt-3 pb-1">
              <div className="w-12 h-1.5 bg-primary-container/30 rounded-full" />
            </div>
            <div className="p-6 flex-grow overflow-y-auto hide-scrollbar guest-tray rounded-[2rem]">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="font-headline-md text-headline-md text-primary-text">{selected.name}</h2>
                  <p className="font-body-md text-body-md text-on-surface-variant">
                    {selected.subtitle} • {selected.guestIds.length}/{selected.capacity} seats
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close panel"
                  onClick={() => setSelectedId(null)}
                  className="p-2 rounded-full hover:bg-surface-container-low transition-colors"
                >
                  <Icon name="close" className="text-on-surface-variant" />
                </button>
              </div>

              <div className="flex flex-col gap-3">
                {selected.guestIds.length === 0 && (
                  <p className="font-body-md text-body-md text-on-surface-variant text-center py-6">
                    No guests yet — drag someone here from the tray.
                  </p>
                )}
                {selected.guestIds.map((id) => (
                  <GuestDragItem key={id} guest={GUESTS[id]} variant="row" onSend={() => unassign(id)} />
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-outline-variant/20 flex gap-3">
                <button
                  type="button"
                  onClick={() => removeTable(selected.id)}
                  className="flex-1 py-3 rounded-full border border-error/30 text-error font-button-text text-button-text hover:bg-error/5 transition-colors flex items-center justify-center gap-2"
                >
                  <Icon name="delete" size={18} />
                  Remove Table
                </button>
              </div>
            </div>
          </aside>
        </>
      )}
    </main>
  );
}

export function SeatingPlan() {
  return (
    <DndProvider backend={HTML5Backend}>
      <SeatingPlanInner />
    </DndProvider>
  );
}
