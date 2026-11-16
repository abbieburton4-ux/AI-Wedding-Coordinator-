/**
 * The countdown to a confirmed wedding date (PD-023), shared by the Checklist date box
 * and the home page. Plain JavaScript so Node's own test runner can check it with no
 * install (countdown.test.js).
 */

const DAY_MS = 24 * 60 * 60 * 1000;

/** A YYYY-MM-DD date as a whole-day number, read in UTC so no time zone can shift it. */
function dayNumber(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
}

/**
 * "N days to go", "1 day to go", "Today's the day", or null once the date has passed.
 * `today` is the wedding's own today in Chicago, as the checklist API returns it, never
 * the browser's clock.
 */
export function countdown(weddingDate, today) {
  const days = dayNumber(weddingDate) - dayNumber(today);
  if (days < 0) return null;
  if (days === 0) return "Today's the day";
  return `${days} ${days === 1 ? "day" : "days"} to go`;
}

/** The shown date with its countdown, e.g. "Oct 23, 2027 · 341 days to go". */
export function withCountdown(dateLabel, weddingDate, today) {
  const left = countdown(weddingDate, today);
  return left ? `${dateLabel} · ${left}` : dateLabel;
}
