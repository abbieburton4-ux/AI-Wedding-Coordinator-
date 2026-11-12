import test from "node:test";
import assert from "node:assert/strict";
import { costBox, expenseCost, wouldGoOver } from "./forecast.js";

const base = { target: 100_000, committed: 80_000, total: 1_000_000, totalCommitted: 990_000 };

test("an expense counts its final cost, else quote, else estimate, else scheduled", () => {
  assert.equal(expenseCost(3, 2, 1, 9), 3);
  assert.equal(expenseCost(null, 2, 1, 9), 2);
  assert.equal(expenseCost(null, null, 1, 9), 1);
  assert.equal(expenseCost(null, null, null, 9), 9);
  assert.equal(expenseCost(null, null, null, 0), 0);
  assert.equal(expenseCost(0, 2, 1, 9), 0, "a final cost of 0 is a real figure");
});

test("a new expense that takes the category and the total over", () => {
  assert.deepEqual(wouldGoOver({ ...base, before: 0, after: 30_000 }),
    { categoryOverBy: 10_000, totalOverBy: 20_000 });
});

test("landing exactly on the target isn't over", () => {
  assert.deepEqual(wouldGoOver({ ...base, before: 0, after: 10_000 }),
    { categoryOverBy: 0, totalOverBy: 0 });
});

test("a blank target or total is never over", () => {
  assert.deepEqual(wouldGoOver({ ...base, target: null, total: null, before: 0, after: 999_999 }),
    { categoryOverBy: 0, totalOverBy: 0 });
});

test("a zero target is over with anything on it", () => {
  assert.deepEqual(wouldGoOver({ ...base, target: 0, committed: 0, before: 0, after: 1 }),
    { categoryOverBy: 1, totalOverBy: 0 });
});

test("an edit only counts the change, and lowering a cost never warns", () => {
  const over = { ...base, committed: 120_000 };
  assert.deepEqual(wouldGoOver({ ...over, before: 50_000, after: 40_000 }),
    { categoryOverBy: 0, totalOverBy: 0 });
  assert.deepEqual(wouldGoOver({ ...base, before: 50_000, after: 60_000 }),
    { categoryOverBy: 0, totalOverBy: 0 });
  assert.deepEqual(wouldGoOver({ ...base, before: 50_000, after: 75_000 }),
    { categoryOverBy: 5_000, totalOverBy: 15_000 });
});

test("the one cost box shows and writes the quote if there is one, else the estimate", () => {
  assert.deepEqual(costBox(1200, 1000), { field: "quoted_cents", cents: 1200, keptEstimate: 1000 });
  assert.deepEqual(costBox(0, null), { field: "quoted_cents", cents: 0, keptEstimate: null },
    "a quote of 0 is a real figure");
  assert.deepEqual(costBox(null, 1000), { field: "estimated_cents", cents: 1000, keptEstimate: null });
  assert.deepEqual(costBox(null, null), { field: "estimated_cents", cents: null, keptEstimate: null },
    "a new expense's figure goes in the estimate");
});
