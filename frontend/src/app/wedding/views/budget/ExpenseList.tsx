import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import { filterExpenses, flattenExpenses, sortExpenses } from "./expenses";
import { formatCents, formatDay } from "./money";
import { StatusBadge, inputClass, linkButton } from "./parts";
import type { Category, ExpenseStatus } from "./types";

type SortKey = "name" | "category" | "vendor" | "committed" | "paid" | "remaining" | "next_due";
type Dir = "asc" | "desc";

const SORT_LABEL: Record<SortKey, string> = {
  name: "Name",
  category: "Category",
  vendor: "Vendor",
  committed: "Committed",
  paid: "Paid",
  remaining: "Still to pay",
  next_due: "Next due",
};
// Amounts read best largest first; names, categories and dates from the start.
const FIRST_DIR: Record<SortKey, Dir> = {
  name: "asc", category: "asc", vendor: "asc", committed: "desc", paid: "desc", remaining: "desc", next_due: "asc",
};
const STATUS_LABEL: Record<ExpenseStatus, string> = {
  unpaid: "Unpaid", partly_paid: "Partly paid", paid: "Paid", overdue: "Overdue",
};

const EMPTY = { search: "", categoryId: "", status: "", vendorId: "", due: "", from: "", to: "" };

/** Asks the list to show one category's expenses; n changes on each ask. */
export type CategoryRequest = { id: string; n: number } | null;

/**
 * Every expense in one list (B67), sortable, filterable and searchable. Works from the
 * overview the screen already has: amounts and statuses are the API's, nothing is
 * worked out here. Choosing an expense opens it in its category.
 */
