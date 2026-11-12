import { type ReactNode } from "react";
import { Link } from "react-router";
import { Eyebrow } from "../design-system/primitives";

/** Centered, brand-styled wrapper for the Login / Signup screens. */
export function AuthShell({
  eyebrow,
  title,
  children,
  footer,
}: {
  eyebrow: string;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center px-6 py-16">
      <Link
        to="/"
        className="mb-10 font-sans uppercase tracking-[0.3em] text-sm text-foreground hover:text-primary-text transition-colors"
      >
        VenueFlow
      </Link>
      <div className="w-full max-w-md">
        <Eyebrow text={eyebrow} />
        <h1 className="font-serif text-4xl md:text-5xl font-light leading-[1.1] mb-8">{title}</h1>
        {children}
      </div>
      {footer && <div className="mt-8 text-sm text-muted-foreground">{footer}</div>}
    </div>
  );
}

/** Shared input styling for the auth forms. */
export const authInputClass =
  "w-full bg-transparent border border-border rounded-full px-5 py-3 text-foreground placeholder:text-muted-foreground/60 focus:border-foreground focus:outline-none transition-colors";
