import { useMemo, useState, type ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../../components/ui/tabs";
import { formatCents } from "./money";
import { linkButton } from "./parts";
import { FoldBody, SECTION_SCROLL, SectionHeading, sectionId } from "./sections";
import { TargetChip } from "./status";
import type { Category, Payer } from "./types";
import {
  NOT_SET, compactDollars, paymentProgress, shareText, spendingByCategory, targetVsCommitted, whoPaid,
  type ProgressRow, type TargetRow,
} from "./figures";

// Colours come from the theme tokens in styles/theme.css; SVG reads them as CSS variables.
const slotColour = (slot: number | null) => (slot === null ? "var(--chart-other)" : `var(--chart-${slot + 1})`);
const GAP = "var(--card)";

const reducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// A focus ring that reads on the white card (the global ring is too faint there).
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-on-surface";
// The chosen tab shows by a dark border and bold text, not only the white fill.
const TAB = `whitespace-normal py-2 data-[state=active]:border-on-surface data-[state=active]:font-bold ${FOCUS}`;
const card = "bg-surface-container-lowest rounded-[1.5rem] border border-outline-variant/20 p-5";
const thClass = "py-2 px-2 font-normal text-xs text-on-surface-variant";

type OnCategory = (categoryId: string) => void;

/**
 * The budget charts (PD-013 step 4), one at a time behind tabs so the screen isn't
 * crowded: spending by category, target against committed, payments made, and who paid. Every
 * figure is the API's. Each chart lists its categories in words underneath (the keyboard
 * way in) and can switch to a table; choosing a category opens its expenses.
 */
export function BudgetCharts({
  categories, payers, onCategory,
}: { categories: Category[]; payers: Payer[]; onCategory: OnCategory }) {
  const animate = !reducedMotion();

  // The section's own fold (PD-015) hides the charts, so there's no second toggle here.
  return (
    <section id={sectionId("charts")} tabIndex={-1} aria-labelledby="charts-heading" className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}>
      <SectionHeading section="charts" id="charts-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">
        Charts
      </SectionHeading>
      <FoldBody section="charts">
        {categories.length === 0 ? (
          <p className="text-sm text-on-surface-variant">
            Charts appear once the budget has categories and expenses.
          </p>
        ) : (
          <Tabs defaultValue="spending">
            <TabsList aria-label="Choose a chart" className="h-auto w-full flex-wrap bg-surface-container-low">
              <TabsTrigger value="spending" className={TAB}>Spending by category</TabsTrigger>
              <TabsTrigger value="target" className={TAB}>Target vs committed</TabsTrigger>
              <TabsTrigger value="payments" className={TAB}>Payments made</TabsTrigger>
              <TabsTrigger value="payers" className={TAB}>Who paid</TabsTrigger>
            </TabsList>
            <TabsContent value="spending" className={card}>
              <SpendingChart categories={categories} onCategory={onCategory} animate={animate} />
            </TabsContent>
            <TabsContent value="target" className={card}>
              <TargetChart categories={categories} onCategory={onCategory} animate={animate} />
            </TabsContent>
            <TabsContent value="payments" className={card}>
              <PaymentsChart categories={categories} onCategory={onCategory} animate={animate} />
            </TabsContent>
            <TabsContent value="payers" className={card}>
              <WhoPaidChart categories={categories} payers={payers} animate={animate} />
            </TabsContent>
          </Tabs>
        )}
      </FoldBody>
    </section>
  );
}

/** "Show as a table" / "Show the chart": the label says what pressing it does. */
function useTableToggle(): [boolean, ReactNode] {
  const [table, setTable] = useState(false);
  const button = (
    <button type="button" onClick={() => setTable((t) => !t)} className={`${linkButton} ${FOCUS}`}>
      {table ? "Show the chart" : "Show as a table"}
    </button>
  );
  return [table, button];
}

function Swatch({ colour }: { colour: string }) {
  return <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 rounded-sm" style={{ background: colour }} />;
}

/** A category name that opens its expenses, or plain text when it has none yet. */
function CategoryName({ name, hasExpenses, id, onCategory }: { name: string; hasExpenses: boolean; id: string; onCategory: OnCategory }) {
  if (!hasExpenses) return <span className="text-on-surface">{name}</span>;
  return (
    <button
      type="button"
      onClick={() => onCategory(id)}
      aria-label={`${name}: show its expenses`}
      className={`text-left py-1 ${FOCUS} text-on-surface hover:text-primary underline underline-offset-4 decoration-outline-variant hover:decoration-primary`}
    >
      {name}
    </button>
  );
}

