import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import {
  AMOUNT_HINT, centsToInput, committedLabel, formatCents, formatDay, formatInstantDay, parseDollars,
  safeHttpUrl,
} from "./money";
import { expenseCost, wouldGoOver } from "./forecast";
import { Bar, Chip, TargetChip, targetTone } from "./status";
import type {
  Category, ContractStatus, Contribution, Cost, ExpenseStatus, Payment, Run, Totals, VendorRef,
} from "./types";

type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;

export const inputClass =
  "bg-surface-container-low border border-outline-variant/40 rounded-full px-4 py-2 text-sm text-on-surface focus:border-primary focus:outline-none";
export const primaryButton =
  "bg-primary text-on-primary rounded-full px-5 py-2 font-button-text text-sm disabled:opacity-60";
export const linkButton =
  "text-sm text-on-surface-variant hover:text-primary underline-offset-4 hover:underline disabled:opacity-60";
const dangerLink =
  "text-sm text-on-surface-variant hover:text-error underline-offset-4 hover:underline disabled:opacity-60";

const json = (method: string, body?: unknown): RequestInit => ({
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
    <span className="flex flex-col gap-1">
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
          className={`${inputClass} pl-7 w-36`}
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
    <span className={`flex flex-col gap-1 ${wide ? "flex-grow min-w-[12rem]" : ""}`}>
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
function amountOrError(text: string, setError: (e: string | null) => void): number | null | undefined {
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

function Confirm({
  text, onYes, onNo, busy, yesLabel = "Yes, remove",
}: { text: ReactNode; onYes: () => void; onNo: () => void; busy: boolean; yesLabel?: string }) {
  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <span>{text}</span>
      <button type="button" disabled={busy} onClick={onYes} className="text-error font-bold underline-offset-4 hover:underline">
        {yesLabel}
      </button>
      <button type="button" disabled={busy} onClick={onNo} className={linkButton}>Cancel</button>
    </span>
  );
}

// ---- Category -----------------------------------------------------------------------

/** What a new or edited expense is measured against, for the "would go over" note. */
type Limits = { target: number | null; committed: number; total: number | null; totalCommitted: number };

/** Asks a category to open and scroll to one of its expenses; n changes on each ask. */
export type OpenRequest = { id: string; n: number } | null;

export function CategoryCard({
  base, category, categories, totals, vendors, canEdit, run, request, busy, openRequest, onOpened,
}: {
  base: string; category: Category; categories: Category[]; totals: Totals; vendors: VendorRef[];
  canEdit: boolean; run: Run; request: Req; busy: boolean; openRequest: OpenRequest;
  /** Called once the asked-for expense has been scrolled to, so the ask is cleared. */
  onOpened: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [planned, setPlanned] = useState(centsToInput(category.planned_cents));
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(category.costs.length > 0);
  const [showArchived, setShowArchived] = useState(false);
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
  const limits: Limits = {
    target: planned_cents, committed: category.committed_cents,
    total: totals.total_cents, totalCommitted: totals.committed_cents,
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(planned, setError);
    if (cents === undefined) return;
    const ok = await run(() =>
      request(`${base}/categories/${category.id}`, json("PATCH", { name, planned_cents: cents })),
    );
    if (ok) setEditing(false);
  };

  return (
    <section className="bg-surface-container-lowest p-6 rounded-[2rem] border border-outline-variant/20 shadow-sm">
      {editing ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 mb-4">
          <TextInput id={`cat-name-${category.id}`} label="Category" value={name} onChange={setName} wide />
          <MoneyInput id={`cat-plan-${category.id}`} label="Target" value={planned} onChange={setPlanned} />
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h3 className="flex flex-wrap items-center gap-2 font-headline-sm text-lg text-on-surface">
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
              <span className="flex gap-4">
                <button
                  type="button"
                  onClick={() => { setName(category.name); setPlanned(centsToInput(planned_cents)); setEditing(true); }}
                  className={linkButton}
                >
                  Edit
                </button>
                <button type="button" onClick={() => setConfirm(true)} className={dangerLink}>Remove</button>
              </span>
            )
          )}
        </div>
      )}
      {error && <p role="alert" className="text-sm text-error mb-3">{error}</p>}

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

      <button type="button" onClick={() => setOpen((o) => !o)} className={`${linkButton} mt-2`} aria-expanded={open}>
        {open ? "Hide expenses" : `Show expenses (${active.length})`}
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {active.map((cost) => (
            <CostBlock key={cost.id} base={base} cost={cost} limits={limits} vendors={vendors} canEdit={canEdit} run={run} request={request} busy={busy} focus={focusFor(cost)} onOpened={onOpened} />
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
                <CostBlock key={cost.id} base={base} cost={cost} limits={limits} vendors={vendors} canEdit={canEdit} run={run} request={request} busy={busy} focus={focusFor(cost)} onOpened={onOpened} />
              ))}
            </>
          )}
          {canEdit && (
            <AddCostForm
              base={base} categoryId={category.id} limits={limits} vendors={vendors} run={run} request={request} busy={busy}
              suggestions={category.suggestions} taken={active.map((c) => c.vendor_name)}
            />
          )}
        </div>
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
  const remove = (moveTo?: string) =>
    run(() => request(
      `${base}/categories/${category.id}${moveTo ? `?move_to=${encodeURIComponent(moveTo)}` : ""}`,
      json("DELETE"),
    ));

  if (count === 0) {
    return <Confirm busy={busy} text={`Remove ${category.name}? ${kept}`} onYes={() => remove()} onNo={onCancel} />;
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
      <span className="flex flex-col gap-1">
        <label htmlFor={selectId} className="text-xs text-on-surface-variant">Move them to</label>
        <select id={selectId} value={target} onChange={(e) => setTarget(e.target.value)} className={inputClass}>
          {others.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </span>
      <button type="button" disabled={busy || !target} onClick={() => remove(target)}
        className="text-error font-bold underline-offset-4 hover:underline pb-2">
        Move them and remove {category.name}
      </button>
      <button type="button" disabled={busy} onClick={onCancel} className={`${linkButton} pb-2`}>Cancel</button>
    </span>
  );
}

