import { useState, useEffect, useCallback } from "react";
import { useApi } from "./useApi";
import { USE_FASTAPI_BACKEND } from "./config";

interface BudgetLine {
  id: string;
  category: string;
  allocated_amount: number;
  spent_amount: number;
}

interface TimelineItem {
  id: string;
  title: string;
  description?: string;
  due_at: string;
  status: string;
  kind: string;
}

interface Booking {
  id: string;
  venue_id?: string;
  supplier_id?: string;
  status: string;
  sourced_by_agent_id?: string;
}

interface WeddingData {
  id: string;
  status: string;
  budget_total: number;
  guest_count_estimate: number;
  region: string;
  ceremony_type: string;
  style_notes?: string;
  wedding_date?: string;
}

interface WeddingFullState {
  wedding: WeddingData | null;
  budgetLines: BudgetLine[];
  timelineItems: TimelineItem[];
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
    timelineItems: [],
    bookings: [],
  });

  const fetchAll = useCallback(async () => {
    if (!weddingId || !USE_FASTAPI_BACKEND) return;

    try {
      // Sub-resources use .catch so a single failing endpoint can never blank
      // the whole dashboard (the wedding fetch itself must succeed).
      const [wedding, budgetLines, timelineItems, bookings] = await Promise.all([
        request<WeddingData>(`/weddings/${weddingId}`),
        request<BudgetLine[]>(`/weddings/${weddingId}/budget`).catch(() => [] as BudgetLine[]),
        request<TimelineItem[]>(`/weddings/${weddingId}/timeline`).catch(() => [] as TimelineItem[]),
        request<Booking[]>(`/weddings/${weddingId}/bookings`).catch(() => [] as Booking[]),
      ]);

      setData({
        wedding,
        budgetLines,
        timelineItems,
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
