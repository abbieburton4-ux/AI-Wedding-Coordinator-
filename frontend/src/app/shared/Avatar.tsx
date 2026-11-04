import { cn } from "../design-system/cn";

/** Initial-based avatar used in place of the Stitch mockups' external photos. */
export function Avatar({
  initials,
  className,
}: {
  initials: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full bg-surface-container-high text-on-surface-variant font-label-caps uppercase select-none",
        className,
      )}
    >
      {initials}
    </div>
  );
}
