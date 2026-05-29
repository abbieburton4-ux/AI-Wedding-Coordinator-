import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../shared/Icon";
import { useWedding, useAgentMatcher } from "../../api";
import { POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from "../../api/config";
import { useActiveWedding } from "../WeddingProvider";

export function Dashboard() {
  const navigate = useNavigate();
  const { activeWedding } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;

  const { data, loading, refetch } = useWedding(weddingId);
  const { triggerVenueMatch, status: matchStatus, rationale } = useAgentMatcher(weddingId ?? "");

  const wedding = data.wedding ?? activeWedding;
  const building = !!wedding && wedding.status === "intake";
  const isRunningMatch = matchStatus === "running";

  const venues = data.bookings.filter((b) => b.venue_id);
  const suppliers = data.bookings.filter((b) => b.supplier_id);

  // Poll through intake AND the venue/supplier matcher cascade that lands
  // incrementally just after status flips to "planning". We poll for a bounded
  // window only for a wedding we watched go through intake this session, so the
  // dashboard keeps refreshing until the full shortlist arrives — while a
  // returning couple (already planned) doesn't poll at all.
  const [waited, setWaited] = useState(0);
  const sawBuilding = useRef(false);
  if (building) sawBuilding.current = true;
  const poll = !!weddingId && (building || (sawBuilding.current && waited < POLL_TIMEOUT_MS * 2));
  useEffect(() => {
    if (!poll) return;
    const pollId = setInterval(() => refetch(), POLL_INTERVAL_MS);
    const tickId = setInterval(() => setWaited((w) => w + POLL_INTERVAL_MS), POLL_INTERVAL_MS);
    return () => {
      clearInterval(pollId);
      clearInterval(tickId);
    };
  }, [poll, refetch]);
  const slow = waited >= POLL_TIMEOUT_MS;

  // ---- Activation moment: the AI is drafting the plan ----
  if (building) {
    return (
      <main className="pt-24 pb-32 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop max-w-[1120px] mx-auto">
        <div className="bg-wedding-white custom-shadow rounded-[3rem] p-10 border border-outline-variant/10 flex flex-col items-center text-center max-w-2xl mx-auto mt-8">
          <span className="w-12 h-12 rounded-full border-2 border-primary/30 border-t-primary animate-spin mb-6" />
          <h1 className="font-headline-sm text-headline-sm text-on-surface mb-2">
            Your AI coordinator is building your plan
          </h1>
          <p className="text-body-md text-on-surface-variant max-w-md">
            Drafting your budget, a planning timeline, and a shortlist of venues and suppliers for a{" "}
            {wedding?.guest_count_estimate}-guest {wedding?.ceremony_type} wedding in {wedding?.region}.
          </p>
          {slow && (
            <p className="text-sm text-on-surface-variant/70 mt-4">
              This is taking a little longer than usual — it'll appear here automatically.
            </p>
          )}
        </div>
      </main>
    );
  }

  // ---- The live, agent-built plan ----
  const summary = [
    { label: "Budget lines", value: data.budgetLines.length, icon: "payments", to: "/wedding/budget" },
    { label: "Timeline milestones", value: data.timelineItems.length, icon: "auto_schedule", to: "/wedding/timeline" },
    { label: "Venues shortlisted", value: venues.length, icon: "storefront", to: "/wedding/vendors" },
    { label: "Suppliers shortlisted", value: suppliers.length, icon: "favorite", to: "/wedding/vendors" },
  ];

  return (
    <main className="pt-24 pb-32 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop max-w-[1120px] mx-auto">
      {wedding && (
        <section className="mb-8">
          <div className="bg-primary-container/10 border border-primary-container/20 rounded-[3rem] p-6 flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="font-label-caps text-[10px] text-primary tracking-widest uppercase mb-1">Your wedding</p>
              <h2 className="font-headline-sm text-headline-sm text-on-surface">
                {wedding.region} • {wedding.ceremony_type}
              </h2>
              <p className="text-sm text-on-surface-variant mt-1">
                {wedding.guest_count_estimate} guests • €{wedding.budget_total.toLocaleString()} budget
              </p>
            </div>
            <span className="px-3 py-1.5 bg-primary/10 text-primary rounded-full text-xs font-bold uppercase tracking-wider">
              {wedding.status}
            </span>
          </div>
        </section>
      )}

      {isRunningMatch && (
        <section className="mb-6">
          <div className="bg-primary-container/20 border border-primary-container/40 rounded-[2rem] p-5 flex items-start gap-3">
            <Icon name="psychology" size={22} className="text-primary animate-pulse mt-0.5" />
            <div className="flex-1">
              <p className="font-button-text text-primary text-sm mb-1">AI agent working</p>
              <p className="font-body-md text-on-surface-variant text-sm">{rationale}</p>
            </div>
          </div>
        </section>
      )}

      {/* What the agents produced — live counts */}
      <section className="mb-10 grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summary.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => navigate(s.to)}
            className="text-left bg-wedding-white custom-shadow rounded-[2rem] p-5 border border-outline-variant/10 hover:border-primary/30 transition-colors"
          >
            <Icon name={s.icon} className="text-primary mb-3" />
            <p className="font-display-sm text-display-sm text-on-surface leading-none">
              {loading ? "—" : s.value}
            </p>
            <p className="text-sm text-on-surface-variant mt-1">{s.label}</p>
          </button>
        ))}
      </section>

      <section className="mb-12">
        <header className="flex items-center justify-between mb-6">
          <h2 className="font-headline-sm text-headline-sm text-on-surface">Venue shortlist</h2>
          <span className="bg-soft-clay/10 text-soft-clay font-label-caps text-[10px] px-2 py-1 rounded-full uppercase tracking-tighter">
            AI curated
          </span>
        </header>
        <div className="bg-wedding-white custom-shadow rounded-[3rem] p-6 border border-outline-variant/10">
          <p className="font-body-md text-on-surface-variant mb-6">
            {venues.length > 0
              ? `Your coordinator shortlisted ${venues.length} ${venues.length === 1 ? "venue" : "venues"} that fit your region, guest count, and budget.`
              : "No venues shortlisted yet — run the matcher to curate options that fit your brief."}
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => navigate("/wedding/vendors")}
              className="flex-1 min-w-[160px] bg-primary text-on-primary py-4 rounded-full font-button-text tracking-widest uppercase hover:opacity-90 transition-opacity"
            >
              Review all
            </button>
            <button
              type="button"
              disabled={isRunningMatch}
              onClick={() => triggerVenueMatch()}
              className="px-6 bg-primary/10 text-primary py-4 rounded-full font-button-text tracking-widest uppercase hover:bg-primary/20 transition-colors disabled:opacity-50"
            >
              {isRunningMatch ? "Matching…" : venues.length > 0 ? "Re-match" : "Match venues"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
