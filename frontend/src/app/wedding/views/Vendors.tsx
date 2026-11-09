import { useState, useEffect, useRef } from "react";
import { Icon } from "../../shared/Icon";
import { IMG } from "../../design-system/assets";
import { useWedding, useAgentMatcher, USE_FASTAPI_BACKEND } from "../../../app/api";
import { useReviewedRequest } from "../../api/review";
import { useActiveWedding } from "../WeddingProvider";
import { formatCents } from "./budget/money";

// Real vendors carry no photography, so we cycle a few brand images for warmth.
const CARD_IMAGES = [IMG.showroom, IMG.weddingConfetti, IMG.fineDining];

interface VendorBooking {
  id: string;
  status: string;
  vendor_name?: string;
  vendor_kind?: "venue" | "supplier";
  vendor_category?: string;
  vendor_location?: string;
  matching_rationale?: string;
  draft_inquiry_email?: string;
  quote_total?: number | null;
  quote_currency?: string | null;
  quote_rationale?: string | null;
  budget_category_name?: string | null;
  budget_match_key?: string | null;
  planned_cents?: number | null;
  budget_comparison?: BudgetComparison | null;
  over_budget?: boolean | null;
  over_by_cents?: number | null;
}

type BudgetComparison =
  | "over"
  | "within"
  | "no_category"
  | "no_planned_amount"
  | "currency_mismatch"
  | "no_quote";

/** Quote loop: paste a vendor's email reply → quote_extractor parses it → the card
 *  compares it with the couple's budget. Polls until the agent's result lands. */
