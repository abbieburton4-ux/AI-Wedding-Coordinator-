import { useCallback, useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { Icon } from "../../shared/Icon";
import { SampleDataNotice } from "../../shared/SampleDataNotice";
import { useApi, USE_FASTAPI_BACKEND } from "../../api";
import { useActiveWedding } from "../WeddingProvider";
import { AMOUNT_HINT, centsToInput, formatCents, parseDollars } from "./budget/money";
import {
  AddCategoryForm, CategoryCard, Contributions, MoneyInput, NextDue, linkButton, primaryButton,
} from "./budget/parts";
import type { Overview, Run, SplitSuggestion } from "./budget/types";

// Shown only when the backend is switched off (USE_FASTAPI_BACKEND), and labelled as sample.
const STATIC_CATEGORIES = [
  { name: "Attire & Beauty", spent: "$4,200", total: "$5,000" },
  { name: "Floral & Decor", spent: "$3,100", total: "$4,000" },
];

/**
 * The couple's budget (PD-004): an optional total, categories with planned amounts,
 * vendor costs with deposits and payments, who's contributing, and what's due next.
 * Everyone on the access list can see it; only owners and editors see edit controls,
 * and the API refuses edits from anyone else.
 */
export function Budget() {
  const { activeWedding, myLevel } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { request } = useApi();
  const base = `/weddings/${weddingId}/budget`;
  const canEdit = myLevel === "owner" || myLevel === "editor";

  const [overview, setOverview] = useState<Overview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;
    try {
      setOverview(await request<Overview>(`/weddings/${weddingId}/budget/overview`));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Couldn't load the budget.");
    }
  }, [weddingId, request]);

  useEffect(() => {
    load();
  }, [load]);

  const run: Run = useCallback(
    async (fn) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
        await load();
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "That didn't work. Please try again.");
        return false;
      } finally {
        setBusy(false);
      }
    },
    [load],
  );

  if (!USE_FASTAPI_BACKEND) return <SampleBudget />;

  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <div className="mb-8">
        <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary mb-2">
          Budget
        </h1>
        <p className="text-on-surface-variant">
          Plan each category, record what vendors quote, and tick off payments as you make them. Amounts are in US dollars.
        </p>
        {!canEdit && myLevel && (
          <p className="text-sm text-on-surface-variant mt-2">You can see the budget but not change it.</p>
        )}
      </div>

      {error && (
        <p role="alert" className="mb-6 text-sm text-error">{error}</p>
      )}

      {loadError ? (
        <div role="alert" className="text-on-surface">
          <p className="mb-2">The budget didn't load: {loadError}</p>
          <button type="button" onClick={load} className={linkButton}>Try again</button>
        </div>
      ) : !overview ? (
        <div className="flex flex-col items-center mb-12" aria-busy="true">
          <div className="w-48 h-48 rounded-full bg-surface-container-low animate-pulse" />
          <p className="sr-only">Loading the budget…</p>
        </div>
      ) : (
        <>
          <Summary overview={overview} />
          <TotalCard base={base} totalCents={overview.totals.total_cents} canEdit={canEdit} run={run} request={request} busy={busy} />
          {canEdit && overview.totals.total_cents !== null && (
            <SplitPanel base={base} request={request} run={run} busy={busy} />
          )}

          <NextDue items={overview.next_due} />

          <section aria-labelledby="cat-heading" className="mb-10">
            <h2 id="cat-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">Categories</h2>
            {overview.categories.length === 0 && (
              <p className="text-sm text-on-surface-variant mb-4">
                {canEdit
                  ? "No categories yet. Add your first one below."
                  : "No categories yet."}
              </p>
            )}
            <div className="space-y-6 mb-6">
              {overview.categories.map((cat) => (
                <CategoryCard key={cat.id} base={base} category={cat} canEdit={canEdit} run={run} request={request} busy={busy} />
              ))}
            </div>
            {canEdit && <AddCategoryForm base={base} run={run} request={request} busy={busy} />}
          </section>

          <Contributions
            base={base}
            items={overview.contributions}
            categories={overview.categories}
            totalCents={overview.totals.total_cents}
            sumCents={overview.totals.contributions_cents}
            canEdit={canEdit}
            run={run}
            request={request}
            busy={busy}
          />
        </>
      )}
    </main>
  );
}

