import { useState, useEffect, useCallback } from "react";
import { useApi } from "./useApi";
import { USE_FASTAPI_BACKEND } from "./config";

interface BudgetLine {
  id: string;
  category: string;
  allocated_amount: number;
  spent_amount: number;
}

/** Just what the overview needs from GET /weddings/{id}/checklist (PD-007). */
export interface ChecklistSummary {
  done: number;
  total: number;
  groups: {
    key: string;
    kind: "catch_up" | "stage";
    label: string;
    due_on: string | null;
    current: boolean;
    tasks: { id: string; title: string; done: boolean; label: "catch_up" | "overdue" | null }[];
  }[];
}

interface Booking {
  id: string;
  venue_id?: string;
  supplier_id?: string;
  status: string;
  sourced_by_agent_id?: string;
  vendor_name?: string;
  vendor_kind?: "venue" | "supplier";
  vendor_category?: string;
  vendor_location?: string;
  pricing_summary?: Record<string, unknown> | null;
  matching_rationale?: string;
  draft_inquiry_email?: string;
  quote_total?: number | null;
  quote_currency?: string | null;
  quote_rationale?: string | null;
  budget_category_name?: string | null;
  budget_match_key?: string | null;
  planned_cents?: number | null;
  budget_comparison?: string | null;
  over_budget?: boolean | null;
  over_by_cents?: number | null;
}

interface WeddingData {
  id: string;
  status: string;
  /** The intake estimate; null when the couple left the budget blank (PD-009). */
  budget_total: number | null;
  /** The couple's own total in whole US cents (PD-004); null until they set it. */
  budget_total_cents?: number | null;
  guest_count_estimate: number;
  region: string;
  ceremony_type: string;
  style_notes?: string;
  wedding_date?: string;
}

interface WeddingFullState {
  wedding: WeddingData | null;
  budgetLines: BudgetLine[];
  checklist: ChecklistSummary | null;
  bookings: Booking[];
}

/**
 * Fetches a wedding's full state from the FastAPI backend.
 *
 * When USE_FASTAPI_BACKEND is false, returns null data so
 * components fall back to their existing static mock content.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useWedding(weddingId);
 */
export function useWedding(weddingId: string | null) {
  const { request, loading, error } = useApi();
  const [data, setData] = useState<WeddingFullState>({
    wedding: null,
    budgetLines: [],
    checklist: null,
    bookings: [],
  });

  const fetchAll = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;

    try {
      // Sub-resources use .catch so a single failing endpoint can never blank
      // the whole dashboard (the wedding fetch itself must succeed).
      const [wedding, budgetLines, checklist, bookings] = await Promise.all([
        request<WeddingData>(`/weddings/${weddingId}`),
        request<BudgetLine[]>(`/weddings/${weddingId}/budget`).catch(() => [] as BudgetLine[]),
        request<ChecklistSummary>(`/weddings/${weddingId}/checklist`).catch(() => null),
        request<Booking[]>(`/weddings/${weddingId}/bookings`).catch(() => [] as Booking[]),
      ]);

      setData({
        wedding,
        budgetLines,
        checklist,
        bookings,
      });
    } catch {
      // Error is already captured in useApi's error state
    }
  }, [weddingId, request]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return { data, loading, error, refetch: fetchAll };
}
