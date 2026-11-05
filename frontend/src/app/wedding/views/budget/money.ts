/**
 * Budget amounts are whole US cents everywhere (PD-004, AGENTS.md rule 4). These
 * helpers turn cents into text and typed text into cents without float arithmetic.
 */

/** "$12,500" or "$12,500.50". */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100).toLocaleString("en-US");
  const rest = abs % 100;
  return `${sign}$${dollars}${rest ? `.${String(rest).padStart(2, "0")}` : ""}`;
}

/** Cents as typed text for an input ("12500" or "12500.50"), or "" for none. */
export function centsToInput(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  const rest = cents % 100;
  return `${Math.floor(cents / 100)}${rest ? `.${String(rest).padStart(2, "0")}` : ""}`;
}

/**
 * Typed dollars ("$1,250.5", "1250") to cents. Returns null for an empty box and
 * undefined for something that isn't an amount.
 */
export function parseDollars(text: string): number | null | undefined {
  const cleaned = text.replace(/[\s$,]/g, "");
  if (!cleaned) return null;
  const match = /^(\d{1,7})(?:\.(\d{0,2}))?$/.exec(cleaned);
  if (!match) return undefined;
  return Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
}

export const AMOUNT_HINT = "Please enter an amount in dollars, like 1,250 or 1,250.50.";

/** "Mar 4, 2027" from "2027-03-04", read as a calendar date (no time-zone shift). */
export function formatDay(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
