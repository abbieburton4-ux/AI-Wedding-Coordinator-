import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useNavigate, useLocation } from "react-router";
import { useApi } from "../api/useApi";

export interface WeddingSummary {
  id: string;
  status: string;
  region: string;
  ceremony_type: string;
  /** The intake estimate; null when the couple left the budget blank (PD-009). */
  budget_total: number | null;
  /** The couple's own total in whole US cents (PD-004); null until they set it. */
  budget_total_cents?: number | null;
  guest_count_estimate: number;
  wedding_date?: string;
  /** The couple's "This date is confirmed" switch (B48); false means provisional. */
  wedding_date_confirmed?: boolean;
}

interface WeddingContextValue {
  weddings: WeddingSummary[];
  activeWedding: WeddingSummary | null;
  setActiveWedding: (id: string) => void;
  loading: boolean;
  refetch: () => Promise<void>;
  /** The signed-in person's level on the active wedding (viewer, editor or owner). */
  myLevel: string | null;
  myLevelLoading: boolean;
  refetchMyLevel: () => Promise<void>;
}

export const ACTIVE_WEDDING_KEY = "vf_active_wedding";

/**
 * Set the active wedding id from outside the provider (e.g. after the intake form
 * creates the wedding), then navigate to /wedding — WeddingProvider reads this on
 * mount, so the couple workspace renders the chosen wedding.
 */
export function setStoredActiveWeddingId(id: string) {
  localStorage.setItem(ACTIVE_WEDDING_KEY, id);
}

const ACTIVE_KEY = ACTIVE_WEDDING_KEY;

const WeddingContext = createContext<WeddingContextValue | undefined>(undefined);

/**
 * Resolves the signed-in user's weddings (GET /weddings) and exposes the active
 * one — replacing the previously hardcoded weddingId. A couple with zero weddings
 * is redirected into the intake flow; the active selection is persisted across
 * return visits.
 */
export function WeddingProvider({ children }: { children: ReactNode }) {
  const { request } = useApi();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const [weddings, setWeddings] = useState<WeddingSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() => localStorage.getItem(ACTIVE_KEY));
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const list = await request<WeddingSummary[]>("/weddings/");
      setWeddings(list);
      setActiveId((cur) => (cur && list.some((w) => w.id === cur) ? cur : list[0]?.id ?? null));
    } catch {
      // error surfaced via useApi; treat as no weddings
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  useEffect(() => {
    if (activeId) localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId]);

  // Only decides which screens to offer; the API enforces every level itself.
  const [myLevel, setMyLevel] = useState<string | null>(null);
  const [myLevelLoading, setMyLevelLoading] = useState(true);
  const refetchMyLevel = useCallback(async () => {
    if (!activeId) {
      setMyLevel(null);
      setMyLevelLoading(false);
      return;
    }
    try {
      const res = await request<{ level: string }>(`/weddings/${activeId}/my-access`);
      setMyLevel(res.level ?? null);
    } catch {
      setMyLevel(null);
    } finally {
      setMyLevelLoading(false);
    }
  }, [activeId, request]);

  useEffect(() => {
    refetchMyLevel();
  }, [refetchMyLevel]);

  // A couple with no wedding yet goes straight into intake (the activation hook).
  useEffect(() => {
    if (!loading && weddings.length === 0 && !pathname.endsWith("/intake")) {
      navigate("/wedding/intake", { replace: true });
    }
  }, [loading, weddings.length, pathname, navigate]);

  const value: WeddingContextValue = {
    weddings,
    activeWedding: weddings.find((w) => w.id === activeId) ?? null,
    setActiveWedding: useCallback((id: string) => setActiveId(id), []),
    loading,
    refetch,
    myLevel,
    myLevelLoading,
    refetchMyLevel,
  };

  return <WeddingContext.Provider value={value}>{children}</WeddingContext.Provider>;
}

export function useActiveWedding(): WeddingContextValue {
  const ctx = useContext(WeddingContext);
  if (!ctx) throw new Error("useActiveWedding must be used within <WeddingProvider>");
  return ctx;
}
