import { cn } from "../design-system/cn";

/**
 * Material Symbols Outlined icon. The icon name is the ligature text content
 * (e.g. "group", "auto_awesome"). Sizing/color come from utility classes.
 */
export function Icon({
  name,
  filled,
  className,
  size,
}: {
  name: string;
  filled?: boolean;
  className?: string;
  size?: number;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn("material-symbols-outlined", filled && "is-filled", className)}
      style={size ? { fontSize: size } : undefined}
    >
      {name}
    </span>
  );
}
