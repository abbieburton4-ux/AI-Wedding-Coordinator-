import test from "node:test";
import assert from "node:assert/strict";
import {
  addDays, categoryKey, filterExpenses, flattenExpenses, moveItem, sortExpenses, venueRename,
} from "./expenses.js";

const pay = (due_on, paid = false) => ({ due_on, paid });
const cost = (id, over) => ({
  id, vendor_name: id, vendor: null, archived: false, status: "unpaid",
  committed_cents: 0, paid_cents: 0, remaining_cents: 0, next_due_on: null, payments: [], ...over,
});
const categories = [
  { id: "venue", name: "Venue & Catering", costs: [
    cost("Sample Hall", { status: "partly_paid", committed_cents: 900, paid_cents: 300, remaining_cents: 600,
      vendor: { id: "v1", name: "Sample Hall Ltd" }, next_due_on: "2026-11-25",
      payments: [pay("2026-11-01", true), pay("2026-11-25")] }),
    cost("Catering", { status: "overdue", committed_cents: 500, remaining_cents: 500, next_due_on: "2026-11-10",
      payments: [pay("2026-11-10")] }),
  ] },
  { id: "photo", name: "Photography & Entertainment", costs: [
    cost("photographer", { status: "paid", committed_cents: 200, paid_cents: 200 }),
    cost("Old DJ", { archived: true, committed_cents: 100, remaining_cents: 100, next_due_on: "2026-12-30",
      payments: [pay("2026-12-30")] }),
    cost("DJ", { committed_cents: 100, remaining_cents: 100, next_due_on: "2026-12-30",
      vendor: { id: "v2", name: "Placeholder Sound" }, payments: [pay("2026-12-30")] }),
  ] },
];
const rows = flattenExpenses(categories);
const today = "2026-11-20";
const names = (list) => list.map((r) => r.cost.vendor_name);

test("dates add up across month and year ends", () => {
  assert.equal(addDays("2026-11-20", 7), "2026-11-27");
  assert.equal(addDays("2026-12-28", 7), "2027-01-04");
  assert.equal(addDays("2027-02-27", 2), "2027-03-01");
});

test("archived expenses are left out unless asked for", () => {
  assert.deepEqual(names(filterExpenses(rows, {}, today)), ["Sample Hall", "Catering", "photographer", "DJ"]);
  assert.equal(filterExpenses(rows, { showArchived: true }, today).length, 5);
});

test("filter by category, status and vendor", () => {
  assert.deepEqual(names(filterExpenses(rows, { categoryId: "photo" }, today)), ["photographer", "DJ"]);
  for (const [status, expected] of [["unpaid", ["DJ"]], ["partly_paid", ["Sample Hall"]],
    ["paid", ["photographer"]], ["overdue", ["Catering"]]]) {
    assert.deepEqual(names(filterExpenses(rows, { status }, today)), expected, status);
  }
  assert.deepEqual(names(filterExpenses(rows, { vendorId: "v2" }, today)), ["DJ"]);
  assert.deepEqual(names(filterExpenses(rows, { vendorId: "none" }, today)), ["Catering", "photographer"]);
});

test("due within 7 or 30 days counts unpaid payments from today, not overdue or paid ones", () => {
  assert.deepEqual(names(filterExpenses(rows, { due: "7" }, today)), ["Sample Hall"]);
  assert.deepEqual(names(filterExpenses(rows, { due: "30" }, today)), ["Sample Hall"]);
  assert.deepEqual(names(filterExpenses(rows, { due: "30" }, "2026-12-01")), ["DJ"]);
  assert.deepEqual(names(filterExpenses(rows, { due: "range", from: "2026-11-01", to: "2026-11-10" }, today)),
    ["Catering"], "a paid payment in the range doesn't count");
  assert.deepEqual(names(filterExpenses(rows, { due: "range", from: "2026-12-01" }, today)), ["DJ"]);
  assert.equal(filterExpenses(rows, { due: "range" }, today).length, 4, "an empty range filters nothing");
});

