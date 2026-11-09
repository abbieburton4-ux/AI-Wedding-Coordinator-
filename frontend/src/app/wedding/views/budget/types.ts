/** Shapes returned by GET /weddings/{id}/budget/overview. Amounts are whole US cents. */

/**
 * Where a "committed" figure comes from: the final cost, else the quote, else the
 * estimate, else the payments scheduled so far; a mix across expenses; or nothing yet.
 */
export type CommittedBasis = "none" | "final" | "quote" | "estimate" | "scheduled" | "mixed";

/** Worked out by the API on Chicago's date (PD-013). */
export type ExpenseStatus = "unpaid" | "partly_paid" | "paid" | "overdue";

export type ContractStatus = "none" | "sent" | "signed";

/** A vendor from the Vendors page that an expense can be linked to. Name and section only. */
export interface VendorRef {
  id: string;
  name: string;
  section: string;
}

export interface Payment {
  id: string;
  cost_id: string;
  kind: "deposit" | "payment";
  amount_cents: number;
  due_on: string | null;
  paid: boolean;
  paid_at: string | null;
  paid_by_name: string | null;
  /** The day the couple say they paid; only on a paid payment. */
  paid_on: string | null;
  /** A refundable security deposit: tracked, never part of the cost or "paid". */
  refundable: boolean;
  method: string | null;
  reference: string | null;
  notes: string | null;
  link_url: string | null;
  overdue: boolean;
  /** How far over the cost "paid" would go if this were ticked; 0 if it wouldn't. */
  would_overpay_cents: number;
}

export interface Cost {
  id: string;
  category_id: string;
  vendor_name: string;
  estimated_cents: number | null;
  quoted_cents: number | null;
  final_cents: number | null;
  contract_status: ContractStatus;
  payment_method: string | null;
  notes: string | null;
  link_url: string | null;
  vendor: VendorRef | null;
  /** Kept and listed, but left out of every total. */
  archived: boolean;
  status: ExpenseStatus;
  committed_cents: number;
  committed_basis: CommittedBasis;
  /** Non-refundable payments added so far. */
  scheduled_cents: number;
  /** How much those payments come to beyond the cost; 0 when they don't. */
  over_scheduled_cents: number;
  paid_cents: number;
  /** Never negative. Paying more than agreed shows in overpaid_cents instead. */
  remaining_cents: number;
  overpaid_cents: number;
  refundable_cents: number;
  refundable_paid_cents: number;
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
  refundable_cents: number;
  refundable_paid_cents: number;
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
  cost_id: string;
  category_name: string;
  vendor_name: string;
  kind: "deposit" | "payment";
  amount_cents: number;
  due_on: string | null;
  overdue: boolean;
  refundable: boolean;
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
  refundable_cents: number;
  refundable_paid_cents: number;
}

export interface Overview {
  totals: Totals;
  categories: Category[];
  contributions: Contribution[];
  next_due: DuePayment[];
  /** Today in Chicago, the day "overdue" is measured against. */
  today: string;
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