export function AddCategoryForm({ base, run, request, busy }: { base: string; run: Run; request: Req; busy: boolean }) {
  const [name, setName] = useState("");
  const [planned, setPlanned] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(planned, setError);
    if (cents === undefined) return;
    const ok = await run(() => request(`${base}/categories`, json("POST", { name, planned_cents: cents })));
    if (ok) { setName(""); setPlanned(""); }
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <TextInput id="new-cat-name" label="Category name" value={name} onChange={setName} placeholder="For example, Venue" wide />
      <MoneyInput id="new-cat-plan" label="Target (optional)" value={planned} onChange={setPlanned} />
      <button type="submit" disabled={busy} className={primaryButton}>Add category</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
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
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
      {label} ({host}) <Icon name="open_in_new" size={14} /> <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

function LinkInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <span className="flex flex-col gap-1 flex-grow min-w-[14rem]">
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

function NotesInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <span className="flex flex-col gap-1 w-full">
      <label htmlFor={id} className="text-xs text-on-surface-variant">Notes (optional)</label>
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
    <span className="flex flex-col gap-1">
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

/** "Final $12,000", "Quoted $11,000", "Estimate $10,000" or "No cost recorded". */
function costLine(cost: Cost): string {
  if (cost.final_cents !== null) return `Final ${formatCents(cost.final_cents)}`;
  if (cost.quoted_cents !== null) return `Quoted ${formatCents(cost.quoted_cents)}`;
  if (cost.estimated_cents !== null) return `Estimate ${formatCents(cost.estimated_cents)}`;
  if (cost.scheduled_cents > 0) return `Payments so far ${formatCents(cost.scheduled_cents)}`;
  return "No cost recorded";
}

function CostBlock({
  base, cost, limits, vendors, canEdit, run, request, busy, focus, onOpened,
}: {
  base: string; cost: Cost; limits: Limits; vendors: VendorRef[]; canEdit: boolean; run: Run; request: Req; busy: boolean;
  /** Non-zero when the list of all expenses asked to open this one; a new number each time. */
  focus: number;
  onOpened: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [confirmCopy, setConfirmCopy] = useState(false);
  const box = useRef<HTMLDivElement>(null);

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
        <CostEditForm base={base} cost={cost} limits={limits} vendors={vendors} run={run} request={request} busy={busy} onDone={() => setEditing(false)} />
      ) : (
        <div className="mb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex flex-wrap items-center gap-2 text-on-surface">
              <span className="font-button-text">{cost.vendor_name}</span>
              {counted && <StatusBadge status={cost.status} />}
              {cost.archived && (
                <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold bg-surface-container-high text-on-surface-variant">
                  <Icon name="archive" size={14} /> Archived, not in totals
                </span>
              )}
            </p>
            {canEdit && (confirm ? (
              <Confirm busy={busy} text={`Remove ${cost.vendor_name} and its payments?`}
                onYes={() => run(() => request(`${base}/costs/${cost.id}`, json("DELETE")))}
                onNo={() => setConfirm(false)} />
            ) : confirmCopy ? (
              <Confirm
                busy={busy}
                yesLabel="Yes, make a copy"
                text={`Make a copy of ${cost.vendor_name}? It copies the costs, payment method, notes, link and vendor. It starts with no payments and no contract, and counts in your totals straight away.`}
                onYes={async () => {
                  const ok = await run(() => request(`${base}/costs/${cost.id}/duplicate`, json("POST")));
                  if (ok) setConfirmCopy(false);
                }}
                onNo={() => setConfirmCopy(false)}
              />
            ) : (
              <span className="flex flex-wrap gap-4">
                <button type="button" onClick={() => setEditing(true)} className={linkButton}>Edit</button>
                <button type="button" onClick={() => setConfirmCopy(true)} className={linkButton}>Duplicate</button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => request(`${base}/costs/${cost.id}`, json("PATCH", { archived: !cost.archived })))}
                  className={linkButton}
                >
                  {cost.archived ? "Restore" : "Archive"}
                </button>
                <button type="button" onClick={() => setConfirm(true)} className={dangerLink}>Remove</button>
              </span>
            ))}
          </div>
          <p className="text-on-surface-variant text-sm mt-1">
            {costLine(cost)}
            {" · "}Paid {formatCents(cost.paid_cents)}
            {" · "}Still to pay {formatCents(cost.remaining_cents)}
            {cost.overpaid_cents > 0 && <>{" · "}{overpaidNote(cost.overpaid_cents)}</>}
          </p>
          {cost.refundable_cents > 0 && (
            <p className="text-on-surface-variant text-sm">
              Refundable deposit {formatCents(cost.refundable_cents)}, not part of the cost
              {cost.refundable_paid_cents > 0 ? ` (${formatCents(cost.refundable_paid_cents)} paid, to come back)` : ""}
            </p>
          )}
          <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-on-surface-variant mt-1">
            <span>{CONTRACT_LABEL[cost.contract_status]}</span>
            {cost.payment_method && <span>Paying by {cost.payment_method}</span>}
            {cost.vendor && <span>Linked to {cost.vendor.name} on your Vendors page</span>}
            <OpenLink url={cost.link_url} label="Open link" />
          </p>
          {cost.notes && <p className="text-sm text-on-surface mt-2 whitespace-pre-line">{cost.notes}</p>}
          {cost.over_scheduled_cents > 0 && (
            <p className="flex items-start gap-1 text-sm text-error mt-2">
              <Icon name="warning" size={16} className="mt-0.5" />
              The payments you've added come to {formatCents(cost.over_scheduled_cents)} more than the cost
              ({formatCents(cost.committed_cents)}). Check the amounts, or update the cost.
            </p>
          )}
        </div>
      )}

      {cost.payments.length > 0 && (
        <ul className="divide-y divide-outline-variant/20 mb-2">
          {cost.payments.map((p) => (
            <PaymentRow key={p.id} base={base} payment={p} cost={cost} canEdit={canEdit} run={run} request={request} busy={busy} />
          ))}
        </ul>
      )}
      {canEdit && !cost.archived && <AddPaymentForm base={base} cost={cost} run={run} request={request} busy={busy} />}
    </div>
  );
}

