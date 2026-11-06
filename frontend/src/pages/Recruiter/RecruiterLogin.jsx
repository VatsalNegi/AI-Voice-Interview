
import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  BrainCircuit,
  ArrowRight,
  Loader2,
  AlertCircle,
} from "lucide-react";

import { useAuth } from "../../context/AuthContext";

export default function RecruiterLogin() {
  const navigate = useNavigate();
  const { login, isAuthenticated, loading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#080d18] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/recruiter/dashboard" replace />;
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail || !password) {
      setError("Please enter both email and password.");
      return;
    }

    try {
      setSubmitting(true);

      await login(normalizedEmail, password);

      navigate("/recruiter/dashboard", { replace: true });
    } catch (err) {
      const message = err.response?.data?.detail;

      setError(
        typeof message === "string"
          ? message
          : "Unable to sign in. Please check your credentials."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#080d18] text-white flex">
      {/* LEFT PANEL */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-[#111b35] via-[#10172b] to-[#080d18] p-14 flex-col justify-between">
        <div className="absolute w-96 h-96 bg-indigo-600/20 blur-[120px] rounded-full top-20 left-20" />
        <div className="absolute w-96 h-96 bg-purple-600/10 blur-[120px] rounded-full bottom-10 right-10" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-indigo-500 flex items-center justify-center">
            <BrainCircuit size={25} />
          </div>

          <div>
            <h1 className="font-bold text-xl tracking-wide">
              Interview<span className="text-indigo-400">AI</span>
            </h1>
            <p className="text-xs text-slate-400">
              Intelligent Interview Platform
            </p>
          </div>
        </div>

        <div className="relative z-10 max-w-lg">
          <div className="inline-flex items-center gap-2 border border-indigo-400/30 bg-indigo-400/10 px-4 py-2 rounded-full text-indigo-300 text-sm mb-8">
            <ShieldCheck size={16} />
            Secure Recruiter Workspace
          </div>

          <h2 className="text-5xl font-bold leading-tight mb-6">
            Smarter hiring.
            <br />
            <span className="text-indigo-400">
              Better interviews.
            </span>
          </h2>

          <p className="text-slate-400 text-lg leading-8">
            Manage candidate interviews, review AI-powered
            evaluations, and make informed hiring decisions
            from one centralized workspace.
          </p>

          <div className="grid grid-cols-2 gap-4 mt-12">
            <div className="border border-white/10 bg-white/[0.04] rounded-xl p-5">
              <ShieldCheck className="text-indigo-400 mb-3" size={24} />
              <h3 className="font-semibold">Secure Access</h3>
              <p className="text-sm text-slate-500 mt-1">
                Protected recruiter accounts
              </p>
            </div>

            <div className="border border-white/10 bg-white/[0.04] rounded-xl p-5">
              <BrainCircuit className="text-indigo-400 mb-3" size={24} />
              <h3 className="font-semibold">AI Evaluation</h3>
              <p className="text-sm text-slate-500 mt-1">
                Intelligent candidate insights
              </p>
            </div>
          </div>
        </div>

        <p className="relative z-10 text-sm text-slate-600">
          © {new Date().getFullYear()} InterviewAI. All rights reserved.
        </p>
      </div>

      {/* RIGHT PANEL */}
      <div className="w-full lg:w-1/2 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center justify-center gap-3 mb-12">
            <div className="w-11 h-11 rounded-xl bg-indigo-500 flex items-center justify-center">
              <BrainCircuit size={25} />
            </div>
            <h1 className="font-bold text-xl">
              Interview<span className="text-indigo-400">AI</span>
            </h1>
          </div>

          <div className="mb-10">
            <p className="text-indigo-400 text-sm font-semibold uppercase tracking-widest mb-3">
              Recruiter Portal
            </p>

            <h2 className="text-3xl font-bold mb-3">
              Welcome back
            </h2>

            <p className="text-slate-400">
              Sign in to access your interview management dashboard.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* EMAIL */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Email Address
              </label>

              <div className="relative">
                <Mail
                  size={19}
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"
                />

                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your recruiter email"
                  autoComplete="username"
                  required
                  className="w-full bg-[#111a2b] border border-slate-700 rounded-xl py-4 pl-12 pr-4 text-white outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 placeholder:text-slate-600"
                />
              </div>
            </div>

            {/* PASSWORD */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Password
              </label>

              <div className="relative">
                <LockKeyhole
                  size={19}
                  className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"
                />

                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                  className="w-full bg-[#111a2b] border border-slate-700 rounded-xl py-4 pl-12 pr-12 text-white outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 placeholder:text-slate-600"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </div>
            </div>

            {/* ERROR */}
            {error && (
              <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300 text-sm">
                <AlertCircle size={19} className="shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}

            {/* SUBMIT */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed py-4 font-semibold transition shadow-lg shadow-indigo-600/20"
            >
              {submitting ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In to Dashboard
                  <ArrowRight size={19} />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 flex items-center justify-center gap-2 text-slate-500 text-xs">
            <LockKeyhole size={14} />
            Secure authentication for authorized recruiters only
          </div>

          <p className="text-center text-slate-600 text-xs mt-10">
            Recruiter accounts are created by the system administrator.
            <br />
            Public registration is disabled.
          </p>
        </div>
      </div>
    </div>
  );
}
