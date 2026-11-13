import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import {
  AMOUNT_HINT, centsToInput, committedLabel, formatCents, formatDay, formatInstantDay, parseDollars,
  safeHttpUrl,
} from "./money";
import { venueRename } from "./expenses";
import { PERCENT_HINT, parsePercent, percentOf, percentText, tipBase, tipPaymentsGap, tipsMove } from "./tips";
import { costBox, expenseCost, wouldGoOver } from "./forecast";
import { FoldBody, SECTION_SCROLL, SectionHeading, sectionId, tapArea, useFolds } from "./sections";
import { Bar, Chip, TargetChip, targetTone } from "./status";
import { focusFirstField, useAddForm, useReportDirty } from "./addForms";
import { FormError, useFormError } from "./formError";
import type {
  Category, ContractStatus, Contribution, Cost, ExpenseStatus, Payer, Payment, Run, Totals, VendorRef,
} from "./types";

export type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;

// On a phone (below the sm breakpoint) fields take the full width and every control is
// at least 44px tall, so nothing runs off the screen and taps land (B78). From sm up the
// layout is as before.
const inputBase =
  "bg-surface-container-low border border-outline-variant/40 rounded-full px-4 py-2 text-sm text-on-surface focus:border-primary focus:outline-none max-w-full min-h-11 sm:min-h-0";
export const inputClass = `${inputBase} w-full sm:w-auto`;
/** The label-over-box wrapper every form field uses. */
export const fieldClass = "flex flex-col gap-1 w-full sm:w-auto min-w-0";
export const primaryButton =
  "bg-primary text-on-primary rounded-full px-5 py-2 font-button-text text-sm disabled:opacity-60 min-h-11 sm:min-h-0";
export const linkButton =
  `text-sm text-on-surface-variant hover:text-primary-text underline-offset-4 hover:underline disabled:opacity-60 ${tapArea}`;
export const dangerLink =
  `text-sm text-on-surface-variant hover:text-error underline-offset-4 hover:underline disabled:opacity-60 ${tapArea}`;

export const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

/** A labelled dollar box. */
export function MoneyInput({
  id, label, value, onChange, placeholder = "0.00", required = false,
}: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean;
}) {
  return (
    <span className={fieldClass}>
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <span className="relative">
        <span aria-hidden className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-on-surface-variant">$</span>
        <input
          id={id}
          inputMode="decimal"
          autoComplete="off"
          required={required}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`${inputBase} pl-7 w-full sm:w-36`}
        />
      </span>
    </span>
  );
}

export function TextInput({
  id, label, value, onChange, placeholder, required = true, wide = false,
}: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean; wide?: boolean;
}) {
  return (
    <span className={`${fieldClass} ${wide ? "flex-grow sm:min-w-[12rem]" : ""}`}>
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <input
        id={id}
        autoComplete="off"
        required={required}
        maxLength={120}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </span>
  );
}

/** Reads an amount box; reports a plain-language error instead of guessing. */
export function amountOrError(text: string, setError: (e: string | null) => void): number | null | undefined {
  const cents = parseDollars(text);
  if (cents === undefined) setError(AMOUNT_HINT);
  return cents;
}

function Stat({ label, cents, tone, note }: { label: string; cents: number | null; tone?: "error"; note?: string }) {
  return (
    <div>
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p className={`font-button-text ${tone === "error" ? "text-error" : "text-on-surface"}`}>
        {cents === null ? "Not set" : formatCents(cents)}
      </p>
      {note && <p className="text-[11px] text-on-surface-variant">{note}</p>}
    </div>
  );
}

/** "Overpaid by $200" when more was paid than agreed, for a note under "Still to pay". */
export function overpaidNote(overpaidCents: number): string | undefined {
  return overpaidCents > 0 ? `Overpaid by ${formatCents(overpaidCents)}` : undefined;
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function Confirm({
  text, onYes, onNo, busy, yesLabel = "Yes, remove",
}: { text: ReactNode; onYes: () => void; onNo: () => void; busy: boolean; yesLabel?: string }) {
  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <span>{text}</span>
      <button type="button" disabled={busy} onClick={onYes} className={`text-error font-bold underline-offset-4 hover:underline ${tapArea}`}>
        {yesLabel}
      </button>
      <button type="button" disabled={busy} onClick={onNo} className={linkButton}>Cancel</button>
    </span>
  );
}

// ---- Category -----------------------------------------------------------------------

/** What a new or edited expense is measured against, for the "would go over" note. */
export type Limits = { target: number | null; committed: number; total: number | null; totalCommitted: number };

/** A category's limits: its target and what's on it, and the couple's total. */
export function limitsFor(category: Category, totals: Totals): Limits {
  return {
    target: category.planned_cents, committed: category.committed_cents,
    total: totals.total_cents, totalCommitted: totals.committed_cents,
  };
}

/** Asks a category to open and scroll to one of its expenses; n changes on each ask. */
export type OpenRequest = { id: string; n: number } | null;

