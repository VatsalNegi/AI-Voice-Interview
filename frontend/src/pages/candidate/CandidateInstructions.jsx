
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  BrainCircuit,
  Camera,
  Mic,
  ShieldCheck,
  Clock,
  ArrowRight,
  LoaderCircle,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

import {
  startInterview,
  getInterview,
} from "../../services/api";

export default function CandidateInstructions() {
  const navigate = useNavigate();
  const location = useLocation();

  const { sessionId, candidateName, jobRole } = location.state || {};

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [preparationStatus, setPreparationStatus] = useState("pending");
  const [preparationError, setPreparationError] = useState("");
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [statusCheckError, setStatusCheckError] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);

  // -----------------------------------------
  // POLL INTERVIEW PREPARATION STATUS
  // -----------------------------------------

  useEffect(() => {
    if (!sessionId) return;

    let active = true;
    let intervalId;

    const checkPreparationStatus = async () => {
      try {
        const response = await getInterview(sessionId);

        if (!active) return;

        const status = response.preparation_status;

        setPreparationStatus(status || "pending");
        setPreparationError(response.preparation_error || "");
        setTotalQuestions(response.total_questions || 0);
        setStatusCheckError(false);
        setCheckingStatus(false);

        // Stop polling after a final preparation state.
        if (status === "ready" || status === "failed") {
          if (intervalId) {
            clearInterval(intervalId);
          }
        }
      } catch (err) {
        if (!active) return;

        console.error("Preparation status error:", err);
        setStatusCheckError(true);
        setCheckingStatus(false);
      }
    };

    // Check immediately when the page opens.
    checkPreparationStatus();

    // Check every 3 seconds.
    intervalId = setInterval(() => {
      checkPreparationStatus();
    }, 3000);

    return () => {
      active = false;

      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [sessionId]);

  // -----------------------------------------
  // START INTERVIEW
  // -----------------------------------------

  const handleStart = async () => {
    if (!sessionId) {
      setError("Interview session not found. Please register again.");
      return;
    }

    if (preparationStatus !== "ready") {
      setError("Interview questions are not ready yet.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await startInterview(sessionId);

      sessionStorage.setItem("interviewSessionId", sessionId);
      sessionStorage.setItem(
        "candidateName",
        candidateName || "Candidate"
      );
      sessionStorage.setItem("jobRole", jobRole || "");

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

  // -----------------------------------------
  // INVALID SESSION
  // -----------------------------------------

  if (!sessionId) {
    return (
      <main className="min-h-screen bg-slate-950 p-8 text-center text-white">
        <AlertCircle className="mx-auto mb-4 text-red-400" size={40} />

        <h1 className="text-2xl font-bold">
          Session not found
        </h1>

        <button
          onClick={() => navigate("/candidate/register")}
          className="mt-6 rounded-xl bg-violet-600 px-6 py-3"
        >
          Register Again
        </button>
      </main>
    );
  }

  // -----------------------------------------
  // PREPARATION FAILED
  // -----------------------------------------

  if (preparationStatus === "failed") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-5 py-12 text-white">
        <div className="w-full max-w-xl rounded-3xl border border-red-500/20 bg-slate-900 p-8 text-center">

          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10 text-red-400">
            <AlertCircle size={34} />
          </div>

          <p className="text-sm font-semibold uppercase tracking-widest text-red-400">
            Preparation Failed
          </p>

          <h1 className="mt-4 text-3xl font-bold">
            We couldn't prepare your interview.
          </h1>

          <p className="mt-4 text-slate-400">
            Something went wrong while generating your interview
            questions. Please contact your recruiter for assistance.
          </p>

          {preparationError && (
            <div className="mt-6 break-words rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-left text-sm text-red-300">
              {preparationError}
            </div>
          )}

          <button
            onClick={() => navigate("/")}
            className="mt-7 w-full rounded-xl bg-violet-600 py-4 font-semibold hover:bg-violet-500"
          >
            Return to Home
          </button>

        </div>
      </main>
    );
  }

  // -----------------------------------------
  // PREPARATION WAITING SCREEN
  // -----------------------------------------

  if (preparationStatus !== "ready") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-5 py-12 text-white">

        <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-slate-900 p-7 text-center sm:p-10">

          <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-violet-500/15 text-violet-400">
            <BrainCircuit size={42} />
          </div>

          <p className="text-sm font-semibold uppercase tracking-widest text-violet-400">
            AI Interview Preparation
          </p>

          <h1 className="mt-4 text-3xl font-bold sm:text-4xl">
            Preparing your interview,
            <span className="block text-violet-400">
              {candidateName || "Candidate"}
            </span>
          </h1>

          <p className="mx-auto mt-5 max-w-lg leading-7 text-slate-400">
            Our AI is analyzing your job description and preparing
            personalized interview questions based on the role.
            This may take a little time.
          </p>

          <div className="mt-9 rounded-2xl border border-violet-500/20 bg-violet-500/5 p-6">

            <LoaderCircle
              className="mx-auto animate-spin text-violet-400"
              size={42}
            />

            <h2 className="mt-5 text-lg font-semibold">
              {preparationStatus === "processing"
                ? "Generating your interview questions..."
                : "Getting your interview ready..."}
            </h2>

            <p className="mt-2 text-sm text-slate-400">
              Please keep this page open. We'll automatically
              notify you when your interview is ready.
            </p>

          </div>

          <div className="mt-8 space-y-4 text-left">

            <div className="flex items-center gap-3">
              <CheckCircle2 className="shrink-0 text-green-400" size={21} />
              <span className="text-sm text-slate-300">
                Interview session created
              </span>
            </div>

            <div className="flex items-center gap-3">
              {preparationStatus === "processing" ? (
                <LoaderCircle
                  className="shrink-0 animate-spin text-violet-400"
                  size={21}
                />
              ) : (
                <Clock className="shrink-0 text-slate-500" size={21} />
              )}

              <span className="text-sm text-slate-300">
                AI job description analysis and question generation
              </span>
            </div>

            <div className="flex items-center gap-3">
              <Clock className="shrink-0 text-slate-500" size={21} />
              <span className="text-sm text-slate-300">
                Validating and saving interview questions
              </span>
            </div>

          </div>

          {statusCheckError && (
            <div className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-sm text-amber-300">
              <RefreshCw size={16} />
              Unable to refresh status. Retrying automatically...
            </div>
          )}

          <div className="mt-8 border-t border-white/10 pt-5">
            <p className="text-xs text-slate-500">
              {checkingStatus
                ? "Connecting to the interview server..."
                : "Checking preparation status automatically every 3 seconds."}
            </p>
          </div>

        </div>
      </main>
    );
  }

  // -----------------------------------------
  // INTERVIEW READY - SHOW INSTRUCTIONS
  // -----------------------------------------

  return (
    <main className="min-h-screen bg-slate-950 px-5 py-12 text-white">
      <div className="mx-auto max-w-3xl">

        <div className="mb-8 text-center">

          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-green-500/15 text-green-400">
            <CheckCircle2 size={34} />
          </div>

          <p className="text-sm font-semibold uppercase tracking-widest text-green-400">
            Interview Ready
          </p>

          <h1 className="mt-3 text-3xl font-bold sm:text-4xl">
            You're ready, {candidateName || "Candidate"}.
          </h1>

          <p className="mt-4 text-slate-400">
            Your personalized interview questions have been
            successfully prepared. Review the instructions below.
          </p>

        </div>

        <div className="mb-6 rounded-2xl border border-green-500/20 bg-green-500/5 p-6">

          <p className="text-sm text-slate-400">
            Interview preparation completed
          </p>

          <h2 className="mt-2 text-xl font-semibold">
            {jobRole}
          </h2>

          <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-300">
            <span>
              <CheckCircle2 className="mr-2 inline text-green-400" size={17} />
              {totalQuestions} questions ready
            </span>
          </div>

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
          disabled={loading || preparationStatus !== "ready"}
          className="mt-7 flex w-full items-center justify-center gap-3 rounded-xl bg-violet-600 py-4 font-semibold hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
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
