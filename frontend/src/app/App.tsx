import { BrowserRouter, Routes, Route } from "react-router";
import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { RoleRedirect } from "./auth/RoleRedirect";
import { Login } from "./auth/views/Login";
import { Signup } from "./auth/views/Signup";
import { Layout } from "./design-system/Layout";
import { Landing } from "./views/Landing";
import { Experience } from "./views/Experience";
import { PlannerLayout } from "./planner/PlannerLayout";
import { Overview } from "./planner/views/Overview";
import { Clients } from "./planner/views/Clients";
import { Tasks } from "./planner/views/Tasks";
import { Subscriptions } from "./planner/views/Subscriptions";
import { Analytics } from "./planner/views/Analytics";
import { Concierge } from "./planner/views/Concierge";
import { WeddingLayout } from "./wedding/WeddingLayout";
import { Dashboard } from "./wedding/views/Dashboard";
import { Intake } from "./wedding/views/Intake";
import { Checkout } from "./wedding/views/Checkout";
import { Vendors } from "./wedding/views/Vendors";
import { Budget } from "./wedding/views/Budget";
import { Guests } from "./wedding/views/Guests";
import { Timeline } from "./wedding/views/Timeline";
import { SeatingPlan } from "./wedding/views/SeatingPlan";
import { Concierge as WeddingConcierge } from "./wedding/views/Concierge";
import { AdminLayout } from "./admin/AdminLayout";
import { Overview as AdminOverview } from "./admin/views/Overview";
import { Planners as AdminPlanners } from "./admin/views/Planners";
import { AgentLog as AdminAgentLog } from "./admin/views/AgentLog";

const basename = import.meta.env.BASE_URL.replace(/\/$/, "") || "/";

export default function App() {
  return (
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <Routes>
          {/* Public marketing site */}
          <Route element={<Layout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/experience" element={<Experience />} />
            <Route path="*" element={<Landing />} />
          </Route>

          {/* Auth + post-login resolver */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/app" element={<RoleRedirect />} />

          {/* Couple workspace (also reachable by planners/admins) */}
          <Route element={<ProtectedRoute roles={["couple", "planner", "admin"]} />}>
            <Route path="/wedding" element={<WeddingLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="intake" element={<Intake />} />
              <Route path="checkout" element={<Checkout />} />
              <Route path="vendors" element={<Vendors />} />
              <Route path="budget" element={<Budget />} />
              <Route path="guests" element={<Guests />} />
              <Route path="seating" element={<SeatingPlan />} />
              <Route path="timeline" element={<Timeline />} />
              <Route path="concierge" element={<WeddingConcierge />} />
              <Route path="*" element={<Dashboard />} />
            </Route>
          </Route>

          {/* Planner workspace */}
          <Route element={<ProtectedRoute roles={["planner", "admin"]} />}>
            <Route path="/planner" element={<PlannerLayout />}>
              <Route index element={<Overview />} />
              <Route path="clients" element={<Clients />} />
              <Route path="tasks" element={<Tasks />} />
              <Route path="subscriptions" element={<Subscriptions />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="concierge" element={<Concierge />} />
              <Route path="*" element={<Overview />} />
            </Route>
          </Route>

          {/* Admin workspace */}
          <Route element={<ProtectedRoute roles={["admin"]} />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminOverview />} />
              <Route path="planners" element={<AdminPlanners />} />
              <Route path="agent-log" element={<AdminAgentLog />} />
              <Route path="*" element={<AdminOverview />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