export function CategoryCard({
  base, category, categories, totals, vendors, payers, canEdit, run, request, busy, openRequest, onOpened,
  addRequest = null, onAddHandled,
}: {
  base: string; category: Category; categories: Category[]; totals: Totals; vendors: VendorRef[]; payers: Payer[];
  canEdit: boolean; run: Run; request: Req; busy: boolean; openRequest: OpenRequest;
  /** Called once the asked-for expense has been scrolled to, so the ask is cleared. */
  onOpened: () => void;
  /** Asks the category with this id to open its "Add expense" form (the top-level button). */
  addRequest?: OpenRequest;
  /** Called once the asked-for form is open, so the ask is cleared. */
  onAddHandled?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [planned, setPlanned] = useState(centsToInput(category.planned_cents));
  const [confirm, setConfirm] = useState(false);
  const { error, setError, clear } = useFormError();
  const [open, setOpen] = useState(category.costs.length > 0);
  const [showArchived, setShowArchived] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // The Add expense form opens only when asked for (PD-020). Each ask counts up, so an
  // ask while it's already open still moves to it (opening again wouldn't re-render).
  const adder = useAddForm(`expense:${category.id}`);
  const [addTick, setAddTick] = useState(0);
  // After a save the form closes and an "Add another" link stands in for it.
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [addedTick, setAddedTick] = useState(0);
  const addAnotherRef = useRef<HTMLButtonElement>(null);
  const addInputId = `new-cost-${category.id}`;
  const rename = venueRename(category, categories);

  const startAdding = () => {
    if (!adder.open()) return;
    setJustAdded(null);
    setOpen(true);
    setAddTick((t) => t + 1);
  };
  const toggleAdding = () => {
    if (adder.isOpen) adder.close(true);
    else startAdding();
  };
  useEffect(() => {
    if (addTick === 0 || !adder.isOpen) return;
    const input = document.getElementById(addInputId);
    if (!input) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    input.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
    input.focus({ preventScroll: true });
    // Only a new click moves focus; other re-renders don't.
  }, [addTick]);
  useEffect(() => {
    if (addedTick > 0) addAnotherRef.current?.focus();
  }, [addedTick]);
  const added = (name: string) => {
    // Another form opened while this one was saving: leave that one alone.
    if (!adder.isCurrent()) return;
    adder.closeQuietly();
    setOpen(true);
    setJustAdded(name);
    setAddedTick((t) => t + 1);
  };
  useEffect(() => {
    if (!addRequest || addRequest.id !== category.id) return;
    startAdding();
    onAddHandled?.();
    // Only a new ask (a new n) opens the form; reloads don't.
  }, [addRequest?.n]);

  const renameToVenue = async () => {
    clear();
    const ok = await run(() => request(`${base}/categories/${category.id}`, json("PATCH", { name: "Venue" })), setError);
    // The button is gone once renamed, so focus moves to the category's new name.
    if (ok) headingRef.current?.focus();
  };
  const active = category.costs.filter((c) => !c.archived);
  const archived = category.costs.filter((c) => c.archived);
  const asked = openRequest ? category.costs.find((c) => c.id === openRequest.id) : undefined;
  const focusFor = (cost: Cost) => (openRequest && asked && cost.id === openRequest.id ? openRequest.n : 0);

  // Opened from the list of all expenses: show this category's expenses (and the
  // archived ones, if that's where it is) so the expense can be scrolled to.
  const askedArchived = asked?.archived;
  useEffect(() => {
    if (!asked) return;
    setOpen(true);
    if (askedArchived) setShowArchived(true);
    // Only a new ask (a new n) opens the category again; reloads don't.
  }, [openRequest?.n]);

  const planned_cents = category.planned_cents;
  const over = category.state === "over";
  const limits = limitsFor(category, totals);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(planned, setError);
    if (cents === undefined) return;
    const ok = await run(
      () => request(`${base}/categories/${category.id}`, json("PATCH", { name, planned_cents: cents })),
      setError,
    );
    if (ok) setEditing(false);
  };

  return (
    <section className="bg-surface-container-lowest p-6 rounded-[2rem] border border-outline-variant/20 shadow-sm">
      {editing ? (
        <form onSubmit={save} onChange={clear} className="flex flex-wrap items-end gap-3 mb-4">
          <TextInput id={`cat-name-${category.id}`} label="Category" value={name} onChange={setName} wide />
          <MoneyInput id={`cat-plan-${category.id}`} label="Target" value={planned} onChange={setPlanned} />
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" disabled={busy} onClick={() => { clear(); setEditing(false); }} className={linkButton}>Cancel</button>
          <FormError error={error} />
        </form>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h3 ref={headingRef} tabIndex={-1} className="flex flex-wrap items-center gap-2 font-headline-sm text-lg text-on-surface focus:outline-none">
            {category.name}
            <TargetChip state={category.state} />
            {category.is_contingency && <Chip tone="neutral">Contingency</Chip>}
          </h3>
          {canEdit && (
            confirm ? (
              <RemoveCategory
                base={base} category={category} categories={categories} run={run} request={request} busy={busy}
                onCancel={() => setConfirm(false)}
              />
            ) : (
              <span className="flex flex-wrap items-center gap-4">
                {rename === "offer" && (
                  <button
                    type="button" disabled={busy} onClick={renameToVenue}
                    className="rounded-full border border-outline-variant/60 px-3 py-2.5 sm:py-1 text-sm text-on-surface hover:border-primary disabled:opacity-60"
                  >
                    Rename to Venue
                  </button>
                )}
                {rename === "clash" && (
                  <span className="text-xs text-on-surface-variant max-w-[22rem]">
                    You already have a category called Venue, so this one can't be renamed to it. You can move its
                    expenses there when you remove this one.
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => { clear(); setName(category.name); setPlanned(centsToInput(planned_cents)); setEditing(true); }}
                  className={linkButton}
                >
                  Edit
                </button>
                <button type="button" onClick={() => { clear(); setConfirm(true); }} className={dangerLink}>Remove</button>
              </span>
            )
          )}
        </div>
      )}
      {!editing && <FormError error={error} className="mb-3" />}

      {category.is_contingency && (
        <p className="text-sm text-on-surface-variant mb-3">
          Money kept aside for costs you didn't plan for. Change its target, or move money in or out of it.
        </p>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-3">
        <Stat label="Target" cents={planned_cents} />
        <div>
          <p className="text-xs text-on-surface-variant">Share of your total</p>
          <p className="font-button-text text-on-surface">
            {category.share_pct === null
              ? "—"
              : category.share_pct === 0 && (planned_cents ?? 0) > 0 ? "Under 1%" : `${category.share_pct}%`}
          </p>
          {category.share_pct === null && (
            <p className="text-[11px] text-on-surface-variant">
              {totals.total_cents === null ? "Set your total to see this" : "Needs a target"}
            </p>
          )}
        </div>
        <Stat label={committedLabel(category.committed_basis)} cents={category.committed_cents} tone={over ? "error" : undefined} />
        <Stat label="Paid" cents={category.paid_cents} />
        <Stat label="Still to pay" cents={category.remaining_cents} note={overpaidNote(category.overpaid_cents)} />
        {over ? (
          <Stat label="Over target by" cents={category.over_target_cents} tone="error" />
        ) : (
          <Stat label="Left of target" cents={category.target_left_cents} />
        )}
      </div>
      {planned_cents !== null && (
        <Bar
          label={`${category.name}: committed against target`}
          pct={category.used_pct ?? (category.committed_cents > 0 ? 100 : 0)}
          tone={targetTone(category.state)}
          text={category.used_pct === null
            ? `${formatCents(category.committed_cents)} of a ${formatCents(planned_cents)} target`
            : `${formatCents(category.committed_cents)} of ${formatCents(planned_cents)} (${category.used_pct}%)`}
        />
      )}
      {over && planned_cents !== null && (
        <p className="flex items-start gap-1 text-sm text-error mt-2">
          <Icon name="warning" size={16} className="mt-0.5" />
          Over target: what you've committed is {formatCents(category.over_target_cents)} more than this category's
          target. You could raise the target or move money in from another category.
        </p>
      )}
      {category.state === "near_limit" && (
        <p className="text-sm text-on-surface mt-2">
          Near the limit: {formatCents(category.target_left_cents ?? 0)} of this target is left.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mt-3">
        <button type="button" onClick={() => setOpen((o) => !o)} className={linkButton} aria-expanded={open}>
          {open ? "Hide expenses" : `Show expenses (${active.length})`}
        </button>
        {canEdit && (
          <button
            ref={adder.opener} type="button" onClick={toggleAdding} aria-expanded={adder.isOpen}
            className="inline-flex items-center gap-1 rounded-full border border-primary px-4 py-2.5 sm:py-1.5 text-sm text-primary-text hover:bg-primary hover:text-on-primary"
          >
            <Icon name="add" size={16} /> Add expense<span className="sr-only"> to {category.name}</span>
          </button>
        )}
      </div>
      {open && (
        <div className="mt-4 space-y-4">
          {active.map((cost) => (
            <CostBlock key={cost.id} base={base} cost={cost} siblings={category.costs} categoryName={category.name} limits={limits} vendors={vendors} payers={payers} canEdit={canEdit} run={run} request={request} busy={busy} focus={focusFor(cost)} onOpened={onOpened} />
          ))}
          {active.length === 0 && (
            <p className="text-sm text-on-surface-variant">No expenses yet.</p>
          )}
          {archived.length > 0 && (
            <>
              <button type="button" onClick={() => setShowArchived((o) => !o)} className={linkButton} aria-expanded={showArchived}>
                {showArchived ? "Hide archived" : `Show archived (${archived.length}), not counted in totals`}
              </button>
              {showArchived && archived.map((cost) => (
                <CostBlock key={cost.id} base={base} cost={cost} siblings={category.costs} categoryName={category.name} limits={limits} vendors={vendors} payers={payers} canEdit={canEdit} run={run} request={request} busy={busy} focus={focusFor(cost)} onOpened={onOpened} />
              ))}
            </>
          )}
        </div>
      )}
      {/* Outside the expenses fold, so hiding the expenses never loses a half-typed form. */}
      {canEdit && adder.isOpen && (
        <div className="mt-4 border-t border-outline-variant/20 pt-4">
          <AddCostForm
            base={base} categoryId={category.id} categoryName={category.name} limits={limits} vendors={vendors} payers={payers}
            run={run} request={request} busy={busy}
            suggestions={category.suggestions} taken={active.map((c) => c.vendor_name)}
            onAdded={added} onCancel={() => adder.close()}
          />
        </div>
      )}
      {canEdit && !adder.isOpen && justAdded !== null && (
        <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span id={`added-${category.id}`} role="status" className="text-on-surface">Added {justAdded}.</span>
          <button
            ref={addAnotherRef} type="button" onClick={startAdding} aria-describedby={`added-${category.id}`}
            className={`${linkButton} text-primary-text font-bold`}
          >
            Add another<span className="sr-only"> expense to {category.name}</span>
          </button>
        </p>
      )}
    </section>
  );
}

/**
 * Removing a category. Its expenses and payments are money records, so they're never
 * removed with it: the couple choose another category to move them to first (the API
 * refuses otherwise). An empty category just asks for a yes.
 */
function RemoveCategory({
  base, category, categories, run, request, busy, onCancel,
}: {
  base: string; category: Category; categories: Category[]; run: Run; request: Req; busy: boolean;
  onCancel: () => void;
}) {
  const others = categories.filter((c) => c.id !== category.id);
  const [picked, setTarget] = useState(others[0]?.id ?? "");
  // The list can reload while this is open; never send a category that's gone.
  const target = others.some((c) => c.id === picked) ? picked : others[0]?.id ?? "";
  const count = category.costs.length;
  const kept = "Contributions towards it are kept, towards the whole budget.";
  const { error, setError, clear } = useFormError();
  const remove = (moveTo?: string) => {
    clear();
    run(() => request(
      `${base}/categories/${category.id}${moveTo ? `?move_to=${encodeURIComponent(moveTo)}` : ""}`,
      json("DELETE"),
    ), setError);
  };

  if (count === 0) {
    return (
      <>
        <Confirm busy={busy} text={`Remove ${category.name}? ${kept}`} onYes={() => remove()} onNo={onCancel} />
        <FormError error={error} />
      </>
    );
  }
  const payments = category.costs.reduce((n, c) => n + c.payments.length, 0);
  const paid = category.costs.reduce((n, c) => n + c.payments.filter((p) => p.paid).length, 0);
  const what = `${plural(count, "expense")}` +
    (payments ? ` with ${plural(payments, "payment")}${paid ? ` (${paid} ticked paid)` : ""}` : "");
  if (others.length === 0) {
    return (
      <span role="alert" className="flex flex-wrap items-center gap-2 text-sm w-full">
        <span>
          {category.name} has {what}. To remove it, first add another category to move them to, or remove the
          expenses one by one.
        </span>
        <button type="button" onClick={onCancel} className={linkButton}>OK</button>
      </span>
    );
  }
  const selectId = `move-to-${category.id}`;
  return (
    <span className="flex flex-wrap items-end gap-3 text-sm w-full">
      <span className="w-full">
        {category.name} has {what}. They aren't removed: choose where they move, with their payments and ticks. {kept}
      </span>
      <span className={fieldClass}>
        <label htmlFor={selectId} className="text-xs text-on-surface-variant">Move them to</label>
        <select id={selectId} value={target} onChange={(e) => { clear(); setTarget(e.target.value); }} className={inputClass}>
          {others.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </span>
      <button type="button" disabled={busy || !target} onClick={() => remove(target)}
        className={`text-error font-bold underline-offset-4 hover:underline pb-2 ${tapArea}`}>
        Move them and remove {category.name}
      </button>
      <button type="button" disabled={busy} onClick={onCancel} className={`${linkButton} pb-2`}>Cancel</button>
      <FormError error={error} />
    </span>
  );
}

export function AddCategoryForm({ base, run, request, busy }: { base: string; run: Run; request: Req; busy: boolean }) {
  const [name, setName] = useState("");
  const [planned, setPlanned] = useState("");
  const { error, setError, clear } = useFormError();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(planned, setError);
    if (cents === undefined) return;
    const ok = await run(() => request(`${base}/categories`, json("POST", { name, planned_cents: cents })), setError);
    if (ok) { setName(""); setPlanned(""); }
  };
  return (
    <form onSubmit={submit} onChange={clear} className="flex flex-wrap items-end gap-3">
      <TextInput id="new-cat-name" label="Category name" value={name} onChange={setName} placeholder="For example, Venue" wide />
      <MoneyInput id="new-cat-plan" label="Target (optional)" value={planned} onChange={setPlanned} />
      <button type="submit" disabled={busy} className={primaryButton}>Add category</button>
      <FormError error={error} />
    </form>
  );
}

// ---- Expense (vendor cost) ----------------------------------------------------------

// Colour is never the only cue: each status carries its word and an icon.
const STATUS_STYLE: Record<ExpenseStatus, { label: string; icon: string; badge: string }> = {
  unpaid: { label: "Unpaid", icon: "radio_button_unchecked", badge: "bg-status-looking text-status-looking-foreground" },
  partly_paid: { label: "Partly paid", icon: "timelapse", badge: "bg-status-contacted text-status-contacted-foreground" },
  paid: { label: "Paid", icon: "check_circle", badge: "bg-status-booked text-status-booked-foreground" },
  overdue: { label: "Overdue", icon: "warning", badge: "bg-status-not-selected text-status-not-selected-foreground" },
};

export function StatusBadge({ status }: { status: ExpenseStatus }) {
  const s = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${s.badge}`}>
      <Icon name={s.icon} size={14} /> {s.label}
    </span>
  );
}

const CONTRACT_LABEL: Record<ContractStatus, string> = {
  none: "No contract yet",
  sent: "Contract sent",
  signed: "Contract signed",
};

/** Suggestions only; the couple can type any method. */
const METHOD_SUGGESTIONS = ["Check", "Credit card", "Debit card", "Bank transfer", "Cash", "Zelle", "Venmo"];

export function MethodSuggestions() {
  return (
    <datalist id="budget-method-suggestions">
      {METHOD_SUGGESTIONS.map((m) => <option key={m} value={m} />)}
    </datalist>
  );
}

/** A pasted link, opened in a new tab. Not shown at all unless it's a web link. */
function OpenLink({ url, label }: { url: string | null; label: string }) {
  const href = safeHttpUrl(url);
  if (!href) return null;
  // The site's name is shown, so nobody clicks a link without seeing where it goes.
  const host = new URL(href).hostname;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary-text underline-offset-4 hover:underline">
      {label} ({host}) <Icon name="open_in_new" size={14} /> <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

function LinkInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <span className={`${fieldClass} flex-grow sm:min-w-[14rem]`}>
      <label htmlFor={id} className="text-xs text-on-surface-variant">Link (optional), for example to the file in your Google Drive</label>
      <input
        id={id}
        type="url"
        inputMode="url"
        autoComplete="off"
        placeholder="https://"
        maxLength={2000}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </span>
  );
}

function NotesInput({
  id, value, onChange, label = "Notes (optional)",
}: { id: string; value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <span className="flex flex-col gap-1 w-full">
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <textarea
        id={id}
        rows={2}
        maxLength={2000}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-surface-container-low border border-outline-variant/40 rounded-2xl px-4 py-2 text-sm text-on-surface focus:border-primary focus:outline-none"
      />
    </span>
  );
}

function SelectInput({ id, label, value, onChange, children }: { id: string; label: string; value: string; onChange: (v: string) => void; children: ReactNode }) {
  return (
    <span className={fieldClass}>
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>
        {children}
      </select>
    </span>
  );
}

const SECTION_LABEL: Record<string, string> = {
  venue: "Venue",
  food_drink: "Food & drink",
  flowers_decoration: "Flowers & decoration",
  photo_video: "Photographer & videographer",
  entertainment: "Entertainment",
  hair_makeup: "Hair & makeup",
  transportation: "Transportation",
};

function VendorSelect({ id, vendors, value, onChange }: { id: string; vendors: VendorRef[]; value: string; onChange: (v: string) => void }) {
  return (
    <SelectInput id={id} label="Vendor on your Vendors page (optional)" value={value} onChange={onChange}>
      <option value="">Not linked</option>
      {vendors.map((v) => (
        <option key={v.id} value={v.id}>{v.name} ({SECTION_LABEL[v.section] ?? v.section})</option>
      ))}
    </SelectInput>
  );
}

/** "Actual cost $12,000", "Estimate or quote $11,000" or "No cost recorded". */
function costLine(cost: Cost): string {
  if (cost.tip_state) return tipWorking(cost);
  if (cost.final_cents !== null) return `Actual cost ${formatCents(cost.final_cents)}`;
  const box = costBox(cost.quoted_cents, cost.estimated_cents);
  if (box.cents !== null) return `Estimate or quote ${formatCents(box.cents)}`;
  if (cost.scheduled_cents > 0) return `Payments so far ${formatCents(cost.scheduled_cents)}`;
  return "No cost recorded";
}

/** The "Who paid" dropdown, from the wedding's "People who pay" list. Blank is allowed. */
function PayerSelect({
  id, payers, value, onChange, label = "Who paid (optional)",
}: { id: string; payers: Payer[]; value: string; onChange: (v: string) => void; label?: string }) {
  // A payer removed since the form opened reads as "Not set", never as a stale id.
  const shown = payers.some((p) => p.id === value) ? value : "";
  return (
    <SelectInput id={id} label={label} value={shown} onChange={onChange}>
      <option value="">Not set</option>
      {payers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
    </SelectInput>
  );
}

/** A payer id that's still on the list, or null. */
function payerOrNull(payers: Payer[], id: string): string | null {
  return payers.some((p) => p.id === id) ? id : null;
}

/** Under a payer dropdown while the list is empty: where to add the names. */
function NoPayersHint() {
  const folds = useFolds();
  const go = () => {
    const el = document.getElementById(PAYERS_INPUT_ID);
    if (!el) return;
    if (folds) folds.jumpTo("payers", el);
    else el.scrollIntoView({ block: "center" });
    window.requestAnimationFrame(() => el.focus({ preventScroll: true }));
  };
  return (
    <p className="w-full text-xs text-on-surface-variant">
      To choose who paid, first{" "}
      <button type="button" onClick={go} className={`${linkButton} text-xs text-primary-text`}>
        add the people who pay
      </button>
      .
    </p>
  );
}

/** The name box on the "People who pay" list, which other forms point to. */
export const PAYERS_INPUT_ID = "new-payer-name";

function CostBlock({
  base, cost, siblings, categoryName, limits, vendors, payers, canEdit, run, request, busy, focus, onOpened,
}: {
  base: string; cost: Cost;
  /** Every expense in its category, where its tips are too. */
  siblings: Cost[]; categoryName: string;
  limits: Limits; vendors: VendorRef[]; payers: Payer[]; canEdit: boolean; run: Run; request: Req; busy: boolean;
  /** Non-zero when the list of all expenses asked to open this one; a new number each time. */
  focus: number;
  onOpened: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [confirmCopy, setConfirmCopy] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  // Refusals of this expense's own buttons (archive, remove, copy); its forms have their own.
  const { error, setError, clear } = useFormError();
  const tipAdder = useAddForm(`tip:${cost.id}`);
  const payAdder = useAddForm(`payment:${cost.id}`);
  const tipBox = useRef<HTMLDivElement>(null);
  const payBox = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const isTip = cost.tip_state !== null;
  const tips = siblings.filter((c) => cost.tip_ids.includes(c.id));
  const activeTips = tips.filter((c) => !c.archived);
  const linked = isTip ? siblings.find((c) => c.id === cost.tip_for_cost_id) : undefined;
  const act = (fn: () => Promise<unknown>) => { clear(); return run(fn, setError); };
  const archive = (choice?: "remove" | "keep") =>
    act(() => request(`${base}/costs/${cost.id}${choice ? `?tips=${choice}` : ""}`, json("PATCH", { archived: !cost.archived })));
  const remove = (choice?: "remove" | "keep") =>
    act(() => request(`${base}/costs/${cost.id}${choice ? `?tips=${choice}` : ""}`, json("DELETE")));
  // Opening or cancelling one of this expense's questions clears an old refusal.
  const ask = (open: (v: boolean) => void) => () => { clear(); open(true); };
  const cancel = (close: (v: boolean) => void) => () => { clear(); close(false); };

  // Focus moves into an add form when it opens (its button gets it back on close).
  useEffect(() => { if (tipAdder.isOpen) focusFirstField(tipBox.current); }, [tipAdder.isOpen]);
  useEffect(() => { if (payAdder.isOpen) focusFirstField(payBox.current); }, [payAdder.isOpen]);

  useEffect(() => {
    if (!focus || !box.current) return;
    box.current.scrollIntoView({ block: "center", behavior: "smooth" });
    box.current.focus({ preventScroll: true });
    onOpened();
  }, [focus]);

  const counted = cost.payments.length > 0 || cost.committed_cents > 0;
  return (
    <div
      ref={box}
      id={`expense-${cost.id}`}
      tabIndex={-1}
      aria-label={`Expense: ${cost.vendor_name}`}
      className={`border rounded-[1.5rem] p-4 scroll-mt-24 focus:outline-none focus:ring-2 focus:ring-primary/40 ${cost.archived ? "border-dashed border-outline-variant/40 bg-surface-container-low/40" : "border-outline-variant/30"}`}
    >
      {editing ? (
        isTip ? (
          <TipEditForm base={base} cost={cost} linked={linked} limits={limits} run={run} request={request} busy={busy} onDone={() => setEditing(false)} />
        ) : (
          <CostEditForm base={base} cost={cost} tips={tips} limits={limits} vendors={vendors} run={run} request={request} busy={busy} onDone={() => setEditing(false)} />
        )
      ) : (
        <div className="mb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex flex-wrap items-center gap-2 text-on-surface">
              <span className="font-button-text">{cost.vendor_name}</span>
              {isTip && <TipChip />}
              {counted && <StatusBadge status={cost.status} />}
              {cost.archived && (
                <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold bg-surface-container-high text-on-surface-variant">
                  <Icon name="archive" size={14} /> Archived, not in totals
                </span>
              )}
            </p>
            {canEdit && (confirm ? (
              tips.length > 0 ? (
                <TipsQuestion cost={cost} tips={tips} archiving={false} busy={busy} onChoose={remove} onNo={cancel(setConfirm)} />
              ) : (
                <Confirm busy={busy} text={`Remove ${cost.vendor_name} and its payments?`}
                  onYes={() => remove()}
                  onNo={cancel(setConfirm)} />
              )
            ) : confirmArchive ? (
              <TipsQuestion
                cost={cost} tips={activeTips} archiving busy={busy}
                onChoose={async (choice) => { if (await archive(choice)) setConfirmArchive(false); }}
                onNo={cancel(setConfirmArchive)}
              />
            ) : confirmCopy ? (
              <Confirm
                busy={busy}
                yesLabel="Yes, make a copy"
                text={isTip
                  ? `Make a copy of ${cost.vendor_name}? It's another tip for ${cost.tip_for_name ?? "the same expense"}, with the same percentage or amount and notes. It starts with no payments and counts in your totals straight away.`
                  : `Make a copy of ${cost.vendor_name}? It copies the costs, payment method, notes, link and vendor. It starts with no payments and no contract, and counts in your totals straight away.`}
                onYes={async () => {
                  const ok = await act(() => request(`${base}/costs/${cost.id}/duplicate`, json("POST")));
                  if (ok) setConfirmCopy(false);
                }}
                onNo={cancel(setConfirmCopy)}
              />
            ) : (
              <span className="flex flex-wrap gap-4">
                <button type="button" onClick={ask(setEditing)} className={linkButton}>Edit</button>
                <button type="button" onClick={ask(setConfirmCopy)} className={linkButton}>Duplicate</button>
                {!isTip && !cost.archived && (
                  <button
                    ref={tipAdder.opener} type="button" onClick={() => { clear(); tipAdder.toggle(); }} aria-expanded={tipAdder.isOpen}
                    className={linkButton}
                  >
                    Add tip<span className="sr-only"> for {cost.vendor_name}</span>
                  </button>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => (!cost.archived && activeTips.length > 0 ? ask(setConfirmArchive)() : archive())}
                  className={linkButton}
                >
                  {cost.archived ? "Restore" : "Archive"}
                </button>
                <button type="button" onClick={ask(setConfirm)} className={dangerLink}>Remove</button>
              </span>
            ))}
          </div>
          {isTip && (
            <p className="text-xs text-on-surface-variant mt-1">
              {cost.tip_for_name ? `Tip for ${cost.tip_for_name}` : "Tip"}
              {cost.tip_state === "following" && `, changes with ${cost.tip_for_name ? `${cost.tip_for_name}'s` : "its"} cost`}
            </p>
          )}
          <p className="text-on-surface-variant text-sm mt-1">
            {costLine(cost)}
            {" · "}Paid {formatCents(cost.paid_cents)}
            {" · "}Still to pay {formatCents(cost.remaining_cents)}
            {cost.overpaid_cents > 0 && <>{" · "}{overpaidNote(cost.overpaid_cents)}</>}
          </p>
          {cost.tip_state === "frozen" && (
            <p className="flex items-start gap-1 text-sm text-on-surface mt-1">
              <Icon name="lock" size={16} className="mt-0.5" />
              A payment on this tip is ticked paid, so it stays at {formatCents(cost.committed_cents)} even if{" "}
              {cost.tip_for_name ?? "the expense"}'s cost changes. Untick it to have the tip follow the cost again.
            </p>
          )}
          {cost.tip_state === "waiting" && (
            <p className="text-sm text-on-surface mt-1">
              Waiting for a cost: once {cost.tip_for_name ?? "the expense"} has an estimate, quote or actual cost, this
              tip works itself out. Until then it counts as $0.
            </p>
          )}
          {tips.length > 0 && (
            <p className="text-xs text-on-surface-variant mt-1">
              {tips.length === 1 ? "Has a tip" : `Has ${tips.length} tips`}:{" "}
              {tips.map((t) => `${t.vendor_name} ${formatCents(t.committed_cents)}${t.archived ? " (archived, not counted)" : ""}`).join(", ")}
            </p>
          )}
          {canEdit && !cost.archived && tips.length > activeTips.length && (
            <button
              type="button" disabled={busy} className={`${linkButton} mt-1`}
              onClick={() => act(async () => {
                for (const t of tips.filter((x) => x.archived)) {
                  await request(`${base}/costs/${t.id}`, json("PATCH", { archived: false }));
                }
              })}
            >
              Restore its archived {tips.length - activeTips.length === 1 ? "tip" : "tips"} too
            </button>
          )}
          {cost.refundable_cents > 0 && (
            <p className="text-on-surface-variant text-sm">
              Refundable deposit {formatCents(cost.refundable_cents)}, not part of the cost
              {cost.refundable_paid_cents > 0 ? ` (${formatCents(cost.refundable_paid_cents)} paid, to come back)` : ""}
            </p>
          )}
          <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-on-surface-variant mt-1">
            {!isTip && <span>{CONTRACT_LABEL[cost.contract_status]}</span>}
            {cost.payment_method && <span>Paying by {cost.payment_method}</span>}
            {cost.vendor && <span>Linked to {cost.vendor.name} on your Vendors page</span>}
            <OpenLink url={cost.link_url} label="Open link" />
          </p>
          {cost.notes && <p className="text-sm text-on-surface mt-2 whitespace-pre-line">{cost.notes}</p>}
          {isTip && <TipPaymentsNote cost={cost} />}
          {!isTip && cost.over_scheduled_cents > 0 && (
            <p className="flex items-start gap-1 text-sm text-error mt-2">
              <Icon name="warning" size={16} className="mt-0.5" />
              The payments you've added come to {formatCents(cost.over_scheduled_cents)} more than the cost
              ({formatCents(cost.committed_cents)}). Check the amounts, or update the cost.
            </p>
          )}
          <FormError error={error} className="mt-2" />
        </div>
      )}

      {canEdit && tipAdder.isOpen && !isTip && !cost.archived && (
        <div ref={tipBox} className="border-t border-outline-variant/20 pt-3 mb-3">
          <AddTipForm
            base={base} targets={[{ cost, categoryName, limits }]} fixedId={cost.id} payers={payers}
            run={run} request={request} busy={busy} idPrefix={`tip-${cost.id}`} formKey={`tip:${cost.id}`}
            onDone={() => tipAdder.close()}
          />
        </div>
      )}

      {cost.payments.length > 0 && (
        <ul className="divide-y divide-outline-variant/20 mb-2">
          {cost.payments.map((p) => (
            <PaymentRow key={p.id} base={base} payment={p} cost={cost} payers={payers} canEdit={canEdit} run={run} request={request} busy={busy} />
          ))}
        </ul>
      )}
      {canEdit && !cost.archived && (
        <>
          <button
            ref={payAdder.opener} type="button" onClick={() => { clear(); payAdder.toggle(); }} aria-expanded={payAdder.isOpen}
            className="mt-1 inline-flex items-center gap-1 rounded-full border border-outline-variant/60 px-4 py-3 sm:py-1 text-sm text-on-surface hover:border-primary hover:text-primary-text"
          >
            <Icon name="add" size={16} /> Add payment<span className="sr-only"> for {cost.vendor_name}</span>
          </button>
          {payAdder.isOpen && (
            <div ref={payBox}>
              <AddPaymentForm
                base={base} cost={cost} payers={payers} run={run} request={request} busy={busy} onDone={() => payAdder.close()}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---- Tips (PD-017) ------------------------------------------------------------------

function TipChip() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold bg-surface-container-high text-on-surface">
      <Icon name="volunteer_activism" size={14} /> Tip
    </span>
  );
}

/**
 * A tip whose payments don't add up to it (PD-018): "Payments come to $1,600; the tip
 * is now $1,800." A percentage tip's one unpaid payment for the whole tip changes with
 * it; anything else (a part payment, several payments) stays as typed, so this says so.
 */
function TipPaymentsNote({ cost }: { cost: Cost }) {
  const gap = tipPaymentsGap(cost);
  if (!gap) return null;
  const waiting = cost.tip_state === "waiting";
  const tipText = waiting
    ? `the tip counts as $0 until ${cost.tip_for_name ?? "its expense"} has a cost`
    : `the tip is ${cost.tip_state === "following" ? "now " : ""}${formatCents(gap.tipCents)}`;
  const fix = gap.paymentsCents < gap.tipCents
    ? " Add a payment for the rest, or change a payment's amount to match."
    : " Change a payment's amount to match.";
  return (
    <p className="flex items-start gap-1 text-sm text-on-surface mt-2">
      <Icon name="error" size={16} className="mt-0.5 text-status-todo" />
      <span>Payments come to {formatCents(gap.paymentsCents)}; {tipText}.{waiting ? "" : fix}</span>
    </p>
  );
}

/** "20% of $8,000 = $1,600", or what a tip's amount is doing instead. */
export function tipWorking(cost: Cost): string {
  const pct = `${percentText(cost.tip_basis_points)}%`;
  switch (cost.tip_state) {
    case "following":
      return `${pct} of ${formatCents(cost.tip_base_cents ?? 0)} = ${formatCents(cost.committed_cents)}`;
    case "frozen":
      return `${pct}, fixed at ${formatCents(cost.committed_cents)}`;
    case "waiting":
      return `${pct} of a cost not entered yet = $0 for now`;
    default:
      return `Tip of ${formatCents(cost.committed_cents)}`;
  }
}

/**
 * Removing or archiving an expense that has tips (PD-017 call c): remove the tips too,
 * or keep them as plain lines. Says how many payments would go, so none is deleted
 * without the couple seeing it.
 */
function TipsQuestion({
  cost, tips, archiving, busy, onChoose, onNo,
}: {
  cost: Cost; tips: Cost[]; archiving: boolean; busy: boolean;
  onChoose: (choice: "remove" | "keep") => void; onNo: () => void;
}) {
  const one = tips.length === 1;
  const them = one ? "it" : "them";
  const payments = tips.reduce((n, t) => n + t.payments.length, 0);
  const paid = tips.reduce((n, t) => n + t.payments.filter((p) => p.paid).length, 0);
  const names = tips.map((t) => t.vendor_name).join(", ");
  const pays = payments ? ` with ${plural(payments, "payment")}${paid ? ` (${paid} ticked paid)` : ""}` : "";
  const text = archiving
    ? `${cost.vendor_name} has ${plural(tips.length, "tip")} (${names}). Archive ${them} too, or keep ${them} in your totals as ${one ? "a plain line" : "plain lines"}?`
    : `Remove ${cost.vendor_name} and its payments? It has ${plural(tips.length, "tip")} (${names})${pays}.`;
  const btn = `font-bold underline-offset-4 hover:underline text-left ${tapArea}`;
  return (
    <span role="group" aria-label={archiving ? "Archive with tips" : "Remove with tips"} className="flex flex-wrap items-center gap-x-4 gap-y-3 text-sm w-full">
      <span className="w-full">{text}</span>
      <button type="button" disabled={busy} onClick={() => onChoose("remove")} className={`${btn} ${archiving ? "text-on-surface" : "text-error"}`}>
        {archiving
          ? `Archive ${one ? "the tip" : "the tips"} too`
          : `Remove ${one ? "the tip" : "the tips"}${payments ? ` and ${plural(payments, "payment")}` : ""} too`}
      </button>
      <button type="button" disabled={busy} onClick={() => onChoose("keep")} className={`${btn} text-primary-text`}>
        Keep {one ? "the tip as a plain line" : "the tips as plain lines"}
      </button>
      <button type="button" disabled={busy} onClick={onNo} className={linkButton}>Cancel</button>
      <span className="w-full text-xs text-on-surface-variant">
        A kept tip stays in your totals at the amount it is now, with its payments, but is no longer linked
        {archiving ? ` to ${cost.vendor_name}` : ""} or worked out from a percentage.
      </span>
    </span>
  );
}

type TipMode = "percent" | "amount";

/** "A percentage" or "An amount in dollars": one or the other, never both. */
function TipModePicker({ name, mode, onChange }: { name: string; mode: TipMode; onChange: (m: TipMode) => void }) {
  const option = (value: TipMode, label: string) => (
    <label className="flex items-center gap-2 text-sm cursor-pointer min-h-11 sm:min-h-0">
      <input type="radio" name={name} value={value} checked={mode === value} onChange={() => onChange(value)} className="h-4 w-4 accent-primary" />
      {label}
    </label>
  );
  return (
    <fieldset className="w-full">
      <legend className="text-xs text-on-surface-variant mb-1">Tip as</legend>
      <span className="flex flex-wrap gap-x-6">
        {option("percent", "A percentage")}
        {option("amount", "An amount in dollars")}
      </span>
    </fieldset>
  );
}

function PercentInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <span className={fieldClass}>
      <label htmlFor={id} className="text-xs text-on-surface-variant">Percentage</label>
      <span className="relative">
        <input
          id={id} inputMode="decimal" autoComplete="off" required placeholder="20" value={value}
          onChange={(e) => onChange(e.target.value)} className={`${inputBase} pr-8 w-full sm:w-28`}
        />
        <span aria-hidden className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-on-surface-variant">%</span>
      </span>
    </span>
  );
}

/** What a typed tip comes to, shown before saving. */
function tipPreview(target: Cost | undefined, mode: TipMode, percent: string, amount: string): string | null {
  if (!target) return null;
  if (mode === "amount") {
    const cents = parseDollars(amount);
    return typeof cents === "number" && cents > 0 ? `A tip of ${formatCents(cents)} for ${target.vendor_name}.` : null;
  }
  const bp = parsePercent(percent);
  if (typeof bp !== "number") return null;
  const base = tipBase(target);
  if (base === null) {
    return `${target.vendor_name} has no cost yet, so this tip will wait for one and count as $0 until then.`;
  }
  return `${percentText(bp)}% of ${formatCents(base)} = ${formatCents(percentOf(base, bp))}`;
}

/**
 * What a typed tip comes to in whole cents, for the "would go over" note: the amount,
 * or the percentage of base (0 while there's no cost); null while the box isn't valid.
 */
function typedTipCents(mode: TipMode, percent: string, amount: string, base: number | null): number | null {
  if (mode === "amount") {
    const cents = parseDollars(amount);
    return typeof cents === "number" ? cents : null;
  }
  const bp = parsePercent(percent);
  if (typeof bp !== "number") return null;
  return base === null ? 0 : percentOf(base, bp);
}

/** Reads the percentage or amount box; null (with an error set) if it isn't valid. */
function tipValue(mode: TipMode, percent: string, amount: string, setError: (e: string | null) => void) {
  if (mode === "percent") {
    const bp = parsePercent(percent);
    if (typeof bp !== "number") { setError(PERCENT_HINT); return null; }
    return { percent_basis_points: bp };
  }
  const cents = amountOrError(amount, setError);
  if (cents === undefined) return null;
  if (!cents) { setError("Please enter how much the tip is."); return null; }
  return { amount_cents: cents };
}

/**
 * Adding a tip (PD-017): which expense it's for (unless already chosen), a percentage
 * or a dollar amount, and optionally a due date, who pays and comments, as the Add
 * expense form has. It saves as its own line, "Tip: <expense>", in the same category.
 * A due date or who pays adds one payment for the tip, not ticked as paid (rule 4).
 */
export function AddTipForm({
  base, targets, fixedId, payers, run, request, busy, idPrefix, formKey, onDone,
}: {
  base: string;
  /** The expenses a tip can be for, with their category's name and limits. */
  targets: { cost: Cost; categoryName: string; limits: Limits }[];
  /** Set when the form opens from one expense, so it doesn't ask which. */
  fixedId?: string;
  payers: Payer[]; run: Run; request: Req; busy: boolean; idPrefix: string;
  /** Which add form this is on the screen, for asking before typed input is lost. */
  formKey: string;
  onDone: () => void;
}) {
  const [picked, setPicked] = useState("");
  const [mode, setMode] = useState<TipMode>("percent");
  const [percent, setPercent] = useState("");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [payer, setPayer] = useState("");
  const [notes, setNotes] = useState("");
  const { error, setError, clear } = useFormError();
  useReportDirty(formKey, !!(picked || percent || amount || due || payer || notes) || mode !== "percent");
  // The list can reload while this is open; never send an expense that's gone.
  const targetId = fixedId ?? (targets.some((t) => t.cost.id === picked) ? picked : targets[0]?.cost.id ?? "");
  const picks = targets.find((t) => t.cost.id === targetId);
  const target = picks?.cost;
  const preview = tipPreview(target, mode, percent, amount);
  const typed = target ? typedTipCents(mode, percent, amount, tipBase(target)) : null;
  const groups = targets.reduce<{ name: string; items: Cost[] }[]>((acc, t) => {
    const last = acc[acc.length - 1];
    if (last && last.name === t.categoryName) last.items.push(t.cost);
    else acc.push({ name: t.categoryName, items: [t.cost] });
    return acc;
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!target) { setError("Choose the expense the tip is for."); return; }
    const value = tipValue(mode, percent, amount, setError);
    if (!value) return;
    const payerId = payerOrNull(payers, payer);
    if (mode === "percent" && tipBase(target) === null && (due || payerId)) {
      setError(`${target.vendor_name} has no cost yet, so the tip is $0 for now. Leave the due date and who pays empty, or add its cost first.`);
      return;
    }
    const ok = await run(
      () => request(`${base}/costs/${target.id}/tips`, json("POST", {
        ...value, due_on: due || null, payer_id: payerId, notes: notes || null,
      })),
      setError,
    );
    if (ok) onDone();
  };

  if (targets.length === 0) {
    return (
      <p className="text-sm text-on-surface-variant">
        A tip goes with an expense, like the caterer. Add the expense first, then add its tip.
      </p>
    );
  }

  return (
    <form onSubmit={submit} onChange={clear} className="flex flex-wrap items-end gap-3" aria-label={target && fixedId ? `Add a tip for ${target.vendor_name}` : "Add a tip"}>
      {!fixedId && (
        <span className={`${fieldClass} sm:min-w-[14rem]`}>
          <label htmlFor={`${idPrefix}-for`} className="text-xs text-on-surface-variant">Which expense is the tip for?</label>
          <select id={`${idPrefix}-for`} value={targetId} onChange={(e) => setPicked(e.target.value)} className={inputClass}>
            {groups.map((g) => (
              <optgroup key={g.name} label={g.name}>
                {g.items.map((c) => <option key={c.id} value={c.id}>{c.vendor_name}</option>)}
              </optgroup>
            ))}
          </select>
        </span>
      )}
      <TipModePicker name={`${idPrefix}-mode`} mode={mode} onChange={setMode} />
      {mode === "percent" ? (
        <PercentInput id={`${idPrefix}-percent`} value={percent} onChange={setPercent} />
      ) : (
        <MoneyInput id={`${idPrefix}-amount`} label="Amount" value={amount} onChange={setAmount} required />
      )}
      <span className={fieldClass}>
        <label htmlFor={`${idPrefix}-due`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`${idPrefix}-due`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputClass} />
      </span>
      <PayerSelect id={`${idPrefix}-payer`} payers={payers} value={payer} onChange={setPayer} />
      {payers.length === 0 && <NoPayersHint />}
      <NotesInput id={`${idPrefix}-notes`} value={notes} onChange={setNotes} label="Comments (optional)" />
      {preview && <p aria-live="polite" className="w-full text-sm font-button-text text-on-surface">{preview}</p>}
      <p className="w-full text-xs text-on-surface-variant">
        The tip is added as its own line{target ? `, "Tip: ${target.vendor_name}",` : ""} in the same category, and counts in
        your totals. A percentage tip changes when {target ? `${target.vendor_name}'s` : "the expense's"} cost changes, until
        a payment on the tip is ticked paid. A tip in dollars stays as you typed it. A due date or who pays adds a payment
        for the tip, not ticked as paid. For a percentage tip, that payment changes with the tip while it's the tip's
        only payment, isn't paid and still matches the tip.
      </p>
      {picks && (
        <OverNote
          limits={picks.limits} before={0} after={typed}
          follows={mode === "percent" ? picks.cost.vendor_name : undefined}
        />
      )}
      <button type="submit" disabled={busy} className={primaryButton}>Add tip</button>
      <button type="button" disabled={busy} onClick={onDone} className={linkButton}>Cancel</button>
      <FormError error={error} />
    </form>
  );
}

/**
 * Editing a tip: rename it, switch between a percentage and an amount, change it, or
 * its comments. ``linked`` is the expense it's for, when it's in the list.
 */
function TipEditForm({
  base, cost, linked, limits, run, request, busy, onDone,
}: {
  base: string; cost: Cost; linked: Cost | undefined; limits: Limits; run: Run; request: Req; busy: boolean;
  onDone: () => void;
}) {
  const [name, setName] = useState(cost.vendor_name);
  const [mode, setMode] = useState<TipMode>(cost.tip_basis_points !== null ? "percent" : "amount");
  const [percent, setPercent] = useState(percentText(cost.tip_basis_points));
  const [amount, setAmount] = useState(cost.tip_basis_points === null ? centsToInput(cost.committed_cents) : "");
  const [notes, setNotes] = useState(cost.notes ?? "");
  const { error, setError, clear } = useFormError();
  const id = `tip-edit-${cost.id}`;
  const paid = cost.payments.some((p) => p.paid);
  const base_cents = cost.tip_base_cents ?? null;
  const bp = parsePercent(percent);
  const preview = mode === "percent" && typeof bp === "number" && base_cents !== null && cost.tip_state === "following"
    ? `${percentText(bp)}% of ${formatCents(base_cents)} = ${formatCents(percentOf(base_cents, bp))}`
    : null;
  const typed = typedTipCents(mode, percent, amount, linked ? tipBase(linked) : base_cents);
  // The one unpaid payment for the whole tip, which a new percentage moves too (PD-018).
  const only = cost.payments.length === 1 ? cost.payments[0] : null;
  const follows = cost.tip_basis_points !== null && mode === "percent" && typeof bp === "number"
    && bp !== cost.tip_basis_points && only !== null
    && !only.paid && !only.refundable && only.amount_cents === cost.committed_cents
    && cost.tip_state === "following" && typed !== null && typed > 0 && typed !== only.amount_cents;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const value = tipValue(mode, percent, amount, setError);
    if (!value) return;
    if (!name.trim()) { setError("Please type a name for the tip."); return; }
    const ok = await run(() => request(`${base}/tips/${cost.id}`, json("PATCH", {
      vendor_name: name, ...value, notes: notes || null,
    })), setError);
    if (ok) onDone();
  };

  return (
    <form onSubmit={save} onChange={clear} className="flex flex-wrap items-end gap-3 mb-3" aria-label={`Edit ${cost.vendor_name}`}>
      {cost.tip_for_name && <p className="w-full text-sm text-on-surface">A tip for {cost.tip_for_name}</p>}
      <TextInput id={`${id}-name`} label="Line item name" value={name} onChange={setName} wide />
      <TipModePicker name={`${id}-mode`} mode={mode} onChange={setMode} />
      {mode === "percent" ? (
        <PercentInput id={`${id}-percent`} value={percent} onChange={setPercent} />
      ) : (
        <MoneyInput id={`${id}-amount`} label="Amount" value={amount} onChange={setAmount} required />
      )}
      <NotesInput id={`${id}-notes`} value={notes} onChange={setNotes} label="Comments (optional)" />
      {preview && <p aria-live="polite" className="w-full text-sm font-button-text text-on-surface">{preview}</p>}
      {mode === "percent" && paid && (
        <p className="w-full text-xs text-on-surface-variant">
          A payment on this tip is ticked paid, so a new percentage is worked out once, now, and then stays fixed.
        </p>
      )}
      {follows && only && (
        <p className="w-full text-xs text-on-surface-variant">
          Its payment of {formatCents(only.amount_cents)} isn't paid yet and is for the whole tip, so it changes to
          match the new percentage.
        </p>
      )}
      {!cost.archived && (
        <OverNote
          limits={limits} before={cost.committed_cents} after={typed}
          follows={mode === "percent" && !paid ? cost.tip_for_name ?? undefined : undefined}
        />
      )}
      <button type="submit" disabled={busy} className={primaryButton}>Save</button>
      <button type="button" disabled={busy} onClick={onDone} className={linkButton}>Cancel</button>
      <FormError error={error} />
    </form>
  );
}

function CostEditForm({
  base, cost, tips, limits, vendors, run, request, busy, onDone,
}: {
  base: string; cost: Cost;
  /** This expense's tips: percentage ones move with the cost typed here. */
  tips: Cost[];
  limits: Limits; vendors: VendorRef[]; run: Run; request: Req; busy: boolean; onDone: () => void;
}) {
  const [vendor, setVendor] = useState(cost.vendor_name);
  const [vendorId, setVendorId] = useState(cost.vendor?.id ?? "");
  // One box for the estimate or quote (PD-016). It shows the quote if there is one and
  // saves back to the same field, so an earlier estimate under a quote stays saved.
  const box = costBox(cost.quoted_cents, cost.estimated_cents);
  const [figure, setFigure] = useState(centsToInput(box.cents));
  const [actual, setActual] = useState(centsToInput(cost.final_cents));
  const [contract, setContract] = useState<ContractStatus>(cost.contract_status);
  const [method, setMethod] = useState(cost.payment_method ?? "");
  const [link, setLink] = useState(cost.link_url ?? "");
  const [notes, setNotes] = useState(cost.notes ?? "");
  const { error, setError, clear } = useFormError();
  const id = cost.id;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const amounts = [figure, actual].map((t) => amountOrError(t, setError));
    if (amounts.some((a) => a === undefined)) return;
    const [figure_cents, final_cents] = amounts;
    const ok = await run(() => request(`${base}/costs/${id}`, json("PATCH", {
      vendor_name: vendor, [box.field]: figure_cents, final_cents, contract_status: contract,
      payment_method: method || null, link_url: link || null, notes: notes || null,
      couple_vendor_id: vendorId || null,
    })), setError);
    if (ok) onDone();
  };
  const typedBoxes: (string | null)[] = box.field === "quoted_cents"
    ? [actual, figure, centsToInput(cost.estimated_cents)]
    : [actual, null, figure];
  // Percentage tips follow the cost (PD-017), so the "would go over" note counts how
  // they'd move too: worked out from the typed boxes, never from payments.
  const typedAfter = typedCost(typedBoxes, cost.scheduled_cents);
  const moving = tipsMove(tips, typedTipBase(typedBoxes));

  const pickVendor = (value: string) => {
    setVendorId(value);
    const picked = vendors.find((v) => v.id === value);
    if (picked && !vendor.trim()) setVendor(picked.name);
  };

  return (
    <form onSubmit={save} onChange={clear} className="flex flex-wrap items-end gap-3 mb-3">
      <TextInput id={`cost-name-${id}`} label="Line item name" value={vendor} onChange={setVendor} wide />
      <VendorSelect id={`cost-vendor-${id}`} vendors={vendors} value={vendorId} onChange={pickVendor} />
      <MoneyInput id={`cost-figure-${id}`} label="Estimate or quote" value={figure} onChange={setFigure} />
      <MoneyInput id={`cost-final-${id}`} label="Actual cost (fill in later)" value={actual} onChange={setActual} />
      <SelectInput id={`cost-contract-${id}`} label="Contract" value={contract} onChange={(v) => setContract(v as ContractStatus)}>
        <option value="none">No contract yet</option>
        <option value="sent">Sent</option>
        <option value="signed">Signed</option>
      </SelectInput>
      <span className={fieldClass}>
        <label htmlFor={`cost-method-${id}`} className="text-xs text-on-surface-variant">How you'll pay (optional)</label>
        <input id={`cost-method-${id}`} list="budget-method-suggestions" autoComplete="off" maxLength={120}
          value={method} onChange={(e) => setMethod(e.target.value)} className={inputClass} />
      </span>
      <LinkInput id={`cost-link-${id}`} value={link} onChange={setLink} />
      <NotesInput id={`cost-notes-${id}`} value={notes} onChange={setNotes} />
      <p className="w-full text-xs text-on-surface-variant">
        The budget counts the actual cost once you've entered it, otherwise the estimate or quote.
        {box.keptEstimate !== null && (
          <> Your earlier estimate of {formatCents(box.keptEstimate)} is also saved. This box is the quote, which
          the budget uses instead; if you empty it, the earlier estimate counts again.</>
        )}
      </p>
      {!cost.archived && (
        <OverNote
          limits={limits}
          before={cost.committed_cents + moving.before}
          after={typedAfter === null ? null : typedAfter + moving.after}
        />
      )}
      {!cost.archived && typedAfter !== null && moving.count > 0 && moving.after !== moving.before && (
        <p className="w-full text-xs text-on-surface-variant">
          With this cost, its percentage {moving.count === 1 ? "tip comes" : "tips come"} to {formatCents(moving.after)}{" "}
          (now {formatCents(moving.before)}). A tip's payment changes with it when it's the tip's only payment, isn't
          paid yet and is for the whole tip.
        </p>
      )}
      <button type="submit" disabled={busy} className={primaryButton}>Save</button>
      <button type="button" disabled={busy} onClick={onDone} className={linkButton}>Cancel</button>
      <FormError error={error} />
    </form>
  );
}

