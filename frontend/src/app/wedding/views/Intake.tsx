import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useApi } from "../../api/useApi";
import { useActiveWedding } from "../WeddingProvider";

// Regions that have seeded venues, so the matcher returns real results.
const REGIONS = [
  "Dublin", "Wicklow", "Meath", "Kildare", "Louth", "Galway", "Mayo", "Sligo",
  "Donegal", "Clare", "Limerick", "Cork", "Tipperary", "Wexford", "Cavan",
  "Monaghan", "Westmeath", "Down",
];

const CEREMONY_TYPES = ["Civil/Humanist", "Irish Catholic", "Hindu", "Multi-cultural"];

const inputClass =
  "w-full rounded-2xl border border-outline-variant/40 bg-surface-container-low px-4 py-3 text-on-surface placeholder:text-on-surface-variant/60 focus:border-primary focus:outline-none transition-colors";
const labelClass = "block font-button-text text-button-text text-on-surface-variant mb-2";

export function Intake() {
  const { request, loading, error } = useApi();
  const { refetch, setActiveWedding } = useActiveWedding();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    couple_name: "",
    region: "Dublin",
    ceremony_type: "Civil/Humanist",
    guest_count_estimate: 120,
    budget_total: 35000,
    wedding_date: "",
    style_notes: "",
  });

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const payload: Record<string, unknown> = {
      region: form.region,
      ceremony_type: form.ceremony_type,
      guest_count_estimate: Number(form.guest_count_estimate),
      budget_total: Number(form.budget_total),
      couple_name: form.couple_name || undefined,
      style_notes: form.style_notes || undefined,
    };
    if (form.wedding_date) payload.wedding_date = form.wedding_date;

    try {
      const created = await request<{ id: string }>("/weddings/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refetch();
      setActiveWedding(created.id);
      // The AI planner runs free now and builds the teaser; the dashboard shows the
      // "building" spinner → preview. Payment (from the teaser) unlocks the rest.
      navigate("/wedding", { replace: true });
    } catch {
      // error rendered below via useApi state
    }
  }

  return (
    <div className="min-h-screen bg-background px-6 py-12 md:py-20 flex justify-center">
      <div className="w-full max-w-xl">
        <p className="font-label-caps text-label-caps uppercase tracking-widest text-on-surface-variant mb-3">
          Let's begin
        </p>
        <h1 className="font-display-sm text-display-sm text-on-surface mb-2">Tell us about your wedding</h1>
        <p className="text-body-md text-on-surface-variant mb-8">
          Your AI coordinator will draft a budget, a planning timeline, and a shortlist of venues and
          suppliers from this. You can refine everything afterwards.
        </p>

        {error && <p className="mb-4 text-sm text-error">{error}</p>}

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <div>
            <label className={labelClass}>Your names</label>
            <input className={inputClass} type="text" placeholder="e.g. Priya & David"
              value={form.couple_name} onChange={(e) => set("couple_name", e.target.value)} />
          </div>

          <div>
            <label className={labelClass}>Region</label>
            <select className={inputClass} value={form.region} onChange={(e) => set("region", e.target.value)}>
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          <div>
            <label className={labelClass}>Ceremony type</label>
            <select className={inputClass} value={form.ceremony_type} onChange={(e) => set("ceremony_type", e.target.value)}>
              {CEREMONY_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Estimated guests</label>
              <input className={inputClass} type="number" min={1} value={form.guest_count_estimate}
                onChange={(e) => set("guest_count_estimate", Number(e.target.value))} required />
            </div>
            <div>
              <label className={labelClass}>Total budget (€)</label>
              <input className={inputClass} type="number" min={0} step={500} value={form.budget_total}
                onChange={(e) => set("budget_total", Number(e.target.value))} required />
            </div>
          </div>

          <div>
            <label className={labelClass}>Wedding date <span className="text-on-surface-variant/60">(optional)</span></label>
            <input className={inputClass} type="date" value={form.wedding_date}
              onChange={(e) => set("wedding_date", e.target.value)} />
          </div>

          <div>
            <label className={labelClass}>Style notes <span className="text-on-surface-variant/60">(optional)</span></label>
            <textarea className={inputClass} rows={3} placeholder="e.g. coastal, relaxed, live trad music, documentary photography"
              value={form.style_notes} onChange={(e) => set("style_notes", e.target.value)} />
          </div>

          <button type="submit" disabled={loading}
            className="mt-2 rounded-full bg-primary text-on-primary px-8 py-3.5 font-button-text text-button-text disabled:opacity-60 hover:opacity-90 transition-opacity">
            {loading ? "Saving your details…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