function CostEditForm({
  base, cost, limits, vendors, run, request, busy, onDone,
}: { base: string; cost: Cost; limits: Limits; vendors: VendorRef[]; run: Run; request: Req; busy: boolean; onDone: () => void }) {
  const [vendor, setVendor] = useState(cost.vendor_name);
  const [vendorId, setVendorId] = useState(cost.vendor?.id ?? "");
  const [estimate, setEstimate] = useState(centsToInput(cost.estimated_cents));
  const [quote, setQuote] = useState(centsToInput(cost.quoted_cents));
  const [final, setFinal] = useState(centsToInput(cost.final_cents));
  const [contract, setContract] = useState<ContractStatus>(cost.contract_status);
  const [method, setMethod] = useState(cost.payment_method ?? "");
  const [link, setLink] = useState(cost.link_url ?? "");
  const [notes, setNotes] = useState(cost.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const id = cost.id;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const amounts = [estimate, quote, final].map((t) => amountOrError(t, setError));
    if (amounts.some((a) => a === undefined)) return;
    const [estimated_cents, quoted_cents, final_cents] = amounts;
    const ok = await run(() => request(`${base}/costs/${id}`, json("PATCH", {
      vendor_name: vendor, estimated_cents, quoted_cents, final_cents, contract_status: contract,
      payment_method: method || null, link_url: link || null, notes: notes || null,
      couple_vendor_id: vendorId || null,
    })));
    if (ok) onDone();
  };

  const pickVendor = (value: string) => {
    setVendorId(value);
    const picked = vendors.find((v) => v.id === value);
    if (picked && !vendor.trim()) setVendor(picked.name);
  };

  return (
    <form onSubmit={save} className="flex flex-wrap items-end gap-3 mb-3">
      <TextInput id={`cost-name-${id}`} label="Expense or vendor name" value={vendor} onChange={setVendor} wide />
      <VendorSelect id={`cost-vendor-${id}`} vendors={vendors} value={vendorId} onChange={pickVendor} />
      <MoneyInput id={`cost-est-${id}`} label="Estimated cost" value={estimate} onChange={setEstimate} />
      <MoneyInput id={`cost-quote-${id}`} label="Quoted cost" value={quote} onChange={setQuote} />
      <MoneyInput id={`cost-final-${id}`} label="Final cost" value={final} onChange={setFinal} />
      <SelectInput id={`cost-contract-${id}`} label="Contract" value={contract} onChange={(v) => setContract(v as ContractStatus)}>
        <option value="none">No contract yet</option>
        <option value="sent">Sent</option>
        <option value="signed">Signed</option>
      </SelectInput>
      <span className="flex flex-col gap-1">
        <label htmlFor={`cost-method-${id}`} className="text-xs text-on-surface-variant">How you'll pay (optional)</label>
        <input id={`cost-method-${id}`} list="budget-method-suggestions" autoComplete="off" maxLength={120}
          value={method} onChange={(e) => setMethod(e.target.value)} className={inputClass} />
      </span>
      <LinkInput id={`cost-link-${id}`} value={link} onChange={setLink} />
      <NotesInput id={`cost-notes-${id}`} value={notes} onChange={setNotes} />
      <p className="w-full text-xs text-on-surface-variant">
        The budget counts the final cost if you've entered one, otherwise the quote, otherwise the estimate.
      </p>
      {!cost.archived && (
        <OverNote
          limits={limits}
          before={cost.committed_cents}
          after={typedCost([final, quote, estimate], cost.scheduled_cents)}
        />
      )}
      <button type="submit" disabled={busy} className={primaryButton}>Save</button>
      <button type="button" onClick={onDone} className={linkButton}>Cancel</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
    </form>
  );
}

