import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "../../shared/Icon";
import { SampleDataNotice } from "../../shared/SampleDataNotice";
import { useApi, USE_FASTAPI_BACKEND } from "../../api";
import { useActiveWedding } from "../WeddingProvider";
import { BudgetDashboard, MoveMoney } from "./budget/Dashboard";
import { CategoryOrder, DefaultCategoriesOffer } from "./budget/Categories";
import { BudgetCharts } from "./budget/Charts";
import { ExpenseList, type CategoryRequest } from "./budget/ExpenseList";
import { UpcomingPayments } from "./budget/Upcoming";
import { BudgetExport } from "./budget/Export";
import { Payers } from "./budget/Payers";
import { AddFormsProvider, focusFirstField, useAddForm, useOpenAddForm } from "./budget/addForms";
import { AMOUNT_HINT, centsToInput, formatCents, parseDollars } from "./budget/money";
import {
  AddCategoryForm, AddTipForm, CategoryCard, Contributions, MethodSuggestions, MoneyInput, fieldClass, inputClass, limitsFor,
  linkButton, primaryButton, type OpenRequest, type Req,
} from "./budget/parts";
import { tipTargets } from "./budget/tips";
import {
  FoldBody, FoldProvider, JumpBar, SECTIONS, SECTION_SCROLL, SectionHeading, scrollToElement, sectionId, useFolds,
} from "./budget/sections";
import type { Category, Overview, Payer, Run, SplitSuggestion, Totals, VendorRef } from "./budget/types";
import { useReviewedRequest } from "../../api/review";

const SUGGESTIONS_ID = "budget-suggestions";

// Shown only when the backend is switched off (USE_FASTAPI_BACKEND), and labelled as sample.
const STATIC_CATEGORIES = [
  { name: "Attire & Beauty", spent: "$4,200", total: "$5,000" },
  { name: "Floral & Decor", spent: "$3,100", total: "$4,000" },
];

/**
 * The couple's budget (PD-004): an optional total, categories with planned amounts,
 * vendor costs with deposits and payments, who's contributing, and what's due next.
 * Everyone on the access list can see it; only owners and editors see edit controls,
 * and the API refuses edits from anyone else. A jump-to bar and a fold on each section
 * (PD-015) keep the long page manageable.
 */
export function Budget() {
  const { activeWedding } = useActiveWedding();
  return (
    <FoldProvider weddingId={activeWedding?.id ?? null}>
      <AddFormsProvider>
        <BudgetScreen />
      </AddFormsProvider>
    </FoldProvider>
  );
}

