
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  User,
  FileText,
  Briefcase,
  Clock,
  Sparkles,
  BrainCircuit,
  LoaderCircle,
} from "lucide-react";

import { createInterview } from "../../services/api";

export default function CandidateRegistration() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    candidate_id: "",
    candidate_name: "",
    email: "",
    resume_text: "",
    job_role: "",
    job_description: "",
    interview_duration: 30,
    language: "English",
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    setLoading(true);
    setError("");

    try {
      const payload = {
        candidate: {
          candidate_id: form.candidate_id.trim(),
          candidate_name: form.candidate_name.trim(),
          email: form.email.trim(),
          resume_text: form.resume_text.trim(),
          job_role: form.job_role.trim(),
          job_description: form.job_description.trim(),
        },
        interview_duration: Number(form.interview_duration),
        language: form.language,
      };

      const response = await createInterview(payload);

      navigate("/candidate/instructions", {
        state: {
          sessionId: response.session_id,
          candidateName: response.candidate_name,
          jobRole: response.job_role,
        },
      });
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to create interview. Please check your backend server."
      );
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    "mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-violet-500";

  return (
    <div className="min-h-screen bg-slate-950 px-5 py-10 text-white">
      <div className="mx-auto max-w-3xl">
        <button
          onClick={() => navigate("/")}
          className="mb-8 flex items-center gap-2 text-sm text-slate-400 hover:text-white"
        >
          <ArrowLeft size={17} />
          Back to home
        </button>

        <div className="mb-8">
          <div className="mb-4 inline-flex rounded-xl bg-violet-500/15 p-3 text-violet-400">
            <BrainCircuit size={28} />
          </div>

          <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-violet-400">
            Candidate Registration
          </p>

          <h1 className="text-3xl font-bold sm:text-4xl">
            Let's prepare for your interview.
          </h1>

          <p className="mt-3 leading-7 text-slate-400">
            Provide your details and professional background to create
            your personalized AI interview session.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-7 rounded-3xl border border-white/10 bg-slate-900 p-6 sm:p-9"
        >
          {/* PERSONAL INFORMATION */}
          <section>
            <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold">
              <User className="text-violet-400" size={20} />
              Personal Information
            </h2>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="text-sm text-slate-300">
                  Candidate ID
                </label>
                <input
                  required
                  name="candidate_id"
                  value={form.candidate_id}
                  onChange={handleChange}
                  placeholder="e.g. CAND001"
                  className={inputClass}
                />
              </div>

              <div>
                <label className="text-sm text-slate-300">
                  Full Name
                </label>
                <input
                  required
                  name="candidate_name"
                  value={form.candidate_name}
                  onChange={handleChange}
                  placeholder="Enter your full name"
                  className={inputClass}
                />
              </div>

              <div className="sm:col-span-2">
                <label className="text-sm text-slate-300">
                  Email Address
                </label>
                <input
                  required
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  className={inputClass}
                />
              </div>
            </div>
          </section>

          <div className="border-t border-white/10" />

          {/* JOB INFORMATION */}
          <section>
            <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold">
              <Briefcase className="text-violet-400" size={20} />
              Job Information
            </h2>

            <div className="space-y-5">
              <div>
                <label className="text-sm text-slate-300">
                  Target Job Role
                </label>
                <input
                  required
                  name="job_role"
                  value={form.job_role}
                  onChange={handleChange}
                  placeholder="Python Full Stack Developer"
                  className={inputClass}
                />
              </div>

              <div>
                <label className="text-sm text-slate-300">
                  Job Description
                </label>
                <textarea
                  required
                  rows={4}
                  name="job_description"
                  value={form.job_description}
                  onChange={handleChange}
                  placeholder="Paste the job description here..."
                  className={inputClass}
                />
              </div>
            </div>
          </section>

          <div className="border-t border-white/10" />

          {/* RESUME */}
          <section>
            <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold">
              <FileText className="text-violet-400" size={20} />
              Resume / Professional Background
            </h2>

            <label className="text-sm text-slate-300">
              Resume Text
            </label>

            <textarea
              required
              rows={7}
              name="resume_text"
              value={form.resume_text}
              onChange={handleChange}
              placeholder="Paste your resume text, including education, skills, projects and experience..."
              className={inputClass}
            />

            <p className="mt-2 text-xs text-slate-500">
              Resume context will be used to personalize the interview.
            </p>
          </section>

          <div className="border-t border-white/10" />

          {/* INTERVIEW PREFERENCES */}
          <section>
            <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold">
              <Clock className="text-violet-400" size={20} />
              Interview Preferences
            </h2>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label className="text-sm text-slate-300">
                  Interview Duration
                </label>

                <select
                  name="interview_duration"
                  value={form.interview_duration}
                  onChange={handleChange}
                  className={inputClass}
                >
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={45}>45 minutes</option>
                  <option value={60}>60 minutes</option>
                  <option value={90}>90 minutes</option>
                  <option value={120}>120 minutes</option>
                </select>
              </div>

              <div>
                <label className="text-sm text-slate-300">
                  Interview Language
                </label>

                <select
                  name="language"
                  value={form.language}
                  onChange={handleChange}
                  className={inputClass}
                >
                  <option value="English">English</option>
                </select>
              </div>
            </div>
          </section>

          {/* ERROR */}
          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
              {error}
            </div>
          )}

          {/* INFO */}
          <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 text-sm text-slate-300">
            <div className="mb-2 flex items-center gap-2 font-semibold text-violet-300">
              <Sparkles size={17} />
              Personalized AI Interview
            </div>

            Your resume and job information will help prepare a relevant
            interview experience.
          </div>

          {/* SUBMIT */}
          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-3 rounded-xl bg-violet-600 py-4 font-semibold transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <>
                <LoaderCircle className="animate-spin" size={19} />
                Creating Interview...
              </>
            ) : (
              <>
                Create Interview Session
                <ArrowRight size={19} />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