/**
 * Adding an expense (PD-016 step 1): its name, the estimate or quote, and its first
 * payment (type, amount, due date, who paid) plus comments, saved in one go. The
 * amount starts as the estimate or quote; change it for a deposit, or empty it to add
 * the expense with no payment yet. The payment is added unpaid (rule 4).
 */
function AddCostForm({
  base, categoryId, categoryName, limits, vendors, payers, run, request, busy, suggestions, taken, onAdded, onCancel,
}: {
  base: string; categoryId: string; categoryName: string; limits: Limits; vendors: VendorRef[]; payers: Payer[]; run: Run;
  request: Req; busy: boolean;
  /** One-tap ideas for this category; those already used here aren't offered. */
  suggestions: string[]; taken: string[];
  /** Called with the new expense's name once it's saved; the form closes. */
  onAdded: (name: string) => void;
  onCancel: () => void;
}) {
  const [vendor, setVendor] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [figure, setFigure] = useState("");
  const [kind, setKind] = useState<"deposit" | "payment">("payment");
  // The amount follows the estimate or quote until the couple type their own.
  const [typedAmount, setTypedAmount] = useState<string | null>(null);
  const amount = typedAmount ?? figure;
  const [due, setDue] = useState("");
  const [payer, setPayer] = useState("");
  const [notes, setNotes] = useState("");
  const { error, setError, clear } = useFormError();
  useReportDirty(
    `expense:${categoryId}`,
    !!(vendor || vendorId || figure || typedAmount || due || payer || notes) || kind !== "payment",
  );
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const figureCents = amountOrError(figure, setError);
    const amountCents = amountOrError(amount, setError);
    if (figureCents === undefined || amountCents === undefined) return;
    const payerId = payerOrNull(payers, payer);
    if (!amountCents && (due || payerId)) {
      setError("Please enter the amount of this payment, or clear its due date and who paid to add the expense without one.");
      return;
    }
    const ok = await run(
      () => request(`${base}/categories/${categoryId}/costs`, json("POST", {
        vendor_name: vendor, estimated_cents: figureCents, couple_vendor_id: vendorId || null,
        notes: notes || null,
        first_payment: amountCents
          ? { kind, amount_cents: amountCents, due_on: due || null, payer_id: payerId }
          : null,
      })),
      setError,
    );
    if (ok) onAdded(vendor.trim());
  };
  const typedAmountCents = parseDollars(amount);
  const typedFigureCents = parseDollars(figure);
  // Shown, never blocking: a first payment bigger than the estimate or quote.
  const overFigure = typeof typedAmountCents === "number" && typeof typedFigureCents === "number"
    ? typedAmountCents - typedFigureCents
    : 0;
  const pickVendor = (value: string) => {
    setVendorId(value);
    const picked = vendors.find((v) => v.id === value);
    if (picked && !vendor.trim()) setVendor(picked.name);
  };
  const used = new Set(taken.map((t) => t.trim().toLowerCase()));
  const ideas = suggestions.filter((s) => !used.has(s.toLowerCase()));
  const ideasId = `ideas-${categoryId}`;
  return (
    <form onSubmit={submit} onChange={clear} className="flex flex-wrap items-end gap-3" aria-label={`Add an expense to ${categoryName}`}>
      {ideas.length > 0 && (
        <div className="w-full">
          <p id={ideasId} className="text-xs text-on-surface-variant mb-1">Ideas for this category: tap one to use it as the name</p>
          <div role="group" aria-labelledby={ideasId} className="flex flex-wrap gap-2">
            {ideas.map((idea) => (
              <button
                key={idea}
                type="button"
                aria-pressed={vendor === idea}
                onClick={() => { clear(); setVendor(idea); }}
                className={`rounded-full border px-3 py-3 sm:py-1 text-xs ${vendor === idea ? "bg-primary text-on-primary border-primary" : "border-outline-variant/50 text-on-surface hover:border-primary"}`}
              >
                {idea}
              </button>
            ))}
          </div>
        </div>
      )}
      {vendors.length > 0 && (
        <VendorSelect id={`new-cost-vendor-${categoryId}`} vendors={vendors} value={vendorId} onChange={pickVendor} />
      )}
      <TextInput id={`new-cost-${categoryId}`} label="Line item name" value={vendor} onChange={setVendor} wide />
      <MoneyInput id={`new-figure-${categoryId}`} label="Estimate or quote (optional)" value={figure} onChange={setFigure} />
      <SelectInput id={`new-kind-${categoryId}`} label="Type" value={kind} onChange={(v) => setKind(v as "deposit" | "payment")}>
        <option value="payment">Payment</option>
        <option value="deposit">Deposit</option>
      </SelectInput>
      <MoneyInput
        id={`new-amount-${categoryId}`} label="Amount of this payment" value={amount}
        onChange={(v) => setTypedAmount(v)} placeholder="None yet"
      />
      <span className={fieldClass}>
        <label htmlFor={`new-due-${categoryId}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`new-due-${categoryId}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputClass} />
      </span>
      <PayerSelect id={`new-payer-${categoryId}`} payers={payers} value={payer} onChange={setPayer} />
      {payers.length === 0 && <NoPayersHint />}
      <NotesInput id={`new-notes-${categoryId}`} value={notes} onChange={setNotes} label="Comments (optional)" />
      <p className="w-full text-xs text-on-surface-variant">
        The amount starts as the full estimate or quote; change it for a deposit. Saving adds the expense and this
        payment together, not ticked as paid. Leave the amount empty to add the expense without a payment. You can
        add more payments under it later, and fill in the actual cost once you know it.
      </p>
      <button type="submit" disabled={busy} className={primaryButton}>Add expense</button>
      <button type="button" disabled={busy} onClick={onCancel} className={linkButton}>Cancel</button>
      {overFigure > 0 && (
        <p role="status" className="w-full flex items-start gap-1 text-sm text-error">
          <Icon name="warning" size={16} className="mt-0.5" />
          This payment is {formatCents(overFigure)} more than the estimate or quote. You can still add it.
        </p>
      )}
      <OverNote
        limits={limits} before={0}
        after={typedCost([null, null, figure], typeof typedAmountCents === "number" ? typedAmountCents : 0)}
      />
      <FormError error={error} />
    </form>
  );
}

