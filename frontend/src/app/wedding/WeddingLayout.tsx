import { useEffect, useRef } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router";
import { cn } from "../design-system/cn";
import { Icon } from "../planner/Icon";
import { IMG } from "../design-system/assets";

const NAV_ITEMS = [
  { path: "/wedding", label: "Overview", deskIcon: "dashboard", mobileLabel: "Home", mobileIcon: "home", end: true },
  { path: "/wedding/vendors", label: "Vendors", deskIcon: "storefront", mobileLabel: "Vendors", mobileIcon: "favorite" },
  { path: "/wedding/budget", label: "Budget", deskIcon: "payments", mobileLabel: "Budget", mobileIcon: "account_balance_wallet" },
  { path: "/wedding/guests", label: "Guests & Seating", deskIcon: "group", mobileLabel: "Guests", mobileIcon: "people" },
  { path: "/wedding/timeline", label: "Timeline", deskIcon: "auto_schedule", mobileLabel: "Timeline", mobileIcon: "event" },
];

function WeddingHeader() {
  const navigate = useNavigate();
  return (
    <header className="bg-surface text-primary font-headline-sm text-headline-sm fixed top-0 w-full z-50 border-b border-outline-variant/20 flex justify-between items-center px-margin-mobile md:px-margin-desktop h-16">
      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="Menu"
          className="md:hidden material-symbols-outlined cursor-pointer hover:bg-surface-container-low transition-colors p-2 rounded-full"
        >
          menu
        </button>
        <button
          type="button"
          onClick={() => navigate("/wedding")}
          className="font-headline-sm text-headline-sm tracking-widest text-primary cursor-pointer"
        >
          VENUEFLOW
        </button>
      </div>
      <button
        type="button"
        onClick={() => navigate("/wedding/concierge")}
        aria-label="Open concierge"
        className="w-10 h-10 rounded-full overflow-hidden bg-surface-container-high cursor-pointer hover:opacity-90 transition-opacity"
      >
        <img alt="Profile" className="w-full h-full object-cover" src={IMG.founderPortrait} />
      </button>
    </header>
  );
}

function WeddingDesktopNav() {
  return (
    <nav className="hidden md:flex flex-col gap-base p-6 fixed left-0 top-0 h-full w-72 bg-surface-container-low border-r border-outline-variant/20 pt-24 z-40">
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
      {NAV_ITEMS.map((item) => (
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
  const topRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return (
    <div
      ref={topRef}
      className="wedding min-h-screen flex flex-col md:flex-row bg-background text-on-background font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container"
    >
      {showShell && <WeddingHeader />}
      {showShell && <WeddingDesktopNav />}
      <div className="flex-grow w-full min-w-0">
        <Outlet />
      </div>
      {showShell && <WeddingBottomNav />}
    </div>
  );
}