function AddCostForm({
  base, categoryId, limits, vendors, run, request, busy, suggestions, taken,
}: {
  base: string; categoryId: string; limits: Limits; vendors: VendorRef[]; run: Run; request: Req; busy: boolean;
  /** One-tap ideas for this category; those already used here aren't offered. */
  suggestions: string[]; taken: string[];
}) {
  const [vendor, setVendor] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [estimate, setEstimate] = useState("");
  const [quote, setQuote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const est = amountOrError(estimate, setError);
    const quoted = amountOrError(quote, setError);
    if (est === undefined || quoted === undefined) return;
    const ok = await run(() =>
      request(`${base}/categories/${categoryId}/costs`, json("POST", {
        vendor_name: vendor, estimated_cents: est, quoted_cents: quoted, couple_vendor_id: vendorId || null,
      })),
    );
    if (ok) { setVendor(""); setVendorId(""); setEstimate(""); setQuote(""); }
  };
  const pickVendor = (value: string) => {
    setVendorId(value);
    const picked = vendors.find((v) => v.id === value);
    if (picked && !vendor.trim()) setVendor(picked.name);
  };
  const used = new Set(taken.map((t) => t.trim().toLowerCase()));
  const ideas = suggestions.filter((s) => !used.has(s.toLowerCase()));
  const ideasId = `ideas-${categoryId}`;
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      {ideas.length > 0 && (
        <div className="w-full">
          <p id={ideasId} className="text-xs text-on-surface-variant mb-1">Ideas for this category: tap one to use it as the name</p>
          <div role="group" aria-labelledby={ideasId} className="flex flex-wrap gap-2">
            {ideas.map((idea) => (
              <button
                key={idea}
                type="button"
                aria-pressed={vendor === idea}
                onClick={() => setVendor(idea)}
                className={`rounded-full border px-3 py-1 text-xs ${vendor === idea ? "bg-primary text-on-primary border-primary" : "border-outline-variant/50 text-on-surface hover:border-primary"}`}
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
      <TextInput id={`new-cost-${categoryId}`} label="Expense or vendor name" value={vendor} onChange={setVendor} wide />
      <MoneyInput id={`new-est-${categoryId}`} label="Estimated (optional)" value={estimate} onChange={setEstimate} />
      <MoneyInput id={`new-quote-${categoryId}`} label="Quoted (optional)" value={quote} onChange={setQuote} />
      <button type="submit" disabled={busy} className={primaryButton}>Add expense</button>
      <OverNote limits={limits} before={0} after={typedCost([null, quote, estimate], 0)} />
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
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

/** A note, never a block: saving this would take the category or the total over. */
function OverNote({ limits, before, after }: { limits: Limits; before: number; after: number | null }) {
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
      {over.length > 0 && <p className="text-xs text-on-surface-variant pl-5">Over {amounts.join(", ")}.</p>}
    </div>
  );
}

// ---- Payment ------------------------------------------------------------------------

const KIND_LABEL = { deposit: "Deposit", payment: "Payment" } as const;

function PaymentRow({
  base, payment, cost, canEdit, run, request, busy,
}: { base: string; payment: Payment; cost: Cost; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const [confirmOverpay, setConfirmOverpay] = useState(false);
  const [editing, setEditing] = useState(false);
  const paidUrl = `${base}/payments/${payment.id}/paid`;

  const tick = (checked: boolean) => {
    // A warning, not a block: the couple may really have paid more than agreed.
    if (checked && payment.would_overpay_cents > 0) { setConfirmOverpay(true); return; }
    run(() => request(paidUrl, json("PUT", { paid: checked })));
  };

  if (editing) {
    return (
      <li className="py-2">
        <PaymentEditForm base={base} payment={payment} run={run} request={request} busy={busy} onDone={() => setEditing(false)} />
      </li>
    );
  }

  const due = payment.due_on ? `due ${formatDay(payment.due_on)}` : "no due date";
  const paidOn = payment.paid_on ? formatDay(payment.paid_on) : payment.paid_at ? formatInstantDay(payment.paid_at) : "";
  const paidNote = payment.paid
    ? `Paid${paidOn ? ` on ${paidOn}` : ""}${payment.paid_by_name ? `, ticked by ${payment.paid_by_name}` : ""}`
    : "Not paid yet";
  const details = [payment.method && `By ${payment.method}`, payment.reference && `Ref. ${payment.reference}`].filter(Boolean);
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
        <span className={`block text-xs ${payment.paid ? "text-primary" : "text-on-surface-variant"}`}>{paidNote}</span>
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
              <button type="button" disabled={busy} className="text-error font-bold underline-offset-4 hover:underline"
                onClick={async () => { setConfirmOverpay(false); await run(() => request(paidUrl, json("PUT", { paid: true }))); }}>
                Yes, tick it
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirmOverpay(false)} className={linkButton}>Cancel</button>
            </span>
          ) : (
            <label className="flex items-center gap-2 cursor-pointer">
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
              onYes={() => run(() => request(`${base}/payments/${payment.id}`, json("DELETE")))}
              onNo={() => setConfirm(false)} />
          ) : (
            <span className="flex gap-4">
              <button type="button" onClick={() => setEditing(true)} className={linkButton}>Edit</button>
              <button type="button" onClick={() => setConfirm(true)} className={dangerLink}>Remove</button>
            </span>
          )}
        </>
      )}
    </li>
  );
}