/**
 * What the typed boxes (final, quote, estimate; null for a box the form doesn't
 * have) would make the expense count as, or null while one isn't a valid amount.
 */
function typedCost(boxes: (string | null)[], scheduledCents: number): number | null {
  const parsed = boxes.map((b) => (b === null ? null : parseDollars(b)));
  if (parsed.some((p) => p === undefined)) return null;
  const [f, q, e] = parsed as (number | null)[];
  return expenseCost(f, q, e, scheduledCents);
}

/**
 * What a percentage tip would be worked out from with these typed boxes (final, quote,
 * estimate; null for a box the form doesn't have): the first one filled in, else null.
 * Payments never count, as in the API. Null too while a box isn't a valid amount,
 * which only matters while the note is hidden anyway.
 */
function typedTipBase(boxes: (string | null)[]): number | null {
  for (const b of boxes) {
    if (b === null) continue;
    const cents = parseDollars(b);
    if (cents === undefined) return null;
    if (cents !== null) return cents;
  }
  return null;
}

/**
 * A note, never a block: saving this would take the category or the total over.
 * ``follows`` names the expense a percentage tip changes with, so the note says the
 * figure can move later.
 */
function OverNote({ limits, before, after, follows }: {
  limits: Limits; before: number; after: number | null; follows?: string;
}) {
  const { categoryOverBy, totalOverBy } =
    after === null ? { categoryOverBy: 0, totalOverBy: 0 } : wouldGoOver({ ...limits, before, after });
  const over = [
    categoryOverBy > 0 && "this category's target",
    totalOverBy > 0 && "your total budget",
  ].filter(Boolean);
  const amounts = [
    categoryOverBy > 0 && `the category by ${formatCents(categoryOverBy)}`,
    totalOverBy > 0 && `the total by ${formatCents(totalOverBy)}`,
  ].filter(Boolean);
  // The live region always exists and only says which limit is crossed, so a screen
  // reader hears it when it appears, not on every keystroke. The amounts sit just
  // after it, outside the live region, still readable.
  return (
    <div className="w-full text-sm text-on-surface">
      <p aria-live="polite" className="flex items-start gap-1">
        {over.length > 0 && (
          <>
            <Icon name="error" size={16} className="mt-0.5 text-status-todo" />
            Heads up: with this, you'd be over {over.join(" and ")}. You can still save it.
          </>
        )}
      </p>
      {over.length > 0 && (
        <p className="text-xs text-on-surface-variant pl-5">
          Over {amounts.join(", ")}.
          {follows && ` This is a percentage tip, so it will go up or down when ${follows}'s cost changes, and so will how far over you are.`}
        </p>
      )}
    </div>
  );
}