function BudgetScreen() {
  const { activeWedding, myLevel } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { request } = useApi();
  const base = `/weddings/${weddingId}/budget`;
  const canEdit = myLevel === "owner" || myLevel === "editor";
  const folds = useFolds();
  const openFold = folds?.open;

  const [overview, setOverview] = useState<Overview | null>(null);
  const [vendors, setVendors] = useState<VendorRef[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openRequest, setOpenRequest] = useState<OpenRequest>(null);
  // Opening an expense (from Upcoming payments or All expenses) unfolds Categories first.
  const openExpense = useCallback(
    (id: string) => {
      openFold?.("categories");
      setOpenRequest((prev) => ({ id, n: (prev?.n ?? 0) + 1 }));
    },
    [openFold],
  );
  const [addRequest, setAddRequest] = useState<OpenRequest>(null);
  const addExpenseTo = useCallback(
    (id: string) => {
      openFold?.("categories");
      setAddRequest((prev) => ({ id, n: (prev?.n ?? 0) + 1 }));
    },
    [openFold],
  );
  const clearAdd = useCallback(() => setAddRequest(null), []);
  const clearOpen = useCallback(() => setOpenRequest(null), []);
  // A chart's category opens the list of all expenses, filtered to it.
  const [categoryRequest, setCategoryRequest] = useState<CategoryRequest>(null);
  const showCategory = useCallback(
    (id: string) => setCategoryRequest((prev) => ({ id, n: (prev?.n ?? 0) + 1 })),
    [],
  );

  const load = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;
    try {
      const [ov, list] = await Promise.all([
        request<Overview>(`/weddings/${weddingId}/budget/overview`),
        // Only for linking an expense to a vendor; the budget works without it.
        request<{ vendors: VendorRef[] }>(`/weddings/${weddingId}/vendors`).catch(() => null),
      ]);
      setOverview(ov);
      if (list) setVendors(list.vendors.map(({ id, name, section }) => ({ id, name, section })));
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
        <h1 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary-text mb-2">
          Budget
        </h1>
        <p className="text-on-surface-variant">
          Give each category a target, add each expense with its estimate or quote and who is paying, fill in the actual cost
          later, and tick off payments as you make
          them. Amounts are in US dollars; "overdue" uses today's date in Chicago.
        </p>
        {!canEdit && myLevel && (
          <p className="text-sm text-on-surface-variant mt-2">You can see the budget but not change it.</p>
        )}
        {canEdit && overview && (
          <AddExpenseStart
            categories={overview.categories}
            hasSuggestions={overview.missing_default_categories.length > 0 || overview.removed_default_categories.length > 0}
            onPick={addExpenseTo}
          />
        )}
        {canEdit && overview && overview.categories.some((c) => c.costs.length > 0) && (
          <AddTipStart
            base={base} categories={overview.categories} totals={overview.totals} payers={overview.payers}
            run={run} request={request} busy={busy}
          />
        )}
      </div>

      {overview && (
        <JumpBar
          present={SECTIONS.map((s) => s.key).filter((k) =>
            (k !== "expenses" || overview.categories.some((c) => c.costs.length > 0)) && (k !== "export" || !!weddingId))}
        />
      )}

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
          <BudgetDashboard overview={overview}>
            <div className="mt-10">
              <TotalCard base={base} totalCents={overview.totals.total_cents} canEdit={canEdit} run={run} request={request} busy={busy} />
              {canEdit && overview.totals.total_cents !== null && (
                <SplitPanel base={base} request={request} run={run} busy={busy} />
              )}
            </div>
          </BudgetDashboard>

          <UpcomingPayments categories={overview.categories} today={overview.today} onOpen={openExpense} />

          <BudgetCharts categories={overview.categories} payers={overview.payers} onCategory={showCategory} />

          <ExpenseList
            categories={overview.categories} today={overview.today} onOpen={openExpense} categoryRequest={categoryRequest}
          />

          <section
            id={sectionId("categories")} tabIndex={-1} aria-labelledby="cat-heading"
            className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}
          >
            <SectionHeading section="categories" id="cat-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">
              Categories
            </SectionHeading>
            <FoldBody section="categories">
            {overview.categories.length === 0 && (
              <p className="text-sm text-on-surface-variant mb-4">
                {canEdit
                  ? "No categories yet. Add the suggested ones, or your own below."
                  : "No categories yet."}
              </p>
            )}
            {canEdit && (overview.missing_default_categories.length > 0
              || overview.removed_default_categories.length > 0) && (
              <div id={SUGGESTIONS_ID} tabIndex={-1} className={`${SECTION_SCROLL} focus:outline-none`}>
                <DefaultCategoriesOffer
                  base={base} missing={overview.missing_default_categories} removed={overview.removed_default_categories}
                  hasAny={overview.categories.length > 0} run={run} request={request} busy={busy}
                />
              </div>
            )}
            {canEdit && (
              <CategoryOrder base={base} categories={overview.categories} run={run} request={request} busy={busy} />
            )}
            <div className="space-y-6 mb-6">
              {overview.categories.map((cat) => (
                <CategoryCard
                  key={cat.id} base={base} category={cat} categories={overview.categories} totals={overview.totals}
                  vendors={vendors} payers={overview.payers} canEdit={canEdit} run={run} request={request} busy={busy} openRequest={openRequest}
                  onOpened={clearOpen} addRequest={addRequest} onAddHandled={clearAdd}
                />
              ))}
            </div>
            {canEdit && <AddCategoryForm base={base} run={run} request={request} busy={busy} />}
            {canEdit && (
              <MoveMoney weddingId={weddingId} base={base} categories={overview.categories} run={run} request={request} busy={busy} />
            )}
            {canEdit && <MethodSuggestions />}
            </FoldBody>
          </section>

          <Payers base={base} payers={overview.payers} canEdit={canEdit} run={run} request={request} busy={busy} />

          {weddingId && <BudgetExport weddingId={weddingId} today={overview.today} />}

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
  const sendReviewed = useReviewedRequest();
  const [suggestion, setSuggestion] = useState<SplitSuggestion | null>(null);
  const [amounts, setAmounts] = useState<string[]>([]);
  const [left, setLeft] = useState<boolean[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    setAsking(true);
    setError(null);
    try {
      // Shows the couple what goes to the AI first; nothing is sent until they click (PD-008).
      const s = await sendReviewed<SplitSuggestion>(`${base}/suggest-split`);
      if (s === null) return;
      setSuggestion(s);
      setAmounts(s.lines.map((l) => centsToInput(l.planned_cents)));
      setLeft(s.lines.map(() => false));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The suggestion didn't work. Please try again.");
    } finally {
      setAsking(false);
    }
  };

  // A line is left out when the couple remove it or empty its box; either way it's shown
  // as left out, isn't saved, and its amount no longer counts towards the total.
  const parsed = amounts.map((a) => parseDollars(a));
  const included = parsed.map((c, i) => !left[i] && c !== null);
  const invalid = parsed.some((c, i) => included[i] && c === undefined);
  const sum = parsed.reduce<number>((s, c, i) => s + (included[i] && typeof c === "number" ? c : 0), 0);
  const total = suggestion?.total_cents ?? 0;
  const noneLeft = !included.some(Boolean);
  const balanced = !invalid && !noneLeft && sum === total;

  const toggleLine = (i: number) => setLeft((prev) => prev.map((v, j) => (j === i ? !v : v)));

  const use = async () => {
    if (!suggestion) return;
    if (invalid) { setError(AMOUNT_HINT); return; }
    if (!balanced) { setError(`The amounts need to add up to your total of ${formatCents(total)}.`); return; }
    const lines = suggestion.lines
      .map((l, i) => ({ name: l.name, planned_cents: parsed[i] as number }))
      .filter((_, i) => included[i]);
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
      {!!suggestion.reasons_removed && (
        <p className="text-sm text-on-surface-variant mb-4">
          {suggestion.reasons_removed === 1 ? "One of the AI's reasons was" : "Some of the AI's reasons were"} left
          out because {suggestion.reasons_removed === 1 ? "it" : "they"} seemed to mention an amount of money. The
          amounts here come only from your own total.
        </p>
      )}
      <ul className="space-y-3 mb-4">
        {suggestion.lines.map((line, i) =>
          left[i] ? (
            <li key={`${i}-${line.name}`} className="flex flex-wrap items-center gap-3 text-sm text-on-surface-variant">
              <span className="line-through">{line.name}</span>
              <span>left out, won't be saved</span>
              <button type="button" onClick={() => toggleLine(i)} className={linkButton}>Add back</button>
            </li>
          ) : (
            <li key={`${i}-${line.name}`} className="flex flex-wrap items-end gap-3">
              <MoneyInput
                id={`split-${i}`}
                label={`${line.name}${line.existing ? "" : " (new category)"}${included[i] ? "" : ", left out while empty"}`}
                value={amounts[i] ?? ""}
                onChange={(v) => setAmounts((prev) => prev.map((a, j) => (j === i ? v : a)))}
              />
              <button type="button" onClick={() => toggleLine(i)} className={linkButton}>Leave out</button>
              {line.rationale && <p className="text-sm text-on-surface-variant flex-grow">{line.rationale}</p>}
            </li>
          ),
        )}
      </ul>
      <p className={`text-sm mb-4 ${balanced ? "text-on-surface-variant" : "text-error"}`} aria-live="polite">
        Adds up to {formatCents(sum)}
        {sum < total && `, ${formatCents(total - sum)} short of your total of ${formatCents(total)}`}
        {sum > total && `, ${formatCents(sum - total)} more than your total of ${formatCents(total)}`}.
        {!balanced && " Adjust the amounts so they add up to your total to use this split."}
      </p>
      <p className="text-xs text-on-surface-variant mb-4">
        Using it sets the target for these categories and adds any new ones. Lines you leave out, other
        categories, vendor costs and payments stay as they are.
      </p>
      {error && <p role="alert" className="text-sm text-error mb-3">{error}</p>}
      <div className="flex flex-wrap gap-4 items-center">
        <button type="button" onClick={use} disabled={busy || !balanced} className={primaryButton}>Use this split</button>
        <button type="button" onClick={() => setSuggestion(null)} className={linkButton}>Discard</button>
      </div>
    </section>
  );
}

