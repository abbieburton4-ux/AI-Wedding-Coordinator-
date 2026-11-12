import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router";
import { Icon } from "../../../shared/Icon";
import { useApi, USE_FASTAPI_BACKEND } from "../../../api";
import { useActiveWedding } from "../../WeddingProvider";
import { committedLabel, formatCents, formatDay, safeHttpUrl } from "./money";
import { linkButton, primaryButton, tipWorking } from "./parts";
import type { Cost, ExpenseStatus, Overview, Payment, TargetState } from "./types";

const STATUS: Record<ExpenseStatus, string> = {
  unpaid: "Unpaid", partly_paid: "Partly paid", paid: "Paid", overdue: "Overdue",
};
const TARGET: Record<TargetState, string> = {
  no_target: "No target", within: "Within target", near_limit: "Near the limit", over: "Over target",
};
const BUDGET: Record<Overview["dashboard"]["budget_state"], string> = {
  not_set: "Total not set", within: "Within budget", near_limit: "Near the limit", over: "Over budget",
};
const CONTRACT = { none: "No contract", sent: "Contract sent", signed: "Contract signed" } as const;

type VendorInfo = { id: string; name: string; website: string | null };

const money = (cents: number | null | undefined) => (cents === null || cents === undefined ? "—" : formatCents(cents));
const day = (iso: string | null) => (iso ? formatDay(iso) : "No date");

function paymentStatus(p: Payment): string {
  if (p.paid) return p.paid_on ? `Paid ${formatDay(p.paid_on)}` : "Paid";
  return p.overdue ? "Overdue" : "Unpaid";
}

/**
 * The budget laid out for printing, or saving as a PDF from the browser's print dialog
 * (PD-013 step 5). Every figure is the API's, as on the Budget screen; nothing is
 * worked out here. Navigation and buttons don't print.
 */
