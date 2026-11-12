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
  /** Who ticked it in the app; not who paid it (that's payer_id). */
  paid_by_name: string | null;
  /** The day the couple say they paid; only on a paid payment. */
  paid_on: string | null;
  /** A refundable security deposit: tracked, never part of the cost or "paid". */
  refundable: boolean;
  method: string | null;
  reference: string | null;
  notes: string | null;
  link_url: string | null;
  /** Who paid or will pay it, from the "People who pay" list (PD-016); null if not set. */
  payer_id: string | null;
  payer_name: string | null;
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
  /** Shown to the couple as "Actual cost" (PD-016). */
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
  /** The soonest due date among its unpaid payments; null when none has a date. */
  next_due_on: string | null;
  /** The payer of its most recently added payment, which a new payment starts with. */
  last_payer_id: string | null;
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
  /** The category named Contingency: money set aside for surprises. */
  is_contingency: boolean;
  /** Committed against the target: none set, within, at 90% or more, or over. */
  state: TargetState;
  /** The target as a share of the total budget; null when either is blank. */
  share_pct: number | null;
  /** Target minus committed, never below 0; null with no target. */
  target_left_cents: number | null;
  over_target_cents: number;
  /** Committed as a share of the target; null with no target or a 0 target. */
  used_pct: number | null;
  /** Expenses that aren't archived. */
  expense_count: number;
  /** One-tap ideas for a new expense, for the suggested categories; empty otherwise. */
  suggestions: string[];
  costs: Cost[];
}

export type TargetState = "no_target" | "within" | "near_limit" | "over";

/** The dashboard's figures, worked out by the API. null means "not set yet", never 0. */
export interface Dashboard {
  budget_state: "not_set" | "within" | "near_limit" | "over";
  left_of_total_cents: number | null;
  over_total_cents: number | null;
  unallocated_cents: number | null;
  over_allocated_cents: number | null;
  allocated_pct: number | null;
  committed_pct: number | null;
  /** Paid, counting each expense only up to its cost. */
  paid_toward_cost_cents: number;
  paid_pct: number | null;
  categories_over: number;
  categories_near_limit: number;
  near_limit_pct: number;
  expense_count: number;
  /** Unpaid payments not yet overdue, refundable deposits included. */
  upcoming_count: number;
  overdue_count: number;
  contingency_id: string | null;
}

export interface Contribution {
  id: string;
  contributor: string;
  amount_cents: number;
  category_id: string | null;
}

/** Someone on the "People who pay" list (PD-016). The couple type the names in the app. */
export interface Payer {
  id: string;
  name: string;
  /** Payments that name them; someone named on any can't be removed. */
  payment_count: number;
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
  dashboard: Dashboard;
  categories: Category[];
  contributions: Contribution[];
  payers: Payer[];
  next_due: DuePayment[];
  /** The suggested categories the couple don't have yet, in the suggested order. */
  missing_default_categories: string[];
  /** Suggested categories the couple removed, so no longer offered until they ask (B71). */
  removed_default_categories: string[];
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
