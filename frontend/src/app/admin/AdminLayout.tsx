import { useEffect } from "react";
import { Outlet, useLocation } from "react-router";
import { AdminSidebar } from "./AdminSidebar";
import { WorkspaceHeader } from "../shared/WorkspaceHeader";

export function AdminLayout() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);

  return (
    <div className="admin min-h-screen bg-surface-bright text-on-surface font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container">
      <WorkspaceHeader searchPlaceholder="Search planners, logs…" />
      <AdminSidebar />
      <main className="md:ml-64 pt-16 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
