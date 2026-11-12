/**
 * The upcoming-payments timeline and the chart figures (B68). Everything is read from
 * the budget overview the screen already has: amounts, "overdue" and today's date are
 * the API's (Chicago's date). Plain JavaScript so Node's own test runner can check it
 * with no install (figures.test.js). Amounts are whole cents; dates are "YYYY-MM-DD"
 * strings compared as text.
 */

import { addDays } from "./expenses.js";

export const GROUPS = ["overdue", "week", "month", "later"];

/** A payment's place in time: undated ones go after every dated one. */
const byDue = (a, b) => {
  if (a.due_on === b.due_on) return 0;
  if (!a.due_on) return 1;
  if (!b.due_on) return -1;
  return a.due_on < b.due_on ? -1 : 1;
};

/**
 * Which tag a payment wears: a refundable deposit, a deposit, the final balance (the
 * last unpaid, non-refundable payment of its expense that isn't a deposit), or a payment.
 * @param {any} payment
 * @param {any[]} unpaidOfCost the expense's unpaid, non-refundable payments
 */
export function paymentTag(payment, unpaidOfCost) {
  if (payment.refundable) return "refundable";
  if (payment.kind === "deposit") return "deposit";
  const sorted = unpaidOfCost.filter((p) => p.kind !== "deposit").sort(byDue);
  return sorted[sorted.length - 1]?.id === payment.id ? "final" : "payment";
}