/** The ring and the headline numbers, from real totals only (B30). */
function Summary({ overview }: { overview: Overview }) {
  const t = overview.totals;
  // Measured against the couple's total when set, otherwise against what they've planned.
  const against = t.total_cents ?? (t.planned_cents > 0 ? t.planned_cents : null);
  const againstLabel = t.total_cents !== null ? "of your total budget" : "of what you've planned";
  const pct = against ? Math.min(100, Math.round((t.paid_cents * 100) / against)) : 0;
  const overTotal = t.total_cents !== null && t.committed_cents > t.total_cents;

  return (
    <div className="mb-10">
      {against !== null && (
        <div className="flex flex-col items-center mb-6">
          <div
            className="chart-donut shadow-sm"
            style={{ "--ring-pct": `${pct}%` } as CSSProperties}
            role="img"
            aria-label={`${pct}% paid ${againstLabel}`}
          >
            <div className="absolute flex flex-col items-center justify-center z-10 text-center">
              <span className="font-body-md text-on-surface-variant text-xs">Paid so far</span>
              <span className="font-headline-sm text-headline-sm text-on-surface">{formatCents(t.paid_cents)}</span>
              <span className="text-[11px] text-outline px-6">{againstLabel}, {formatCents(against)}</span>
            </div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-surface-container-lowest rounded-[2rem] border border-outline-variant/20 p-5">
        <Figure label="Planned" cents={t.planned_cents} />
        <Figure label="Committed (quoted)" cents={t.committed_cents} />
        <Figure label="Paid" cents={t.paid_cents} />
        <Figure label="Still to pay" cents={t.remaining_cents} />
        {t.total_cents !== null && (
          <Figure
            label="Left of your total"
            cents={t.total_cents - t.committed_cents}
            note="Your total minus everything quoted"
          />
        )}
      </div>
      {overTotal && t.total_cents !== null && (
        <div className="bg-error-container/15 border border-error-container/40 rounded-[2rem] p-4 mt-4 flex items-start gap-3">
          <Icon name="warning" size={22} className="text-error mt-0.5" />
          <p className="text-sm text-on-surface">
            What you've committed to is {formatCents(t.committed_cents - t.total_cents)} more than your total budget.
          </p>
        </div>
      )}
    </div>
  );
}

function Figure({ label, cents, note }: { label: string; cents: number; note?: string }) {
  return (
    <div>
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p className={`font-headline-sm text-lg ${cents < 0 ? "text-error" : "text-on-surface"}`}>{formatCents(cents)}</p>
      {note && <p className="text-[11px] text-on-surface-variant">{note}</p>}
    </div>
  );
}

function TotalCard({
  base, totalCents, canEdit, run, request, busy,
}: {
  base: string; totalCents: number | null; canEdit: boolean; run: Run;
  request: ReturnType<typeof useApi>["request"]; busy: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const cents = parseDollars(value);
    if (cents === undefined) { setError(AMOUNT_HINT); return; }
    const ok = await run(() =>
      request(`${base}/total`, { method: "PUT", body: JSON.stringify({ total_cents: cents || null }) }),
    );
    if (ok) setEditing(false);
  };

  return (
    <section aria-labelledby="total-heading" className="mb-10 flex flex-wrap items-end gap-4">
      <div className="flex-grow">
        <h2 id="total-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">Total budget</h2>
        {!editing && (
          <p className="text-on-surface">
            {totalCents === null ? (
              <span className="text-on-surface-variant">Not set yet. Everything else works without it.</span>
            ) : (
              <span className="font-headline-sm text-lg">{formatCents(totalCents)}</span>
            )}
          </p>
        )}
      </div>
      {editing ? (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <MoneyInput id="total-budget" label="Total budget (leave empty to clear)" value={value} onChange={setValue} />
          <button type="submit" disabled={busy} className={primaryButton}>Save</button>
          <button type="button" onClick={() => setEditing(false)} className={linkButton}>Cancel</button>
          {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
        </form>
      ) : (
        canEdit && (
          <button
            type="button"
            onClick={() => { setValue(centsToInput(totalCents)); setEditing(true); }}
            className={linkButton}
          >
            {totalCents === null ? "Set your total" : "Change"}
          </button>
        )
      )}
    </section>
  );
}

/** The AI starting split (PD-004 call b). Nothing is saved until the couple choose to use it. */
function SplitPanel({
  base, request, run, busy,
}: { base: string; request: ReturnType<typeof useApi>["request"]; run: Run; busy: boolean }) {
  const [suggestion, setSuggestion] = useState<SplitSuggestion | null>(null);
  const [amounts, setAmounts] = useState<string[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    setAsking(true);
    setError(null);
    try {
      const s = await request<SplitSuggestion>(`${base}/suggest-split`, { method: "POST" });
      setSuggestion(s);
      setAmounts(s.lines.map((l) => centsToInput(l.planned_cents)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The suggestion didn't work. Please try again.");
    } finally {
      setAsking(false);
    }
  };

  const parsed = amounts.map((a) => parseDollars(a));
  const invalid = parsed.some((c) => c === undefined || c === null);
  const sum = parsed.reduce<number>((s, c) => s + (typeof c === "number" ? c : 0), 0);

  const use = async () => {
    if (!suggestion || invalid) { setError(AMOUNT_HINT); return; }
    const lines = suggestion.lines.map((l, i) => ({ name: l.name, planned_cents: parsed[i] as number }));
    const ok = await run(() =>
      request(`${base}/apply-split`, { method: "POST", body: JSON.stringify({ lines }) }),
    );
    if (ok) setSuggestion(null);
  };

  if (!suggestion) {
    return (
      <div className="mb-10">
        <button type="button" onClick={ask} disabled={asking || busy} className={`${primaryButton} flex items-center gap-2`}>
          <Icon name="auto_awesome" size={18} />
          {asking ? "Working out a suggestion…" : "Suggest a starting split"}
        </button>
        <p className="text-xs text-on-surface-variant mt-2">
          The AI suggests how your total could be shared across categories. It only splits your own total and
          doesn't use vendor prices. Nothing changes until you choose to use it.
        </p>
        {error && <p role="alert" className="text-sm text-error mt-2">{error}</p>}
      </div>
    );
  }

  return (
    <section aria-labelledby="split-heading" className="mb-10 bg-secondary-fixed/20 border border-secondary-fixed/50 rounded-[2rem] p-5">
      <p className="font-label-caps text-[11px] text-secondary mb-1 flex items-center gap-1">
        <Icon name="auto_awesome" size={14} /> AI suggestion, not saved
      </p>
      <h2 id="split-heading" className="font-headline-sm text-headline-sm text-on-surface mb-2">A starting split of {formatCents(suggestion.total_cents)}</h2>
      {suggestion.rationale_summary && (
        <p className="text-sm text-on-surface-variant mb-4">{suggestion.rationale_summary}</p>
      )}
      <ul className="space-y-3 mb-4">
        {suggestion.lines.map((line, i) => (
          <li key={line.name} className="flex flex-wrap items-end gap-3">
            <MoneyInput
              id={`split-${i}`}
              label={`${line.name}${line.existing ? "" : " (new category)"}`}
              value={amounts[i] ?? ""}
              onChange={(v) => setAmounts((prev) => prev.map((a, j) => (j === i ? v : a)))}
            />
            {line.rationale && <p className="text-sm text-on-surface-variant flex-grow">{line.rationale}</p>}
          </li>
        ))}
      </ul>
      <p className={`text-sm mb-4 ${sum !== suggestion.total_cents ? "text-error" : "text-on-surface-variant"}`}>
        Adds up to {formatCents(sum)}
        {sum !== suggestion.total_cents && ` (your total is ${formatCents(suggestion.total_cents)})`}.
      </p>
      <p className="text-xs text-on-surface-variant mb-4">
        Using it sets the planned amount for these categories and adds any new ones. Other categories, vendor
        costs and payments stay as they are.
      </p>
      {error && <p role="alert" className="text-sm text-error mb-3">{error}</p>}
      <div className="flex flex-wrap gap-4 items-center">
        <button type="button" onClick={use} disabled={busy || invalid} className={primaryButton}>Use this split</button>
        <button type="button" onClick={() => setSuggestion(null)} className={linkButton}>Discard</button>
      </div>
    </section>
  );
}

/** The emergency static mode (backend switched off): sample figures, labelled as such. */
function SampleBudget() {
  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <h1 className="font-display-lg-mobile text-display-lg-mobile text-primary mb-2">Budget</h1>
      <SampleDataNotice className="mt-4 mb-8">
        These categories and amounts are made-up examples, not your budget.
      </SampleDataNotice>
      <div className="space-y-6">
        {STATIC_CATEGORIES.map((cat) => (
          <div key={cat.name} className="bg-surface-container-lowest p-6 rounded-[2rem] border border-outline-variant/20">
            <p className="font-headline-sm text-lg text-on-surface">{cat.name}</p>
            <p className="text-on-surface-variant">{cat.spent} of {cat.total}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