function QuoteLogger({ booking, refetch }: { booking: VendorBooking; refetch: () => Promise<void> }) {
  const sendReviewed = useReviewedRequest();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  async function submit() {
    if (!text.trim()) return;
    setSubmitting(true);
    setErr(null);
    try {
      // Shows the cleaned email first; nothing is sent until they click (PD-008).
      const sent = await sendReviewed(`/inquiries/${booking.id}/quote`, { email_body: text });
      if (sent === null) return; // went back to edit the pasted text
      // The extractor runs async on the worker — poll until the quote lands (which
      // re-renders this card into the "quote received" panel and unmounts us).
      for (let i = 0; i < 20 && mounted.current; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        await refetch();
      }
      if (mounted.current) setErr("Still working… give it a moment and refresh.");
    } catch (e: any) {
      if (mounted.current) setErr(e?.message || "Could not extract the quote. Try again.");
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 text-sm font-button-text text-primary hover:opacity-80 transition-opacity"
      >
        <Icon name="forward_to_inbox" size={18} /> Heard back? Log their reply
      </button>
    );
  }

  return (
    <div>
      <p className="text-xs text-on-surface-variant mb-2">
        Paste the vendor's email reply — the AI reads the price, checks it against your budget,
        and updates your tracker. You'll see exactly what goes to the AI before it's sent.
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder="Paste the vendor's reply here…"
        className="w-full rounded-2xl border border-outline-variant/40 bg-surface-container-low px-3 py-2 text-sm text-on-surface focus:border-primary focus:outline-none"
      />
      {err && <p className="text-xs text-error mt-1">{err}</p>}
      <div className="flex items-center gap-2 mt-2">
        <button
          type="button"
          onClick={submit}
          disabled={submitting || !text.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-full text-xs font-button-text uppercase tracking-wider hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {submitting ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-on-primary border-t-transparent rounded-full animate-spin" />
              Extracting…
            </>
          ) : (
            <>
              <Icon name="auto_awesome" size={15} /> Extract quote
            </>
          )}
        </button>
        {!submitting && (
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="px-3 py-2 text-xs text-on-surface-variant hover:text-on-surface"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

/** The quote in its own currency, e.g. "€4,500" or "$3,000.50". Display only. */
function formatQuote(amount: number, currency?: string | null): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: (currency || "").trim().toUpperCase(),
      maximumFractionDigits: 2,
      minimumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString("en-US")} ${currency ?? ""}`.trim();
  }
}

/** How the quote compares with the couple's own budget for this category (PD-004). */
function budgetLine(booking: VendorBooking): string | null {
  // The name the backend matched on ("venue" for every venue), not the venue's type.
  const key = booking.budget_match_key;
  const category =
    booking.budget_category_name ?? (key ? key.charAt(0).toUpperCase() + key.slice(1) : "this");
  const planned = booking.planned_cents;
  switch (booking.budget_comparison) {
    case "over":
      return planned != null && booking.over_by_cents != null
        ? `${formatCents(booking.over_by_cents)} over the ${formatCents(planned)} planned for ${category}`
        : null;
    case "within":
      return planned != null ? `Within the ${formatCents(planned)} planned for ${category}` : null;
    case "no_category":
      return `Not compared: your budget has no ${category} category.`;
    case "no_planned_amount":
      return `Not compared: no planned amount for ${category} in your budget yet.`;
    case "currency_mismatch":
      return `Not compared: this quote is in ${booking.quote_currency || "another currency"} and your budget is in US dollars.`;
    default:
      return null;
  }
}

/** Shows the AI-read quote and how it compares with the couple's budget. */
function QuotePanel({ booking }: { booking: VendorBooking }) {
  const over = booking.budget_comparison === "over";
  const note = budgetLine(booking);
  return (
    <div
      className={`rounded-2xl p-3 border ${
        over
          ? "bg-error-container/15 border-error-container/40"
          : "bg-primary-container/10 border-primary-container/20"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="font-label-caps text-[10px] tracking-widest uppercase text-on-surface-variant">
          AI-read quote
        </p>
        {over && (
          <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-error">
            <Icon name="warning" size={13} /> Over budget
          </span>
        )}
      </div>
      <p className="font-title-lg text-title-lg text-on-surface mt-1 leading-tight">
        {formatQuote(booking.quote_total ?? 0, booking.quote_currency)}
      </p>
      {note && <p className="text-xs text-on-surface-variant">{note}</p>}
      {booking.quote_rationale && (
        <p className="text-xs text-on-surface-variant mt-2 leading-relaxed">{booking.quote_rationale}</p>
      )}
    </div>
  );
}

function prettyCategory(b: VendorBooking) {
  const c = b.vendor_category || (b.vendor_kind === "venue" ? "Venue" : "Supplier");
  return c.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function VendorCard({ booking, img, refetch }: { booking: VendorBooking; img: string; refetch: () => Promise<void> }) {
  const [showEmail, setShowEmail] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!booking.draft_inquiry_email) return;
    try {
      await navigator.clipboard.writeText(booking.draft_inquiry_email);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — no-op */
    }
  };

  return (
    <div className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 overflow-hidden flex flex-col group hover:shadow-lg transition-all">
      <div className="relative h-40 w-full">
        <img src={img} alt={booking.vendor_name ?? "Vendor"} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
        <div className="absolute top-3 right-3 bg-surface-container-lowest/90 px-3 py-1 rounded-full flex items-center gap-1">
          <Icon name="auto_awesome" filled size={14} className="text-tertiary" />
          <span className="font-label-caps text-[10px] text-tertiary font-bold">AI MATCH</span>
        </div>
      </div>

      <div className="p-gutter flex flex-col flex-1 gap-3">
        <div className="flex justify-between items-start gap-2">
          <div>
            <span className="font-label-caps text-[10px] text-outline tracking-widest uppercase">{prettyCategory(booking)}</span>
            <h3 className="font-title-lg text-title-lg text-on-surface mt-1 leading-tight">{booking.vendor_name ?? "Vendor"}</h3>
            {booking.vendor_location && (
              <p className="text-sm text-on-surface-variant mt-0.5 flex items-center gap-1">
                <Icon name="location_on" size={14} className="text-outline" />
                {booking.vendor_location}
              </p>
            )}
          </div>
          <span className="shrink-0 px-2.5 py-1 bg-primary/10 text-primary rounded-full text-[10px] font-bold uppercase tracking-wider">
            {booking.status}
          </span>
        </div>

        {/* The magic: why the coordinator picked this one */}
        {booking.matching_rationale && (
          <div className="bg-primary-container/10 border border-primary-container/20 rounded-2xl p-3">
            <p className="font-label-caps text-[10px] text-primary tracking-widest uppercase mb-1">Why your coordinator picked this</p>
            <p className="text-sm text-on-surface-variant leading-relaxed">{booking.matching_rationale}</p>
          </div>
        )}

        {/* The ready-to-send draft email */}
        {booking.draft_inquiry_email && (
          <div className="mt-auto">
            <button
              type="button"
              onClick={() => setShowEmail((s) => !s)}
              className="flex items-center gap-2 text-sm font-button-text text-primary hover:opacity-80 transition-opacity"
            >
              <Icon name={showEmail ? "expand_less" : "mail"} size={18} />
              {showEmail ? "Hide draft email" : "View draft inquiry email"}
            </button>
            {showEmail && (
              <div className="mt-3">
                <pre className="whitespace-pre-wrap text-xs text-on-surface-variant bg-surface-container-low rounded-2xl p-4 max-h-56 overflow-y-auto font-body-md">
                  {booking.draft_inquiry_email}
                </pre>
                <button
                  type="button"
                  onClick={copy}
                  className="mt-2 flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-full text-xs font-button-text uppercase tracking-wider hover:opacity-90 transition-opacity"
                >
                  <Icon name={copied ? "check" : "content_copy"} size={15} />
                  {copied ? "Copied" : "Copy email"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Quote loop: log a vendor reply → AI reads the quote → compared with the budget */}
        <div className="pt-1">
          {booking.quote_total != null ? (
            <QuotePanel booking={booking} />
          ) : (
            <QuoteLogger booking={booking} refetch={refetch} />
          )}
        </div>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-surface-container-lowest rounded-[3rem] border border-outline-variant/20 overflow-hidden flex flex-col animate-pulse">
      <div className="h-40 w-full bg-surface-container-low" />
      <div className="p-gutter flex flex-col gap-3">
        <div className="h-3 bg-surface-container-low rounded-full w-1/3" />
        <div className="h-5 bg-surface-container-low rounded-full w-2/3" />
        <div className="h-3 bg-surface-container-low rounded-full w-1/2" />
      </div>
    </div>
  );
}

export function Vendors() {
  const { activeWedding } = useActiveWedding();
  const weddingId = activeWedding?.id ?? "";
  const { data, loading, refetch } = useWedding(weddingId || null);
  const { triggerVenueMatch, status, rationale, errorMsg } = useAgentMatcher(weddingId);

  const isRunning = status === "running";
  const bookings = (data.bookings ?? []) as VendorBooking[];
  const venues = bookings.filter((b) => b.vendor_kind === "venue");
  const suppliers = bookings.filter((b) => b.vendor_kind === "supplier");
  const ordered = [...venues, ...suppliers];
  const hasResults = ordered.length > 0;

  return (
    <main className="pt-16 md:pl-72 pb-20 md:pb-8">
      <section className="px-margin-mobile md:px-margin-desktop py-8 md:py-12 bg-surface">
        <div className="flex flex-col gap-6">
          <div>
            <h2 className="font-display-lg-mobile md:font-display-lg text-display-lg-mobile md:text-display-lg text-primary">
              Curated Vendors
            </h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mt-2">
              {hasResults
                ? `Your coordinator shortlisted ${venues.length} venue${venues.length === 1 ? "" : "s"} and ${suppliers.length} supplier${suppliers.length === 1 ? "" : "s"} that fit your brief — with a reason and a ready-to-send email for each.`
                : "Discover and manage the professionals bringing your vision to life."}
            </p>
          </div>
          {USE_FASTAPI_BACKEND && (
            <div className="flex">
              <button
                type="button"
                disabled={isRunning}
                onClick={() => triggerVenueMatch()}
                className="flex items-center gap-2 px-6 h-12 bg-primary/10 rounded-full border border-primary/20 text-primary hover:bg-primary/20 transition-colors disabled:opacity-50 disabled:cursor-wait"
              >
                {isRunning ? (
                  <>
                    <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    <span className="font-button-text">Matching...</span>
                  </>
                ) : (
                  <>
                    <Icon name="auto_awesome" size={18} />
                    <span className="font-button-text">{hasResults ? "Re-run venue matcher" : "Run AI venue matcher"}</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </section>

      <section className="px-margin-mobile md:px-margin-desktop py-6">
        {/* Agent status banners */}
        {isRunning && (
          <div className="bg-primary-container/20 border border-primary-container/40 rounded-[2rem] p-5 mb-6 flex items-start gap-3">
            <Icon name="psychology" size={22} className="text-primary animate-pulse mt-0.5" />
            <div className="flex-1">
              <p className="font-button-text text-primary text-sm mb-1">AI agent working</p>
              <p className="font-body-md text-on-surface-variant text-sm">{rationale}</p>
            </div>
          </div>
        )}
        {status === "blocked" && (
          <div className="bg-tertiary-container/20 border border-tertiary-container/50 rounded-[2rem] p-5 mb-6 flex items-start gap-3">
            <Icon name="shield" size={22} className="text-tertiary mt-0.5" />
            <p className="font-body-md text-on-surface-variant text-sm">{rationale}</p>
          </div>
        )}
        {status === "error" && (
          <div className="bg-error-container/20 border border-error-container/40 rounded-[2rem] p-5 mb-6 flex items-start gap-3">
            <Icon name="error" size={22} className="text-error mt-0.5" />
            <p className="font-body-md text-on-surface-variant text-sm">{errorMsg}</p>
          </div>
        )}

        {/* Empty state */}
        {!isRunning && !loading && !hasResults && (
          <div className="bg-wedding-white custom-shadow rounded-[3rem] p-10 border border-outline-variant/10 text-center max-w-xl mx-auto">
            <Icon name="storefront" size={32} className="text-primary mb-3 mx-auto" />
            <h3 className="font-headline-sm text-headline-sm text-on-surface mb-2">No vendors yet</h3>
            <p className="text-body-md text-on-surface-variant">
              Run the AI venue matcher above and your coordinator will curate options that fit your region, guest count, and budget.
            </p>
          </div>
        )}

        {/* Vendor grid — skeleton or real AI-matched cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-gutter">
          {isRunning && !hasResults ? (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          ) : (
            ordered.map((b, i) => <VendorCard key={b.id} booking={b} img={CARD_IMAGES[i % CARD_IMAGES.length]} refetch={refetch} />)
          )}
        </div>
      </section>
    </main>
  );
}
