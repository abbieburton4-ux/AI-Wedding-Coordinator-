import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth, homeForRole } from "./AuthProvider";
import { AuthLoading } from "./AuthLoading";

/**
 * Gates a route group. Redirects unauthenticated users to /login (preserving the
 * intended path) and wrong-role users to their own home workspace.
 */
export function ProtectedRoute({ roles }: { roles?: string[] }) {
  const { user, role, loading } = useAuth();
  const location = useLocation();

  if (loading) return <AuthLoading />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (roles && role && !roles.includes(role)) {
    return <Navigate to={homeForRole(role)} replace />;
  }
  return <Outlet />;
}
