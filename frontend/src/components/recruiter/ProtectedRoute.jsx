
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#080d18] flex items-center justify-center text-white">
        Checking authentication...
      </div>
    );
  }

  return isAuthenticated
    ? <Outlet />
    : <Navigate to="/recruiter/login" replace />;
}
