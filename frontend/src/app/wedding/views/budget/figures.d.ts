import type { Category, TargetState } from "./types";

export type Group = "overdue" | "week" | "month" | "later";
export type PaymentTag = "refundable" | "deposit" | "final" | "payment";

export interface UpcomingItem {
  paymentId: string;
  costId: string;
  categoryId: string;
  categoryName: string;
  /** The expense's own name. */
  expenseName: string;
  /** The linked vendor from the Vendors page, if any. */
  vendorName: string | null;
  amountCents: number;
  dueOn: string | null;
  tag: PaymentTag;
}

export interface SpendingRow {
  id: string;
  name: string;
  cents: number;
  /** Its colour (0 to 7), or null when it shares the "everything else" slice. */
  slot: number | null;
  hasExpenses: boolean;
}

export interface Slice {
  key: string;
  name: string;
  cents: number;
  slot: number | null;
  ids: string[];
}

export interface ProgressRow {
  id: string;
  name: string;
  committedCents: number;
  paidTowardCents: number;
  remainingCents: number;
  overpaidCents: number;
  hasExpenses: boolean;
}

export interface TargetRow {
  id: string;
  name: string;
  targetCents: number | null;
  committedCents: number;
  state: TargetState;
  overCents: number;
  hasExpenses: boolean;
}

export const GROUPS: Group[];
export const SLOTS: number;
export function paymentTag(payment: unknown, unpaidOfCost: unknown[]): PaymentTag;
export function daysUntil(today: string, isoDate: string): number;
export function groupOf(payment: { overdue: boolean; due_on: string | null }, today: string): Group;
export function upcomingPayments(
  categories: Category[], today: string,
): Record<Group, { items: UpcomingItem[]; totalCents: number }>;
export function spendingByCategory(
  categories: Category[], measure: "committed" | "paid",
): { rows: SpendingRow[]; slices: Slice[]; totalCents: number };
export function sharePct(cents: number, totalCents: number): number | null;
export function shareText(cents: number, totalCents: number): string;
export function paymentProgress(categories: Category[]): ProgressRow[];
export function targetVsCommitted(categories: Category[]): TargetRow[];
export function compactDollars(cents: number): string;
