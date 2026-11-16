import test from "node:test";
import assert from "node:assert/strict";
import { countdown, withCountdown } from "./countdown.js";

const WEDDING = "2027-10-23";

test("whole days to go, counted from the wedding's own today", () => {
  assert.equal(countdown(WEDDING, "2026-11-16"), "341 days to go");
  assert.equal(countdown(WEDDING, "2027-10-21"), "2 days to go");
});

test("a daylight-saving change in between doesn't shift the count", () => {
  assert.equal(countdown("2027-03-15", "2027-03-13"), "2 days to go");
  assert.equal(countdown("2027-11-08", "2027-11-06"), "2 days to go");
});

test("one day before, on the day, and after", () => {
  assert.equal(countdown(WEDDING, "2027-10-22"), "1 day to go");
  assert.equal(countdown(WEDDING, WEDDING), "Today's the day");
  assert.equal(countdown(WEDDING, "2027-10-24"), null);
});

test("the date reads with its countdown, and alone once it has passed", () => {
  assert.equal(withCountdown("Oct 23, 2027", WEDDING, "2026-11-16"), "Oct 23, 2027 · 341 days to go");
  assert.equal(withCountdown("Oct 23, 2027", WEDDING, "2027-10-24"), "Oct 23, 2027");
});