test("search matches the expense name or the linked vendor, ignoring case", () => {
  assert.deepEqual(names(filterExpenses(rows, { search: "  dj " }, today)), ["DJ"]);
  assert.deepEqual(names(filterExpenses(rows, { search: "placeholder SOUND" }, today)), ["DJ"]);
  assert.deepEqual(names(filterExpenses(rows, { search: "ltd" }, today)), ["Sample Hall"]);
  assert.deepEqual(filterExpenses(rows, { search: "nobody" }, today), []);
});

test("sorting each way; blanks last both ways; ties by category then name", () => {
  const live = filterExpenses(rows, {}, today);
  assert.deepEqual(names(sortExpenses(live, "name", "asc")), ["Catering", "DJ", "photographer", "Sample Hall"]);
  assert.deepEqual(names(sortExpenses(live, "name", "desc")), ["Sample Hall", "photographer", "DJ", "Catering"]);
  assert.deepEqual(names(sortExpenses(live, "category", "desc")), ["DJ", "photographer", "Catering", "Sample Hall"]);
  assert.deepEqual(names(sortExpenses(live, "committed", "desc")), ["Sample Hall", "Catering", "photographer", "DJ"]);
  assert.deepEqual(names(sortExpenses(live, "paid", "asc")), ["Catering", "DJ", "photographer", "Sample Hall"]);
  assert.deepEqual(names(sortExpenses(live, "remaining", "desc")), ["Sample Hall", "Catering", "DJ", "photographer"]);
  assert.deepEqual(names(sortExpenses(live, "next_due", "asc")), ["Catering", "Sample Hall", "DJ", "photographer"]);
  assert.deepEqual(names(sortExpenses(live, "next_due", "desc")), ["DJ", "Sample Hall", "Catering", "photographer"]);
  assert.deepEqual(names(sortExpenses(live, "vendor", "asc")), ["DJ", "Sample Hall", "Catering", "photographer"]);
  assert.deepEqual(names(sortExpenses(live, "vendor", "desc")), ["Sample Hall", "DJ", "Catering", "photographer"]);
  assert.deepEqual(names(live), ["Sample Hall", "Catering", "photographer", "DJ"], "sorting doesn't change the input");
});

test("moving a category up or down", () => {
  assert.deepEqual(moveItem(["a", "b", "c"], 2, 0), ["c", "a", "b"]);
  assert.deepEqual(moveItem(["a", "b", "c"], 0, 1), ["b", "a", "c"]);
  assert.deepEqual(moveItem(["a", "b", "c"], 0, -1), ["a", "b", "c"], "nothing above the first");
  assert.deepEqual(moveItem(["a", "b", "c"], 2, 3), ["a", "b", "c"], "nothing below the last");
});

test("Rename to Venue shows only for a category still called Venue & Catering (PD-015)", () => {
  const cat = (id, name) => ({ id, name });
  const old = cat("a", "Venue & Catering");
  assert.equal(venueRename(old, [old]), "offer");
  for (const name of [" venue  &  CATERING ", "Venue and Catering", "venue AND catering"]) {
    assert.equal(venueRename(cat("a", name), [cat("a", name)]), "offer", name);
  }
  for (const name of ["Venue", "Food & Drink", "Venue & Catering hire", "Catering"]) {
    assert.equal(venueRename(cat("a", name), [cat("a", name)]), null, name);
  }
  assert.equal(venueRename(old, [old, cat("b", " venue ")]), "clash", "a Venue already exists");
  assert.equal(venueRename(old, [old, cat("b", "Venues")]), "clash");
  assert.equal(venueRename(old, [old, cat("b", "Food & Drink")]), "offer");
  assert.equal(categoryKey("  Flowers   &Decor "), "flowers and decor");
});
