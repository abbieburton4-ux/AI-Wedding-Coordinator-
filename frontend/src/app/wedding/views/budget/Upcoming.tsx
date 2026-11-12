import { useId, useMemo, useState } from "react";
import { formatCents, formatDay } from "./money";
import { linkButton } from "./parts";
import { FoldBody, SECTION_SCROLL, SectionHeading, sectionId, tapArea } from "./sections";
import { Chip } from "./status";
import type { Category } from "./types";
import { daysUntil, upcomingPayments, type Group, type PaymentTag, type UpcomingItem } from "./figures";

// A focus ring that reads on a white page (the global ring is too faint there).
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-on-surface";

const GROUP: Record<Group, { title: string; empty: string }> = {
  overdue: { title: "Overdue", empty: "Nothing overdue." },
  week: { title: "Due in the next 7 days", empty: "Nothing due in the next 7 days." },
  month: { title: "Due in 8 to 30 days", empty: "Nothing due in 8 to 30 days." },
  later: { title: "Later, or no due date yet", empty: "" },
};

const TAG_LABEL: Record<PaymentTag, string> = {
  refundable: "Refundable deposit",
  deposit: "Deposit",
  final: "Final balance",
  payment: "Payment",
};

function plural(n: number): string {
  return `${n} payment${n === 1 ? "" : "s"}`;
}

/**
 * Upcoming payments (PD-013 step 4): every unpaid payment, grouped overdue, next 7
 * days, 8 to 30 days and later, on Chicago's date from the API. It's shown here only;
 * nothing sends a reminder, and only a person ticks a payment paid, inside its expense.
 */
export function UpcomingPayments({
  categories, today, onOpen,
}: { categories: Category[]; today: string; onOpen: (costId: string) => void }) {
  const groups = useMemo(() => upcomingPayments(categories, today), [categories, today]);
  const [showLater, setShowLater] = useState(false);
  const laterId = useId();
  const count = (Object.keys(groups) as Group[]).reduce((n, g) => n + groups[g].items.length, 0);

  return (
    <section id={sectionId("upcoming")} tabIndex={-1} aria-labelledby="due-heading" className={`mb-10 ${SECTION_SCROLL} focus:outline-none`}>
      <SectionHeading section="upcoming" id="due-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">
        Upcoming payments
      </SectionHeading>
      <FoldBody section="upcoming">
      <p className="text-xs text-on-surface-variant mb-3">
        Shown here only: the app doesn't send reminders or pay anyone. To tick a payment as paid, open its expense.
        Refundable deposits are listed, but they aren't part of what anything costs.
      </p>
      {count === 0 ? (
        <p className="text-sm text-on-surface-variant">
          Nothing unpaid. Payments you add to an expense show here, with their due dates.
        </p>
      ) : (
        <div className="space-y-6">
          {(["overdue", "week", "month"] as Group[]).map((g) => (
            <GroupList key={g} group={g} items={groups[g].items} totalCents={groups[g].totalCents} today={today} onOpen={onOpen} />
          ))}
          {groups.later.items.length > 0 && (
            <div>
              {/* One button that stays put, so focus isn't lost when the list opens or closes. */}
              <button
                type="button"
                onClick={() => setShowLater((s) => !s)}
                aria-expanded={showLater}
                aria-controls={laterId}
                className={`${linkButton} ${FOCUS}`}
              >
                {showLater ? "Hide" : "Show"} {plural(groups.later.items.length)} due later or with no date
                {" "}({formatCents(groups.later.totalCents)})
              </button>
              <div id={laterId} hidden={!showLater} className="mt-3">
                <GroupList group="later" items={groups.later.items} totalCents={groups.later.totalCents} today={today} onOpen={onOpen} />
              </div>
            </div>
          )}
        </div>
      )}
      </FoldBody>
    </section>
  );
}

function GroupList({
  group, items, totalCents, today, onOpen,
}: { group: Group; items: UpcomingItem[]; totalCents: number; today: string; onOpen: (costId: string) => void }) {
  const g = GROUP[group];
  const id = `due-${group}`;
  const refundable = items.reduce((s, i) => s + (i.tag === "refundable" ? i.amountCents : 0), 0);
  return (
    <div>
      <h3 id={id} className="flex flex-wrap items-center gap-2 text-sm text-on-surface mb-2">
        <span className="font-bold">{g.title}</span>
        {items.length > 0 && (
          <span className="text-on-surface-variant">{plural(items.length)} · {formatCents(totalCents)}{refundable > 0 && `, including ${formatCents(refundable)} refundable`}</span>
        )}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-on-surface-variant">{g.empty}</p>
      ) : (
        <ul aria-labelledby={id} className="divide-y divide-outline-variant/30 border-y border-outline-variant/30">
          {items.map((item) => (
            <li key={item.paymentId} className="py-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
              <span className="min-w-0">
                <button
                  type="button"
                  onClick={() => onOpen(item.costId)}
                  className={`text-left py-1 text-on-surface hover:text-primary underline underline-offset-4 decoration-outline-variant hover:decoration-primary ${FOCUS} ${tapArea}`}
                  aria-label={`${item.expenseName}: open this expense`}
                >
                  {item.expenseName}
                </button>
                <span className="block text-xs text-on-surface-variant">
                  {item.vendorName ?? "No vendor linked"} · {item.categoryName}
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-2 sm:justify-end">
                <span className="rounded-full px-2.5 py-0.5 text-xs font-bold bg-surface-container-low text-on-surface-variant border border-outline-variant/40">
                  {TAG_LABEL[item.tag]}
                </span>
                <span className="font-button-text text-on-surface">{formatCents(item.amountCents)}</span>
                <DueLabel group={group} dueOn={item.dueOn} today={today} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DueLabel({ group, dueOn, today }: { group: Group; dueOn: string | null; today: string }) {
  if (!dueOn) return <span className="text-sm text-on-surface-variant">No due date</span>;
  if (group === "overdue") return <Chip tone="bad">Overdue, was due {formatDay(dueOn)}</Chip>;
  const days = daysUntil(today, dueOn);
  if (group === "week") {
    return <Chip tone="warn">{days === 0 ? "Due today" : `Due in ${days} day${days === 1 ? "" : "s"}`}, {formatDay(dueOn)}</Chip>;
  }
  if (group === "month") return <Chip tone="warn">Due {formatDay(dueOn)}</Chip>;
  return <span className="text-sm text-on-surface-variant">Due {formatDay(dueOn)}</span>;
}
