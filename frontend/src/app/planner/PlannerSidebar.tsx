import { NavLink } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "./Icon";

const NAV_ITEMS = [
  { to: "/planner", label: "Overview", icon: "dashboard", end: true },
  { to: "/planner/clients", label: "Clients", icon: "group" },
  { to: "/planner/tasks", label: "Tasks", icon: "assignment" },
  { to: "/planner/subscriptions", label: "Subscriptions", icon: "payments" },
  { to: "/planner/analytics", label: "Analytics", icon: "analytics" },
];

const FOOTER_ITEMS = [
  { to: "/planner/settings", label: "Settings", icon: "settings" },
  { to: "/", label: "Logout", icon: "logout" },
];

export function PlannerSidebar() {
  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-full w-64 border-r border-outline-variant/20 bg-wedding-white flex-col py-8 px-4 z-40">
      <div className="flex items-center gap-base mb-12 px-4">
        <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center border border-outline-variant/30">
          <Icon name="auto_awesome" className="text-primary" filled />
        </div>
        <div>
          <h1 className="font-title-lg text-title-lg text-primary tracking-tight">VenueFlow</h1>
          <p className="font-label-caps text-label-caps text-on-surface-variant">Planner Studio</p>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              cn(
                "group relative flex items-center gap-base p-4 rounded-[1rem] transition-all duration-150",
                isActive
                  ? "text-primary font-bold bg-surface-container-low"
                  : "text-on-surface-variant font-medium hover:bg-surface-container-highest/50",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full" />
                )}
                <Icon name={item.icon} filled={isActive} className="text-[20px]" />
                <span className="font-body-md text-body-md">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto mb-8 px-2">
        <NavLink
          to="/planner/concierge"
          className="w-full bg-primary-container text-on-primary-container font-button-text text-button-text py-3 rounded-full flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
        >
          <Icon name="auto_awesome" className="text-[18px]" filled />
          AI Concierge
        </NavLink>
      </div>

      <div className="border-t border-outline-variant/20 pt-4 flex flex-col gap-1">
        {FOOTER_ITEMS.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            className="group flex items-center gap-base p-3 rounded-[1rem] text-on-surface-variant font-medium hover:bg-surface-container-highest/50 transition-all duration-150"
          >
            <Icon name={item.icon} className="text-[18px]" />
            <span className="font-body-md text-body-md">{item.label}</span>
          </NavLink>
        ))}
      </div>
    </aside>
  );
}
