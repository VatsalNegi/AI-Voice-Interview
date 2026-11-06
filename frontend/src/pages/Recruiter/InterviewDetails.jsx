
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  UserRound,
  BriefcaseBusiness,
  CalendarDays,
  Clock3,
  CheckCircle2,
  AlertCircle,
  FileText,
  BrainCircuit,
  MessageSquare,
  Target,
  Lightbulb,
  RefreshCw,
  Award,
  ChevronDown,
  ChevronUp,
  ClipboardList,
} from "lucide-react";

import { getRecruiterInterviewDetails } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import Sidebar from "../../components/recruiter/Sidebar";

// ------------------------------------------
// HELPERS
// ------------------------------------------

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}

function formatStatus(value) {
  if (!value) return "Unknown";

  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// ------------------------------------------
// SCORE CARD
// ------------------------------------------

function ScoreCard({ label, value, icon: Icon }) {
  const numericValue = Number(value);

  const hasValue =
    value !== null &&
    value !== undefined &&
    value !== "" &&
    Number.isFinite(numericValue);

  return (
    <div className="rounded-xl border border-white/10 bg-[#101827] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-slate-400">{label}</p>
        <Icon size={17} className="text-indigo-400" />
      </div>

      <p className="mt-3 text-2xl font-bold text-white">
        {hasValue ? numericValue.toFixed(1) : "—"}
      </p>
    </div>
  );
}

// ------------------------------------------
// AI EVALUATION
// ------------------------------------------

function EvaluationSection({ evaluation }) {
  if (!evaluation) return null;

  const scoreItems = [
    {
      label: "Technical Correctness",
      value: evaluation.technical_correctness,
      icon: Target,
    },
    {
      label: "Concept Coverage",
      value: evaluation.concept_coverage,
      icon: BrainCircuit,
    },
    {
      label: "Reasoning Quality",
      value: evaluation.reasoning_quality,
      icon: Lightbulb,
    },
    {
      label: "Communication Clarity",
      value: evaluation.communication_clarity,
      icon: MessageSquare,
    },
  ];

  return (
    <div className="mt-5 rounded-xl border border-white/10 bg-[#0b1220] p-4">
      <div className="mb-4 flex items-center gap-2">
        <BrainCircuit size={18} className="text-violet-400" />
        <h4 className="font-semibold text-white">AI Evaluation</h4>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {scoreItems.map((item) => (
          <ScoreCard
            key={item.label}
            label={item.label}
            value={item.value}
            icon={item.icon}
          />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Answer Classification
          </p>

          <span className="inline-flex rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">
            {formatStatus(evaluation.answer_classification)}
          </span>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Confidence
          </p>

          <p className="text-sm text-slate-300">
            {formatValue(evaluation.confidence)}
          </p>
        </div>
      </div>

      {Array.isArray(evaluation.matched_concepts) &&
        evaluation.matched_concepts.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Matched Concepts
            </p>

            <div className="flex flex-wrap gap-2">
              {evaluation.matched_concepts.map((concept, index) => (
                <span
                  key={index}
                  className="rounded-lg bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300"
                >
                  {formatValue(concept)}
                </span>
              ))}
            </div>
          </div>
        )}

      {Array.isArray(evaluation.missing_concepts) &&
        evaluation.missing_concepts.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Missing Concepts
            </p>

            <div className="flex flex-wrap gap-2">
              {evaluation.missing_concepts.map((concept, index) => (
                <span
                  key={index}
                  className="rounded-lg bg-amber-500/10 px-3 py-1 text-xs text-amber-300"
                >
                  {formatValue(concept)}
                </span>
              ))}
            </div>
          </div>
        )}

      {Array.isArray(evaluation.incorrect_statements) &&
        evaluation.incorrect_statements.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Incorrect Statements
            </p>

            <ul className="space-y-2">
              {evaluation.incorrect_statements.map((statement, index) => (
                <li
                  key={index}
                  className="rounded-lg bg-red-500/5 p-3 text-sm text-red-300"
                >
                  {formatValue(statement)}
                </li>
              ))}
            </ul>
          </div>
        )}

      {evaluation.overall_feedback && (
        <div className="mt-4 rounded-lg border border-white/5 bg-white/[0.03] p-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            AI Feedback
          </p>

          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-300">
            {formatValue(evaluation.overall_feedback)}
          </p>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------
// QUESTION AND ANSWER CARD
// ------------------------------------------

function QuestionCard({ question, index }) {
  const [expanded, setExpanded] = useState(true);

  const answers = Array.isArray(question.answers)
    ? question.answers
    : [];

  const evaluations = Array.isArray(question.evaluations)
    ? question.evaluations
    : [];

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#101827]">
      <button
        type="button"
        onClick={() => setExpanded((previous) => !previous)}
        className="flex w-full items-center justify-between gap-4 p-5 text-left transition hover:bg-white/[0.025]"
      >
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-sm font-bold text-indigo-300">
            {index + 1}
          </div>

          <div className="min-w-0">
            <p className="font-semibold leading-6 text-white">
              {question.question_text || "Question text unavailable"}
            </p>

            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
              {question.competency && (
                <span>{question.competency}</span>
              )}

              {question.difficulty && (
                <span>· {question.difficulty}</span>
              )}

              {question.question_type && (
                <span>· {question.question_type}</span>
              )}
            </div>
          </div>
        </div>

        {expanded ? (
          <ChevronUp size={19} className="shrink-0 text-slate-400" />
        ) : (
          <ChevronDown size={19} className="shrink-0 text-slate-400" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-white/10 p-5">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Candidate Answers
          </h4>

          {answers.length === 0 ? (
            <p className="rounded-xl bg-white/[0.03] p-4 text-sm text-slate-500">
              No answer has been recorded for this question.
            </p>
          ) : (
            <div className="space-y-3">
              {answers.map((answer, answerIndex) => (
                <div
                  key={answer.id || answerIndex}
                  className="rounded-xl border border-white/5 bg-[#0b1220] p-4"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-medium text-indigo-300">
                      {formatStatus(answer.answer_type)} Answer
                    </span>

                    <span className="text-xs text-slate-500">
                      {formatDate(answer.created_at)}
                    </span>
                  </div>

                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                    {answer.answer_text || "No answer text available"}
                  </p>
                </div>
              ))}
            </div>
          )}

          {evaluations.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No individual evaluation is available for this question.
            </p>
          ) : (
            evaluations.map((evaluation, evaluationIndex) => (
              <EvaluationSection
                key={evaluation.id || evaluationIndex}
                evaluation={evaluation}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------
// REPORT SECTION
// ------------------------------------------

function ReportSection({ title, content, icon: Icon }) {
  if (
    content === null ||
    content === undefined ||
    content === ""
  ) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-white/10 bg-[#101827] p-5">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={19} className="text-indigo-400" />
        <h3 className="font-semibold text-white">{title}</h3>
      </div>

      {typeof content === "object" ? (
        <pre className="overflow-x-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
          {JSON.stringify(content, null, 2)}
        </pre>
      ) : (
        <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
          {content}
        </p>
      )}
    </section>
  );
}

// ------------------------------------------
// MAIN INTERVIEW DETAILS PAGE
// ------------------------------------------

export default function InterviewDetails() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const { recruiter, logout } = useAuth();

  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Fetch interview details from the backend.
  // The API helper already returns response.data.
  const fetchDetails = async () => {
    if (!sessionId) {
      setError("Interview session ID is missing.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await getRecruiterInterviewDetails(sessionId);

      // IMPORTANT: api.js returns response.data directly.
      setDetails(response);
    } catch (err) {
      console.error("Interview details error:", err);

      setError(
        err.response?.data?.detail ||
          "Unable to load interview details. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [sessionId]);

  const handleLogout = () => {
    logout();
    navigate("/recruiter/login", { replace: true });
  };

  // Support the response structure from recruiter_dashboard.py.
  const interview = details|| {};

  const candidate =
    interview.candidate ||
    details?.candidate ||
    {};

  const questions = Array.isArray(details?.questions)
    ? details.questions
    : [];

  const evaluations = Array.isArray(details?.evaluations)
    ? details.evaluations
    : Array.isArray(details?.interview_evaluations)
      ? details.interview_evaluations
      : [];

  return (
    <div className="min-h-screen bg-[#080d18] text-white">
      <Sidebar
        recruiter={recruiter}
        onLogout={handleLogout}
      />

      <main className="min-h-screen md:ml-64">
        {/* HEADER */}
        <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080d18]/90 px-5 py-5 backdrop-blur-xl md:px-8">
          <button
            onClick={() => navigate("/recruiter/dashboard")}
            className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <ArrowLeft size={17} />
            Back to Dashboard
          </button>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">
                Recruiter Workspace / Interview Details
              </p>

              <h1 className="mt-1 text-2xl font-bold">
                Interview Details
              </h1>
            </div>

            <button
              onClick={fetchDetails}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition hover:bg-white/10 disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={loading ? "animate-spin" : ""}
              />
              Refresh
            </button>
          </div>
        </header>

        <div className="space-y-6 p-5 md:p-8">
          {/* LOADING */}
          {loading && (
            <div className="rounded-2xl border border-white/10 bg-[#101827] p-10 text-center text-slate-400">
              Loading interview details...
            </div>
          )}

          {/* ERROR */}
          {!loading && error && (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5">
              <div className="flex items-center gap-3 text-red-300">
                <AlertCircle size={20} />
                <p>{error}</p>
              </div>

              <button
                onClick={fetchDetails}
                className="mt-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-300 hover:bg-red-500/20"
              >
                Try Again
              </button>
            </div>
          )}

          {/* DETAILS */}
          {!loading && !error && details && (
            <>
              {/* CANDIDATE INFORMATION */}
              <section className="rounded-2xl border border-white/10 bg-[#101827] p-5 md:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-300">
                      <UserRound size={28} />
                    </div>

                    <div>
                      <h2 className="text-xl font-bold text-white">
                        {candidate.name || "Candidate"}
                      </h2>

                      <p className="mt-1 text-sm text-slate-400">
                        {candidate.email || "Email not available"}
                      </p>
                    </div>
                  </div>

                  <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-300">
                    {formatStatus(interview.status)}
                  </span>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-5 border-t border-white/10 pt-5 sm:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <p className="text-xs text-slate-500">Job Role</p>

                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-200">
                      <BriefcaseBusiness size={15} className="text-indigo-400" />
                      {interview.job_role || "—"}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Created At</p>

                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-200">
                      <CalendarDays size={15} className="text-indigo-400" />
                      {formatDate(interview.created_at)}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Duration</p>

                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-200">
                      <Clock3 size={15} className="text-indigo-400" />
                      {interview.duration
                        ? `${interview.duration} minutes`
                        : "—"}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Language</p>

                    <p className="mt-1 text-sm text-slate-200">
                      {interview.language || "—"}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Start Time</p>

                    <p className="mt-1 text-sm text-slate-200">
                      {formatDate(interview.start_time)}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">End Time</p>

                    <p className="mt-1 text-sm text-slate-200">
                      {formatDate(interview.end_time)}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Session ID</p>

                    <p className="mt-1 break-all text-xs text-slate-300">
                      {interview.session_id || sessionId}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs text-slate-500">Candidate ID</p>

                    <p className="mt-1 text-sm text-slate-200">
                      {candidate.candidate_id || candidate.id || "—"}
                    </p>
                  </div>
                </div>
              </section>

              {/* OVERALL SCORE AND RECOMMENDATION */}
              <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-[#101827] p-6">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-emerald-500/10 p-3 text-emerald-400">
                      <Award size={23} />
                    </div>

                    <div>
                      <p className="text-sm text-slate-400">
                        Overall Interview Score
                      </p>

                      <p className="mt-1 text-3xl font-bold text-white">
                        {interview.overall_score == null
                          ? "—"
                          : Number(interview.overall_score).toFixed(1)}

                        <span className="ml-1 text-sm font-medium text-slate-500">
                          / 100
                        </span>
                      </p>
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-[#101827] p-6">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-indigo-500/10 p-3 text-indigo-400">
                      <CheckCircle2 size={23} />
                    </div>

                    <div>
                      <p className="text-sm text-slate-400">
                        AI Recommendation
                      </p>

                      <p className="mt-1 text-lg font-semibold text-white">
                        {interview.recommendation || "Not available"}
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              {/* QUESTIONS AND ANSWERS */}
              <section>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-white">
                      Interview Questions & Answers
                    </h2>

                    <p className="mt-1 text-sm text-slate-400">
                      Review every question, candidate response, and AI evaluation.
                    </p>
                  </div>

                  <span className="rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-400">
                    {questions.length} Questions
                  </span>
                </div>

                {questions.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-[#101827] p-8 text-center">
                    <ClipboardList
                      size={30}
                      className="mx-auto mb-3 text-slate-600"
                    />

                    <p className="text-sm text-slate-400">
                      No interview questions are available.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {questions.map((question, index) => (
                      <QuestionCard
                        key={
                          question.id ||
                          question.question_id ||
                          index
                        }
                        question={question}
                        index={index}
                      />
                    ))}
                  </div>
                )}
              </section>

              {/* INTERVIEW-LEVEL EVALUATIONS */}
              {evaluations.length > 0 && (
                <section>
                  <h2 className="mb-4 text-lg font-bold text-white">
                    Overall AI Evaluation
                  </h2>

                  <div className="space-y-4">
                    {evaluations.map((evaluation, index) => (
                      <EvaluationSection
                        key={evaluation.id || index}
                        evaluation={evaluation}
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* SUMMARY */}
              <ReportSection
                title="Interview Summary"
                content={details.summary}
                icon={FileText}
              />

              {/* FINAL REPORT */}
              <ReportSection
                title="Final AI Report"
                content={details.final_report}
                icon={BrainCircuit}
              />

              {/* TRANSCRIPT */}
              <ReportSection
                title="Interview Transcript"
                content={details.transcript}
                icon={MessageSquare}
              />
            </>
          )}

          <footer className="border-t border-white/10 pt-5 text-center text-xs text-slate-500">
            VoiceHire AI · Recruiter Workspace
          </footer>
        </div>
      </main>
    </div>
  );
}
