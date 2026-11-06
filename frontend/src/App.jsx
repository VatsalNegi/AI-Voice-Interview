
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Candidate pages
import Home from "./Home";
import CandidateRegistration from "./pages/candidate/CandidateRegistration";
import CandidateInstructions from "./pages/candidate/CandidateInstructions";
import LiveInterview from "./pages/candidate/LiveInterview";

// Recruiter pages
import RecruiterLogin from "./pages/Recruiter/RecruiterLogin";
import RecruiterDashboard from "./pages/Recruiter/RecruiterDashboard";
import InterviewDetails from "./pages/Recruiter/InterviewDetails";

// Authentication
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/recruiter/ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Home */}
          <Route path="/" element={<Home />} />

          {/* Candidate Routes */}
          <Route
            path="/candidate/register"
            element={<CandidateRegistration />}
          />

          <Route
            path="/candidate/instructions"
            element={<CandidateInstructions />}
          />

          <Route
            path="/candidate/interview"
            element={<LiveInterview />}
          />

          {/* Recruiter Login */}
          <Route
            path="/recruiter/login"
            element={<RecruiterLogin />}
          />

          {/* Protected Recruiter Routes */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/recruiter/dashboard"
              element={<RecruiterDashboard />}
            />

            <Route
              path="/recruiter/interviews/:sessionId"
              element={<InterviewDetails />}
            />
          </Route>

          {/* Fallback */}
          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
