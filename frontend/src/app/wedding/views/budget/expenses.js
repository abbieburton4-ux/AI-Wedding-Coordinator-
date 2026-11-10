/**
 * The list of all expenses (B67): filters, search and sorting over what the budget
 * overview already returned. Nothing here is a figure of its own; every amount and
 * status comes from the API. Plain JavaScript so Node's own test runner can check it
 * with no install (expenses.test.js). Dates are "YYYY-MM-DD" strings compared as
 * text, so no time zone can shift them.
 */

/** @typedef {{ id: string, name: string, costs: any[] }} CategoryLike */
/** @typedef {{ cost: any, categoryId: string, categoryName: string, categoryIndex: number }} Row */

export const SORT_KEYS = ["name", "category", "vendor", "committed", "paid", "remaining", "next_due"];
export const STATUS_FILTERS = ["unpaid", "partly_paid", "paid", "overdue"];

/**
 * Every expense with the category it's in, in the screen's category order.
 * @param {CategoryLike[]} categories
 * @returns {Row[]}
 */
export function flattenExpenses(categories) {
  return categories.flatMap((cat, categoryIndex) =>
    cat.costs.map((cost) => ({ cost, categoryId: cat.id, categoryName: cat.name, categoryIndex })),
  );
}

/** "2026-11-20" plus n days, worked out in UTC so it never shifts a day. */
export function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** True when the expense has an unpaid payment due between from and to (both included). */
export function hasUnpaidDue(cost, from, to) {
  return cost.payments.some(
    (p) => !p.paid && p.due_on && (!from || p.due_on >= from) && (!to || p.due_on <= to),
  );
}

/**
 * @param {Row[]} rows
 * @param {{ showArchived?: boolean, categoryId?: string, status?: string, vendorId?: string,
 *   due?: string, from?: string, to?: string, search?: string }} f
 *   vendorId: "" for any, "none" for expenses not linked to a vendor, else a vendor id.
 *   due: "" for any, "7" or "30" for an unpaid payment due from today to that many days
 *   ahead, "range" for one due between from and to.
 * @param {string} today Chicago's date from the API.
 */
export function filterExpenses(rows, f, today) {
  const search = (f.search || "").trim().toLowerCase();
  return rows.filter(({ cost, categoryId }) => {
    if (cost.archived && !f.showArchived) return false;
    if (f.categoryId && categoryId !== f.categoryId) return false;
    if (f.status && cost.status !== f.status) return false;
    if (f.vendorId === "none" && cost.vendor) return false;
    if (f.vendorId && f.vendorId !== "none" && cost.vendor?.id !== f.vendorId) return false;
    if (f.due === "7" || f.due === "30") {
      if (!hasUnpaidDue(cost, today, addDays(today, Number(f.due)))) return false;
    } else if (f.due === "range" && (f.from || f.to)) {
      if (!hasUnpaidDue(cost, f.from || "", f.to || "")) return false;
    }
    if (search) {
      const hay = `${cost.vendor_name} ${cost.vendor?.name ?? ""}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });
}

const text = (a, b) => a.localeCompare(b, "en-US", { sensitivity: "base", numeric: true });

/** The value each sort key compares; null sorts last whichever way the list runs. */
function valueOf(row, key) {
  const c = row.cost;
  switch (key) {
    case "name": return c.vendor_name;
    case "category": return row.categoryIndex;
    case "vendor": return c.vendor ? c.vendor.name : null;
    case "committed": return c.committed_cents;
    case "paid": return c.paid_cents;
    case "remaining": return c.remaining_cents;
    case "next_due": return c.next_due_on;
    default: return null;
  }
}

/**
 * A sorted copy. Blanks (no vendor linked, nothing due) go last in either direction;
 * ties fall back to the category order, then the name.
 * @param {Row[]} rows
 * @param {string} key one of SORT_KEYS
 * @param {"asc"|"desc"} dir
 */
export function sortExpenses(rows, key, dir) {
  const sign = dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const va = valueOf(a, key);
    const vb = valueOf(b, key);
    if (va === null && vb !== null) return 1;
    if (vb === null && va !== null) return -1;
    if (va !== null && vb !== null && va !== vb) {
      const cmp = typeof va === "string" ? text(va, vb) : va - vb;
      if (cmp !== 0) return sign * cmp;
    }
    return a.categoryIndex - b.categoryIndex || text(a.cost.vendor_name, b.cost.vendor_name);
  });
}

/**
 * Category ids in a new order: the one at index `from` moved to index `to`.
 * @param {string[]} ids
 */
export function moveItem(ids, from, to) {
  if (from === to || from < 0 || to < 0 || from >= ids.length || to >= ids.length) return ids;
  const next = [...ids];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/**
 * A category name in one comparable form, as the API compares them: case and spaces
 * ignored, "&" read as "and". "Venue  &  catering" is "venue and catering".
 * @param {string} name
 */
export function categoryKey(name) {
  return name.toLowerCase().replace(/&/g, " and ").split(/\s+/).filter(Boolean).join(" ");
}

const VENUE_KEYS = new Set(["venue", "venues"]);

/**
 * Whether a category gets the "Rename to Venue" button (PD-015 call b): "offer" for one
 * still called Venue & Catering, "clash" if another category is already Venue (renaming
 * would make two), and null for every other category, so the button goes once renamed.
 * @param {{ id: string, name: string }} category
 * @param {{ id: string, name: string }[]} categories
 * @returns {"offer" | "clash" | null}
 */
export function venueRename(category, categories) {
  if (categoryKey(category.name) !== "venue and catering") return null;
  const clash = categories.some((c) => c.id !== category.id && VENUE_KEYS.has(categoryKey(c.name)));
  return clash ? "clash" : "offer";
}
