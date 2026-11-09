import { BrowserRouter, Routes, Route, Navigate } from "react-router";
import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { RoleRedirect } from "./auth/RoleRedirect";
import { Login } from "./auth/views/Login";
import { Signup } from "./auth/views/Signup";
import { WeddingLayout } from "./wedding/WeddingLayout";
import { Dashboard } from "./wedding/views/Dashboard";
import { Intake } from "./wedding/views/Intake";
import { Vendors } from "./wedding/views/Vendors";
import { Budget } from "./wedding/views/Budget";
import { Guests } from "./wedding/views/Guests";
import { Checklist } from "./wedding/views/Checklist";
import { SeatingPlan } from "./wedding/views/SeatingPlan";
import { Concierge } from "./wedding/views/Concierge";
import { Access } from "./wedding/views/Access";
import { AURELIA_ENABLED } from "./wedding/features";

const basename = import.meta.env.BASE_URL.replace(/\/$/, "") || "/";

// A private app for one wedding (PD-001, PD-003): opening it goes to sign-in and
// then to the wedding. There's no public site, checkout, planner or admin area.
export default function App() {
  return (
    <BrowserRouter basename={basename}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/app" element={<RoleRedirect />} />

          {/* Access is enforced per wedding by the API; any signed-in account may open the workspace. */}
          <Route element={<ProtectedRoute />}>
            <Route path="/wedding" element={<WeddingLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="intake" element={<Intake />} />
              <Route path="vendors" element={<Vendors />} />
              <Route path="budget" element={<Budget />} />
              <Route path="guests" element={<Guests />} />
              <Route path="seating" element={<SeatingPlan />} />
              <Route path="checklist" element={<Checklist />} />
              {/* The checklist replaced the AI timeline (PD-007); old links still land there. */}
              <Route path="timeline" element={<Navigate to="/wedding/checklist" replace />} />
              {/* Aurelia is off (PD-010): an old link lands on the overview. */}
              <Route
                path="concierge"
                element={AURELIA_ENABLED ? <Concierge /> : <Navigate to="/wedding" replace />}
              />
              <Route path="access" element={<Access />} />
              <Route path="*" element={<Dashboard />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
