import test from "node:test";
import assert from "node:assert/strict";
import {
  compactDollars, daysUntil, groupOf, paymentProgress, paymentTag, sharePct, shareText, spendingByCategory, targetVsCommitted,
  upcomingPayments, whoPaid,
} from "./figures.js";

const today = "2026-11-20";
const pay = (id, due_on, over = {}) => ({
  id, due_on, kind: "payment", amount_cents: 100, paid: false, refundable: false, overdue: false, ...over,
});

test("groups run overdue, 7 days (today included), 30 days, then later or undated", () => {
  assert.equal(groupOf(pay("a", "2026-11-19", { overdue: true }), today), "overdue");
  assert.equal(groupOf(pay("a", "2026-11-20"), today), "week");
  assert.equal(groupOf(pay("a", "2026-11-27"), today), "week");
  assert.equal(groupOf(pay("a", "2026-11-28"), today), "month");
  assert.equal(groupOf(pay("a", "2026-12-20"), today), "month");
  assert.equal(groupOf(pay("a", "2026-12-21"), today), "later");
  assert.equal(groupOf(pay("a", null), today), "later");
});

test("the last unpaid payment that isn't a deposit is the final balance", () => {
  const first = pay("first", "2026-11-25");
  const last = pay("last", "2027-09-23");
  const undated = pay("undated", null);
  const deposit = pay("dep", "2027-12-01", { kind: "deposit" });
  const refund = pay("ref", "2027-09-23", { kind: "deposit", refundable: true });
  const owed = [first, last, deposit];
  assert.equal(paymentTag(first, owed), "payment");
  assert.equal(paymentTag(deposit, owed), "deposit");
  assert.equal(paymentTag(refund, owed), "refundable");
  // An undated payment comes after every dated one, so it's the final balance.
  assert.equal(paymentTag(last, [first, last, undated]), "payment");
  assert.equal(paymentTag(undated, [first, last, undated]), "final");
  // Once the earlier one is paid, the one left is the final balance.
  assert.equal(paymentTag(last, [last]), "final");
});

test("a deposit due last doesn't stop the latest payment being the final balance", () => {
  const first = pay("first", "2026-11-25");
  const last = pay("last", "2027-09-23");
  const deposit = pay("dep", "2027-12-01", { kind: "deposit" });
  assert.equal(paymentTag(last, [first, last, deposit]), "final");
});

const cost = (id, payments, over = {}) => ({ id, vendor_name: id, vendor: null, archived: false, payments, ...over });
const cat = (id, costs, over = {}) => ({
  id, name: id, costs, planned_cents: null, committed_cents: 0, paid_cents: 0, remaining_cents: 0,
  overpaid_cents: 0, over_target_cents: 0, state: "no_target", expense_count: costs.length, ...over,
});

test("upcoming payments skip paid ones and archived expenses, and add up each group", () => {
  const groups = upcomingPayments([
    cat("Venue", [
      cost("Hall", [
        pay("h1", "2026-11-10", { overdue: true, kind: "deposit", amount_cents: 600000 }),
        pay("h2", "2027-09-23", { amount_cents: 600000 }),
        pay("h3", "2027-09-23", { kind: "deposit", refundable: true, amount_cents: 200000 }),
        pay("h0", "2026-10-01", { paid: true }),
      ], { vendor: { id: "v1", name: "Sample Hall Ltd" } }),
      cost("Old", [pay("o1", "2026-11-21")], { archived: true }),
    ]),
    cat("Photo", [cost("Photographer", [pay("p1", "2026-11-22", { amount_cents: 50050 }), pay("p2", "2026-12-01")])]),
  ], today);
  assert.deepEqual(groups.overdue.items.map((i) => [i.paymentId, i.tag]), [["h1", "deposit"]]);
  assert.equal(groups.overdue.totalCents, 600000);
  assert.deepEqual(groups.week.items.map((i) => [i.paymentId, i.tag]), [["p1", "payment"]]);
  assert.deepEqual(groups.month.items.map((i) => [i.paymentId, i.tag]), [["p2", "final"]]);
  assert.deepEqual(groups.later.items.map((i) => [i.paymentId, i.tag]), [["h2", "final"], ["h3", "refundable"]]);
  assert.equal(groups.later.totalCents, 800000);
  assert.equal(groups.overdue.items[0].vendorName, "Sample Hall Ltd");
  assert.equal(groups.week.items[0].vendorName, null);
});

