import { useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import { AMOUNT_HINT, centsToInput, formatCents, formatDay, parseDollars } from "./money";
import type { Category, Contribution, Cost, DuePayment, Payment, Run } from "./types";

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

function Stat({ label, cents, tone }: { label: string; cents: number | null; tone?: "error" }) {
  return (
    <div>
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p className={`font-button-text ${tone === "error" ? "text-error" : "text-on-surface"}`}>
        {cents === null ? "Not set" : formatCents(cents)}
      </p>
    </div>
  );
}

function Confirm({ text, onYes, onNo, busy }: { text: ReactNode; onYes: () => void; onNo: () => void; busy: boolean }) {
  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <span>{text}</span>
      <button type="button" disabled={busy} onClick={onYes} className="text-error font-bold underline-offset-4 hover:underline">
        Yes, remove
      </button>
      <button type="button" disabled={busy} onClick={onNo} className={linkButton}>Cancel</button>
    </span>
  );
}

// ---- Category -----------------------------------------------------------------------

export function CategoryCard({
  base, category, canEdit, run, request, busy,
}: { base: string; category: Category; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(category.name);
  const [planned, setPlanned] = useState(centsToInput(category.planned_cents));
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(category.costs.length > 0);

  const planned_cents = category.planned_cents;
  const over = planned_cents !== null && category.committed_cents > planned_cents;
  const pct = planned_cents ? Math.min(100, Math.round((category.committed_cents * 100) / planned_cents)) : 0;

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
          <MoneyInput id={`cat-plan-${category.id}`} label="Planned" value={planned} onChange={setPlanned} />
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <h3 className="font-headline-sm text-lg text-on-surface">{category.name}</h3>
          {canEdit && (
            confirm ? (
              <Confirm
                busy={busy}
                text={category.costs.length
                  ? `Remove ${category.name} and its ${category.costs.length} vendor cost${category.costs.length > 1 ? "s" : ""} and payments?`
                  : `Remove ${category.name}?`}
                onYes={() => run(() => request(`${base}/categories/${category.id}`, json("DELETE")))}
                onNo={() => setConfirm(false)}
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

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-3">
        <Stat label="Planned" cents={planned_cents} />
        <Stat label="Committed (quoted)" cents={category.committed_cents} tone={over ? "error" : undefined} />
        <Stat label="Paid" cents={category.paid_cents} />
        <Stat label="Still to pay" cents={category.remaining_cents} />
      </div>
      {planned_cents ? (
        <div className="w-full bg-surface-container-low h-2 rounded-full mb-2" aria-hidden>
          <div className={`h-2 rounded-full ${over ? "bg-error" : "bg-primary-container"}`} style={{ width: `${pct}%` }} />
        </div>
      ) : null}
      {over && planned_cents !== null && (
        <p className="text-sm text-error mb-2">
          Quotes are {formatCents(category.committed_cents - planned_cents)} over what you planned.
        </p>
      )}

      <button type="button" onClick={() => setOpen((o) => !o)} className={`${linkButton} mt-2`} aria-expanded={open}>
        {open ? "Hide vendor costs" : `Show vendor costs (${category.costs.length})`}
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {category.costs.map((cost) => (
            <CostBlock key={cost.id} base={base} cost={cost} canEdit={canEdit} run={run} request={request} busy={busy} />
          ))}
          {category.costs.length === 0 && (
            <p className="text-sm text-on-surface-variant">No vendor costs recorded yet.</p>
          )}
          {canEdit && <AddCostForm base={base} categoryId={category.id} run={run} request={request} busy={busy} />}
        </div>
      )}
    </section>
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
      <MoneyInput id="new-cat-plan" label="Planned (optional)" value={planned} onChange={setPlanned} />
      <button type="submit" disabled={busy} className={primaryButton}>Add category</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
    </form>
  );
}

// ---- Vendor cost --------------------------------------------------------------------

function CostBlock({ base, cost, canEdit, run, request, busy }: { base: string; cost: Cost; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [editing, setEditing] = useState(false);
  const [vendor, setVendor] = useState(cost.vendor_name);
  const [quote, setQuote] = useState(centsToInput(cost.quoted_cents));
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(quote, setError);
    if (cents === undefined) return;
    const ok = await run(() => request(`${base}/costs/${cost.id}`, json("PATCH", { vendor_name: vendor, quoted_cents: cents })));
    if (ok) setEditing(false);
  };

  return (
    <div className="border border-outline-variant/30 rounded-[1.5rem] p-4">
      {editing ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 mb-3">
          <TextInput id={`cost-name-${cost.id}`} label="Vendor" value={vendor} onChange={setVendor} wide />
          <MoneyInput id={`cost-quote-${cost.id}`} label="Quoted price" value={quote} onChange={setQuote} />
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
        </form>
      ) : (
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
          <p className="text-on-surface">
            <span className="font-button-text">{cost.vendor_name}</span>
            <span className="text-on-surface-variant text-sm">
              {" · "}
              {cost.quoted_cents === null ? "No quote recorded" : `Quoted ${formatCents(cost.quoted_cents)}`}
              {" · "}Paid {formatCents(cost.paid_cents)}
            </span>
          </p>
          {canEdit && (confirm ? (
            <Confirm busy={busy} text={`Remove ${cost.vendor_name} and its payments?`}
              onYes={() => run(() => request(`${base}/costs/${cost.id}`, json("DELETE")))}
              onNo={() => setConfirm(false)} />
          ) : (
            <span className="flex gap-4">
              <button
                type="button"
                onClick={() => { setVendor(cost.vendor_name); setQuote(centsToInput(cost.quoted_cents)); setEditing(true); }}
                className={linkButton}
              >
                Edit
              </button>
              <button type="button" onClick={() => setConfirm(true)} className={dangerLink}>Remove</button>
            </span>
          ))}
        </div>
      )}
      {error && <p role="alert" className="text-sm text-error mb-2">{error}</p>}

      {cost.payments.length > 0 && (
        <ul className="divide-y divide-outline-variant/20 mb-2">
          {cost.payments.map((p) => (
            <PaymentRow key={p.id} base={base} payment={p} canEdit={canEdit} run={run} request={request} busy={busy} />
          ))}
        </ul>
      )}
      {canEdit && <AddPaymentForm base={base} costId={cost.id} run={run} request={request} busy={busy} />}
    </div>
  );
}

