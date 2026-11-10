/**
 * The note shown while adding or editing an expense: would it take its category or
 * the whole budget over its target? Plain JavaScript so Node's own test runner can
 * check it with no install (forecast.test.js). Amounts are whole cents.
 */

/**
 * What an expense counts as, as the API works it out: the final cost, else the
 * quote, else the estimate, else the payments scheduled on it so far.
 * @param {number|null} finalCents
 * @param {number|null} quotedCents
 * @param {number|null} estimatedCents
 * @param {number} scheduledCents
 */
export function expenseCost(finalCents, quotedCents, estimatedCents, scheduledCents) {
  for (const cents of [finalCents, quotedCents, estimatedCents]) {
    if (cents !== null && cents !== undefined) return cents;
  }
  return scheduledCents || 0;
}

/**
 * How far over the category's target and the total this change would go. Only
 * reported when the change adds to what's committed and the result is over, so a
 * category that's already over doesn't warn about an edit that lowers it.
 * A blank target or total (null) is never "over".
 * @param {{ target: number|null, committed: number, total: number|null,
 *   totalCommitted: number, before: number, after: number }} f
 *   before: what this expense counts for now (0 for a new or archived one);
 *   after: what it would count for once saved.
 * @returns {{ categoryOverBy: number, totalOverBy: number }}
 */
export function wouldGoOver({ target, committed, total, totalCommitted, before, after }) {
  const change = after - before;
  if (change <= 0) return { categoryOverBy: 0, totalOverBy: 0 };
  const overBy = (limit, now) =>
    limit === null || limit === undefined ? 0 : Math.max(now + change - limit, 0);
  return { categoryOverBy: overBy(target, committed), totalOverBy: overBy(total, totalCommitted) };
}
