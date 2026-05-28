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
      const [wedding, budgetLines, timelineItems] = await Promise.all([
        request<WeddingData>(`/weddings/${weddingId}`),
        request<BudgetLine[]>(`/weddings/${weddingId}/budget`),
        request<TimelineItem[]>(`/weddings/${weddingId}/timeline`),
      ]);

      setData({
        wedding,
        budgetLines,
        timelineItems,
        bookings: [], // Bookings endpoint can be added later
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