export function BudgetPrint() {
  const { activeWedding, loading: weddingLoading } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;
  const { request } = useApi();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [vendors, setVendors] = useState<Record<string, VendorInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [archived, setArchived] = useState(false);

  const load = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;
    try {
      const [ov, list] = await Promise.all([
        request<Overview>(`/weddings/${weddingId}/budget/overview`),
        // Only for each vendor's website; the page prints without it.
        request<{ vendors: VendorInfo[] }>(`/weddings/${weddingId}/vendors`).catch(() => null),
      ]);
      setOverview(ov);
      if (list) {
        setVendors(Object.fromEntries(list.vendors.map(({ id, name, website }) => [id, { id, name, website }])));
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the budget.");
    }
  }, [weddingId, request]);

  useEffect(() => {
    load();
  }, [load]);

  if (!USE_FASTAPI_BACKEND) {
    return (
      <main className="p-8">
        <p>The printable budget needs the app's server, which is switched off.</p>
        <Link to="/wedding/budget" className={linkButton}>Back to the budget</Link>
      </main>
    );
  }

  const t = overview?.totals;
  const d = overview?.dashboard;
  const withCosts = overview?.categories
    .map((cat) => ({ cat, costs: cat.costs.filter((c) => archived || !c.archived) }))
    .filter(({ costs }) => costs.length > 0) ?? [];

  return (
    <main className="budget-print max-w-[960px] mx-auto px-6 py-8 print:p-0 print:max-w-none text-on-surface print:text-black">
      <div className="print:hidden mb-8 flex flex-wrap items-center gap-4 border-b border-outline-variant/30 pb-4">
        <Link to="/wedding/budget" className={`${linkButton} flex items-center gap-1`}>
          <Icon name="arrow_back" size={18} /> Back to the budget
        </Link>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          Include archived expenses
        </label>
        <button
          type="button" onClick={() => window.print()} disabled={!overview}
          className={`${primaryButton} flex items-center gap-2 ml-auto`}
        >
          <Icon name="print" size={18} /> Print / save as PDF
        </button>
        <p className="w-full text-xs text-on-surface-variant">
          In the print window, choose "Save as PDF" as the printer to keep a PDF copy.
        </p>
      </div>

      {error ? (
        <div role="alert">
          <p className="mb-2">The budget didn't load: {error}</p>
          <button type="button" onClick={load} className={`${linkButton} print:hidden`}>Try again</button>
        </div>
      ) : !weddingId && !weddingLoading ? (
        <p>No wedding is open. Go back to the budget and try again.</p>
      ) : !overview || !t || !d ? (
        <p aria-busy="true">Loading the budget…</p>
      ) : (
        <>
          <header className="mb-6">
            <h1 className="font-display-lg-mobile text-display-lg-mobile text-primary print:text-black mb-1">Wedding budget</h1>
            <p className="text-sm text-on-surface-variant print:text-black">
              As of {formatDay(overview.today)} (Chicago). Amounts in US dollars.
              {archived
                ? " Archived expenses are listed but not counted in any total."
                : " Archived expenses aren't listed or counted."}
            </p>
          </header>

          <Section title="Summary">
            <dl className="grid grid-cols-2 md:grid-cols-3 print:grid-cols-3 gap-x-6 gap-y-3 text-sm">
              <Figure label="Total budget" value={t.total_cents === null ? "Not set" : formatCents(t.total_cents)} />
              <Figure label={committedLabel(t.committed_basis)} value={formatCents(t.committed_cents)} />
              <Figure label="Paid" value={formatCents(t.paid_cents)} />
              <Figure label="Still to pay" value={formatCents(t.remaining_cents)} />
              {d.left_of_total_cents !== null && <Figure label="Left of the total" value={formatCents(d.left_of_total_cents)} />}
              {!!d.over_total_cents && <Figure label="Over the total" value={formatCents(d.over_total_cents)} />}
              {!!t.overpaid_cents && <Figure label="Overpaid" value={formatCents(t.overpaid_cents)} />}
              <Figure label="Category targets" value={formatCents(t.planned_cents)} />
              {!!t.refundable_cents && (
                <Figure
                  label="Refundable deposits (not part of the cost)"
                  value={`${formatCents(t.refundable_cents)} (${formatCents(t.refundable_paid_cents)} paid)`}
                />
              )}
              <Figure label="Status" value={BUDGET[d.budget_state]} />
              <Figure label="Payments overdue" value={String(d.overdue_count)} />
            </dl>
          </Section>

          <Section title="Categories">
            {overview.categories.length === 0 ? (
              <p className="text-sm">No categories yet.</p>
            ) : (
              <Table head={["Category", "Target", "Committed", "Paid", "Still to pay", "Status"]} numeric={[1, 2, 3, 4]}>
                {overview.categories.map((cat) => (
                  <tr key={cat.id} className="border-t border-outline-variant/30 break-inside-avoid">
                    <td className="py-1.5 pr-2">{cat.name}</td>
                    <td className="py-1.5 px-2 text-right">{money(cat.planned_cents)}</td>
                    <td className="py-1.5 px-2 text-right">{formatCents(cat.committed_cents)}</td>
                    <td className="py-1.5 px-2 text-right">{formatCents(cat.paid_cents)}</td>
                    <td className="py-1.5 px-2 text-right">{formatCents(cat.remaining_cents)}</td>
                    <td className="py-1.5 pl-2">{TARGET[cat.state]}</td>
                  </tr>
                ))}
              </Table>
            )}
          </Section>

          <Section title="Upcoming payment deadlines">
            {overview.next_due.length === 0 ? (
              <p className="text-sm">Nothing left to pay.</p>
            ) : (
              <Table head={["Due", "Expense", "Category", "Type", "Amount", "Status"]} numeric={[4]}>
                {overview.next_due.map((p) => (
                  <tr key={p.payment_id} className="border-t border-outline-variant/30 break-inside-avoid">
                    <td className="py-1.5 pr-2 whitespace-nowrap">{day(p.due_on)}</td>
                    <td className="py-1.5 px-2">{p.vendor_name}</td>
                    <td className="py-1.5 px-2">{p.category_name}</td>
                    <td className="py-1.5 px-2">
                      {p.kind === "deposit" ? "Deposit" : "Payment"}{p.refundable ? " (refundable)" : ""}
                    </td>
                    <td className="py-1.5 px-2 text-right">{formatCents(p.amount_cents)}</td>
                    <td className="py-1.5 pl-2">{p.overdue ? "Overdue" : "Unpaid"}</td>
                  </tr>
                ))}
              </Table>
            )}
          </Section>

          <Section title="Expenses and payments" breakBefore>
            {withCosts.length === 0 ? (
              <p className="text-sm">No expenses yet.</p>
            ) : (
              withCosts.map(({ cat, costs }) => (
                <div key={cat.id} className="mb-6">
                  <h3 className="font-bold text-base mb-2 break-after-avoid">{cat.name}</h3>
                  <div className="space-y-4">
                    {costs.map((cost) => <ExpenseBlock key={cost.id} cost={cost} vendor={cost.vendor ? vendors[cost.vendor.id] : undefined} />)}
                  </div>
                </div>
              ))
            )}
          </Section>
        </>
      )}
    </main>
  );
}