function AddCostForm({ base, categoryId, run, request, busy }: { base: string; categoryId: string; run: Run; request: Req; busy: boolean }) {
  const [vendor, setVendor] = useState("");
  const [quote, setQuote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(quote, setError);
    if (cents === undefined) return;
    const ok = await run(() =>
      request(`${base}/categories/${categoryId}/costs`, json("POST", { vendor_name: vendor, quoted_cents: cents })),
    );
    if (ok) { setVendor(""); setQuote(""); }
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <TextInput id={`new-cost-${categoryId}`} label="Vendor name" value={vendor} onChange={setVendor} wide />
      <MoneyInput id={`new-quote-${categoryId}`} label="Quoted price (optional)" value={quote} onChange={setQuote} />
      <button type="submit" disabled={busy} className={primaryButton}>Add vendor cost</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
    </form>
  );
}

// ---- Payment ------------------------------------------------------------------------

const KIND_LABEL = { deposit: "Deposit", payment: "Payment" } as const;

function PaymentRow({ base, payment, canEdit, run, request, busy }: { base: string; payment: Payment; canEdit: boolean; run: Run; request: Req; busy: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState<"deposit" | "payment">(payment.kind);
  const [amount, setAmount] = useState(centsToInput(payment.amount_cents));
  const [dueOn, setDueOn] = useState(payment.due_on ?? "");
  const [error, setError] = useState<string | null>(null);

  const startEdit = () => {
    setKind(payment.kind);
    setAmount(centsToInput(payment.amount_cents));
    setDueOn(payment.due_on ?? "");
    setError(null);
    setEditing(true);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (!cents) { setError("Please enter how much this payment is."); return; }
    const ok = await run(() =>
      request(`${base}/payments/${payment.id}`, json("PATCH", { kind, amount_cents: cents, due_on: dueOn || null })),
    );
    if (ok) setEditing(false);
  };

  if (editing) {
    return (
      <li className="py-2">
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <span className="flex flex-col gap-1">
            <label htmlFor={`edit-kind-${payment.id}`} className="text-xs text-on-surface-variant">Type</label>
            <select id={`edit-kind-${payment.id}`} value={kind} onChange={(e) => setKind(e.target.value as "deposit" | "payment")} className={inputClass}>
              <option value="deposit">Deposit</option>
              <option value="payment">Payment</option>
            </select>
          </span>
          <MoneyInput id={`edit-amount-${payment.id}`} label="Amount" value={amount} onChange={setAmount} required />
          <span className="flex flex-col gap-1">
            <label htmlFor={`edit-due-${payment.id}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
            <input id={`edit-due-${payment.id}`} type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} className={inputClass} />
          </span>
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
          {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
        </form>
      </li>
    );
  }

  const due = payment.due_on ? `due ${formatDay(payment.due_on)}` : "no due date";
  const paidNote = payment.paid
    ? `Marked paid${payment.paid_by_name ? ` by ${payment.paid_by_name}` : ""}${payment.paid_at ? ` on ${formatDay(payment.paid_at.slice(0, 10))}` : ""}`
    : "Not paid yet";
  return (
    <li className="py-2 flex flex-wrap items-center gap-3 text-sm">
      <span className="flex-grow">
        {KIND_LABEL[payment.kind]} of <span className="font-button-text">{formatCents(payment.amount_cents)}</span>, {due}
        <span className={`block text-xs ${payment.paid ? "text-primary" : "text-on-surface-variant"}`}>{paidNote}</span>
      </span>
      {canEdit && (
        <>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={payment.paid}
              disabled={busy}
              onChange={(e) =>
                run(() => request(`${base}/payments/${payment.id}/paid`, json("PUT", { paid: e.target.checked })))
              }
              className="h-4 w-4 accent-primary"
            />
            Paid
          </label>
          {confirm ? (
            <Confirm busy={busy} text="Remove this payment?"
              onYes={() => run(() => request(`${base}/payments/${payment.id}`, json("DELETE")))}
              onNo={() => setConfirm(false)} />
          ) : (
            <span className="flex gap-4">
              <button type="button" onClick={startEdit} className={linkButton}>Edit</button>
              <button type="button" onClick={() => setConfirm(true)} className={dangerLink}>Remove</button>
            </span>
          )}
        </>
      )}
    </li>
  );
}

function AddPaymentForm({ base, costId, run, request, busy }: { base: string; costId: string; run: Run; request: Req; busy: boolean }) {
  const [kind, setKind] = useState<"deposit" | "payment">("deposit");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = amountOrError(amount, setError);
    if (cents === undefined) return;
    if (!cents) { setError("Please enter how much this payment is."); return; }
    const ok = await run(() =>
      request(`${base}/costs/${costId}/payments`, json("POST", { kind, amount_cents: cents, due_on: due || null })),
    );
    if (ok) { setAmount(""); setDue(""); setKind("payment"); }
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 pt-2">
      <span className="flex flex-col gap-1">
        <label htmlFor={`pay-kind-${costId}`} className="text-xs text-on-surface-variant">Type</label>
        <select id={`pay-kind-${costId}`} value={kind} onChange={(e) => setKind(e.target.value as "deposit" | "payment")} className={inputClass}>
          <option value="deposit">Deposit</option>
          <option value="payment">Payment</option>
        </select>
      </span>
      <MoneyInput id={`pay-amount-${costId}`} label="Amount" value={amount} onChange={setAmount} required />
      <span className="flex flex-col gap-1">
        <label htmlFor={`pay-due-${costId}`} className="text-xs text-on-surface-variant">Due date (optional)</label>
        <input id={`pay-due-${costId}`} type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputClass} />
      </span>
      <button type="submit" disabled={busy} className={primaryButton}>Add payment</button>
      {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
    </form>
  );
}

// ---- Next payments due --------------------------------------------------------------

export function NextDue({ items }: { items: DuePayment[] }) {
  return (
    <section aria-labelledby="due-heading" className="mb-10">
      <h2 id="due-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">Next payments due</h2>
      <p className="text-xs text-on-surface-variant mb-3">
        Shown here only. The app doesn't send reminders or pay anyone.
      </p>
      {items.length === 0 ? (
        <p className="text-sm text-on-surface-variant">Nothing unpaid. Payments you add to a vendor cost show here.</p>
      ) : (
        <ul className="divide-y divide-outline-variant/30 border-y border-outline-variant/30">
          {items.map((d) => (
            <li key={d.payment_id} className="py-3 flex flex-wrap items-center justify-between gap-2">
              <span>
                <span className="text-on-surface">{d.vendor_name}</span>
                <span className="text-sm text-on-surface-variant"> · {d.category_name} · {KIND_LABEL[d.kind]}</span>
              </span>
              <span className="flex items-center gap-3">
                <span className="font-button-text text-on-surface">{formatCents(d.amount_cents)}</span>
                {d.overdue ? (
                  <span className="flex items-center gap-1 text-sm text-error font-bold">
                    <Icon name="warning" size={16} /> Overdue, was due {formatDay(d.due_on as string)}
                  </span>
                ) : (
                  <span className="text-sm text-on-surface-variant">
                    {d.due_on ? `Due ${formatDay(d.due_on)}` : "No due date"}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
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
