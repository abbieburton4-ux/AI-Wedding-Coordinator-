/** Shapes returned by GET /weddings/{id}/budget/overview. Amounts are whole US cents. */

/**
 * Where a "committed" figure comes from: the vendor's quote, the payments scheduled so
 * far (no quote recorded), a mix of both across vendors, or nothing recorded yet.
 */
export type CommittedBasis = "none" | "quote" | "scheduled" | "mixed";

export interface Payment {
  id: string;
  cost_id: string;
  kind: "deposit" | "payment";
  amount_cents: number;
  due_on: string | null;
  paid: boolean;
  paid_at: string | null;
  paid_by_name: string | null;
}

export interface Cost {
  id: string;
  category_id: string;
  vendor_name: string;
  quoted_cents: number | null;
  committed_cents: number;
  committed_basis: CommittedBasis;
  paid_cents: number;
  /** Never negative. Paying more than agreed shows in overpaid_cents instead. */
  remaining_cents: number;
  overpaid_cents: number;
  payments: Payment[];
}

export interface Category {
  id: string;
  name: string;
  planned_cents: number | null;
  committed_cents: number;
  committed_basis: CommittedBasis;
  paid_cents: number;
  remaining_cents: number;
  overpaid_cents: number;
  costs: Cost[];
}

export interface Contribution {
  id: string;
  contributor: string;
  amount_cents: number;
  category_id: string | null;
}

export interface DuePayment {
  payment_id: string;
  category_name: string;
  vendor_name: string;
  kind: "deposit" | "payment";
  amount_cents: number;
  due_on: string | null;
  overdue: boolean;
}

export interface Totals {
  total_cents: number | null;
  planned_cents: number;
  committed_cents: number;
  committed_basis: CommittedBasis;
  paid_cents: number;
  remaining_cents: number;
  overpaid_cents: number;
  contributions_cents: number;
}

export interface Overview {
  totals: Totals;
  categories: Category[];
  contributions: Contribution[];
  next_due: DuePayment[];
}

export interface SplitLine {
  name: string;
  planned_cents: number;
  existing: boolean;
  rationale: string;
}

export interface SplitSuggestion {
  total_cents: number;
  lines: SplitLine[];
  rationale_summary: string;
}

/** Runs a change against the API, then reloads the budget. Resolves true on success. */
export type Run = (fn: () => Promise<unknown>) => Promise<boolean>;
