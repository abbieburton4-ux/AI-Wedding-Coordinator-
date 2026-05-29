import { useState, useEffect, useCallback } from "react";
import { useApi } from "../api/useApi";

export interface PlannerClient {
  id: string;
  couple_user_id: string;
  status: string;
  region: string;
  ceremony_type: string;
  budget_total: number;
  guest_count_estimate: number;
  wedding_date?: string | null;
}

/**
 * The signed-in planner's managed weddings. GET /weddings already filters by
 * planner_user_id when the caller's role is "planner" (see weddings.list_weddings).
 */
export function usePlannerClients() {
  const { request, error } = useApi();
  const [clients, setClients] = useState<PlannerClient[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    setLoading(true);
    try {
      setClients(await request<PlannerClient[]>("/weddings/"));
    } catch {
      /* surfaced via useApi error */
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { clients, loading, error, refetch };
}

const PROGRESS: Record<string, { pct: number; phase: string }> = {
  intake: { pct: 10, phase: "Intake" },
  planning: { pct: 50, phase: "Planning" },
  booked: { pct: 80, phase: "Booked" },
  completed: { pct: 100, phase: "Completed" },
  cancelled: { pct: 0, phase: "Cancelled" },
};

export function statusProgress(status: string) {
  return PROGRESS[status] ?? { pct: 25, phase: status };
}

export function formatWeddingDate(d?: string | null): string {
  if (!d) return "Date TBD";
  return new Date(d).toLocaleDateString("en-IE", { day: "2-digit", month: "short", year: "numeric" });
}

export function daysUntil(d?: string | null): string | null {
  if (!d) return null;
  const days = Math.ceil((new Date(d).getTime() - Date.now()) / 86_400_000);
  return days < 0 ? "Past" : `${days} days`;
}
