import type { Category, Cost } from "./types";

export interface ExpenseRow {
  cost: Cost;
  categoryId: string;
  categoryName: string;
  /** The category's place on the screen, for sorting by category. */
  categoryIndex: number;
}

export interface ExpenseFilters {
  showArchived?: boolean;
  categoryId?: string;
  status?: string;
  /** "" for any, "none" for not linked, else a vendor id. */
  vendorId?: string;
  /** "", "7", "30" or "range". */
  due?: string;
  from?: string;
  to?: string;
  search?: string;
}

export const SORT_KEYS: string[];
export const STATUS_FILTERS: string[];
export function flattenExpenses(categories: Category[]): ExpenseRow[];
export function addDays(isoDate: string, days: number): string;
export function hasUnpaidDue(cost: Cost, from: string, to: string): boolean;
export function filterExpenses(rows: ExpenseRow[], f: ExpenseFilters, today: string): ExpenseRow[];
export function sortExpenses(rows: ExpenseRow[], key: string, dir: "asc" | "desc"): ExpenseRow[];
export function moveItem(ids: string[], from: number, to: number): string[];
export function categoryKey(name: string): string;
export function venueRename(
  category: { id: string; name: string }, categories: { id: string; name: string }[],
): "offer" | "clash" | null;
