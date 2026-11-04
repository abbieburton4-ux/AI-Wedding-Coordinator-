import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";
import { PlannerSidebar } from "./PlannerSidebar";
import { WorkspaceHeader } from "../shared/WorkspaceHeader";

export function PlannerLayout() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return (
    <div className="planner min-h-screen bg-surface-bright text-on-surface font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container">
      <WorkspaceHeader profileTo="/planner/concierge" searchPlaceholder="Search clients, tasks…" />
      <PlannerSidebar />
      <main className="md:ml-64 pt-16 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
