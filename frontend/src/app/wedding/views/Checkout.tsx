import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useApi } from "../../api/useApi";
import { useActiveWedding } from "../WeddingProvider";
import { COUPLE_PRICE_EUR } from "../../api/config";

interface CheckoutResponse {
  provider: "mock" | "stripe";
  status: string;
  url: string | null;
  amount: number;
  currency: string;
}

const INCLUDED = [
  "An AI-drafted budget split across every category",
  "A full planning timeline tailored to your ceremony",
  "A shortlist of venues + suppliers, with inquiry emails drafted for you",
];

const cardClass =
  "rounded-3xl border border-outline-variant/40 bg-surface-container-low p-8 shadow-sm";

export function Checkout() {
  const { request, loading, error } = useApi();
  const { activeWedding, refetch } = useActiveWedding();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  const weddingId = activeWedding?.id ?? null;

  // Checkout is valid while the plan is unpaid ('intake' building, or 'preview'
  // teaser). Once paid (status 'planning' or later) bounce to the dashboard —
  // payment is idempotent.
  useEffect(() => {
    if (activeWedding && activeWedding.status !== "intake" && activeWedding.status !== "preview") {
      navigate("/wedding", { replace: true });
    }
  }, [activeWedding, navigate]);

  async function onPay() {
    if (!weddingId) return;
    setSubmitting(true);
    try {
      const res = await request<CheckoutResponse>("/payments/checkout", {
        method: "POST",
        body: JSON.stringify({ wedding_id: weddingId }),
      });
      if (res.url) {
        // Stripe path: hand off to the hosted checkout page.
        window.location.href = res.url;
        return;
      }
      // Mock path: payment recorded server-side, planning already kicked off.
      await refetch();
      navigate("/wedding", { replace: true });
    } catch {
      // surfaced via useApi error state below
    } finally {
      setSubmitting(false);
    }
  }

  const busy = loading || submitting;

  return (
    <div className="min-h-screen bg-background px-6 py-12 md:py-20 flex justify-center">
      <div className="w-full max-w-md">
        <p className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant mb-3">
          One last step
        </p>
        <h1 className="font-display-sm text-display-sm text-on-surface mb-2">
          Unlock your AI Wedding Coordinator
        </h1>
        <p className="text-body-md text-on-surface-variant mb-8">
          A one-time fee unlocks your full plan. Less than 1% of the average Irish
          wedding — and a fraction of a human coordinator's €4,000+ fee.
        </p>

        <div className={cardClass}>
          <div className="flex items-baseline gap-2 mb-6">
            <span className="font-display-sm text-display-sm text-on-surface">
              €{COUPLE_PRICE_EUR}
            </span>
            <span className="text-body-md text-on-surface-variant">· one-time</span>
          </div>

          <ul className="flex flex-col gap-3 mb-8">
            {INCLUDED.map((item) => (
              <li key={item} className="flex items-start gap-3 text-body-md text-on-surface">
                <span className="mt-0.5 text-primary" aria-hidden>✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          {error && <p className="mb-4 text-sm text-error">{error}</p>}

          <button
            type="button"
            onClick={onPay}
            disabled={busy || !weddingId}
            className="w-full rounded-full bg-primary text-on-primary px-8 py-3.5 font-button-text text-button-text disabled:opacity-60 hover:opacity-90 transition-opacity"
          >
            {busy ? "Processing…" : `Pay €${COUPLE_PRICE_EUR} & build my plan`}
          </button>

          {!weddingId && (
            <p className="mt-4 text-center text-sm text-on-surface-variant">
              No wedding found.{" "}
              <button
                type="button"
                className="text-primary underline"
                onClick={() => navigate("/wedding/intake")}
              >
                Start your intake
              </button>
            </p>
          )}
        </div>

        {/* Demo-mode notice. Remove or revise when PAYMENTS_PROVIDER=stripe. */}
        <p className="mt-4 text-center text-xs text-on-surface-variant/70">
          Demo checkout — no real charge is made.
        </p>
      </div>
    </div>
  );
}
