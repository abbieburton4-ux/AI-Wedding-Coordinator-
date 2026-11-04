import React from "react";
import { Link, type LinkProps } from "react-router";
import { cn } from "./cn";

type ButtonVariant = "outline" | "solid" | "ghost" | "link";

const buttonBase =
  "inline-flex items-center justify-center font-sans uppercase tracking-[0.2em] text-[11px] font-medium transition-all duration-300 cursor-pointer";

const buttonVariants: Record<ButtonVariant, string> = {
  outline:
    "border border-foreground/20 text-foreground hover:border-foreground hover:bg-foreground hover:text-background px-8 py-3 rounded-full",
  solid:
    "bg-primary text-primary-foreground hover:bg-primary/90 px-8 py-3 rounded-full",
  ghost:
    "text-foreground hover:text-primary px-0 py-0",
  link:
    "text-primary underline-offset-4 hover:underline px-0 py-0",
};

export function Button({
  children,
  className,
  variant = "outline",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button className={cn(buttonBase, buttonVariants[variant], className)} {...props}>
      {children}
    </button>
  );
}

export function ButtonLink({
  children,
  className,
  variant = "outline",
  ...props
}: LinkProps & { variant?: ButtonVariant }) {
  return (
    <Link className={cn(buttonBase, buttonVariants[variant], className)} {...props}>
      {children}
    </Link>
  );
}

export function Eyebrow({ text, className }: { text: string; className?: string }) {
  return (
    <div
      className={cn(
        "text-[0.65rem] md:text-xs tracking-[0.2em] uppercase font-medium text-muted-foreground mb-6",
        className,
      )}
    >
      {text}
    </div>
  );
}

export function SectionHeading({
  subtitle,
  title,
  italic,
  className,
}: {
  subtitle?: string;
  title: React.ReactNode;
  italic?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {subtitle && <Eyebrow text={subtitle} className="mb-0" />}
      <h2 className="font-serif text-4xl md:text-5xl lg:text-[4rem] leading-[1.1] text-foreground font-light">
        {title}
        {italic && <> <span className="italic">{italic}</span></>}
      </h2>
    </div>
  );
}

export function ReadMoreLink({
  text,
  to,
  className,
}: {
  text: string;
  to?: string;
  className?: string;
}) {
  const inner = (
    <>
      <span className="w-8 h-[1px] bg-muted-foreground mr-4 group-hover:w-12 group-hover:bg-primary transition-all duration-300" />
      <span className="text-[0.65rem] tracking-[0.2em] uppercase font-medium text-foreground group-hover:text-primary transition-colors">
        {text}
      </span>
    </>
  );
  const classes = cn("inline-flex items-center group w-fit cursor-pointer", className);
  if (to) {
    return (
      <Link to={to} className={classes}>
        {inner}
      </Link>
    );
  }
  return (
    <a href="#" className={classes}>
      {inner}
    </a>
  );
}

export function GoldSpecks({ className }: { className?: string }) {
  return (
    <div className={cn("absolute pointer-events-none", className)}>
      <div className="absolute w-1 h-1 bg-primary rounded-full top-0 left-0 opacity-60" />
      <div className="absolute w-1.5 h-1.5 bg-primary rounded-full top-6 left-10 opacity-40" />
      <div className="absolute w-[3px] h-[3px] bg-primary rounded-full top-12 left-2 opacity-80" />
      <div className="absolute w-2 h-2 bg-primary rounded-full top-4 left-20 opacity-30" />
      <div className="absolute w-1 h-1 bg-primary rounded-full top-16 left-16 opacity-50" />
    </div>
  );
}

export function MenuItem({
  title,
  description,
  price,
}: {
  title: string;
  description: string;
  price: string;
}) {
  return (
    <div className="flex flex-col group">
      <div className="flex items-baseline w-full">
        <h3 className="font-serif text-xl md:text-2xl font-light whitespace-nowrap">{title}</h3>
        <div className="flex-grow mx-4 relative overflow-hidden h-[1em]">
          <div className="absolute top-[0.7em] w-full border-b border-dotted border-border/80" />
        </div>
        <span className="font-sans text-sm md:text-base text-muted-foreground">{price}</span>
      </div>
      <p className="text-xs text-muted-foreground mt-1 font-light tracking-wide">{description}</p>
    </div>
  );
}
