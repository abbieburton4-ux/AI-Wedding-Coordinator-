import React, { useEffect, useState } from "react";
import { Link, NavLink } from "react-router";
import { Menu, X } from "lucide-react";
import { cn } from "./cn";

const NAV_ITEMS = [
  { label: "Home", to: "/" },
  { label: "Experience", to: "/experience" },
  { label: "Portfolio", to: "/#portfolio" },
  { label: "Blog", to: "/#blog" },
  { label: "Contact", to: "/#contact" },
];

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <>
      <header
        className={cn(
          "fixed top-0 inset-x-0 z-50 transition-all duration-500 px-6 md:px-12 flex items-center justify-between",
          scrolled
            ? "bg-background/90 backdrop-blur-md shadow-sm py-4"
            : "bg-transparent py-6",
        )}
      >
        <Link to="/" className="flex flex-col items-start leading-none">
          <span className="font-serif text-xl tracking-[0.25em] text-foreground uppercase">
            VenueFlow
          </span>
          <span className="font-sans text-[9px] tracking-[0.3em] text-foreground/60 uppercase mt-1">
            Ireland
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-10">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "font-sans text-[11px] uppercase tracking-[0.2em] transition-colors",
                  isActive ? "text-primary" : "text-muted-foreground hover:text-primary",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:block">
          <Link
            to="/experience"
            className="inline-flex items-center justify-center font-sans uppercase tracking-[0.2em] text-[11px] font-medium border border-primary text-primary hover:bg-primary hover:text-primary-foreground px-10 py-2.5 rounded-full transition-colors duration-300"
          >
            Book
          </Link>
        </div>

        <button
          className="md:hidden text-foreground"
          aria-label="Toggle menu"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 bg-background z-40 flex items-center justify-center md:hidden">
          <div className="flex flex-col items-center space-y-8 text-sm tracking-[0.2em] uppercase font-medium">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.label}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "transition-colors",
                    isActive ? "text-primary" : "text-foreground hover:text-primary",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            <Link
              to="/experience"
              onClick={() => setOpen(false)}
              className="mt-4 inline-flex items-center justify-center font-sans uppercase tracking-[0.2em] text-[11px] border border-primary text-primary hover:bg-primary hover:text-primary-foreground px-10 py-3 rounded-full transition-colors"
            >
              Book
            </Link>
          </div>
        </div>
      )}
    </>
  );
}
