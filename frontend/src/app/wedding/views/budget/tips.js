/**
 * Tips (PD-017): reading a typed percentage, showing one, and previewing what a
 * percentage tip comes to before it's saved. Percentages are whole hundredths of a
 * percent (2000 is 20%) and amounts whole cents, so nothing here is float money
 * arithmetic; the API works the saved figure out the same way. Plain JavaScript so
 * Node's own test runner can check it with no install (tips.test.js).
 */

/** The largest tip percentage the API accepts: 100%. */
export const MAX_TIP_BASIS_POINTS = 10000;

/**
 * Typed text ("20", "20%", "18.5", " 12.25 % ") to hundredths of a percent. Returns
 * null for an empty box and undefined for anything that isn't a percentage above 0
 * and up to 100 with at most two decimals.
 * @param {string} text
 * @returns {number | null | undefined}
 */
export function parsePercent(text) {
  const cleaned = text.replace(/[\s%]/g, "");
  if (!cleaned) return null;
  const match = /^(\d{1,3})(?:\.(\d{0,2}))?$/.exec(cleaned);
  if (!match) return undefined;
  const bp = Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
  return bp > 0 && bp <= MAX_TIP_BASIS_POINTS ? bp : undefined;
}

export const PERCENT_HINT = "Please enter a percentage above 0 and up to 100, like 20 or 18.5.";

/**
 * Hundredths of a percent as text for the screen and the box: 2000 is "20", 1850
 * is "18.5", 1825 is "18.25".
 * @param {number | null | undefined} bp
 */
export function percentText(bp) {
  if (bp === null || bp === undefined) return "";
  const whole = Math.floor(bp / 100);
  const part = bp % 100;
  if (!part) return String(whole);
  return `${whole}.${String(part).padStart(2, "0")}`.replace(/0$/, "");
}

/**
 * bp hundredths of a percent of cents, rounded half up to the whole cent, as the API
 * does: 2000 of 800000 is 160000.
 * @param {number} cents
 * @param {number} bp
 */
export function percentOf(cents, bp) {
  return Math.floor((cents * bp + 5000) / 10000);
}

/**
 * The cost a percentage tip is worked out from, as the API counts it: the actual
 * cost, else the quote, else the estimate; null when none is set (payments don't
 * count).
 * @param {{ final_cents: number | null, quoted_cents: number | null, estimated_cents: number | null }} cost
 */
export function tipBase(cost) {
  for (const cents of [cost.final_cents, cost.quoted_cents, cost.estimated_cents]) {
    if (cents !== null && cents !== undefined) return cents;
  }
  return null;
}

/**
 * The expenses a tip can be for: not archived, and not tips themselves.
 * @template {{ archived: boolean, tip_state: string | null }} T
 * @param {T[]} costs
 * @returns {T[]}
 */
export function tipTargets(costs) {
  return costs.filter((c) => !c.archived && !c.tip_state);
}