/**
 * The main "Add expense" (PD-015 step 2): asks which category, then opens that
 * category's own form. With no categories yet, it points to the suggestions first.
 */
function AddExpenseStart({
  categories, hasSuggestions, onPick,
}: { categories: Category[]; hasSuggestions: boolean; onPick: (categoryId: string) => void }) {
  const folds = useFolds();
  const openForm = useOpenAddForm();
  const [asking, setAsking] = useState(false);
  const [picked, setPicked] = useState("");
  // The list can reload while this is open; never pick a category that's gone.
  const target = categories.some((c) => c.id === picked) ? picked : categories[0]?.id ?? "";

  const goTo = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (folds) folds.jumpTo("categories", el);
    else scrollToElement(el);
  };

  const start = (
    <button
      type="button"
      onClick={() => setAsking((a) => !a)}
      aria-expanded={asking}
      className={`${primaryButton} inline-flex items-center gap-2`}
    >
      <Icon name="add" size={18} /> Add expense
    </button>
  );

  if (!asking) return <div className="mt-4">{start}</div>;

  if (categories.length === 0) {
    return (
      <div className="mt-4 flex flex-wrap items-center gap-4">
        {start}
        <p className="text-sm text-on-surface">
          Each expense goes in a category, and you don't have any yet.{" "}
          {hasSuggestions ? (
            <button type="button" onClick={() => goTo(SUGGESTIONS_ID)} className={`${linkButton} font-bold text-primary-text`}>
              Add the suggested categories first
            </button>
          ) : (
            <button type="button" onClick={() => goTo("new-cat-name")} className={`${linkButton} font-bold text-primary-text`}>
              Add a category first
            </button>
          )}
        </p>
      </div>
    );
  }

  return (
    <form
      className="mt-4 flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!target) return;
        // Kept open, with focus where it was, if the couple keep what they typed elsewhere.
        if (!openForm(`expense:${target}`)) return;
        setAsking(false);
        onPick(target);
      }}
    >
      {start}
      <span className={fieldClass}>
        <label htmlFor="add-expense-category" className="text-xs text-on-surface-variant">Which category is it for?</label>
        <select
          id="add-expense-category" value={target} onChange={(e) => setPicked(e.target.value)}
          className={inputClass}
        >
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </span>
      <button type="submit" className={primaryButton}>Continue</button>
      <button type="button" onClick={() => setAsking(false)} className={linkButton}>Cancel</button>
    </form>
  );
}

