
import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import {
  BrainCircuit,
  Camera,
  Mic,
  ShieldCheck,
  Clock,
  ArrowRight,
  LoaderCircle,
} from "lucide-react";

import { startInterview } from "../../services/api";

export default function CandidateInstructions() {
  const navigate = useNavigate();
  const location = useLocation();

  const { sessionId, candidateName, jobRole } = location.state || {};

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleStart = async () => {
    if (!sessionId) {
      setError("Interview session not found. Please register again.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await startInterview(sessionId);

      // Save session information for the live interview page
      sessionStorage.setItem("interviewSessionId", sessionId);
      sessionStorage.setItem("candidateName", candidateName || "Candidate");
      sessionStorage.setItem("jobRole", jobRole || "");

      // Navigate to the live interview screen
      navigate("/candidate/interview", {
        state: {
          sessionId,
          candidateName,
          jobRole,
          firstQuestion: response.first_question,
        },
      });

    } catch (err) {
      console.error("Start interview error:", err);

      setError(
        err.response?.data?.detail ||
        "Unable to start the interview. Please try again."
      );

    } finally {
      setLoading(false);
    }
  };

  if (!sessionId) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-center text-white">
        <h1 className="text-2xl font-bold">Session not found</h1>

        <button
          onClick={() => navigate("/candidate/register")}
          className="mt-6 rounded-xl bg-violet-600 px-6 py-3"
        >
          Register Again
        </button>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-12 text-white">
      <div className="mx-auto max-w-3xl">

        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/15 text-violet-400">
            <BrainCircuit size={34} />
          </div>

          <p className="text-sm font-semibold uppercase tracking-widest text-violet-400">
            Interview Preparation
          </p>

          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">
            You're almost ready, {candidateName}.
          </h1>

          <p className="mt-4 text-slate-400">
            Review the instructions before starting your AI interview.
          </p>
        </div>

        <div className="mb-6 rounded-2xl border border-white/10 bg-slate-900 p-6">
          <p className="text-sm text-slate-400">Interview details</p>

          <h2 className="mt-2 text-xl font-semibold">{jobRole}</h2>

          <p className="mt-3 break-all text-sm text-slate-500">
            Session ID: {sessionId}
          </p>
        </div>

        <div className="space-y-5 rounded-2xl border border-white/10 bg-slate-900 p-6">

          <h2 className="text-xl font-semibold">
            Before you begin
          </h2>

          {[
            {
              icon: Camera,
              title: "Camera access",
              text: "Keep your camera ready for the interview.",
            },
            {
              icon: Mic,
              title: "Microphone access",
              text: "Use a working microphone and speak clearly.",
            },
            {
              icon: ShieldCheck,
              title: "Interview integrity",
              text: "Stay on the interview screen and answer independently.",
            },
            {
              icon: Clock,
              title: "Interview duration",
              text: "Complete your interview within the allotted time.",
            },
          ].map((item, index) => {
            const Icon = item.icon;

            return (
              <div key={index} className="flex gap-4">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-500/15 text-violet-400">
                  <Icon size={22} />
                </div>

                <div>
                  <h3 className="font-semibold">{item.title}</h3>

                  <p className="mt-1 text-sm text-slate-400">
                    {item.text}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <p className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
            {error}
          </p>
        )}

        <button
          onClick={handleStart}
          disabled={loading}
          className="mt-7 flex w-full items-center justify-center gap-3 rounded-xl bg-violet-600 py-4 font-semibold hover:bg-violet-500 disabled:opacity-60"
        >
          {loading ? (
            <>
              <LoaderCircle className="animate-spin" size={20} />
              Starting Interview...
            </>
          ) : (
            <>
              Start Interview
              <ArrowRight size={20} />
            </>
          )}
        </button>

      </div>
    </main>
  );
}