export function ExpenseList({
  categories, today, onOpen, categoryRequest = null,
}: { categories: Category[]; today: string; onOpen: (costId: string) => void; categoryRequest?: CategoryRequest }) {
  const [f, setF] = useState(EMPTY);
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("category");
  const [dir, setDir] = useState<Dir>("asc");

  const sectionRef = useRef<HTMLElement>(null);

  // Chosen from a chart: show only that category, with every other filter cleared,
  // and move there so the list is what the couple see next.
  useEffect(() => {
    if (!categoryRequest) return;
    setF({ ...EMPTY, categoryId: categoryRequest.id });
    const el = sectionRef.current;
    if (!el) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    el.focus({ preventScroll: true });
    // Only a new ask (a new n) filters again; reloads don't.
  }, [categoryRequest?.n]);

  const all = useMemo(() => flattenExpenses(categories), [categories]);
  const archivedCount = all.filter((r) => r.cost.archived).length;
  // Only vendors some expense is linked to, so every choice finds something.
  const vendors = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of all) if (r.cost.vendor) seen.set(r.cost.vendor.id, r.cost.vendor.name);
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [all]);
  const shown = sortExpenses(filterExpenses(all, { ...f, showArchived }, today), sortKey, dir);
  const total = all.filter((r) => showArchived || !r.cost.archived).length;
  const filtered = Object.values(f).some(Boolean);
  const onlyCategory = f.categoryId !== "" && Object.entries(f).every(([k, v]) => k === "categoryId" || !v);

  if (all.length === 0) return null;

  const set = (key: keyof typeof EMPTY) => (value: string) => setF((prev) => ({ ...prev, [key]: value }));
  const sortBy = (key: SortKey) => {
    if (key === sortKey) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setDir(FIRST_DIR[key]); }
  };

  const header = (key: SortKey, align: "left" | "right" = "left") => (
    <th
      scope="col"
      aria-sort={sortKey === key ? (dir === "asc" ? "ascending" : "descending") : undefined}
      className={`py-2 px-2 font-normal text-xs text-on-surface-variant ${align === "right" ? "text-right" : "text-left"}`}
    >
      <button type="button" onClick={() => sortBy(key)} className="inline-flex items-center gap-1 hover:text-primary">
        {SORT_LABEL[key]}
        {sortKey === key && <Icon name={dir === "asc" ? "arrow_upward" : "arrow_downward"} size={14} />}
      </button>
    </th>
  );

  return (
    <section ref={sectionRef} tabIndex={-1} aria-labelledby="all-expenses-heading" className="mb-10 scroll-mt-24 focus:outline-none">
      <h2 id="all-expenses-heading" className="font-headline-sm text-headline-sm text-on-surface mb-1">All expenses</h2>
      <p className="text-xs text-on-surface-variant mb-3">
        Every expense in one place. Choose one to open it in its category.
      </p>

      <div className="flex flex-wrap items-end gap-3 mb-3">
        <span className="flex flex-col gap-1 flex-grow min-w-[12rem]">
          <label htmlFor="exp-search" className="text-xs text-on-surface-variant">Search by expense or vendor</label>
          <input id="exp-search" type="search" autoComplete="off" value={f.search}
            onChange={(e) => set("search")(e.target.value)} className={inputClass} />
        </span>
        <Select id="exp-cat" label="Category" value={f.categoryId} onChange={set("categoryId")}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select id="exp-status" label="Status" value={f.status} onChange={set("status")}>
          <option value="">Any status</option>
          {(Object.keys(STATUS_LABEL) as ExpenseStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </Select>
        <Select id="exp-vendor" label="Vendor" value={f.vendorId} onChange={set("vendorId")}>
          <option value="">Any vendor</option>
          {vendors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          <option value="none">Not linked to a vendor</option>
        </Select>
        <Select id="exp-due" label="Payment due" value={f.due} onChange={set("due")}>
          <option value="">Any time</option>
          <option value="7">In the next 7 days</option>
          <option value="30">In the next 30 days</option>
          <option value="range">Between dates…</option>
        </Select>
        {f.due === "range" && (
          <>
            <DateBox id="exp-from" label="From" value={f.from} onChange={set("from")} />
            <DateBox id="exp-to" label="To" value={f.to} onChange={set("to")} />
          </>
        )}
        <span className="flex flex-col gap-1 md:hidden">
          <label htmlFor="exp-sort" className="text-xs text-on-surface-variant">Sort by</label>
          <span className="flex items-center gap-2">
            <select id="exp-sort" value={sortKey} className={inputClass}
              onChange={(e) => { const k = e.target.value as SortKey; setSortKey(k); setDir(FIRST_DIR[k]); }}>
              {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => <option key={k} value={k}>{SORT_LABEL[k]}</option>)}
            </select>
            <button type="button" onClick={() => setDir((d) => (d === "asc" ? "desc" : "asc"))} className={linkButton}
              aria-label={dir === "asc" ? "Sorted lowest or earliest first; switch" : "Sorted highest or latest first; switch"}>
              <Icon name={dir === "asc" ? "arrow_upward" : "arrow_downward"} size={18} />
            </button>
          </span>
        </span>
      </div>
      {f.due !== "" && (
        <p className="text-xs text-on-surface-variant mb-2">
          Shows expenses with an unpaid payment due {f.due === "range" ? "between those dates" : `from today to ${f.due} days ahead`}.
          Overdue ones are under Status: Overdue.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-4 mb-3 text-sm">
        <p aria-live="polite" className="text-on-surface-variant">
          {onlyCategory && `${categories.find((c) => c.id === f.categoryId)?.name ?? "This category"} only: `}
          {shown.length === total ? `${plural(total)}` : `Showing ${shown.length} of ${plural(total)}`}
        </p>
        {filtered && <button type="button" onClick={() => setF(EMPTY)} className={linkButton}>Clear filters</button>}
        {archivedCount > 0 && (
          <label className="flex items-center gap-2 cursor-pointer text-on-surface-variant">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)}
              className="h-4 w-4 accent-primary" />
            Show archived ({archivedCount}), not counted in totals
          </label>
        )}
      </div>

      {shown.length === 0 ? (
        <p className="text-sm text-on-surface-variant">
          {onlyCategory ? "No expenses in this category yet." : "No expenses match. Try clearing the filters."}
        </p>
      ) : (
        <>
          {/* Wide screens: a table with sortable headings. */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-outline-variant/40">
                <tr>
                  {header("name")}
                  {header("category")}
                  {header("vendor")}
                  {header("committed", "right")}
                  {header("paid", "right")}
                  {header("remaining", "right")}
                  {header("next_due")}
                  <th scope="col" className="py-2 px-2 font-normal text-xs text-on-surface-variant text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {shown.map(({ cost, categoryName }) => (
                  <tr key={cost.id} onClick={() => onOpen(cost.id)} className="cursor-pointer hover:bg-surface-container-low">
                    <td className="py-2 px-2">
                      <button type="button" onClick={(e) => { e.stopPropagation(); onOpen(cost.id); }}
                        className="text-left text-on-surface hover:text-primary underline-offset-4 hover:underline">
                        {cost.vendor_name}
                      </button>
                      {cost.archived && <span className="block text-xs text-on-surface-variant">Archived</span>}
                    </td>
                    <td className="py-2 px-2 text-on-surface-variant">{categoryName}</td>
                    <td className="py-2 px-2 text-on-surface-variant">{cost.vendor?.name ?? "—"}</td>
                    <td className="py-2 px-2 text-right text-on-surface">{formatCents(cost.committed_cents)}</td>
                    <td className="py-2 px-2 text-right text-on-surface">{formatCents(cost.paid_cents)}</td>
                    <td className="py-2 px-2 text-right text-on-surface">{formatCents(cost.remaining_cents)}</td>
                    <td className="py-2 px-2 text-on-surface-variant">{cost.next_due_on ? formatDay(cost.next_due_on) : "—"}</td>
                    <td className="py-2 px-2"><StatusBadge status={cost.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phones: one card per expense. */}
          <ul className="md:hidden space-y-3">
            {shown.map(({ cost, categoryName }) => (
              <li key={cost.id}>
                <button type="button" onClick={() => onOpen(cost.id)}
                  className="w-full text-left border border-outline-variant/30 rounded-[1.5rem] p-4 hover:border-primary">
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-button-text text-on-surface">{cost.vendor_name}</span>
                    <StatusBadge status={cost.status} />
                  </span>
                  <span className="block text-xs text-on-surface-variant mt-1">
                    {categoryName}{cost.vendor ? ` · ${cost.vendor.name}` : ""}{cost.archived ? " · Archived" : ""}
                  </span>
                  <span className="block text-sm text-on-surface-variant mt-1">
                    Committed {formatCents(cost.committed_cents)} · Paid {formatCents(cost.paid_cents)} · Still to pay{" "}
                    {formatCents(cost.remaining_cents)}
                  </span>
                  {cost.next_due_on && (
                    <span className="block text-xs text-on-surface-variant mt-1">Next due {formatDay(cost.next_due_on)}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function plural(n: number): string {
  return `${n} expense${n === 1 ? "" : "s"}`;
}

function Select({
  id, label, value, onChange, children,
}: { id: string; label: string; value: string; onChange: (v: string) => void; children: ReactNode }) {
  return (
    <span className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={inputClass}>{children}</select>
    </span>
  );
}

function DateBox({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (v: string) => void }) {
  return (
    <span className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-on-surface-variant">{label}</label>
      <input id={id} type="date" value={value} onChange={(e) => onChange(e.target.value)} className={inputClass} />
    </span>
  );
}
