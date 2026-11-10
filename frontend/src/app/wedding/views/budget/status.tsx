import type { ReactNode } from "react";
import { Icon } from "../../../shared/Icon";
import type { TargetState } from "./types";

// Green paid or within, amber close to a limit or coming up, red over or overdue,
// neutral for plain information. Colour is never the only cue: each has its words.
export type Tone = "good" | "warn" | "bad" | "neutral";

const CHIP: Record<Tone, string> = {
  good: "bg-status-booked text-status-booked-foreground",
  warn: "bg-status-todo text-status-todo-foreground",
  bad: "bg-status-not-selected text-status-not-selected-foreground",
  neutral: "bg-status-looking text-status-looking-foreground",
};
const FILL: Record<Tone, string> = {
  good: "bg-status-booked-foreground",
  warn: "bg-status-todo",
  bad: "bg-error",
  neutral: "bg-primary-container",
};
const ICON: Record<Tone, string> = { good: "check_circle", warn: "error", bad: "warning", neutral: "info" };

export function Chip({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${CHIP[tone]}`}>
      <Icon name={ICON[tone]} size={14} /> {children}
    </span>
  );
}

const TARGET: Record<TargetState, { tone: Tone; label: string }> = {
  no_target: { tone: "neutral", label: "No target set" },
  within: { tone: "good", label: "Within target" },
  near_limit: { tone: "warn", label: "Near the limit" },
  over: { tone: "bad", label: "Over target" },
};

export function TargetChip({ state }: { state: TargetState }) {
  const t = TARGET[state];
  return <Chip tone={t.tone}>{t.label}</Chip>;
}

export function targetTone(state: TargetState): Tone {
  return TARGET[state].tone;
}

/** A plain progress bar with its figure in words beside it. */
export function Bar({ label, pct, tone, text }: { label: string; pct: number | null; tone: Tone; text: string }) {
  const width = pct === null ? 0 : Math.max(0, Math.min(100, pct));
  return (
    <div>
      <div className="flex flex-wrap justify-between gap-x-3 text-sm mb-1">
        <span className="text-on-surface">{label}</span>
        <span className="text-on-surface-variant">{text}</span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={width}
        aria-valuetext={text}
        className="w-full bg-surface-container-low h-2.5 rounded-full overflow-hidden"
      >
        <div className={`h-full rounded-full ${FILL[tone]}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
