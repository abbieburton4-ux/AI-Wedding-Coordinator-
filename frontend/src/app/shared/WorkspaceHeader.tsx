import { useState } from "react";
import { Link, useLocation } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "../planner/Icon";
import { Avatar } from "../planner/Avatar";

type WorkspaceKey = "admin" | "planner" | "wedding";

const WORKSPACES: { key: WorkspaceKey; label: string; sub: string; to: string; icon: string; level: number }[] = [
  { key: "admin", label: "Admin", sub: "Internal ops & submission", to: "/admin", icon: "admin_panel_settings", level: 0 },
  { key: "planner", label: "Planner", sub: "Manage your weddings", to: "/planner", icon: "business_center", level: 1 },
  { key: "wedding", label: "Wedding", sub: "Couple's planning space", to: "/wedding", icon: "celebration", level: 2 },
];

export function WorkspaceHeader({ profileTo, searchPlaceholder = "Search…" }: { profileTo?: string; searchPlaceholder?: string }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const current = WORKSPACES.find((w) => pathname.startsWith(w.to)) ?? WORKSPACES[1];

  return (
    <header className="fixed top-0 inset-x-0 h-16 z-50 bg-wedding-white/90 backdrop-blur-md border-b border-outline-variant/20 flex items-center justify-between gap-4 px-margin-mobile md:px-margin-desktop">
      <div className="flex items-center gap-3 min-w-0">
        <Link to={current.to} className="flex items-center gap-2 shrink-0">
          <span className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center">
            <Icon name="auto_awesome" filled size={18} className="text-on-primary-container" />
          </span>
          <span className="font-headline-sm text-headline-sm text-on-surface tracking-widest hidden sm:inline">VENUEFLOW</span>
        </Link>

        <span className="text-outline-variant hidden sm:inline">/</span>

        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={open}
            className="flex items-center gap-2 rounded-full pl-2 pr-3 py-1.5 hover:bg-surface-container-low transition-colors"
          >
            <Icon name={current.icon} size={18} className="text-on-surface-variant" />
            <span className="font-button-text text-button-text text-on-surface">{current.label}</span>
            <Icon name="unfold_more" size={18} className="text-on-surface-variant" />
          </button>

          {open && (
            <>
              <div className="fixed inset-0 z-[59]" onClick={() => setOpen(false)} />
              <div className="absolute left-0 mt-2 w-72 z-[60] bg-wedding-white rounded-[1rem] border border-outline-variant/30 shadow-[0_8px_30px_rgba(142,103,73,0.12)] p-2 animate-slide-up">
                <p className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider px-3 py-2">Switch workspace</p>
                {WORKSPACES.map((w) => {
                  const active = w.key === current.key;
                  return (
                    <Link
                      key={w.key}
                      to={w.to}
                      onClick={() => setOpen(false)}
                      style={{ paddingLeft: 12 + w.level * 16 }}
                      className={cn(
                        "flex items-center gap-3 pr-3 py-2.5 rounded-[0.75rem] transition-colors",
                        active ? "bg-primary-container/20 text-on-primary-container" : "hover:bg-surface-container-low text-on-surface",
                      )}
                    >
                      {w.level > 0 && <Icon name="subdirectory_arrow_right" size={16} className="text-outline-variant -ml-1" />}
                      <Icon name={w.icon} size={20} className={active ? "text-on-primary-container" : "text-on-surface-variant"} />
                      <span className="flex-1 min-w-0">
                        <span className="block font-button-text text-button-text">{w.label}</span>
                        <span className="block text-[11px] text-on-surface-variant truncate">{w.sub}</span>
                      </span>
                      {active && <Icon name="check" size={18} className="text-on-primary-container" />}
                    </Link>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 md:gap-5">
        <div className="hidden lg:flex items-center w-64 bg-surface-container-low rounded-full px-4 py-2 border border-outline-variant/30 focus-within:border-outline transition-colors">
          <Icon name="search" size={20} className="text-on-surface-variant mr-2" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            className="bg-transparent border-none focus:ring-0 focus:outline-none text-body-md w-full placeholder:text-on-surface-variant/60 p-0 text-on-surface"
          />
        </div>
        <button type="button" aria-label="Notifications" className="relative text-on-surface-variant hover:text-on-surface transition-colors">
          <Icon name="notifications" />
          <span className="absolute top-0 right-0 w-2 h-2 bg-error rounded-full" />
        </button>
        <button type="button" aria-label="Help" className="hidden sm:block text-on-surface-variant hover:text-on-surface transition-colors">
          <Icon name="help_outline" />
        </button>
        {profileTo ? (
          <Link to={profileTo} aria-label="Profile">
            <Avatar initials="AM" className="w-8 h-8 text-[11px] border border-outline-variant/30" />
          </Link>
        ) : (
          <Avatar initials="AM" className="w-8 h-8 text-[11px] border border-outline-variant/30" />
        )}
      </div>
    </header>
  );
}
