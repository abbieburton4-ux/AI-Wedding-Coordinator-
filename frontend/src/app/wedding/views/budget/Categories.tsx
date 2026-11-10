import { useEffect, useRef, useState } from "react";
import { Icon } from "../../../shared/Icon";
import { moveItem } from "./expenses";
import { linkButton, primaryButton } from "./parts";
import type { Category, Run } from "./types";

type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;

/**
 * The suggested categories (PD-013 call b), added only when the couple click. Each
 * starts with no target, and categories they already have stay exactly as they are.
 * One the couple removed isn't offered again (B71) until they click the quiet
 * "Show suggestions you removed" link, which puts it back on this list, not yet added.
 */
export function DefaultCategoriesOffer({
  base, missing, removed, hasAny, run, request, busy,
}: {
  base: string; missing: string[]; removed: string[]; hasAny: boolean; run: Run; request: Req; busy: boolean;
}) {
  const [picked, setPicked] = useState<string[]>(missing);
  const [hidden, setHidden] = useState(false);
  const key = missing.join("|");
  // A new list from the API (one was added or removed elsewhere): start fully ticked again.
  useEffect(() => { setPicked(key ? key.split("|") : []); }, [key]);
  // "Not now" lasts until the list empties; restored suggestions then show open.
  useEffect(() => { if (!key) setHidden(false); }, [key]);

  const showRemoved = removed.length > 0 && (
    <button
      type="button"
      disabled={busy}
      onClick={() => run(() => request(`${base}/categories/defaults/restore`, { method: "POST" }))}
      className={`${linkButton} text-xs`}
    >
      Show suggestions you removed ({removed.length})
    </button>
  );

  if (missing.length === 0) {
    return <p className="mb-6">{showRemoved}</p>;
  }

  if (hidden) {
    return (
      <p className="mb-6">
        <button type="button" onClick={() => setHidden(false)} className={linkButton}>
          Show the suggested categories ({missing.length})
        </button>
      </p>
    );
  }

  const toggle = (name: string) =>
    setPicked((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]));
  const add = () =>
    run(() => request(`${base}/categories/defaults`, { method: "POST", body: JSON.stringify({ names: picked }) }));
  const count = picked.length;

  return (
    <section aria-labelledby="defaults-heading" className="mb-8 bg-secondary-fixed/20 border border-secondary-fixed/50 rounded-[1.5rem] p-5">
      <h3 id="defaults-heading" className="font-headline-sm text-lg text-on-surface mb-1">Add the suggested categories</h3>
      <p className="text-sm text-on-surface-variant mb-3">
        {hasAny
          ? "These suggested categories aren't in your budget yet. Untick any you don't want. Your own categories and expenses stay as they are."
          : "Start with the suggested categories. Untick any you don't want."}
        {" "}Each starts with no target, so set one when you're ready. When you add an expense, each category offers
        ideas such as Photographer or Invitations. Contingency is money kept aside for costs you didn't plan for.
      </p>
      <fieldset className="mb-4">
        <legend className="sr-only">Categories to add</legend>
        <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1">
          {missing.map((name) => (
            <li key={name}>
              <label className="flex items-center gap-2 text-sm text-on-surface cursor-pointer py-1">
                <input
                  type="checkbox"
                  checked={picked.includes(name)}
                  onChange={() => toggle(name)}
                  className="h-4 w-4 accent-primary"
                />
                {name}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <div className="flex flex-wrap items-center gap-4">
        <button type="button" onClick={add} disabled={busy || count === 0} className={primaryButton}>
          {count === missing.length
            ? "Add the suggested categories"
            : `Add ${count} ${count === 1 ? "category" : "categories"}`}
        </button>
        <button type="button" onClick={() => setHidden(true)} className={linkButton}>Not now</button>
        {showRemoved}
      </div>
    </section>
  );
}

/**
 * Put the categories in the couple's order: drag a row, or use its Move up and
 * Move down buttons (keyboard and phone). Each move is saved straight away.
 */
export function CategoryOrder({
  base, categories, run, request, busy,
}: { base: string; categories: Category[]; run: Run; request: Req; busy: boolean }) {
  const [open, setOpen] = useState(false);
  const [dragging, setDragging] = useState<number | null>(null);
  const [announce, setAnnounce] = useState("");
  const buttons = useRef(new Map<string, HTMLButtonElement | null>());
  const refocus = useRef<string | null>(null);
  const ids = categories.map((c) => c.id);

  // Reordering moves the rows, which can drop keyboard focus; put it back on the
  // button the couple used (or its partner, once the row reaches an end).
  useEffect(() => {
    const target = refocus.current;
    if (!target) return;
    refocus.current = null;
    const [id, dir] = target.split(":");
    const index = ids.indexOf(id);
    const usable = dir === "up" ? index > 0 : index < ids.length - 1;
    buttons.current.get(`${id}:${usable ? dir : dir === "up" ? "down" : "up"}`)?.focus();
  });

  if (categories.length < 2) return null;

  const move = async (from: number, to: number, dir?: "up" | "down") => {
    const next = moveItem(ids, from, to);
    if (next === ids) return;
    const name = categories[from].name;
    const ok = await run(() =>
      request(`${base}/categories/order`, { method: "PUT", body: JSON.stringify({ category_ids: next }) }),
    );
    if (ok) {
      if (dir) refocus.current = `${ids[from]}:${dir}`;
      setAnnounce(`${name} moved to position ${to + 1} of ${ids.length}.`);
    }
  };

  return (
    <div className="mb-6">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className={linkButton}>
        {open ? "Done changing the order" : "Change the order of categories"}
      </button>
      <p aria-live="polite" className="sr-only">{announce}</p>
      {open && (
        <>
          <p className="text-xs text-on-surface-variant mt-2 mb-2">
            Drag a category, or use its arrows. Each change is saved straight away.
          </p>
          <ol className="divide-y divide-outline-variant/30 border-y border-outline-variant/30">
            {categories.map((cat, i) => (
              <li
                key={cat.id}
                draggable={!busy}
                onDragStart={(e) => { setDragging(i); e.dataTransfer.effectAllowed = "move"; }}
                onDragOver={(e) => { if (dragging !== null) e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); if (dragging !== null) move(dragging, i); setDragging(null); }}
                onDragEnd={() => setDragging(null)}
                className={`py-2 flex items-center gap-3 ${dragging === i ? "opacity-50" : ""}`}
              >
                <Icon name="drag_indicator" size={20} className="text-on-surface-variant cursor-grab" />
                <span className="text-sm text-on-surface w-6 text-right">{i + 1}.</span>
                <span className="flex-grow text-on-surface">{cat.name}</span>
                <button
                  type="button"
                  ref={(el) => { buttons.current.set(`${cat.id}:up`, el); }}
                  onClick={() => move(i, i - 1, "up")}
                  disabled={busy || i === 0}
                  aria-label={`Move ${cat.name} up`}
                  className="p-2 rounded-full text-on-surface-variant hover:text-primary disabled:opacity-40"
                >
                  <Icon name="arrow_upward" size={18} />
                </button>
                <button
                  type="button"
                  ref={(el) => { buttons.current.set(`${cat.id}:down`, el); }}
                  onClick={() => move(i, i + 1, "down")}
                  disabled={busy || i === categories.length - 1}
                  aria-label={`Move ${cat.name} down`}
                  className="p-2 rounded-full text-on-surface-variant hover:text-primary disabled:opacity-40"
                >
                  <Icon name="arrow_downward" size={18} />
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
