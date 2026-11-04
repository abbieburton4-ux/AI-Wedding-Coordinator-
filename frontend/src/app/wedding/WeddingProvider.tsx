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
  budget_total: number;
  guest_count_estimate: number;
  wedding_date?: string;
}

interface WeddingContextValue {
  weddings: WeddingSummary[];
  activeWedding: WeddingSummary | null;
  setActiveWedding: (id: string) => void;
  loading: boolean;
  refetch: () => Promise<void>;
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
  };

  return <WeddingContext.Provider value={value}>{children}</WeddingContext.Provider>;
}

export function useActiveWedding(): WeddingContextValue {
  const ctx = useContext(WeddingContext);
  if (!ctx) throw new Error("useActiveWedding must be used within <WeddingProvider>");
  return ctx;
}
