import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useApi } from "../../api/useApi";
import { useActiveWedding } from "../WeddingProvider";
import { AMOUNT_HINT, parseDollars } from "./budget/money";

// Starting values from what the couple told us (docs/product/wedding.md, PD-009).
// Every one of them can be changed here, and later in the app.
const DEFAULTS = {
  place: "Chicago, IL, United States",
  ceremony_type: "Jewish",
  guest_count_estimate: 225,
  wedding_date: "2027-10-23",
};

const CEREMONY_TYPES = [
  "Jewish",
  "Interfaith",
  "Civil or non-religious",
  "Christian",
  "Hindu",
  "Muslim",
  "Other",
];

const inputClass =
  "w-full rounded-2xl border border-outline-variant/40 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant/60 focus:border-primary focus:outline-none transition-colors";
const labelClass = "block font-button-text text-button-text text-on-surface-variant mb-2";
const hintClass = "mt-2 text-sm text-on-surface-variant";
const optional = <span className="text-on-surface-variant/60">(optional)</span>;

export function Intake() {
  const { request, loading, error } = useApi();
  // The date hint follows the couple's "This date is confirmed" switch (B48). A new
  // wedding starts unconfirmed, so the form says "provisional" until they switch it on.
  const { activeWedding, refetch, setActiveWedding } = useActiveWedding();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    couple_name: "",
    region: DEFAULTS.place,
    ceremony_type: DEFAULTS.ceremony_type,
    guest_count_estimate: String(DEFAULTS.guest_count_estimate),
    budget: "",
    wedding_date: DEFAULTS.wedding_date,
    style_notes: "",
  });
  const [budgetError, setBudgetError] = useState<string | null>(null);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    // Whole cents, no float arithmetic (AGENTS.md rule 4). Blank means "not set yet".
    const cents = parseDollars(form.budget);
    if (cents === undefined || cents === 0) {
      setBudgetError(cents === 0 ? "Leave the budget blank if you haven't decided it yet." : AMOUNT_HINT);
      return;
    }
    setBudgetError(null);

    const payload: Record<string, unknown> = {
      region: form.region.trim(),
      ceremony_type: form.ceremony_type,
      guest_count_estimate: Number(form.guest_count_estimate),
      currency: "USD",
      couple_name: form.couple_name.trim() || undefined,
      style_notes: form.style_notes.trim() || undefined,
    };
    if (cents !== null) payload.budget_total_cents = cents;
    if (form.wedding_date) payload.wedding_date = form.wedding_date;

    try {
      const created = await request<{ id: string }>("/weddings/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refetch();
      setActiveWedding(created.id);
      // The dashboard shows a short "building" state while the planner checks the
      // details; saving never contacts a vendor or starts vendor matching (PD-003).
      navigate("/wedding", { replace: true });
    } catch {
      // error rendered below via useApi state
    }
  }

  return (
    <div className="min-h-screen bg-background px-6 py-12 md:py-20 flex justify-center">
      <div className="w-full max-w-xl">
        <p className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant mb-3">
          Let's begin
        </p>
        <h1 className="font-display-sm text-display-sm text-on-surface mb-2">Tell us about your wedding</h1>
        <p className="text-body-md text-on-surface-variant mb-8">
          We've filled in what you've told us so far. Check it, change anything that's
          different, and you can edit all of it later.
        </p>

        {error && <p role="alert" className="mb-4 text-sm text-error">{error}</p>}

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <div>
            <label htmlFor="intake-names" className={labelClass}>Your names {optional}</label>
            <input id="intake-names" className={inputClass} type="text" placeholder="e.g. Sam & Alex"
              value={form.couple_name} onChange={(e) => set("couple_name", e.target.value)} />
          </div>

          <div>
            <label htmlFor="intake-place" className={labelClass}>Where</label>
            <input id="intake-place" className={inputClass} type="text" required maxLength={120}
              value={form.region} onChange={(e) => set("region", e.target.value)} />
            <p className={hintClass}>City, state and country.</p>
          </div>

          <div>
            <label htmlFor="intake-ceremony" className={labelClass}>Ceremony</label>
            <select id="intake-ceremony" className={inputClass} value={form.ceremony_type}
              onChange={(e) => set("ceremony_type", e.target.value)}>
              {CEREMONY_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <label htmlFor="intake-guests" className={labelClass}>Guests invited</label>
            <input id="intake-guests" className={inputClass} type="number" min={1} step={1} required
              value={form.guest_count_estimate}
              onChange={(e) => set("guest_count_estimate", e.target.value)} />
          </div>

          <div>
            <label htmlFor="intake-budget" className={labelClass}>Total budget in US dollars ($) {optional}</label>
            <div className="relative">
              <span aria-hidden className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant">$</span>
              <input id="intake-budget" className={`${inputClass} pl-8`} inputMode="decimal" autoComplete="off"
                placeholder="Not set yet" value={form.budget}
                aria-describedby="intake-budget-hint" aria-invalid={budgetError ? true : undefined}
                onChange={(e) => { set("budget", e.target.value); setBudgetError(null); }} />
            </div>
            {budgetError ? (
              <p id="intake-budget-hint" role="alert" className="mt-2 text-sm text-error">{budgetError}</p>
            ) : (
              <p id="intake-budget-hint" className={hintClass}>
                Still deciding? Leave it blank and add it later on the Budget screen.
              </p>
            )}
          </div>

          <div>
            <label htmlFor="intake-date" className={labelClass}>Wedding date {optional}</label>
            <input id="intake-date" className={inputClass} type="date" aria-describedby="intake-date-hint"
              value={form.wedding_date} onChange={(e) => set("wedding_date", e.target.value)} />
            <p id="intake-date-hint" className={hintClass}>
              {activeWedding?.wedding_date_confirmed
                ? "You can change this any time."
                : "Provisional, you can change this any time."}
            </p>
          </div>

          <div>
            <label htmlFor="intake-style" className={labelClass}>Style notes {optional}</label>
            <textarea id="intake-style" className={inputClass} rows={3}
              placeholder="e.g. industrial loft, relaxed, live band, documentary photography"
              value={form.style_notes} onChange={(e) => set("style_notes", e.target.value)} />
          </div>

          <button type="submit" disabled={loading}
            className="mt-2 rounded-full bg-primary text-on-primary px-8 py-3.5 font-button-text text-button-text disabled:opacity-60 hover:opacity-90 transition-opacity">
            {loading ? "Saving your details…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