test("each category keeps its colour; past eight, the rest share one slice", () => {
  const cats = Array.from({ length: 10 }, (_, i) =>
    cat(`c${i}`, [], { committed_cents: i === 2 ? 0 : 100 * (i + 1), paid_cents: i === 0 ? 50 : 0 }));
  const committed = spendingByCategory(cats, "committed");
  assert.deepEqual(committed.slices.map((s) => [s.key, s.slot]),
    [["c0", 0], ["c1", 1], ["c3", 3], ["c4", 4], ["c5", 5], ["c6", 6], ["other", null]]);
  assert.deepEqual(committed.slices.at(-1).ids, ["c7", "c8", "c9"]);
  assert.equal(committed.slices.at(-1).cents, 800 + 900 + 1000);
  assert.equal(committed.totalCents, 5200);
  const paid = spendingByCategory(cats, "paid");
  assert.deepEqual(paid.slices.map((s) => [s.key, s.slot]), [["c0", 0]]);
  // Eight categories fit without folding.
  assert.equal(spendingByCategory(cats.slice(0, 8), "committed").slices.at(-1).slot, 7);
});

test("payment progress always adds up to committed, even with an overpayment", () => {
  const [row, ...rest] = paymentProgress([
    cat("Venue", [], { committed_cents: 1000, paid_cents: 900, remaining_cents: 300, overpaid_cents: 200 }),
    cat("Empty", [], { committed_cents: 0 }),
  ]);
  assert.equal(rest.length, 0);
  assert.equal(row.paidTowardCents + row.remainingCents, row.committedCents);
  assert.equal(row.paidTowardCents, 700);
});

test("target vs committed leaves out categories with neither", () => {
  const rows = targetVsCommitted([
    cat("a", [], { planned_cents: 0 }), cat("b", []), cat("c", [], { committed_cents: 5 }),
  ]);
  assert.deepEqual(rows.map((r) => [r.id, r.targetCents]), [["a", 0], ["c", null]]);
});

test("days until a due date, across a month end", () => {
  assert.equal(daysUntil(today, "2026-11-20"), 0);
  assert.equal(daysUntil(today, "2026-12-01"), 11);
  assert.equal(daysUntil(today, "2026-11-19"), -1);
});

test("shares and axis labels", () => {
  assert.equal(sharePct(1, 3), 33);
  // Rounded down, like the dashboard: $2,000 of $3,000 is 66%, not 67%.
  assert.equal(sharePct(200000, 300000), 66);
  assert.equal(sharePct(5, 0), null);
  assert.equal(shareText(1, 1000), "under 1%");
  assert.equal(shareText(0, 1000), "0%");
  assert.equal(shareText(999, 1000), "99%");
  assert.equal(shareText(1000, 1000), "100%");
  assert.equal(shareText(5, 0), "");
  assert.equal(compactDollars(95000), "$950");
  assert.equal(compactDollars(1200000), "$12k");
  assert.equal(compactDollars(150000), "$1.5k");
});

test("who paid: paid and still to come per payer, unset ones last, deposits back and archived left out", () => {
  const payers = [{ id: "a", name: "Sample Payer A" }, { id: "b", name: "Placeholder Family" }];
  const p = (amount_cents, payer_id, over = {}) => ({ amount_cents, payer_id, paid: false, refundable: false, ...over });
  const categories = [
    { costs: [
      { archived: false, payments: [p(100, "a", { paid: true }), p(300, "a"), p(50, null), p(200, "b", { refundable: true })] },
      { archived: true, payments: [p(999, "a", { paid: true })] },
    ] },
    { costs: [{ archived: false, payments: [p(20, "gone", { paid: true })] }] },
  ];
  assert.deepEqual(whoPaid(categories, payers), [
    { id: "a", name: "Sample Payer A", paidCents: 100, toComeCents: 300, totalCents: 400, count: 2 },
    { id: "b", name: "Placeholder Family", paidCents: 0, toComeCents: 0, totalCents: 0, count: 0 },
    { id: "not_set", name: "Not set", paidCents: 20, toComeCents: 50, totalCents: 70, count: 2 },
  ]);
  assert.deepEqual(whoPaid([], payers).map((r) => r.id), ["a", "b"], "no Not set row when nothing's unset");
});
