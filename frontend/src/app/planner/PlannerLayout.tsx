import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";
import { PlannerSidebar } from "./PlannerSidebar";
import { PlannerTopBar } from "./PlannerTopBar";

export function PlannerLayout() {
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return (
    <div className="planner flex min-h-screen bg-surface-bright text-on-surface font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container">
      <PlannerSidebar />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen min-w-0">
        <PlannerTopBar />
        <main ref={mainRef} className="flex-1 min-h-0 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