/**
 * The main "Add tip" (PD-017), beside Add expense: asks which expense the tip is for,
 * then a percentage or an amount. Each expense also has its own Add tip.
 */
function AddTipStart({
  base, categories, totals, payers, run, request, busy,
}: { base: string; categories: Category[]; totals: Totals; payers: Payer[]; run: Run; request: Req; busy: boolean }) {
  const adder = useAddForm("tip:main");
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { if (adder.isOpen) focusFirstField(box.current); }, [adder.isOpen]);
  const targets = categories.flatMap((cat) => tipTargets(cat.costs).map((cost) => ({
    cost, categoryName: cat.name, limits: limitsFor(cat, totals),
  })));
  return (
    <div className="mt-3">
      <button
        ref={adder.opener} type="button" onClick={adder.toggle} aria-expanded={adder.isOpen}
        className="inline-flex items-center gap-1 rounded-full border border-primary px-4 py-2.5 sm:py-1.5 text-sm text-primary-text hover:bg-primary hover:text-on-primary"
      >
        <Icon name="volunteer_activism" size={16} /> Add tip
      </button>
      {adder.isOpen && (
        <div ref={box} className="mt-3 bg-surface-container-lowest rounded-[1.5rem] border border-outline-variant/20 p-4">
          <AddTipForm
            base={base} targets={targets} payers={payers} run={run} request={request} busy={busy}
            idPrefix="main-tip" formKey="tip:main" onDone={() => adder.close()}
          />
        </div>
      )}
    </div>
  );
}

/** The emergency static mode (backend switched off): sample figures, labelled as such. */
function SampleBudget() {
  return (
    <main className="pt-24 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop pb-32 max-w-[1120px] mx-auto">
      <h1 className="font-display-lg-mobile text-display-lg-mobile text-primary-text mb-2">Budget</h1>
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
