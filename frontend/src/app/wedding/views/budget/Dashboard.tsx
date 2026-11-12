import { useId, useState, type FormEvent, type ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import { AMOUNT_HINT, committedLabel, formatCents, parseDollars } from "./money";
import { MoneyInput, inputClass, linkButton, overpaidNote, primaryButton } from "./parts";
import { FoldBody, SECTION_SCROLL, SectionHeading, scrollToElement, sectionId, useFolds } from "./sections";
import { Bar, Chip, type Tone } from "./status";
import type { Category, Overview, Run } from "./types";

type Req = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;

/** "What's this?": a one-line explanation, opened by tap, click or keyboard. */
export function Explain({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-xs text-on-surface-variant hover:text-primary underline-offset-4 hover:underline mt-2"
      >
        <Icon name="help" size={14} /> {open ? "Hide" : "What's this?"}
      </button>
      <p id={id} hidden={!open} className="text-xs text-on-surface-variant mt-1">{children}</p>
    </>
  );
}

function Card({
  label, value, tone, sub, chip, explain, children,
}: {
  label: string; value: string; tone?: Tone; sub?: ReactNode; chip?: ReactNode; explain: ReactNode; children?: ReactNode;
}) {
  return (
    <div className="bg-surface-container-lowest rounded-[1.5rem] border border-outline-variant/20 p-5 flex flex-col">
      <h3 className="text-sm text-on-surface-variant">{label}</h3>
      <p className={`font-headline-sm text-headline-sm ${tone === "bad" ? "text-error" : "text-on-surface"}`}>{value}</p>
      {chip && <p className="mt-1">{chip}</p>}
      {sub && <p className="text-xs text-on-surface-variant mt-1">{sub}</p>}
      {children}
      <span className="mt-auto">
        <Explain>{explain}</Explain>
      </span>
    </div>
  );
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** Scrolls to the "Upcoming payments" list (unfolding it) and moves focus there. */
function goToDue(folds: ReturnType<typeof useFolds>) {
  if (folds) { folds.jumpTo("upcoming"); return; }
  const el = document.getElementById(sectionId("upcoming"));
  if (el) scrollToElement(el);
}

/**
 * The top of the Budget screen (PD-013 step 2): what you can spend, what's committed,
 * what's paid, what's still owed, what's coming up, and whether you're within budget.
 * Every figure comes from the API, worked out on read.
 */
export function BudgetDashboard({ overview, children }: { overview: Overview; children?: ReactNode }) {
  const folds = useFolds();
  const t = overview.totals;
  const d = overview.dashboard;
  const hasTotal = t.total_cents !== null;

  const within =
    d.budget_state === "not_set"
      ? { value: "Not set yet", tone: "neutral" as Tone, chip: null, sub: "Set your total budget to see this." }
      : d.budget_state === "over"
        ? {
            value: `Over by ${formatCents(d.over_total_cents ?? 0)}`, tone: "bad" as Tone,
            chip: <Chip tone="bad">Over budget</Chip>, sub: "Committed is more than your total.",
          }
        : {
            value: `${formatCents(d.left_of_total_cents ?? 0)} left`,
            tone: d.budget_state === "near_limit" ? ("warn" as Tone) : ("good" as Tone),
            chip: d.budget_state === "near_limit"
              ? <Chip tone="warn">Close to your limit</Chip>
              : <Chip tone="good">Within budget</Chip>,
            sub: `Of your ${formatCents(t.total_cents ?? 0)} total, not yet committed.`,
          };

  return (
    <section id={sectionId("overview")} tabIndex={-1} aria-labelledby="glance-heading" className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}>
      <SectionHeading section="overview" id="glance-heading" className="font-headline-sm text-headline-sm text-on-surface mb-3">
        Overview
      </SectionHeading>
      <FoldBody section="overview">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <Card
          label="What you can spend"
          value={hasTotal ? formatCents(t.total_cents as number) : "Not set yet"}
          sub={`Your category targets add up to ${formatCents(t.planned_cents)}.`}
          explain="Your total wedding budget: the most you want to spend. Category targets are how you've shared it out, and the two can differ."
        />
        <Card
          label={committedLabel(t.committed_basis)}
          value={formatCents(t.committed_cents)}
          sub={plural(d.expense_count, "expense")}
          explain="What you've agreed or expect to spend: each expense's actual cost, else its estimate or quote. It isn't money paid yet."
        />
        <Card
          label="Paid"
          value={formatCents(t.paid_cents)}
          sub={d.paid_pct === null
            ? "Nothing committed yet."
            : t.overpaid_cents > 0
              ? `${formatCents(d.paid_toward_cost_cents)} of it covers what you've committed (${d.paid_pct}%); ${formatCents(t.overpaid_cents)} is more than agreed.`
              : `${d.paid_pct}% of what you've committed.`}
          explain="Payments you've ticked as paid. Refundable deposits aren't counted, because you should get them back."
        />
        <Card
          label="Still to pay"
          value={formatCents(t.remaining_cents)}
          sub={overpaidNote(t.overpaid_cents) ?? "Committed minus paid."}
          explain="What's left to pay on everything you've committed to, worked out expense by expense. Paying one vendor too much doesn't reduce what you owe another."
        />
        <Card
          label="Coming up"
          value={plural(d.upcoming_count, "payment")}
          chip={d.overdue_count > 0 ? <Chip tone="bad">{plural(d.overdue_count, "payment")} overdue</Chip> : undefined}
          explain="Unpaid payments that aren't overdue yet, including ones with no due date. Overdue means the due date has passed (Chicago's date). The app doesn't send reminders."
        >
          {d.upcoming_count + d.overdue_count > 0 && (
            <button type="button" onClick={() => goToDue(folds)} className={`${linkButton} self-start mt-2`}>
              See the payments due
            </button>
          )}
        </Card>
        <Card
          label="Are you within budget?"
          value={within.value}
          tone={within.tone}
          chip={within.chip}
          sub={within.sub}
          explain={`Your total budget minus what you've committed. "Close to your limit" means you've committed ${d.near_limit_pct}% or more of it.`}
        />
      </div>

      <div className="bg-surface-container-lowest rounded-[1.5rem] border border-outline-variant/20 p-5 space-y-4">
        {hasTotal ? (
          <>
            <Bar
              label="Shared out into category targets"
              pct={d.allocated_pct}
              tone={(d.over_allocated_cents ?? 0) > 0 ? "warn" : "neutral"}
              text={`${formatCents(t.planned_cents)} of ${formatCents(t.total_cents as number)} (${d.allocated_pct}%)`}
            />
            <Bar
              label="Committed"
              pct={d.committed_pct}
              tone={d.budget_state === "over" ? "bad" : d.budget_state === "near_limit" ? "warn" : "good"}
              text={`${formatCents(t.committed_cents)} of ${formatCents(t.total_cents as number)} (${d.committed_pct}%)`}
            />
          </>
        ) : (
          <p className="text-sm text-on-surface-variant">
            Set your total budget to see how much of it you've shared out and committed.
          </p>
        )}
        <Bar
          label="Paid toward what you've committed"
          pct={d.paid_pct}
          tone="good"
          text={d.paid_pct === null
            ? "Nothing committed yet"
            : `${formatCents(d.paid_toward_cost_cents)} of ${formatCents(t.committed_cents)} (${d.paid_pct}%)`}
        />
        {(d.over_allocated_cents ?? 0) > 0 && (
          <p className="text-sm text-on-surface">
            Your category targets add up to {formatCents(d.over_allocated_cents as number)} more than your total.
            That's allowed; lower a target or move money if you want them to match.
          </p>
        )}
        {(d.unallocated_cents ?? 0) > 0 && (
          <p className="text-sm text-on-surface-variant">
            {formatCents(d.unallocated_cents as number)} of your total isn't in any category target yet.
          </p>
        )}
      </div>

      {t.refundable_cents > 0 && (
        <p className="text-sm text-on-surface-variant mt-3">
          Refundable deposits held: {formatCents(t.refundable_cents)}, kept out of the figures above
          {t.refundable_paid_cents > 0 ? `. ${formatCents(t.refundable_paid_cents)} paid so far, to come back to you.` : "."}
        </p>
      )}

      {d.budget_state === "over" && (
        <Warning>
          What you've committed is {formatCents(d.over_total_cents ?? 0)} more than your total budget.
        </Warning>
      )}
      {d.categories_over > 0 && (
        <Warning>
          {d.categories_over === 1 ? "1 category is" : `${d.categories_over} categories are`} over target.
          {" "}See the categories below.
        </Warning>
      )}
      {d.categories_near_limit > 0 && (
        <p className="flex items-start gap-2 text-sm text-on-surface mt-3">
          <Chip tone="warn">Near the limit</Chip>
          {d.categories_near_limit === 1 ? "1 category has" : `${d.categories_near_limit} categories have`} used
          {" "}{d.near_limit_pct}% or more of {d.categories_near_limit === 1 ? "its" : "their"} target.
        </p>
      )}
      {children}
      </FoldBody>
    </section>
  );
}

function Warning({ children }: { children: ReactNode }) {
  return (
    <div className="bg-error-container/15 border border-error-container/40 rounded-[1.5rem] p-4 mt-4 flex items-start gap-3">
      <Icon name="warning" size={22} className="text-error mt-0.5" />
      <p className="text-sm text-on-surface"><span className="font-bold">Warning: </span>{children}</p>
    </div>
  );
}

/**
 * "Move $X from A to B": lowers one target and raises another in one step on the
 * server, so the two always change together. A target can't go below 0.
 */
export function MoveMoney({
  base, categories, run, request, busy,
}: { base: string; categories: Category[]; run: Run; request: Req; busy: boolean }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const withMoney = categories.filter((c) => (c.planned_cents ?? 0) > 0);
  if (categories.length < 2) return null;
  const source = categories.find((c) => c.id === from);
  const dest = categories.find((c) => c.id === to);
  const cents = parseDollars(amount);
  const available = source?.planned_cents ?? 0;
  const tooMuch = typeof cents === "number" && cents > available;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setDone(null);
    if (!source || !dest) { setError("Choose where the money comes from and where it goes."); return; }
    if (source.id === dest.id) { setError("Choose two different categories."); return; }
    if (cents === undefined) { setError(AMOUNT_HINT); return; }
    if (!cents) { setError("Please enter how much to move."); return; }
    if (tooMuch) { setError(`${source.name} only has ${formatCents(available)} in its target.`); return; }
    const ok = await run(() =>
      request(`${base}/move`, {
        method: "POST",
        body: JSON.stringify({ from_category_id: source.id, to_category_id: dest.id, amount_cents: cents }),
      }),
    );
    if (ok) {
      setDone(`Moved ${formatCents(cents)} from ${source.name} to ${dest.name}.`);
      setAmount("");
      setFrom("");
      setTo("");
    }
  };

  return (
    <section aria-labelledby="move-heading" className="mb-8 bg-surface-container-lowest rounded-[1.5rem] border border-outline-variant/20 p-5">
      <h3 id="move-heading" className="font-headline-sm text-lg text-on-surface mb-1">Move money between categories</h3>
      <p className="text-xs text-on-surface-variant mb-3">
        Lowers one category's target and raises another's by the same amount. Your total, expenses and payments stay as they are.
      </p>
      {withMoney.length === 0 ? (
        <p className="text-sm text-on-surface-variant">Give a category a target first, then you can move money out of it.</p>
      ) : (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <MoneyInput id="move-amount" label="Move" value={amount} onChange={(v) => { setAmount(v); setDone(null); }} required />
          <span className="flex flex-col gap-1">
            <label htmlFor="move-from" className="text-xs text-on-surface-variant">From</label>
            <select id="move-from" value={from} onChange={(e) => { setFrom(e.target.value); setDone(null); }} className={inputClass} required>
              <option value="">Choose a category</option>
              {withMoney.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({formatCents(c.planned_cents as number)})</option>
              ))}
            </select>
          </span>
          <span className="flex flex-col gap-1">
            <label htmlFor="move-to" className="text-xs text-on-surface-variant">To</label>
            <select id="move-to" value={to} onChange={(e) => setTo(e.target.value)} className={inputClass} required>
              <option value="">Choose a category</option>
              {categories.filter((c) => c.id !== from).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.planned_cents === null ? "no target" : formatCents(c.planned_cents)})
                </option>
              ))}
            </select>
          </span>
          <button type="submit" disabled={busy} className={primaryButton}>Move money</button>
          {source && dest && typeof cents === "number" && cents > 0 && !tooMuch && (
            <p className="w-full text-sm text-on-surface-variant" aria-live="polite">
              {source.name}: {formatCents(available)} to {formatCents(available - cents)}.{" "}
              {dest.name}: {formatCents(dest.planned_cents ?? 0)} to {formatCents((dest.planned_cents ?? 0) + cents)}.
            </p>
          )}
          {tooMuch && source && (
            <p className="w-full text-sm text-error" aria-live="polite">
              {source.name} only has {formatCents(available)} in its target, so you can move up to that.
            </p>
          )}
          {error && <p role="alert" className="w-full text-sm text-error">{error}</p>}
          {done && <p role="status" className="w-full text-sm text-on-surface">{done}</p>}
        </form>
      )}
    </section>
  );
}
