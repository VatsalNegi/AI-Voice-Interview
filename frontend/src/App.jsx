
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Pages
import Home from "./Home";
import CandidateRegistration from "./pages/candidate/CandidateRegistration";
import CandidateInstructions from "./pages/candidate/CandidateInstructions";
import LiveInterview from "./pages/candidate/LiveInterview";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* Home Page */}
        <Route
          path="/"
          element={<Home />}
        />

        {/* Candidate Registration */}
        <Route
          path="/candidate/register"
          element={<CandidateRegistration />}
        />

        {/* Candidate Interview Instructions */}
        <Route
          path="/candidate/instructions"
          element={<CandidateInstructions />}
        />

        {/* Live Interview */}
        <Route
          path="/candidate/interview"
          element={<LiveInterview />}
        />

        {/* Unknown routes */}
        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />

      </Routes>
    </BrowserRouter>
  );
}
