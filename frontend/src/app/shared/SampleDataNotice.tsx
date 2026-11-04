import type { ReactNode } from "react";
import { cn } from "../design-system/cn";
import { Icon } from "./Icon";

/**
 * Visible label for screens that show made-up example content instead of the
 * wedding's own data (AGENTS.md rule 10). Place it directly under the page
 * title so it's seen without scrolling.
 */
export function SampleDataNotice({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      role="note"
      className={cn(
        "bg-tertiary-fixed border border-tertiary/40 rounded-[2rem] px-5 py-4 flex items-start gap-3",
        className,
      )}
    >
      <Icon name="info" size={22} className="text-on-tertiary-fixed mt-0.5 shrink-0" />
      <div>
        <p className="font-button-text text-sm font-semibold text-on-tertiary-fixed">
          Sample data, not your wedding
        </p>
        <p className="text-sm text-on-tertiary-fixed-variant">{children}</p>
      </div>
    </div>
  );
}
