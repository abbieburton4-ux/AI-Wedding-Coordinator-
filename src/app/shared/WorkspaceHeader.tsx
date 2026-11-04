import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";
import { useAuth } from "../auth/AuthProvider";

type WorkspaceKey = "admin" | "planner" | "wedding";

const WORKSPACES: {
  key: WorkspaceKey; label: string; sub: string; to: string; icon: string; level: number; roles: string[];
}[] = [
  { key: "admin", label: "Admin", sub: "Internal ops & submission", to: "/admin", icon: "admin_panel_settings", level: 0, roles: ["admin"] },
  { key: "planner", label: "Planner", sub: "Manage your weddings", to: "/planner", icon: "business_center", level: 1, roles: ["planner", "admin"] },
  { key: "wedding", label: "Wedding", sub: "Couple's planning space", to: "/wedding", icon: "celebration", level: 2, roles: ["couple", "planner", "admin"] },
];

function initialsOf(name?: string | null): string {
  if (!name) return "··";
  const parts = name.split(/\s+/).filter((w) => /[a-z]/i.test(w[0] ?? ""));
  if (parts.length === 0) return name.slice(0, 2).toUpperCase();
  return parts.slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

export function WorkspaceHeader({ profileTo, searchPlaceholder = "Search…" }: { profileTo?: string; searchPlaceholder?: string }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, role, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const accessible = WORKSPACES.filter((w) => role && w.roles.includes(role));
  const current = WORKSPACES.find((w) => pathname.startsWith(w.to)) ?? accessible[0] ?? WORKSPACES[2];

  async function handleSignOut() {
    setProfileOpen(false);
    await signOut();
    navigate("/login", { replace: true });
  }

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

        {/* Workspace switcher — only shown when the role can reach more than one. */}
        {accessible.length > 1 ? (
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
                  {accessible.map((w) => {
                    const active = w.key === current.key;
                    return (
                      <Link
                        key={w.key}
                        to={w.to}
                        onClick={() => setOpen(false)}
                        className={cn(
                          "flex items-center gap-3 pr-3 pl-3 py-2.5 rounded-[0.75rem] transition-colors",
                          active ? "bg-primary-container/20 text-on-primary-container" : "hover:bg-surface-container-low text-on-surface",
                        )}
                      >
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
        ) : (
          <span className="flex items-center gap-2 pl-2 pr-3 py-1.5">
            <Icon name={current.icon} size={18} className="text-on-surface-variant" />
            <span className="font-button-text text-button-text text-on-surface">{current.label}</span>
          </span>
        )}
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

        {/* Profile + sign out */}
        <div className="relative">
          <button type="button" aria-label="Account" aria-haspopup="menu" aria-expanded={profileOpen} onClick={() => setProfileOpen((v) => !v)}>
            <Avatar initials={initialsOf(user?.name)} className="w-8 h-8 text-[11px] border border-outline-variant/30" />
          </button>
          {profileOpen && (
            <>
              <div className="fixed inset-0 z-[59]" onClick={() => setProfileOpen(false)} />
              <div className="absolute right-0 mt-2 w-60 z-[60] bg-wedding-white rounded-[1rem] border border-outline-variant/30 shadow-[0_8px_30px_rgba(142,103,73,0.12)] p-2 animate-slide-up">
                <div className="px-3 py-2">
                  <p className="font-button-text text-button-text text-on-surface truncate">{user?.name ?? "Guest"}</p>
                  <p className="text-[11px] text-on-surface-variant truncate">{user?.email}</p>
                </div>
                {profileTo && (
                  <Link to={profileTo} onClick={() => setProfileOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-[0.75rem] hover:bg-surface-container-low text-on-surface transition-colors">
                    <Icon name="smart_toy" size={20} className="text-on-surface-variant" />
                    <span className="font-button-text text-button-text">Concierge</span>
                  </Link>
                )}
                <button type="button" onClick={handleSignOut}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[0.75rem] hover:bg-surface-container-low text-on-surface transition-colors text-left">
                  <Icon name="logout" size={20} className="text-on-surface-variant" />
                  <span className="font-button-text text-button-text">Sign out</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
