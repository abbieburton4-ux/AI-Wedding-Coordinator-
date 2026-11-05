import { useEffect, useState, useRef, useCallback, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../shared/Icon";
import { useWedding, useAgentMatcher, useApi } from "../../api";
import { POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from "../../api/config";
import { useActiveWedding } from "../WeddingProvider";

interface IntakeLog {
  id: string;
  agent_id: string;
  status: string;
  rationale_summary?: string;
  error_message?: string;
}

function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function Dashboard() {
  const navigate = useNavigate();
  const { activeWedding, refetch: refetchWeddings } = useActiveWedding();
  const weddingId = activeWedding?.id ?? null;

  const { data, loading, refetch } = useWedding(weddingId);
  const { triggerVenueMatch, status: matchStatus, rationale } = useAgentMatcher(weddingId ?? "");
  const { request } = useApi();

  const wedding = data.wedding ?? activeWedding;
  const building = !!wedding && wedding.status === "intake";
  const isRunningMatch = matchStatus === "running";

  const venues = data.bookings.filter((b) => b.venue_id);
  const suppliers = data.bookings.filter((b) => b.supplier_id);

  // The "what do I do next?" answer: the first unfinished checklist tasks, from the
  // groups open by default ("Catch up" and the current stage), else from the top.
  const groups = data.checklist?.groups ?? [];
  const current = groups.filter((g) => g.current);
  const nextSteps = (current.length ? current : groups)
    .flatMap((g) => g.tasks.filter((t) => !t.done).map((t) => ({ ...t, group: g })))
    .slice(0, 3);

  // ---- Intake recovery state ----
  // The wedding only flips to "planning" when the intake agent *succeeds*. If it
  // errors or the budget guardrail fires, status stays "intake" forever — so we
  // watch the latest intake_planner decision log and turn the dead-end spinner
  // into an actionable state (guardrail warning, retry).
  const [intakeLog, setIntakeLog] = useState<IntakeLog | null>(null);
  const [replanning, setReplanning] = useState(false);
  const replanBaselineId = useRef<string | undefined>(undefined);
  const [editingBudget, setEditingBudget] = useState(false);
  const [newBudget, setNewBudget] = useState(0);

  const fetchIntakeLog = useCallback(async () => {
    if (!weddingId) return;
    try {
      const logs = await request<IntakeLog[]>(`/weddings/${weddingId}/decisions`);
      const latest = logs.find((l) => l.agent_id === "intake_planner") ?? null;
      setIntakeLog(latest);
      // Release the local replan lock once a *fresh* run has landed (new log id,
      // no longer pending), so we don't flash the old guardrail card.
      setReplanning((r) =>
        r && latest && latest.id !== replanBaselineId.current && latest.status !== "pending" ? false : r,
      );
    } catch {
      /* keep last known intake log */
    }
  }, [weddingId, request]);

  // ---- Polling: while the intake planner drafts the budget ----
  const [waited, setWaited] = useState(0);
  const sawBuilding = useRef(false);
  if (building) sawBuilding.current = true;
  // Vendor matching no longer runs on its own at setup (PD-003, B11), so there's no
  // shortlist to wait for here.
  const poll =
    !!weddingId &&
    (building || replanning || (sawBuilding.current && waited < POLL_TIMEOUT_MS * 2));

  useEffect(() => {
    if (weddingId) fetchIntakeLog();
  }, [weddingId, fetchIntakeLog]);

  useEffect(() => {
    if (!poll) return;
    const pollId = setInterval(() => {
      refetch();
      fetchIntakeLog();
    }, POLL_INTERVAL_MS);
    const tickId = setInterval(() => setWaited((w) => w + POLL_INTERVAL_MS), POLL_INTERVAL_MS);
    return () => {
      clearInterval(pollId);
      clearInterval(tickId);
    };
  }, [poll, refetch, fetchIntakeLog]);

  // ---- Recovery actions ----
  const replan = useCallback(
    async (force: boolean) => {
      if (!weddingId) return;
      replanBaselineId.current = intakeLog?.id;
      setReplanning(true);
      setEditingBudget(false);
      setWaited(0);
      sawBuilding.current = true;
      try {
        await request(`/weddings/${weddingId}/replan?force=${force}`, { method: "POST" });
        await refetchWeddings();
      } catch {
        setReplanning(false);
      }
    },
    [weddingId, request, intakeLog, refetchWeddings],
  );

  const saveBudgetAndReplan = useCallback(async () => {
    if (!weddingId) return;
    replanBaselineId.current = intakeLog?.id;
    setReplanning(true);
    setEditingBudget(false);
    setWaited(0);
    sawBuilding.current = true;
    try {
      await request(`/weddings/${weddingId}`, {
        method: "PATCH",
        body: JSON.stringify({ budget_total: newBudget }),
      });
      await request(`/weddings/${weddingId}/replan?force=false`, { method: "POST" });
      await refetchWeddings();
      await refetch();
    } catch {
      setReplanning(false);
    }
  }, [weddingId, request, intakeLog, newBudget, refetchWeddings, refetch]);

  const intakeBlocked = building && !replanning && intakeLog?.status === "blocked_by_guardrail";
  const intakeFailed = building && !replanning && intakeLog?.status === "error";
  const slow = waited >= POLL_TIMEOUT_MS;
  const intakeStalled = building && !replanning && !intakeBlocked && !intakeFailed && slow;

  const shell = (children: ReactNode) => (
    <main className="pt-24 pb-32 px-margin-mobile md:pl-[calc(18rem+24px)] md:pr-margin-desktop max-w-[1120px] mx-auto">
      {children}
    </main>
  );

  // ---- Budget guardrail fired: the most valuable "AI caught it" moment ----
  if (intakeBlocked) {
    return shell(
      <div className="bg-wedding-white custom-shadow rounded-[3rem] p-10 border border-soft-clay/30 max-w-2xl mx-auto mt-8">
        <div className="flex items-start gap-4 mb-4">
          <Icon name="savings" size={28} className="text-soft-clay mt-1" />
          <div>
            <span className="font-label-caps text-[10px] text-soft-clay tracking-widest uppercase">
              Your coordinator flagged something
            </span>
            <h1 className="font-headline-sm text-headline-sm text-on-surface mt-1">
              This budget may fall short
            </h1>
          </div>
        </div>
        <p className="text-body-md text-on-surface-variant mb-6">
          {intakeLog?.error_message ||
            "The budget looks low for this guest count and region against typical Irish market rates."}
        </p>

        {editingBudget ? (
          <div className="flex flex-wrap items-end gap-3 mb-2">
            <div className="flex-1 min-w-[200px]">
              <label className="block font-button-text text-on-surface-variant mb-2 text-sm">
                Updated total budget (€)
              </label>
              <input
                type="number"
                min={0}
                step={500}
                value={newBudget}
                onChange={(e) => setNewBudget(Number(e.target.value))}
                className="w-full rounded-2xl border border-outline-variant/40 bg-surface-container-low px-4 py-3 text-on-surface focus:border-primary focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={saveBudgetAndReplan}
              className="bg-primary text-on-primary px-6 py-3 rounded-full font-button-text tracking-widest uppercase hover:opacity-90 transition-opacity"
            >
              Save & rebuild
            </button>
            <button
              type="button"
              onClick={() => setEditingBudget(false)}
              className="px-4 py-3 text-on-surface-variant text-sm hover:text-on-surface"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                setNewBudget(wedding?.budget_total ?? 0);
                setEditingBudget(true);
              }}
              className="bg-primary text-on-primary px-6 py-4 rounded-full font-button-text tracking-widest uppercase hover:opacity-90 transition-opacity"
            >
              Adjust my budget
            </button>
            <button
              type="button"
              onClick={() => replan(true)}
              className="px-6 bg-primary/10 text-primary py-4 rounded-full font-button-text tracking-widest uppercase hover:bg-primary/20 transition-colors"
            >
              Continue anyway
            </button>
          </div>
        )}
      </div>,
    );
  }

  // ---- Intake agent errored: never strand the user on a spinner ----
  if (intakeFailed) {
    return shell(
      <div className="bg-wedding-white custom-shadow rounded-[3rem] p-10 border border-error/30 max-w-2xl mx-auto mt-8 text-center">
        <Icon name="error" size={32} className="text-error mb-4 mx-auto" />
        <h1 className="font-headline-sm text-headline-sm text-on-surface mb-2">
          We couldn't finish building your plan
        </h1>
        <p className="text-body-md text-on-surface-variant max-w-md mx-auto mb-6">
          The AI coordinator hit a temporary problem. Your details are saved — you can try again now.
        </p>
        <button
          type="button"
          onClick={() => replan(false)}
          className="bg-primary text-on-primary px-8 py-4 rounded-full font-button-text tracking-widest uppercase hover:opacity-90 transition-opacity"
        >
          Try again
        </button>
      </div>,
    );
  }

  // ---- Activation moment: the AI is drafting the plan ----
  if (building || replanning) {
    return shell(
      <div className="bg-wedding-white custom-shadow rounded-[3rem] p-10 border border-outline-variant/10 flex flex-col items-center text-center max-w-2xl mx-auto mt-8">
        <span className="w-12 h-12 rounded-full border-2 border-primary/30 border-t-primary animate-spin mb-6" />
        <h1 className="font-headline-sm text-headline-sm text-on-surface mb-2">
          Your AI coordinator is building your plan
        </h1>
        <p className="text-body-md text-on-surface-variant max-w-md">
          Drafting a budget for a{" "}
          {wedding?.guest_count_estimate}-guest {wedding?.ceremony_type} wedding in {wedding?.region}.
        </p>
        {intakeStalled && (
          <div className="mt-6">
            <p className="text-sm text-on-surface-variant/70 mb-3">
              This is taking longer than usual.
            </p>
            <button
              type="button"
              onClick={() => replan(false)}
              className="px-6 bg-primary/10 text-primary py-3 rounded-full font-button-text tracking-widest uppercase hover:bg-primary/20 transition-colors"
            >
              Retry now
            </button>
          </div>
        )}
      </div>,
    );
  }

  // ---- The live, agent-built plan ----
  const summary = [
    { label: "Budget lines", value: data.budgetLines.length, icon: "payments", to: "/wedding/budget" },
    {
      label: "Checklist tasks done",
      value: data.checklist ? `${data.checklist.done} / ${data.checklist.total}` : "—",
      icon: "checklist",
      to: "/wedding/checklist",
    },
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

      {/* What to do next — the single most useful thing a coordinator gives you */}
      {nextSteps.length > 0 && (
        <section className="mb-10">
          <header className="flex items-center justify-between mb-4">
            <h2 className="font-headline-sm text-headline-sm text-on-surface">Your next steps</h2>
            <button
              type="button"
              onClick={() => navigate("/wedding/checklist")}
              className="text-sm font-button-text text-primary hover:opacity-80 transition-opacity"
            >
              View the checklist
            </button>
          </header>
          <div className="bg-wedding-white custom-shadow rounded-[3rem] p-3 border border-outline-variant/10 divide-y divide-outline-variant/10">
            {nextSteps.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => navigate("/wedding/checklist")}
                className="w-full text-left flex items-start gap-4 p-4 hover:bg-primary/5 rounded-[2rem] transition-colors"
              >
                <span className="mt-1 w-9 h-9 shrink-0 rounded-full bg-primary/10 flex items-center justify-center">
                  <Icon name="task_alt" size={18} className="text-primary" />
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-button-text text-on-surface">{t.title}</p>
                  <p className={`text-xs mt-1 font-bold uppercase tracking-wider ${t.label === "overdue" ? "text-error" : "text-on-surface-variant/70"}`}>
                    {t.label === "catch_up" ? "Catch up" : t.group.label}
                    {t.group.due_on ? ` · due ${formatDay(t.group.due_on)}` : ""}
                    {t.label === "overdue" ? " · overdue" : ""}
                  </p>
                </div>
                <Icon name="chevron_right" size={20} className="text-outline mt-1.5 shrink-0" />
              </button>
            ))}
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