function ExpenseBlock({ cost, vendor }: { cost: Cost; vendor?: VendorInfo }) {
  const site = safeHttpUrl(vendor?.website);
  const link = safeHttpUrl(cost.link_url);
  const facts = cost.tip_state ? [
    `Tip${cost.tip_for_name ? ` for ${cost.tip_for_name}` : ""}: ${tipWorking(cost)}`,
  ] : [
    cost.estimated_cents !== null && `Estimate ${formatCents(cost.estimated_cents)}`,
    cost.quoted_cents !== null && `Quote ${formatCents(cost.quoted_cents)}`,
    cost.final_cents !== null && `Actual cost ${formatCents(cost.final_cents)}`,
    CONTRACT[cost.contract_status],
    cost.payment_method && `Pays by ${cost.payment_method}`,
  ].filter(Boolean);
  return (
    <article className="border border-outline-variant/30 rounded-xl p-3 break-inside-avoid text-sm">
      <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 mb-1">
        <p className="font-bold">
          {cost.vendor_name}
          {cost.archived && <span className="font-normal"> (archived, not counted)</span>}
        </p>
        <p>{STATUS[cost.status]}</p>
      </div>
      {cost.vendor && (
        <p className="mb-1">
          Vendor: {cost.vendor.name}
          {site && <> · <span className="break-all">{site}</span></>}
        </p>
      )}
      <p className="mb-1">
        Cost {formatCents(cost.committed_cents)} · Paid {formatCents(cost.paid_cents)} · Still to pay{" "}
        {formatCents(cost.remaining_cents)}
        {!!cost.overpaid_cents && <> · Overpaid {formatCents(cost.overpaid_cents)}</>}
      </p>
      {facts.length > 0 && <p className="mb-1 text-on-surface-variant print:text-black">{facts.join(" · ")}</p>}
      {link && <p className="mb-1 break-all">File: {link}</p>}
      {cost.notes && <p className="mb-1 whitespace-pre-line">Notes: {cost.notes}</p>}
      {cost.payments.length > 0 && (
        <table className="w-full mt-2 text-xs">
          <thead>
            <tr className="text-left">
              <th scope="col" className="py-1 pr-2 font-bold">Payment</th>
              <th scope="col" className="py-1 px-2 font-bold text-right">Amount</th>
              <th scope="col" className="py-1 px-2 font-bold">Due</th>
              <th scope="col" className="py-1 px-2 font-bold">Status</th>
              <th scope="col" className="py-1 px-2 font-bold">Who paid</th>
              <th scope="col" className="py-1 pl-2 font-bold">How it was paid / reference</th>
            </tr>
          </thead>
          <tbody>
            {cost.payments.map((p) => (
              <tr key={p.id} className="border-t border-outline-variant/30">
                <td className="py-1 pr-2">
                  {p.kind === "deposit" ? "Deposit" : "Payment"}{p.refundable ? " (refundable)" : ""}
                </td>
                <td className="py-1 px-2 text-right">{formatCents(p.amount_cents)}</td>
                <td className="py-1 px-2 whitespace-nowrap">{day(p.due_on)}</td>
                <td className="py-1 px-2">{paymentStatus(p)}</td>
                <td className="py-1 px-2">{p.payer_name ?? "Not set"}</td>
                <td className="py-1 pl-2">{[p.method, p.reference].filter(Boolean).join(" · ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </article>
  );
}

function Section({ title, children, breakBefore }: { title: string; children: ReactNode; breakBefore?: boolean }) {
  return (
    <section className={`mb-8 ${breakBefore ? "print:break-before-page" : ""}`}>
      <h2 className="font-headline-sm text-headline-sm text-on-surface print:text-black mb-3 break-after-avoid">{title}</h2>
      {children}
    </section>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="break-inside-avoid">
      <dt className="text-on-surface-variant print:text-black">{label}</dt>
      <dd className="font-bold text-base">{value}</dd>
    </div>
  );
}

function Table({ head, numeric, children }: { head: string[]; numeric: number[]; children: ReactNode }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left">
          {head.map((h, i) => (
            <th key={h} scope="col" className={`py-1.5 px-2 first:pl-0 last:pr-0 font-bold ${numeric.includes(i) ? "text-right" : ""}`}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}
