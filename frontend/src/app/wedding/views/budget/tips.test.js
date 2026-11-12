import test from "node:test";
import assert from "node:assert/strict";
import { parsePercent, percentOf, percentText, tipBase, tipTargets } from "./tips.js";

test("typed percentages become hundredths of a percent", () => {
  assert.equal(parsePercent("20"), 2000);
  assert.equal(parsePercent(" 20 % "), 2000);
  assert.equal(parsePercent("18.5"), 1850);
  assert.equal(parsePercent("12.25"), 1225);
  assert.equal(parsePercent("100"), 10000);
  assert.equal(parsePercent("0.01"), 1);
  assert.equal(parsePercent(""), null);
  for (const bad of ["0", "0.00", "100.01", "101", "12.345", "abc", "-5", "1,5", "20.5.1"]) {
    assert.equal(parsePercent(bad), undefined, bad);
  }
});

test("percentages read back as typed", () => {
  assert.equal(percentText(2000), "20");
  assert.equal(percentText(1850), "18.5");
  assert.equal(percentText(1825), "18.25");
  assert.equal(percentText(5), "0.05");
  assert.equal(percentText(null), "");
  for (const bp of [1, 50, 999, 1850, 2000, 10000]) assert.equal(parsePercent(percentText(bp)), bp);
});

test("a percentage of a cost rounds half up to the cent, as the API does", () => {
  assert.equal(percentOf(800000, 2000), 160000);
  assert.equal(percentOf(1, 5000), 1);
  assert.equal(percentOf(3, 5000), 2);
  assert.equal(percentOf(33333, 1875), 6250);
  assert.equal(percentOf(3, 1500), 0);
  assert.equal(percentOf(100000000000, 10000), 100000000000);
});

test("a tip is worked out from the actual cost, else the quote, else the estimate", () => {
  assert.equal(tipBase({ final_cents: 900, quoted_cents: 800, estimated_cents: 700 }), 900);
  assert.equal(tipBase({ final_cents: null, quoted_cents: 800, estimated_cents: 700 }), 800);
  assert.equal(tipBase({ final_cents: null, quoted_cents: null, estimated_cents: 0 }), 0);
  assert.equal(tipBase({ final_cents: null, quoted_cents: null, estimated_cents: null }), null);
});

test("only expenses still counted, and not tips, can have a tip", () => {
  const costs = [
    { id: "a", archived: false, tip_state: null },
    { id: "b", archived: true, tip_state: null },
    { id: "c", archived: false, tip_state: "following" },
  ];
  assert.deepEqual(tipTargets(costs).map((c) => c.id), ["a"]);
});
