import { NavLink } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "../planner/Icon";

const NAV_ITEMS = [
  { to: "/admin", label: "Ops Overview", icon: "dashboard", end: true },
  { to: "/admin/planners", label: "Planners", icon: "group" },
  { to: "/admin/agent-log", label: "Agent Decision Log", icon: "smart_toy" },
];

const FOOTER_ITEMS = [
  { to: "/admin/settings", label: "Settings", icon: "settings" },
  { to: "/", label: "Logout", icon: "logout" },
];

export function AdminSidebar() {
  return (
    <aside className="hidden md:flex fixed left-0 top-16 bottom-0 w-64 border-r border-outline-variant/20 bg-wedding-white flex-col py-6 px-4 z-40 overflow-y-auto">
      <div className="px-4 mb-6">
        <p className="font-headline-sm text-headline-sm text-primary">Admin Console</p>
        <p className="font-label-caps text-label-caps text-on-surface-variant">Internal Operations</p>
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
                {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full" />}
                <Icon name={item.icon} filled={isActive} className="text-[20px]" />
                <span className="font-body-md text-body-md">{item.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

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