/** Whole days from today to a due date (0 for today, negative once it's passed). */
export function daysUntil(today, isoDate) {
  const utc = (s) => {
    const [y, m, d] = s.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((utc(isoDate) - utc(today)) / 86400000);
}

/**
 * Which group a payment falls in: overdue (the API's flag), due in the next 7 days
 * (today included), due in 8 to 30 days, or later (beyond 30 days, or no due date).
 */
export function groupOf(payment, today) {
  if (payment.overdue) return "overdue";
  if (!payment.due_on) return "later";
  if (payment.due_on <= addDays(today, 7)) return "week";
  if (payment.due_on <= addDays(today, 30)) return "month";
  return "later";
}

/**
 * Every unpaid payment on an expense still in play, grouped and soonest first.
 * @param {{ id: string, name: string, costs: any[] }[]} categories
 * @param {string} today
 * @returns {Record<string, { items: any[], totalCents: number }>}
 */
export function upcomingPayments(categories, today) {
  const groups = Object.fromEntries(GROUPS.map((g) => [g, { items: [], totalCents: 0 }]));
  for (const cat of categories) {
    for (const cost of cat.costs) {
      if (cost.archived) continue;
      const unpaid = cost.payments.filter((p) => !p.paid);
      const owed = unpaid.filter((p) => !p.refundable);
      for (const p of unpaid) {
        const g = groups[groupOf(p, today)];
        g.items.push({
          paymentId: p.id,
          costId: cost.id,
          categoryId: cat.id,
          categoryName: cat.name,
          expenseName: cost.vendor_name,
          vendorName: cost.vendor ? cost.vendor.name : null,
          amountCents: p.amount_cents,
          dueOn: p.due_on,
          tag: paymentTag(p, owed),
        });
        g.totalCents += p.amount_cents;
      }
    }
  }
  for (const g of GROUPS) {
    groups[g].items.sort((a, b) => byDue({ due_on: a.dueOn }, { due_on: b.dueOn })
      || a.expenseName.localeCompare(b.expenseName));
  }
  return groups;
}

/** The donut has eight colours; categories past the eighth share one "other" slice. */
export const SLOTS = 8;

/**
 * Spending by category for the donut. Each category keeps the colour of its place in
 * the couple's order, so switching between committed and paid never repaints one.
 * @param {"committed"|"paid"} measure
 * @returns {{ rows: { id: string, name: string, cents: number, slot: number|null,
 *   hasExpenses: boolean }[], slices: { key: string, name: string, cents: number,
 *   slot: number|null, ids: string[] }[], totalCents: number }}
 *   rows: every category, for the list and table; slices: what the donut draws.
 */
export function spendingByCategory(categories, measure) {
  const rows = categories.map((cat, i) => ({
    id: cat.id,
    name: cat.name,
    cents: measure === "paid" ? cat.paid_cents : cat.committed_cents,
    slot: i < SLOTS - 1 || categories.length === SLOTS ? i : null,
    hasExpenses: cat.expense_count > 0,
  }));
  const slices = rows.filter((r) => r.slot !== null && r.cents > 0)
    .map((r) => ({ key: r.id, name: r.name, cents: r.cents, slot: r.slot, ids: [r.id] }));
  const rest = rows.filter((r) => r.slot === null && r.cents > 0);
  if (rest.length > 0) {
    slices.push({
      key: "other", name: rest.length === 1 ? rest[0].name : `Everything else (${rest.length} categories)`,
      cents: rest.reduce((s, r) => s + r.cents, 0), slot: null, ids: rest.map((r) => r.id),
    });
  }
  return { rows, slices, totalCents: rows.reduce((s, r) => s + r.cents, 0) };
}

/**
 * Whole-number share of a total, for labels only; never feeds another figure.
 * Rounded down, as the API's dashboard percentages are, so the two always agree.
 * Returns null for a 0 total, so nothing reads as "0%" of nothing.
 */
export function sharePct(cents, totalCents) {
  if (!totalCents) return null;
  return Math.floor((cents * 100) / totalCents);
}

/** A share as words: "42%", "under 1%" for a small but real amount, "0%" for none. */
export function shareText(cents, totalCents) {
  const pct = sharePct(cents, totalCents);
  if (pct === null) return "";
  if (pct === 0 && cents > 0) return "under 1%";
  return `${pct}%`;
}

/**
 * Per category: what's paid toward what's committed, and what's still to pay. Paying
 * one vendor too much doesn't count toward another, so "paid toward" is committed minus
 * the API's per-expense "still to pay", and the two parts always add up to committed.
 */
export function paymentProgress(categories) {
  return categories.filter((c) => c.committed_cents > 0).map((c) => ({
    id: c.id,
    name: c.name,
    committedCents: c.committed_cents,
    paidTowardCents: c.committed_cents - c.remaining_cents,
    remainingCents: c.remaining_cents,
    overpaidCents: c.overpaid_cents,
    hasExpenses: c.expense_count > 0,
  }));
}

/** Target against committed, for categories with either. */
export function targetVsCommitted(categories) {
  return categories.filter((c) => c.planned_cents !== null || c.committed_cents > 0).map((c) => ({
    id: c.id,
    name: c.name,
    targetCents: c.planned_cents,
    committedCents: c.committed_cents,
    state: c.state,
    overCents: c.over_target_cents,
    hasExpenses: c.expense_count > 0,
  }));
}

/** The id of the "Not set" row: payments nobody has said who paid yet. */
export const NOT_SET = "not_set";

/**
 * Who paid (PD-016 step 4): per person on the list, what they've paid (ticked
 * payments) and what's still to come from them (unticked). Payments with no payer, or
 * a payer no longer on the list, go in a "Not set" row, shown only when there are
 * some. Like the other charts, refundable deposits and archived expenses are left out.
 * These are payments only, never contributions (promises; PD-016 call c).
 * @param {{ costs: any[] }[]} categories
 * @param {{ id: string, name: string }[]} payers
 * @returns {{ id: string, name: string, paidCents: number, toComeCents: number,
 *   totalCents: number, count: number }[]}
 */
export function whoPaid(categories, payers) {
  const rows = payers.map((p) => ({ id: p.id, name: p.name, paidCents: 0, toComeCents: 0, count: 0 }));
  const notSet = { id: NOT_SET, name: "Not set", paidCents: 0, toComeCents: 0, count: 0 };
  const byId = new Map(rows.map((r) => [r.id, r]));
  for (const cat of categories) {
    for (const cost of cat.costs) {
      if (cost.archived) continue;
      for (const p of cost.payments) {
        if (p.refundable) continue;
        const row = (p.payer_id && byId.get(p.payer_id)) || notSet;
        if (p.paid) row.paidCents += p.amount_cents;
        else row.toComeCents += p.amount_cents;
        row.count += 1;
      }
    }
  }
  return (notSet.count > 0 ? [...rows, notSet] : rows)
    .map((r) => ({ ...r, totalCents: r.paidCents + r.toComeCents }));
}

/** "$12k", "$950" or "$1.5k" for an axis tick; labels and tables use the exact amount. */
export function compactDollars(cents) {
  const dollars = Math.round(cents / 100);
  if (Math.abs(dollars) < 1000) return `$${dollars}`;
  const k = dollars / 1000;
  return `$${Number.isInteger(k) ? k : k.toFixed(1)}k`;
}
