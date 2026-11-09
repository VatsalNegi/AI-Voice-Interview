import { useEffect, useMemo, useState } from "react";
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
  RefreshCw,
  Award,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Lightbulb,
  Target,
  MessageSquare,
  Download,
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

function formatStatus(value) {
  if (!value) return "Unknown";
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function asText(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function asList(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function recommendationTone(value) {
  const normalized = String(value || "").toUpperCase();
  if (normalized.includes("RECOMMENDED_FOR_NEXT")) {
    return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  }
  if (normalized.includes("CONSIDER")) {
    return "border-amber-500/20 bg-amber-500/10 text-amber-300";
  }
  return "border-indigo-500/20 bg-indigo-500/10 text-indigo-300";
}

function getReport(details) {
  if (!details) return {};
  return details.final_report && typeof details.final_report === "object"
    ? details.final_report
    : {};
}

// ------------------------------------------
// SMALL PRESENTATION COMPONENTS
// ------------------------------------------

function InfoItem({ label, value, icon: Icon }) {
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 flex items-center gap-2 break-words text-sm text-slate-200">
        {Icon && <Icon size={15} className="shrink-0 text-indigo-400" />}
        {value || "—"}
      </p>
    </div>
  );
}

function BulletList({ items, emptyText }) {
  const values = asList(items);
  if (!values.length) {
    return <p className="text-sm text-slate-500">{emptyText || "Not available."}</p>;
  }
  return (
    <ul className="space-y-2">
      {values.map((item, index) => (
        <li key={index} className="flex gap-2 text-sm leading-6 text-slate-300">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
          <span>{typeof item === "string" ? item : asText(item.label || item.name || item.feedback) || JSON.stringify(item)}</span>
        </li>
      ))}
    </ul>
  );
}

function ReportCard({ title, icon: Icon, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-white/10 bg-[#101827] p-4 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        {Icon && <Icon size={17} className="text-indigo-400" />}
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      {children}
    </section>
  );
}

// ------------------------------------------
// ONE-PAGE RECRUITER REPORT
// ------------------------------------------

function RecruiterReport({ details, interview, candidate }) {
  const report = getReport(details);
  const summary =
    asText(report.summary) ||
    asText(details?.summary) ||
    "The consolidated interview summary is not available yet.";

  const recommendation =
    asText(report.recommendation) ||
    asText(interview.recommendation) ||
    "MANUAL_REVIEW_REQUIRED";

  const score =
    report.overall_score !== undefined && report.overall_score !== null
      ? report.overall_score
      : interview.overall_score;

  const strengths = asList(report.overall_strengths || report.strengths);
  const improvements = asList(
    report.areas_for_improvement || report.improvement_areas
  );
  const competencies = Array.isArray(report.competency_scores)
    ? report.competency_scores
    : [];

  const technicalAssessment =
    asText(report.technical_assessment) ||
    asText(report.technical_feedback);
  const communicationAssessment = asText(report.communication_assessment);
  const practicalAssessment = asText(report.practical_experience_assessment);
  const problemSolvingAssessment = asText(report.problem_solving_assessment);
  const roleFitAssessment = asText(report.role_fit_assessment);
  const nextSteps = asList(report.recruiter_next_steps || report.next_steps);
  const recommendationReason = asText(report.recommendation_reason);

  const handlePrint = () => window.print();

  return (
    <section id="recruiter-ai-report" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit size={20} className="text-violet-400" />
            <h2 className="text-lg font-bold text-white">AI Interview Assessment</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Consolidated recruiter summary · Individual answer evaluations are kept out of this report.
          </p>
        </div>

        <button
          type="button"
          onClick={handlePrint}
          className="no-print inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10"
        >
          <Download size={15} />
          Download / Print
        </button>
      </div>

      <div className="rounded-2xl border border-white/10 bg-[#101827] p-5 md:p-6 print-report">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 pb-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Candidate assessment
            </p>
            <h2 className="mt-1 text-xl font-bold text-white">
              {candidate.name || "Candidate"}
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              {interview.job_role || report.job_role || "Role not specified"}
              {candidate.email ? ` · ${candidate.email}` : ""}
            </p>
          </div>
          <span className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${recommendationTone(recommendation)}`}>
            {formatStatus(recommendation)}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-[#0b1220] p-4">
            <p className="text-xs text-slate-500">Overall interview score</p>
            <p className="mt-1 text-2xl font-bold text-white">
              {score === null || score === undefined ? "Not available" : `${Number(score).toFixed(1)} / 100`}
            </p>
          </div>
          <div className="rounded-xl bg-[#0b1220] p-4">
            <p className="text-xs text-slate-500">Questions answered</p>
            <p className="mt-1 text-2xl font-bold text-white">
              {details?.questions?.filter((q) => Array.isArray(q.answers) && q.answers.length > 0).length ?? "—"}
            </p>
          </div>
          <div className="rounded-xl bg-[#0b1220] p-4">
            <p className="text-xs text-slate-500">Interview duration</p>
            <p className="mt-1 text-2xl font-bold text-white">
              {interview.duration ? `${interview.duration} min` : "—"}
            </p>
          </div>
        </div>

        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold text-white">Executive Summary</h3>
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{summary}</p>
        </div>

        {competencies.length > 0 && (
          <div className="mt-5">
            <h3 className="mb-3 text-sm font-semibold text-white">Competency Overview</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {competencies.map((item, index) => (
                <div key={`${item.competency || "competency"}-${index}`} className="rounded-lg border border-white/5 bg-[#0b1220] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm text-slate-300">{formatStatus(item.competency)}</span>
                    <span className="text-sm font-semibold text-white">
                      {item.score === null || item.score === undefined ? "—" : `${Number(item.score).toFixed(0)}/100`}
                    </span>
                  </div>
                  {item.feedback && (
                    <p className="mt-2 text-xs leading-5 text-slate-500">{item.feedback}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {(technicalAssessment || communicationAssessment || practicalAssessment || problemSolvingAssessment || roleFitAssessment) && (
          <div className="mt-5">
            <h3 className="mb-3 text-sm font-semibold text-white">Assessment Highlights</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {[
                ["Technical assessment", technicalAssessment],
                ["Communication", communicationAssessment],
                ["Practical experience", practicalAssessment],
                ["Problem solving", problemSolvingAssessment],
                ["Role fit", roleFitAssessment],
              ].filter(([, value]) => value).map(([label, value]) => (
                <div key={label} className="rounded-lg bg-[#0b1220] p-3">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                  <p className="text-sm leading-6 text-slate-300">{value}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-emerald-500/10 bg-emerald-500/[0.04] p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-300">
              <CheckCircle2 size={16} /> Key Strengths
            </h3>
            <BulletList items={strengths} emptyText="No strengths summary available." />
          </div>
          <div className="rounded-lg border border-amber-500/10 bg-amber-500/[0.04] p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-300">
              <Lightbulb size={16} /> Areas for Improvement
            </h3>
            <BulletList items={improvements} emptyText="No improvement areas available." />
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-indigo-500/15 bg-indigo-500/[0.05] p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-indigo-300">
            <Target size={16} /> Recruiter Recommendation
          </h3>
          <p className="text-sm font-semibold text-white">{formatStatus(recommendation)}</p>
          {recommendationReason && (
            <p className="mt-2 text-sm leading-6 text-slate-300">{recommendationReason}</p>
          )}
          {nextSteps.length > 0 && (
            <div className="mt-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested next steps</p>
              <BulletList items={nextSteps} />
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">
            AI-generated assessment is decision support only. The recruiter should make the final hiring decision.
          </p>
        </div>
      </div>
    </section>
  );
}

// ------------------------------------------
// TRANSCRIPT QUESTION CARD
// ------------------------------------------

function QuestionCard({ question, index }) {
  const [expanded, setExpanded] = useState(false);
  const answers = Array.isArray(question.answers) ? question.answers : [];

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#101827]">
      <button
        type="button"
        onClick={() => setExpanded((previous) => !previous)}
        className="flex w-full items-center justify-between gap-4 p-4 text-left transition hover:bg-white/[0.025]"
      >
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-sm font-bold text-indigo-300">
            {index + 1}
          </div>
          <div className="min-w-0">
            <p className="font-medium leading-6 text-white">
              {question.question_text || "Question text unavailable"}
            </p>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
              {question.competency && <span>{formatStatus(question.competency)}</span>}
              {question.difficulty && <span>· {formatStatus(question.difficulty)}</span>}
            </div>
          </div>
        </div>
        {expanded ? (
          <ChevronUp size={18} className="shrink-0 text-slate-400" />
        ) : (
          <ChevronDown size={18} className="shrink-0 text-slate-400" />
        )}
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-white/10 p-4">
          {answers.length === 0 ? (
            <p className="rounded-lg bg-[#0b1220] p-3 text-sm text-slate-500">
              No answer has been recorded for this question.
            </p>
          ) : (
            answers.map((answer, answerIndex) => (
              <div key={answer.id || answerIndex} className="rounded-lg border border-white/5 bg-[#0b1220] p-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-medium text-indigo-300">
                    {formatStatus(answer.answer_type || "initial")} Answer
                  </span>
                  <span className="text-xs text-slate-500">{formatDate(answer.created_at)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
                  {answer.answer_text || "No answer text available"}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------
// MAIN PAGE
// ------------------------------------------

export default function InterviewDetails() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { recruiter, logout } = useAuth();

  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const fetchDetails = async ({ silent = false } = {}) => {
    if (!sessionId) {
      setError("Interview session ID is missing.");
      setLoading(false);
      return;
    }
    try {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError("");
      const response = await getRecruiterInterviewDetails(sessionId);
      setDetails(response);
    } catch (err) {
      console.error("Interview details error:", err);
      setError(
        err.response?.data?.detail ||
          "Unable to load interview details. Please try again."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleLogout = () => {
    logout();
    navigate("/recruiter/login", { replace: true });
  };

  const interview = details || {};
  const candidate = interview.candidate || {};
  const questions = Array.isArray(details?.questions) ? details.questions : [];
  const evaluationStatus = String(interview.evaluation_status || "").toLowerCase();
  const reportReady =
    evaluationStatus === "completed" ||
    Boolean(interview.final_report && Object.keys(interview.final_report).length);
  const reportPending = ["pending", "processing"].includes(evaluationStatus);

  // Poll only while the post-interview report is being generated.
  useEffect(() => {
    if (!reportPending || !sessionId) return undefined;
    const timer = window.setInterval(() => fetchDetails({ silent: true }), 5000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportPending, sessionId]);

  return (
    <div className="min-h-screen bg-[#080d18] text-white">
      <Sidebar recruiter={recruiter} onLogout={handleLogout} />

      <main className="min-h-screen md:ml-64">
        <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080d18]/90 px-5 py-5 backdrop-blur-xl md:px-8">
          <button
            onClick={() => navigate("/recruiter/dashboard")}
            className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-white"
          >
            <ArrowLeft size={17} /> Back to Dashboard
          </button>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Recruiter Workspace / Interview Details</p>
              <h1 className="mt-1 text-2xl font-bold">Interview Details</h1>
            </div>
            <button
              onClick={() => fetchDetails({ silent: true })}
              disabled={loading || refreshing}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition hover:bg-white/10 disabled:opacity-50"
            >
              <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </header>

        <div className="space-y-6 p-5 md:p-8">
          {loading && (
            <div className="rounded-2xl border border-white/10 bg-[#101827] p-10 text-center text-slate-400">
              Loading interview details...
            </div>
          )}

          {!loading && error && (
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-5">
              <div className="flex items-center gap-3 text-red-300">
                <AlertCircle size={20} />
                <p>{error}</p>
              </div>
              <button
                onClick={() => fetchDetails()}
                className="mt-4 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-300 hover:bg-red-500/20"
              >
                Try Again
              </button>
            </div>
          )}

          {!loading && !error && details && (
            <>
              <section className="rounded-2xl border border-white/10 bg-[#101827] p-5 md:p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-300">
                      <UserRound size={28} />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">{candidate.name || "Candidate"}</h2>
                      <p className="mt-1 text-sm text-slate-400">{candidate.email || "Email not available"}</p>
                    </div>
                  </div>
                  <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-300">
                    {formatStatus(interview.status)}
                  </span>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-5 border-t border-white/10 pt-5 sm:grid-cols-2 xl:grid-cols-4">
                  <InfoItem label="Job Role" value={interview.job_role} icon={BriefcaseBusiness} />
                  <InfoItem label="Created At" value={formatDate(interview.created_at)} icon={CalendarDays} />
                  <InfoItem label="Duration" value={interview.duration ? `${interview.duration} minutes` : "—"} icon={Clock3} />
                  <InfoItem label="Language" value={interview.language} />
                  <InfoItem label="Start Time" value={formatDate(interview.start_time)} />
                  <InfoItem label="End Time" value={formatDate(interview.end_time)} />
                  <InfoItem label="Session ID" value={interview.session_id || sessionId} />
                  <InfoItem label="Candidate ID" value={candidate.candidate_id || candidate.id} />
                </div>
              </section>

              {reportPending && (
                <div className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-4">
                  <RefreshCw size={18} className="mt-0.5 animate-spin text-amber-300" />
                  <div>
                    <p className="font-medium text-amber-200">AI report analysis is in progress</p>
                    <p className="mt-1 text-sm text-slate-400">
                      The interview transcript has been saved. The consolidated recruiter report will appear here shortly.
                    </p>
                  </div>
                </div>
              )}

              {evaluationStatus === "failed" && (
                <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/[0.06] p-4">
                  <AlertCircle size={18} className="mt-0.5 text-red-300" />
                  <div>
                    <p className="font-medium text-red-200">AI report generation failed</p>
                    <p className="mt-1 text-sm text-slate-400">
                      The interview transcript remains available below. Please retry or review the interview manually.
                    </p>
                  </div>
                </div>
              )}

              {reportReady && (
                <RecruiterReport
                  details={details}
                  interview={interview}
                  candidate={candidate}
                />
              )}

              {!reportReady && !reportPending && evaluationStatus !== "failed" && (
                <div className="rounded-xl border border-white/10 bg-[#101827] p-4 text-sm text-slate-400">
                  <div className="flex items-center gap-2">
                    <FileText size={17} className="text-indigo-400" />
                    The consolidated AI report is not available for this interview.
                  </div>
                </div>
              )}

              <section>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-white">Interview Transcript</h2>
                    <p className="mt-1 text-sm text-slate-400">
                      Original questions and candidate responses are preserved. Expand a question to read its transcript.
                    </p>
                  </div>
                  <span className="rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-400">
                    {questions.length} Questions
                  </span>
                </div>

                {questions.length === 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-[#101827] p-8 text-center">
                    <ClipboardList size={30} className="mx-auto mb-3 text-slate-600" />
                    <p className="text-sm text-slate-400">No interview transcript is available.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {questions.map((question, index) => (
                      <QuestionCard
                        key={question.id || question.question_id || index}
                        question={question}
                        index={index}
                      />
                    ))}
                  </div>
                )}
              </section>
            </>
          )}

          <footer className="border-t border-white/10 pt-5 text-center text-xs text-slate-500">
            VoiceHire AI · Recruiter Workspace
          </footer>
        </div>
      </main>

      <style>{`
        @media print {
          body { background: white !important; }
          body * { visibility: hidden; }
          #recruiter-ai-report, #recruiter-ai-report * { visibility: visible; }
          #recruiter-ai-report {
            position: absolute;
            inset: 0;
            width: 100%;
            color: #111827 !important;
          }
          #recruiter-ai-report .print-report {
            background: white !important;
            border: 1px solid #d1d5db !important;
            color: #111827 !important;
            box-shadow: none !important;
          }
          #recruiter-ai-report .print-report * {
            color: #111827 !important;
            border-color: #d1d5db !important;
          }
          .no-print { display: none !important; }
        }
      `}</style>
    </div>
  );
}