function Legend({ items }: { items: { colour: string; label: string }[] }) {
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-on-surface-variant mb-2" aria-hidden="true">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5"><Swatch colour={i.colour} /> {i.label}</span>
      ))}
    </p>
  );
}

/** A category name short enough for the chart's axis; the list and table have it in full. */
function AxisName({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  const name = payload?.value ?? "";
  const short = name.length > 16 ? `${name.slice(0, 15)}…` : name;
  return (
    <text x={x} y={y} dy={4} textAnchor="end" className="fill-on-surface-variant text-[11px]">
      <title>{name}</title>
      {short}
    </text>
  );
}

const moneyTooltip = (value: unknown) => (value === null || value === undefined ? "Not set" : formatCents(Number(value)));

// ---- Spending by category ------------------------------------------------------------

function SpendingChart({ categories, onCategory, animate }: { categories: Category[]; onCategory: OnCategory; animate: boolean }) {
  const [measure, setMeasure] = useState<"committed" | "paid">("committed");
  const [table, tableButton] = useTableToggle();
  const { rows, slices, totalCents } = useMemo(() => spendingByCategory(categories, measure), [categories, measure]);
  const shown = rows.filter((r) => r.cents > 0);
  const word = measure === "committed" ? "Committed" : "Paid";
  const zero = rows.length - shown.length;

  const chooseSlice = (index: number) => {
    const s = slices[index];
    if (s && s.ids.length === 1) onCategory(s.ids[0]);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div role="group" aria-label="Amount to show" className="inline-flex rounded-full border border-outline-variant/40 p-0.5 text-sm">
          {(["committed", "paid"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={measure === m}
              onClick={() => setMeasure(m)}
              className={`rounded-full px-3 py-1 ${FOCUS} ${measure === m ? "bg-on-surface text-surface-container-lowest font-bold" : "text-on-surface-variant hover:text-primary"}`}
            >
              {m === "committed" ? "Committed" : "Paid"}
            </button>
          ))}
        </div>
        {totalCents > 0 && tableButton}
      </div>
      <p className="text-xs text-on-surface-variant mb-3">
        {measure === "committed"
          ? "What you've agreed or expect to spend in each category. Choose a category to see its expenses."
          : "What you've ticked as paid in each category, refundable deposits left out. Choose a category to see its expenses."}
      </p>

      {totalCents === 0 ? (
        <p className="text-sm text-on-surface-variant">
          {measure === "committed"
            ? "Nothing committed yet. Add an expense with an estimate or quote, or an actual cost, and it shows here."
            : "Nothing paid yet. When you tick a payment as paid, it shows here."}
        </p>
      ) : table ? (
        <div className="overflow-x-auto"><table className="w-full text-sm min-w-[22rem]">
          <caption className="sr-only">{word} by category</caption>
          <thead className="border-b border-outline-variant/40">
            <tr>
              <th scope="col" className={`${thClass} text-left`}>Category</th>
              <th scope="col" className={`${thClass} text-right`}>{word}</th>
              <th scope="col" className={`${thClass} text-right`}>Share</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20">
            {rows.map((r) => (
              <tr key={r.id}>
                <th scope="row" className="py-2 px-2 text-left font-normal">
                  <CategoryName name={r.name} hasExpenses={r.hasExpenses} id={r.id} onCategory={onCategory} />
                </th>
                <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.cents)}</td>
                <td className="py-2 px-2 text-right tabular-nums text-on-surface-variant">{shareText(r.cents, totalCents)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      ) : (
        <div className="grid gap-6 md:grid-cols-[260px_1fr] items-center">
          <div
            role="img"
            aria-label={`Donut chart of ${word.toLowerCase()} spending by category, ${formatCents(totalCents)} in all. The same figures are listed with it.`}
            className="relative h-[240px] w-full max-w-[260px] mx-auto"
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="cents"
                  nameKey="name"
                  innerRadius="62%"
                  outerRadius="95%"
                  paddingAngle={slices.length > 1 ? 1 : 0}
                  stroke={GAP}
                  strokeWidth={2}
                  rootTabIndex={-1}
                  isAnimationActive={animate}
                  onClick={(_, index) => chooseSlice(index)}
                >
                  {slices.map((s) => (
                    <Cell key={s.key} fill={slotColour(s.slot)} className={s.ids.length === 1 ? "cursor-pointer" : undefined} />
                  ))}
                </Pie>
                <Tooltip formatter={moneyTooltip} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-xs text-on-surface-variant">{word}</span>
              <span className="font-button-text text-on-surface">{formatCents(totalCents)}</span>
            </div>
          </div>
          <div>
            <ul className="space-y-2">
              {shown.map((r) => (
                <li key={r.id} className="flex items-center gap-2 text-sm">
                  <Swatch colour={slotColour(r.slot)} />
                  <span className="flex-grow min-w-0">
                    <CategoryName name={r.name} hasExpenses={r.hasExpenses} id={r.id} onCategory={onCategory} />
                  </span>
                  <span className="tabular-nums text-on-surface">{formatCents(r.cents)}</span>
                  <span className="tabular-nums text-on-surface-variant w-20 text-right">{shareText(r.cents, totalCents)}</span>
                </li>
              ))}
            </ul>
            {slices.some((s) => s.slot === null && s.ids.length > 1) && (
              <p className="text-xs text-on-surface-variant mt-2">
                The chart has eight colours, so the categories in grey share one slice. Each is listed here.
              </p>
            )}
            {zero > 0 && (
              <p className="text-xs text-on-surface-variant mt-2">
                {zero === 1 ? "1 category has" : `${zero} categories have`} nothing {measure === "committed" ? "committed" : "paid"} yet.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Target vs committed -------------------------------------------------------------

function TargetChart({ categories, onCategory, animate }: { categories: Category[]; onCategory: OnCategory; animate: boolean }) {
  const [table, tableButton] = useTableToggle();
  const rows = useMemo(() => targetVsCommitted(categories), [categories]);
  const data = rows.map((r) => ({ ...r, target: r.targetCents }));
  const go = (index: number) => {
    const r = rows[index];
    if (r?.hasExpenses) onCategory(r.id);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-xs text-on-surface-variant">
          Each category's target beside what you've committed. Choose a category to see its expenses.
        </p>
        {rows.length > 0 && tableButton}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-on-surface-variant">
          Give your categories a target, or add expenses, to compare them here.
        </p>
      ) : table ? (
        <div className="overflow-x-auto"><table className="w-full text-sm min-w-[22rem]">
          <caption className="sr-only">Target and committed by category</caption>
          <thead className="border-b border-outline-variant/40">
            <tr>
              <th scope="col" className={`${thClass} text-left`}>Category</th>
              <th scope="col" className={`${thClass} text-right`}>Target</th>
              <th scope="col" className={`${thClass} text-right`}>Committed</th>
              <th scope="col" className={`${thClass} text-left`}>Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20">
            {rows.map((r) => (
              <tr key={r.id}>
                <th scope="row" className="py-2 px-2 text-left font-normal">
                  <CategoryName name={r.name} hasExpenses={r.hasExpenses} id={r.id} onCategory={onCategory} />
                </th>
                <td className="py-2 px-2 text-right tabular-nums">{r.targetCents === null ? "Not set" : formatCents(r.targetCents)}</td>
                <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.committedCents)}</td>
                <td className="py-2 px-2"><TargetStatus row={r} /></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      ) : (
        <>
          <Legend items={[{ colour: "var(--chart-target)", label: "Target" }, { colour: "var(--chart-1)", label: "Committed" }]} />
          <div
            role="img"
            aria-label="Bar chart of each category's target and what's committed. The same figures are listed below it."
            style={{ height: rows.length * 44 + 40 }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barGap={2} barCategoryGap="25%">
                <CartesianGrid horizontal={false} stroke="var(--border)" />
                <XAxis type="number" tickFormatter={compactDollars} tick={{ fontSize: 11 }} stroke="var(--border)" />
                <YAxis type="category" dataKey="name" width={118} tick={<AxisName />} interval={0} stroke="var(--border)" />
                <Tooltip formatter={moneyTooltip} cursor={{ fill: "var(--muted)" }} />
                <Bar dataKey="target" name="Target" fill="var(--chart-target)" radius={[0, 4, 4, 0]} barSize={10}
                  isAnimationActive={animate} onClick={(_, i) => go(i)} className="cursor-pointer" />
                <Bar dataKey="committedCents" name="Committed" fill="var(--chart-1)" radius={[0, 4, 4, 0]} barSize={10}
                  isAnimationActive={animate} onClick={(_, i) => go(i)} className="cursor-pointer" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-4 divide-y divide-outline-variant/20">
            {rows.map((r) => (
              <li key={r.id} className="py-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
                <CategoryName name={r.name} hasExpenses={r.hasExpenses} id={r.id} onCategory={onCategory} />
                <span className="flex flex-wrap items-center gap-2 text-on-surface-variant">
                  <span>
                    {r.targetCents === null ? "No target" : `Target ${formatCents(r.targetCents)}`} · Committed{" "}
                    {formatCents(r.committedCents)}
                  </span>
                  <TargetStatus row={r} />
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function TargetStatus({ row }: { row: TargetRow }) {
  if (row.state === "over") {
    return <span className="inline-flex flex-wrap items-center gap-1"><TargetChip state="over" /> <span className="text-xs text-on-surface-variant">by {formatCents(row.overCents)}</span></span>;
  }
  return <TargetChip state={row.state} />;
}

// ---- Payments made -------------------------------------------------------------------

function PaymentsChart({ categories, onCategory, animate }: { categories: Category[]; onCategory: OnCategory; animate: boolean }) {
  const [table, tableButton] = useTableToggle();
  const rows = useMemo(() => paymentProgress(categories), [categories]);
  const committed = rows.reduce((s, r) => s + r.committedCents, 0);
  const paid = rows.reduce((s, r) => s + r.paidTowardCents, 0);
  const pct = shareText(paid, committed);
  const go = (index: number) => {
    const r = rows[index];
    if (r?.hasExpenses) onCategory(r.id);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-xs text-on-surface-variant">
          How much of each category's committed amount you've paid, and what's still to pay. Choose a category to see its expenses.
        </p>
        {rows.length > 0 && tableButton}
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-on-surface-variant">
          Nothing committed yet, so there's nothing to pay. Add an expense with a cost and it shows here.
        </p>
      ) : (
        <>
          <p className="text-on-surface mb-3">
            <span className="font-button-text">{formatCents(paid)}</span> paid of {formatCents(committed)} committed
            {pct && ` (${pct})`}; {formatCents(committed - paid)} still to pay.
          </p>
          {table ? (
            <div className="overflow-x-auto"><table className="w-full text-sm min-w-[22rem]">
              <caption className="sr-only">Paid and still to pay by category</caption>
              <thead className="border-b border-outline-variant/40">
                <tr>
                  <th scope="col" className={`${thClass} text-left`}>Category</th>
                  <th scope="col" className={`${thClass} text-right`}>Committed</th>
                  <th scope="col" className={`${thClass} text-right`}>Paid</th>
                  <th scope="col" className={`${thClass} text-right`}>Still to pay</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <th scope="row" className="py-2 px-2 text-left font-normal">
                      <CategoryName name={r.name} hasExpenses={r.hasExpenses} id={r.id} onCategory={onCategory} />
                    </th>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.committedCents)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.paidTowardCents)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.remainingCents)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          ) : (
            <>
              <Legend items={[{ colour: "var(--chart-paid)", label: "Paid" }, { colour: "var(--chart-owed)", label: "Still to pay" }]} />
              <div
                role="img"
                aria-label="Stacked bar chart of what's paid and still to pay in each category. The same figures are listed below it."
                style={{ height: rows.length * 36 + 40 }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barCategoryGap="30%">
                    <CartesianGrid horizontal={false} stroke="var(--border)" />
                    <XAxis type="number" tickFormatter={compactDollars} tick={{ fontSize: 11 }} stroke="var(--border)" />
                    <YAxis type="category" dataKey="name" width={118} tick={<AxisName />} interval={0} stroke="var(--border)" />
                    <Tooltip formatter={moneyTooltip} cursor={{ fill: "var(--muted)" }} />
                    <Bar dataKey="paidTowardCents" name="Paid" stackId="p" fill="var(--chart-paid)" stroke={GAP} strokeWidth={2}
                      barSize={12} isAnimationActive={animate} onClick={(_, i) => go(i)} className="cursor-pointer" />
                    <Bar dataKey="remainingCents" name="Still to pay" stackId="p" fill="var(--chart-owed)" stroke={GAP} strokeWidth={2}
                      radius={[0, 4, 4, 0]} barSize={12} isAnimationActive={animate} onClick={(_, i) => go(i)} className="cursor-pointer" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-4 divide-y divide-outline-variant/20">
                {rows.map((r) => <ProgressItem key={r.id} row={r} onCategory={onCategory} />)}
              </ul>
            </>
          )}
          <p className="text-xs text-on-surface-variant mt-3">
            Refundable deposits aren't counted. Paying one vendor more than agreed doesn't count toward another.
          </p>
        </>
      )}
    </div>
  );
}

// ---- Who paid --------------------------------------------------------------------------

/**
 * Who paid (PD-016 step 4): per person on the "People who pay" list, what they've paid
 * (ticked payments) and what's still to come from them. Payments with nobody chosen
 * are a "Not set" row. Payments only, never promised contributions.
 */
function WhoPaidChart({ categories, payers, animate }: { categories: Category[]; payers: Payer[]; animate: boolean }) {
  const [table, tableButton] = useTableToggle();
  const rows = useMemo(() => whoPaid(categories, payers), [categories, payers]);
  const any = rows.some((r) => r.count > 0);
  const notSet = rows.find((r) => r.id === NOT_SET);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-xs text-on-surface-variant">
          For each person, what they've paid (payments ticked as paid) and what's still to come from them.
        </p>
        {any && tableButton}
      </div>
      {!any ? (
        <p className="text-sm text-on-surface-variant">
          {payers.length === 0
            ? "Add the people who pay, then choose who paid on each payment, and it shows here."
            : "No payments yet. When you add one and choose who paid, it shows here."}
        </p>
      ) : (
        <>
          {table ? (
            <div className="overflow-x-auto"><table className="w-full text-sm min-w-[22rem]">
              <caption className="sr-only">Paid and still to come by who paid</caption>
              <thead className="border-b border-outline-variant/40">
                <tr>
                  <th scope="col" className={`${thClass} text-left`}>Who</th>
                  <th scope="col" className={`${thClass} text-right`}>Paid</th>
                  <th scope="col" className={`${thClass} text-right`}>Still to come</th>
                  <th scope="col" className={`${thClass} text-right`}>Together</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <th scope="row" className="py-2 px-2 text-left font-normal">{r.name}</th>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.paidCents)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.toComeCents)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{formatCents(r.totalCents)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          ) : (
            <>
              <Legend items={[{ colour: "var(--chart-paid)", label: "Paid" }, { colour: "var(--chart-owed)", label: "Still to come" }]} />
              <div
                role="img"
                aria-label="Stacked bar chart of what each person has paid and what's still to come from them. The same figures are listed below it."
                style={{ height: rows.length * 36 + 40 }}
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }} barCategoryGap="30%">
                    <CartesianGrid horizontal={false} stroke="var(--border)" />
                    <XAxis type="number" tickFormatter={compactDollars} tick={{ fontSize: 11 }} stroke="var(--border)" />
                    <YAxis type="category" dataKey="name" width={118} tick={<AxisName />} interval={0} stroke="var(--border)" />
                    <Tooltip formatter={moneyTooltip} cursor={{ fill: "var(--muted)" }} />
                    <Bar dataKey="paidCents" name="Paid" stackId="w" fill="var(--chart-paid)" stroke={GAP} strokeWidth={2}
                      barSize={12} isAnimationActive={animate} />
                    <Bar dataKey="toComeCents" name="Still to come" stackId="w" fill="var(--chart-owed)" stroke={GAP} strokeWidth={2}
                      radius={[0, 4, 4, 0]} barSize={12} isAnimationActive={animate} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-4 divide-y divide-outline-variant/20">
                {rows.map((r) => (
                  <li key={r.id} className="py-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
                    <span className="text-on-surface">{r.name}</span>
                    <span className="text-on-surface-variant">
                      {r.count === 0
                        ? "No payments yet"
                        : `Paid ${formatCents(r.paidCents)} · ${formatCents(r.toComeCents)} still to come`}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="text-xs text-on-surface-variant mt-3">
            {notSet && `${notSet.count} payment${notSet.count === 1 ? " has" : "s have"} nobody chosen as who paid yet, shown as Not set. `}
            Refundable deposits and archived expenses aren't counted, as in the other charts. Promises in Who's
            contributing aren't counted either; this is payments only.
          </p>
        </>
      )}
    </div>
  );
}

function ProgressItem({ row, onCategory }: { row: ProgressRow; onCategory: OnCategory }) {
  const pct = shareText(row.paidTowardCents, row.committedCents);
  return (
    <li className="py-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
      <CategoryName name={row.name} hasExpenses={row.hasExpenses} id={row.id} onCategory={onCategory} />
      <span className="text-on-surface-variant">
        {row.remainingCents === 0 ? "All paid" : `Paid ${formatCents(row.paidTowardCents)} of ${formatCents(row.committedCents)} (${pct})`}
        {row.remainingCents > 0 && ` · ${formatCents(row.remainingCents)} still to pay`}
        {row.overpaidCents > 0 && ` · ${formatCents(row.overpaidCents)} more than agreed`}
      </span>
    </li>
  );
}
