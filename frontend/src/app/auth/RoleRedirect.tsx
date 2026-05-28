import { Navigate } from "react-router";
import { useAuth, homeForRole } from "./AuthProvider";
import { AuthLoading } from "./AuthLoading";

/** Post-login resolver: sends the user to the workspace matching their role. */
export function RoleRedirect() {
  const { user, role, loading } = useAuth();
  if (loading) return <AuthLoading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={homeForRole(role)} replace />;
}