function PaymentEditForm({
  base, payment, run, request, busy, onDone,
}: { base: string; payment: Payment; run: Run; request: Req; busy: boolean; onDone: () => void }) {
  const [kind, setKind] = useState<"deposit" | "payment">(payment.kind);
  const [amount, setAmount] = useState(centsToInput(payment.amount_cents));
  const [dueOn, setDueOn] = useState(payment.due_on ?? "");
  const [refundable, setRefundable] = useState(payment.refundable);
  const [method, setMethod] = useState(payment.method ?? "");
  const [reference, setReference] = useState(payment.reference ?? "");
  const [link, setLink] = useState(payment.link_url ?? "");
  const [notes, setNotes] = useState(payment.notes ?? "");
  const [paidOn, setPaidOn] = useState(payment.paid_on ?? "");
  const [error, setError] = useState<string | null>(null);
  const id = payment.id;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (!cents) { setError("Please enter how much this payment is."); return; }
    const ok = await run(() =>
      request(`${base}/payments/${id}`, json("PATCH", {
        kind, amount_cents: cents, due_on: dueOn || null, refundable,
        method: method || null, reference: reference || null, link_url: link || null, notes: notes || null,
        ...(payment.paid ? { paid_on: paidOn || null } : {}),
      })),
    );
    if (ok) onDone();
  };

  return (
    <form onSubmit={save} className="flex flex-wrap items-end gap-3">
      <SelectInput id={`edit-kind-${id}`} label="Type" value={kind} onChange={(v) => setKind(v as "deposit" | "payment")}>
        <option value="deposit">Deposit</option>
        <option value="payment">Payment</option>
      </SelectInput>
      <MoneyInput id={`edit-amount-${id}`} label="Amount" value={amount} onChange={setAmount} required />
      <span className="flex flex-col gap-1">
        <label htmlFor={`edit-due-${id}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`edit-due-${id}`} type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} className={inputClass} />
      </span>
      {payment.paid && (
        <span className="flex flex-col gap-1">
          <label htmlFor={`edit-paidon-${id}`} className="text-xs text-on-surface-variant">Date paid (optional)</label>
          <input id={`edit-paidon-${id}`} type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} className={inputClass} />
        </span>
      )}
      <span className="flex flex-col gap-1">
        <label htmlFor={`edit-method-${id}`} className="text-xs text-on-surface-variant">Paid by (optional)</label>
        <input id={`edit-method-${id}`} list="budget-method-suggestions" autoComplete="off" maxLength={120}
          value={method} onChange={(e) => setMethod(e.target.value)} className={inputClass} />
      </span>
      <TextInput id={`edit-ref-${id}`} label="Reference, like a check number (optional)" value={reference} onChange={setReference} required={false} />
      <label className="flex items-center gap-2 text-sm cursor-pointer pb-2">
        <input type="checkbox" checked={refundable} onChange={(e) => setRefundable(e.target.checked)} className="h-4 w-4 accent-primary" />
        Refundable security deposit (not part of the cost)
      </label>
      <LinkInput id={`edit-link-${id}`} value={link} onChange={setLink} />
      <NotesInput id={`edit-notes-${id}`} value={notes} onChange={setNotes} />
      <button type="submit" disabled={busy} className={primaryButton}>Save</button>
      <button type="button" onClick={onDone} className={linkButton}>Cancel</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
    </form>
  );
}

function AddPaymentForm({ base, cost, run, request, busy }: { base: string; cost: Cost; run: Run; request: Req; busy: boolean }) {
  const [kind, setKind] = useState<"deposit" | "payment">("deposit");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [refundable, setRefundable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const costId = cost.id;

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
    const ok = await run(() =>
      request(`${base}/costs/${costId}/payments`, json("POST", { kind, amount_cents: cents, due_on: due || null, refundable })),
    );
    if (ok) { setAmount(""); setDue(""); setKind("payment"); setRefundable(false); }
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 pt-2">
      <SelectInput id={`pay-kind-${costId}`} label="Type" value={kind} onChange={(v) => setKind(v as "deposit" | "payment")}>
        <option value="deposit">Deposit</option>
        <option value="payment">Payment</option>
      </SelectInput>
      <MoneyInput id={`pay-amount-${costId}`} label="Amount" value={amount} onChange={setAmount} required />
      <span className="flex flex-col gap-1">
        <label htmlFor={`pay-due-${costId}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`pay-due-${costId}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputClass} />
      </span>
      <label className="flex items-center gap-2 text-sm cursor-pointer pb-2">
        <input type="checkbox" checked={refundable} onChange={(e) => setRefundable(e.target.checked)} className="h-4 w-4 accent-primary" />
        Refundable security deposit
      </label>
      <button type="submit" disabled={busy} className={primaryButton}>Add payment</button>
      {over > 0 && (
        <p role="status" className="w-full flex items-start gap-1 text-sm text-error">
          <Icon name="warning" size={16} className="mt-0.5" />
          With this one, the payments come to {formatCents(over)} more than the cost ({formatCents(cost.committed_cents)}).
          You can still add it.
        </p>
      )}
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
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
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const catName = (id: string | null) => categories.find((c) => c.id === id)?.name;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (cents === null) { setError("Please enter how much they're contributing."); return; }
    const ok = await run(() =>
      request(`${base}/contributions`, json("POST", { contributor: who, amount_cents: cents, category_id: categoryId || null })),
    );
    if (ok) { setWho(""); setAmount(""); setCategoryId(""); }
  };

  return (
    <section aria-labelledby="contrib-heading" className="mb-10">
      <h2 id="contrib-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">Who's contributing</h2>
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
                    onYes={() => run(() => request(`${base}/contributions/${c.id}`, json("DELETE")))}
                    onNo={() => setConfirm(null)} />
                ) : (
                  <button type="button" onClick={() => setConfirm(c.id)} className={dangerLink}>Remove</button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <TextInput id="contrib-who" label="Who" value={who} onChange={setWho} placeholder="For example, Groom's parents" wide />
          <MoneyInput id="contrib-amount" label="Amount" value={amount} onChange={setAmount} required />
          <span className="flex flex-col gap-1">
            <label htmlFor="contrib-cat" className="text-xs text-on-surface-variant">Towards (optional)</label>
            <select id="contrib-cat" value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className={inputClass}>
              <option value="">The whole budget</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </span>
          <button type="submit" disabled={busy} className={primaryButton}>Add contribution</button>
          {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
        </form>
      )}
    </section>
  );
}
