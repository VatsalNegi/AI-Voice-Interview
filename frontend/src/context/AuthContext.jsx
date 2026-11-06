
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [recruiter, setRecruiter] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("recruiter_token");
    setRecruiter(null);
  }, []);

  const fetchCurrentRecruiter = useCallback(async () => {
    const token = localStorage.getItem("recruiter_token");

    if (!token) {
      setRecruiter(null);
      setLoading(false);
      return;
    }

    try {
      const response = await api.get("/auth/me");
      setRecruiter(response.data);
    } catch (error) {
      console.error("Recruiter authentication failed:", error);
      localStorage.removeItem("recruiter_token");
      setRecruiter(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentRecruiter();
  }, [fetchCurrentRecruiter]);

  const login = async (email, password) => {
    const response = await api.post("/auth/login", {
      email,
      password,
    });

    const token = response.data.access_token;

    localStorage.setItem("recruiter_token", token);

    try {
      const recruiterResponse = await api.get("/auth/me");

      setRecruiter(recruiterResponse.data);

      return recruiterResponse.data;
    } catch (error) {
      localStorage.removeItem("recruiter_token");
      setRecruiter(null);
      throw error;
    }
  };

  const value = {
    recruiter,
    loading,
    isAuthenticated: Boolean(recruiter),
    login,
    logout,
    refreshRecruiter: fetchCurrentRecruiter,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider"
    );
  }

  return context;
}
