import { useEffect } from "react";
import { Outlet, NavLink, useLocation } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "../planner/Icon";
import { WorkspaceHeader } from "../shared/WorkspaceHeader";

const NAV_ITEMS = [
  { path: "/wedding", label: "Overview", deskIcon: "dashboard", mobileLabel: "Home", mobileIcon: "home", end: true, mobile: true },
  { path: "/wedding/vendors", label: "Vendors", deskIcon: "storefront", mobileLabel: "Vendors", mobileIcon: "favorite", mobile: true },
  { path: "/wedding/budget", label: "Budget", deskIcon: "payments", mobileLabel: "Budget", mobileIcon: "account_balance_wallet", mobile: true },
  { path: "/wedding/guests", label: "Guests & Seating", deskIcon: "group", mobileLabel: "Guests", mobileIcon: "people", mobile: true },
  { path: "/wedding/seating", label: "Seating Plan", deskIcon: "table_restaurant", mobileLabel: "Seating", mobileIcon: "table_restaurant", mobile: false },
  { path: "/wedding/timeline", label: "Timeline", deskIcon: "auto_schedule", mobileLabel: "Timeline", mobileIcon: "event", mobile: true },
];

function WeddingDesktopNav() {
  return (
    <nav className="hidden md:flex flex-col gap-base p-6 fixed left-0 top-16 bottom-0 w-72 bg-surface-container-low border-r border-outline-variant/20 z-40 overflow-y-auto">
      <div className="font-label-caps text-label-caps text-on-surface-variant mb-6 px-4 uppercase tracking-widest">
        Wedding Planner
      </div>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 px-4 py-3 rounded-full transition-all duration-200",
              isActive
                ? "bg-primary-container text-on-primary-container shadow-sm"
                : "text-on-secondary-fixed-variant hover:bg-surface-container-high",
            )
          }
        >
          <Icon name={item.deskIcon} />
          <span className="font-button-text text-button-text">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function WeddingBottomNav() {
  return (
    <nav className="bg-wedding-white fixed bottom-0 w-full z-50 md:hidden border-t border-outline-variant/20 shadow-sm flex justify-around items-center py-2 pb-safe">
      {NAV_ITEMS.filter((item) => item.mobile).map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center justify-center w-16 h-12 transition-all",
              isActive ? "text-primary" : "text-outline",
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon name={item.mobileIcon} filled={isActive} className="mb-1" />
              <span className="text-[10px] font-label-caps">{item.mobileLabel}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export function WeddingLayout() {
  const { pathname } = useLocation();
  const showShell = !pathname.endsWith("/concierge");

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return (
    <div className="wedding min-h-screen flex flex-col md:flex-row bg-background text-on-background font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container">
      {showShell && <WorkspaceHeader profileTo="/wedding/concierge" searchPlaceholder="Search vendors, guests…" />}
      {showShell && <WeddingDesktopNav />}
      <div className="flex-grow w-full min-w-0">
        <Outlet />
      </div>
      {showShell && <WeddingBottomNav />}
    </div>
  );
}