// ---- Payment ------------------------------------------------------------------------

const KIND_LABEL = { deposit: "Deposit", payment: "Payment" } as const;

/**
 * Who paid, on a payment row: their name, or for a payment nobody has said yet a
 * "Who paid?" dropdown for owners and editors (PD-016 call b). Choosing saves it
 * straight away and never ticks the payment paid (rule 4).
 */
function WhoPaid({
  base, payment, payers, canEdit, run, request, busy, onError,
}: {
  base: string; payment: Payment; payers: Payer[]; canEdit: boolean; run: Run; request: Req; busy: boolean;
  onError: (message: string) => void;
}) {
  if (payment.payer_name) {
    return <span className="block text-xs text-on-surface">{payment.paid ? "Paid by" : "To be paid by"} {payment.payer_name}</span>;
  }
  if (!canEdit) return <span className="block text-xs text-on-surface-variant">Who paid: not set yet</span>;
  if (payers.length === 0) {
    return <span className="block text-xs text-on-surface-variant">Who paid? Add the people who pay to choose.</span>;
  }
  const id = `who-paid-${payment.id}`;
  return (
    <span className="flex flex-wrap items-center gap-2 text-xs mt-1">
      <label htmlFor={id} className="font-bold text-on-surface">Who paid?</label>
      <select
        id={id} value="" disabled={busy}
        onChange={(e) => {
          const picked = payerOrNull(payers, e.target.value);
          if (picked) run(() => request(`${base}/payments/${payment.id}`, json("PATCH", { payer_id: picked })), onError);
        }}
        className="bg-surface-container-low border border-outline-variant/40 rounded-full px-3 py-1 text-xs text-on-surface focus:border-primary focus:outline-none"
      >
        <option value="">Choose…</option>
        {payers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </span>
  );
}

function PaymentRow({
  base, payment, cost, payers, canEdit, run, request, busy,
}: { base: string; payment: Payment; cost: Cost; payers: Payer[]; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const [confirmOverpay, setConfirmOverpay] = useState(false);
  const [editing, setEditing] = useState(false);
  // Refusals of the row's own controls (the tick, who paid, remove); the edit form has its own.
  const { error, setError, clear } = useFormError();
  const paidUrl = `${base}/payments/${payment.id}/paid`;
  const act = (fn: () => Promise<unknown>) => { clear(); return run(fn, setError); };

  const tick = (checked: boolean) => {
    clear();
    // A warning, not a block: the couple may really have paid more than agreed.
    if (checked && payment.would_overpay_cents > 0) { setConfirmOverpay(true); return; }
    act(() => request(paidUrl, json("PUT", { paid: checked })));
  };

  if (editing) {
    return (
      <li className="py-2">
        <PaymentEditForm base={base} payment={payment} payers={payers} run={run} request={request} busy={busy} onDone={() => setEditing(false)} />
      </li>
    );
  }

  const due = payment.due_on ? `due ${formatDay(payment.due_on)}` : "no due date";
  const paidOn = payment.paid_on ? formatDay(payment.paid_on) : payment.paid_at ? formatInstantDay(payment.paid_at) : "";
  const paidNote = payment.paid
    ? `Paid${paidOn ? ` on ${paidOn}` : ""}${payment.paid_by_name ? `, ticked by ${payment.paid_by_name}` : ""}`
    : "Not paid yet";
  const details = [payment.method && `Paid with ${payment.method}`, payment.reference && `Ref. ${payment.reference}`].filter(Boolean);
  return (
    <li className="py-2 flex flex-wrap items-center gap-3 text-sm">
      <span className="flex-grow">
        {payment.refundable ? "Refundable deposit" : KIND_LABEL[payment.kind]} of{" "}
        <span className="font-button-text">{formatCents(payment.amount_cents)}</span>, {due}
        {payment.overdue && (
          <span className="ml-2 inline-flex items-center gap-1 text-error font-bold">
            <Icon name="warning" size={14} /> Overdue
          </span>
        )}
        <span className={`block text-xs ${payment.paid ? "text-primary-text" : "text-on-surface-variant"}`}>{paidNote}</span>
        <WhoPaid
          base={base} payment={payment} payers={payers} canEdit={canEdit && !cost.archived} run={run} request={request} busy={busy}
          onError={(message) => setError(message)}
        />
        {payment.refundable && (
          <span className="block text-xs text-on-surface-variant">Tracked here, but not counted in the cost or in paid.</span>
        )}
        {(details.length > 0 || safeHttpUrl(payment.link_url)) && (
          <span className="flex flex-wrap gap-x-3 text-xs text-on-surface-variant">
            {details.map((d) => <span key={d as string}>{d}</span>)}
            <OpenLink url={payment.link_url} label="Open link" />
          </span>
        )}
        {payment.notes && <span className="block text-xs text-on-surface mt-1 whitespace-pre-line">{payment.notes}</span>}
      </span>
      {canEdit && (
        <>
          {confirmOverpay ? (
            <span role="alertdialog" aria-label="Paying more than the cost" className="flex flex-wrap items-center gap-2 text-sm w-full">
              <Icon name="warning" size={16} className="text-error" />
              <span>
                Ticking this makes what you've paid {cost.vendor_name} {formatCents(payment.would_overpay_cents)} more
                than the cost ({formatCents(cost.committed_cents)}). Tick it anyway?
              </span>
              <button type="button" disabled={busy} className={`text-error font-bold underline-offset-4 hover:underline ${tapArea}`}
                onClick={async () => { setConfirmOverpay(false); await act(() => request(paidUrl, json("PUT", { paid: true }))); }}>
                Yes, tick it
              </button>
              <button type="button" disabled={busy} onClick={() => { clear(); setConfirmOverpay(false); }} className={linkButton}>Cancel</button>
            </span>
          ) : (
            <label className="flex items-center gap-2 cursor-pointer min-h-11 sm:min-h-0">
              <input
                type="checkbox"
                checked={payment.paid}
                disabled={busy || cost.archived}
                onChange={(e) => tick(e.target.checked)}
                className="h-4 w-4 accent-primary"
              />
              Paid
            </label>
          )}
          {confirm ? (
            <Confirm busy={busy} text="Remove this payment?"
              onYes={() => act(() => request(`${base}/payments/${payment.id}`, json("DELETE")))}
              onNo={() => { clear(); setConfirm(false); }} />
          ) : (
            <span className="flex gap-4">
              <button type="button" onClick={() => { clear(); setEditing(true); }} className={linkButton}>Edit</button>
              <button type="button" onClick={() => { clear(); setConfirm(true); }} className={dangerLink}>Remove</button>
            </span>
          )}
        </>
      )}
      <FormError error={error} />
    </li>
  );
}

function PaymentEditForm({
  base, payment, payers, run, request, busy, onDone,
}: { base: string; payment: Payment; payers: Payer[]; run: Run; request: Req; busy: boolean; onDone: () => void }) {
  const [kind, setKind] = useState<"deposit" | "payment">(payment.kind);
  const [payer, setPayer] = useState(payment.payer_id ?? "");
  const [amount, setAmount] = useState(centsToInput(payment.amount_cents));
  const [dueOn, setDueOn] = useState(payment.due_on ?? "");
  const [refundable, setRefundable] = useState(payment.refundable);
  const [method, setMethod] = useState(payment.method ?? "");
  const [reference, setReference] = useState(payment.reference ?? "");
  const [link, setLink] = useState(payment.link_url ?? "");
  const [notes, setNotes] = useState(payment.notes ?? "");
  const [paidOn, setPaidOn] = useState(payment.paid_on ?? "");
  const { error, setError, clear } = useFormError();
  const id = payment.id;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (!cents) { setError("Please enter how much this payment is."); return; }
    const ok = await run(
      () => request(`${base}/payments/${id}`, json("PATCH", {
        kind, amount_cents: cents, due_on: dueOn || null, refundable,
        method: method || null, reference: reference || null, link_url: link || null, notes: notes || null,
        payer_id: payerOrNull(payers, payer),
        ...(payment.paid ? { paid_on: paidOn || null } : {}),
      })),
      setError,
    );
    if (ok) onDone();
  };

  return (
    <form onSubmit={save} onChange={clear} className="flex flex-wrap items-end gap-3">
      <SelectInput id={`edit-kind-${id}`} label="Type" value={kind} onChange={(v) => setKind(v as "deposit" | "payment")}>
        <option value="deposit">Deposit</option>
        <option value="payment">Payment</option>
      </SelectInput>
      <MoneyInput id={`edit-amount-${id}`} label="Amount" value={amount} onChange={setAmount} required />
      <span className={fieldClass}>
        <label htmlFor={`edit-due-${id}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`edit-due-${id}`} type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} className={inputClass} />
      </span>
      {payment.paid && (
        <span className={fieldClass}>
          <label htmlFor={`edit-paidon-${id}`} className="text-xs text-on-surface-variant">Date paid (optional)</label>
          <input id={`edit-paidon-${id}`} type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} className={inputClass} />
        </span>
      )}
      <PayerSelect id={`edit-payer-${id}`} payers={payers} value={payer} onChange={setPayer} />
      <span className={fieldClass}>
        <label htmlFor={`edit-method-${id}`} className="text-xs text-on-surface-variant">How it was paid (optional)</label>
        <input id={`edit-method-${id}`} list="budget-method-suggestions" autoComplete="off" maxLength={120}
          value={method} onChange={(e) => setMethod(e.target.value)} className={inputClass} />
      </span>
      <TextInput id={`edit-ref-${id}`} label="Reference, like a check number (optional)" value={reference} onChange={setReference} required={false} />
      <label className="flex items-center gap-2 text-sm cursor-pointer pb-2 min-h-11 sm:min-h-0">
        <input type="checkbox" checked={refundable} onChange={(e) => setRefundable(e.target.checked)} className="h-4 w-4 accent-primary" />
        Refundable security deposit (not part of the cost)
      </label>
      <LinkInput id={`edit-link-${id}`} value={link} onChange={setLink} />
      <NotesInput id={`edit-notes-${id}`} value={notes} onChange={setNotes} />
      <button type="submit" disabled={busy} className={primaryButton}>Save</button>
      <button type="button" disabled={busy} onClick={onDone} className={linkButton}>Cancel</button>
      <FormError error={error} />
    </form>
  );
}

function AddPaymentForm({
  base, cost, payers, run, request, busy, onDone,
}: { base: string; cost: Cost; payers: Payer[]; run: Run; request: Req; busy: boolean; onDone: () => void }) {
  // A first payment is usually the deposit; later ones are payments.
  const [firstKind] = useState<"deposit" | "payment">(cost.payments.length > 0 ? "payment" : "deposit");
  const [kind, setKind] = useState(firstKind);
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [refundable, setRefundable] = useState(false);
  // Starts as whoever paid this expense's latest payment (PD-016), until changed.
  const [pickedPayer, setPickedPayer] = useState<string | null>(null);
  const payer = pickedPayer ?? cost.last_payer_id ?? "";
  const { error, setError, clear } = useFormError();
  const costId = cost.id;
  useReportDirty(`payment:${costId}`, !!(amount || due || pickedPayer !== null) || refundable || kind !== firstKind);

  // Shown before adding, never blocking: does this take the payments past the cost?
  const typed = parseDollars(amount);
  const fixedCost = cost.committed_basis !== "scheduled" && cost.committed_basis !== "none";
  const over = typeof typed === "number" && !refundable && fixedCost
    ? cost.scheduled_cents + typed - cost.committed_cents
    : 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (!cents) { setError("Please enter how much this payment is."); return; }
    const ok = await run(
      () => request(`${base}/costs/${costId}/payments`, json("POST", {
        kind, amount_cents: cents, due_on: due || null, refundable, payer_id: payerOrNull(payers, payer),
      })),
      setError,
    );
    if (ok) onDone();
  };
  return (
    <form onSubmit={submit} onChange={clear} className="flex flex-wrap items-end gap-3 pt-2" aria-label={`Add a payment for ${cost.vendor_name}`}>
      <SelectInput id={`pay-kind-${costId}`} label="Type" value={kind} onChange={(v) => setKind(v as "deposit" | "payment")}>
        <option value="deposit">Deposit</option>
        <option value="payment">Payment</option>
      </SelectInput>
      <MoneyInput id={`pay-amount-${costId}`} label="Amount" value={amount} onChange={setAmount} required />
      <span className={fieldClass}>
        <label htmlFor={`pay-due-${costId}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`pay-due-${costId}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputClass} />
      </span>
      <label className="flex items-center gap-2 text-sm cursor-pointer pb-2 min-h-11 sm:min-h-0">
        <input type="checkbox" checked={refundable} onChange={(e) => setRefundable(e.target.checked)} className="h-4 w-4 accent-primary" />
        Refundable security deposit
      </label>
      {payers.length > 0 && (
        <PayerSelect id={`pay-payer-${costId}`} payers={payers} value={payer} onChange={(v) => setPickedPayer(v)} />
      )}
      <button type="submit" disabled={busy} className={primaryButton}>Add payment</button>
      <button type="button" disabled={busy} onClick={onDone} className={linkButton}>Cancel</button>
      {over > 0 && (
        <p role="status" className="w-full flex items-start gap-1 text-sm text-error">
          <Icon name="warning" size={16} className="mt-0.5" />
          With this one, the payments come to {formatCents(over)} more than the cost ({formatCents(cost.committed_cents)}).
          You can still add it.
        </p>
      )}
      <FormError error={error} />
    </form>
  );
}

// ---- Contributions ------------------------------------------------------------------

export function Contributions({
  base, items, categories, totalCents, sumCents, canEdit, run, request, busy,
}: {
  base: string; items: Contribution[]; categories: Category[]; totalCents: number | null; sumCents: number;
  canEdit: boolean; run: Run; request: Req; busy: boolean;
}) {
  const [who, setWho] = useState("");
  const [amount, setAmount] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const { error, setError, clear } = useFormError();
  const [confirm, setConfirm] = useState<string | null>(null);
  const catName = (id: string | null) => categories.find((c) => c.id === id)?.name;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    clear();
    // The add form's messages are "add"; a row's are its id.
    const failed = (message: string | null) => setError(message, "add");
    const cents = amountOrError(amount, failed);
    if (cents === undefined) return;
    if (cents === null) { failed("Please enter how much they're contributing."); return; }
    const ok = await run(
      () => request(`${base}/contributions`, json("POST", { contributor: who, amount_cents: cents, category_id: categoryId || null })),
      failed,
    );
    if (ok) { setWho(""); setAmount(""); setCategoryId(""); }
  };

  return (
    <section id={sectionId("contributions")} tabIndex={-1} aria-labelledby="contrib-heading" className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}>
      <SectionHeading section="contributions" id="contrib-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">
        Who's contributing
      </SectionHeading>
      <FoldBody section="contributions">
      <p className="text-sm text-on-surface-variant mb-3">
        {totalCents === null
          ? `Contributions so far: ${formatCents(sumCents)}.`
          : `Contributions: ${formatCents(sumCents)} of your ${formatCents(totalCents)} total.`}
      </p>
      {items.length > 0 && (
        <ul className="divide-y divide-outline-variant/30 border-y border-outline-variant/30 mb-4">
          {items.map((c) => (
            <li key={c.id} className="py-3 flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="text-on-surface">{c.contributor}</span>
                <span className="text-sm text-on-surface-variant">
                  {" · "}{catName(c.category_id) ? `towards ${catName(c.category_id)}` : "towards the whole budget"}
                </span>
              </span>
              <span className="flex items-center gap-4">
                <span className="font-button-text text-on-surface">{formatCents(c.amount_cents)}</span>
                {canEdit && (confirm === c.id ? (
                  <Confirm busy={busy} text="Remove this contribution?"
                    onYes={() => { clear(); run(() => request(`${base}/contributions/${c.id}`, json("DELETE")), (m) => setError(m, c.id)); }}
                    onNo={() => { clear(); setConfirm(null); }} />
                ) : (
                  <button type="button" onClick={() => { clear(); setConfirm(c.id); }} className={dangerLink}>Remove</button>
                ))}
              </span>
              <FormError error={error} at={c.id} />
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <form onSubmit={submit} onChange={clear} className="flex flex-wrap items-end gap-3">
          <TextInput id="contrib-who" label="Who" value={who} onChange={setWho} placeholder="For example, Groom's parents" wide />
          <MoneyInput id="contrib-amount" label="Amount" value={amount} onChange={setAmount} required />
          <span className={fieldClass}>
            <label htmlFor="contrib-cat" className="text-xs text-on-surface-variant">Towards (optional)</label>
            <select id="contrib-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={inputClass}>
              <option value="">The whole budget</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </span>
          <button type="submit" disabled={busy} className={primaryButton}>Add contribution</button>
          <FormError error={error} at="add" />
        </form>
      )}
      </FoldBody>
    </section>
  );
}
