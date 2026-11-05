
import { useNavigate } from "react-router-dom";
import {
  BrainCircuit,
  Video,
  Users,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Mic,
  ChartNoAxesCombined,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";

export default function Home() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const features = [
    {
      icon: Video,
      title: "Smart Interviews",
      description:
        "Structured interviews with adaptive questions and video-based candidate interaction.",
    },
    {
      icon: BrainCircuit,
      title: "AI Evaluation",
      description:
        "Analyze technical answers, concept coverage, reasoning, and communication.",
    },
    {
      icon: ChartNoAxesCombined,
      title: "Detailed Reports",
      description:
        "Generate interview transcripts, competency insights, and recruiter reports.",
    },
    {
      icon: Mic,
      title: "Voice Interaction",
      description:
        "Designed for natural speech-based interview experiences.",
    },
    {
      icon: ShieldCheck,
      title: "Interview Integrity",
      description:
        "Support secure sessions and transparent interview monitoring.",
    },
    {
      icon: Users,
      title: "Recruiter Dashboard",
      description:
        "Review candidate performance and supporting interview evidence.",
    },
  ];

  const steps = [
    {
      number: "01",
      title: "Start Interview",
      description: "Candidate joins the interview session.",
    },
    {
      number: "02",
      title: "AI Evaluates",
      description: "Answers are analyzed and follow-up questions are generated.",
    },
    {
      number: "03",
      title: "View Report",
      description: "Recruiters receive an evidence-based interview report.",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* NAVBAR */}
      <nav className="border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div
            onClick={() => navigate("/")}
            className="flex cursor-pointer items-center gap-3"
          >
            <div className="rounded-xl bg-violet-600 p-2">
              <BrainCircuit size={25} />
            </div>

            <span className="text-xl font-bold tracking-tight">
              Interview<span className="text-violet-400">AI</span>
            </span>
          </div>

          <div className="hidden items-center gap-8 text-sm text-slate-300 md:flex">
            <a href="#features" className="transition hover:text-white">
              Features
            </a>
            <a href="#how-it-works" className="transition hover:text-white">
              How it works
            </a>
            <a href="#about" className="transition hover:text-white">
              About
            </a>
          </div>

          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden"
          >
            {menuOpen ? <X /> : <Menu />}
          </button>

          <button
            onClick={() => navigate("/recruiter/login")}
            className="hidden rounded-lg border border-white/20 px-5 py-2.5 text-sm font-medium transition hover:bg-white hover:text-slate-950 md:block"
          >
            Recruiter Login
          </button>
        </div>

        {menuOpen && (
          <div className="flex flex-col gap-4 border-t border-white/10 px-6 py-5 text-slate-300 md:hidden">
            <a href="#features" onClick={() => setMenuOpen(false)}>
              Features
            </a>
            <a href="#how-it-works" onClick={() => setMenuOpen(false)}>
              How it works
            </a>
            <a href="#about" onClick={() => setMenuOpen(false)}>
              About
            </a>
            <button
              onClick={() => navigate("/recruiter/login")}
              className="text-left"
            >
              Recruiter Login
            </button>
          </div>
        )}
      </nav>

      {/* HERO SECTION */}
      <main>
        <section className="mx-auto grid max-w-7xl items-center gap-16 px-6 py-24 lg:grid-cols-2 lg:py-32">
          <div>
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-300">
              <Sparkles size={16} />
              AI-powered intelligent interviews
            </div>

            <h1 className="text-5xl font-bold leading-tight tracking-tight sm:text-6xl">
              The smarter way to
              <span className="block text-violet-400">
                conduct interviews.
              </span>
            </h1>

            <p className="mt-7 max-w-xl text-lg leading-8 text-slate-400">
              Experience intelligent technical interviews powered by AI.
              Adaptive questions, real-time evaluation, and detailed
              candidate insights — all in one platform.
            </p>

            <div className="mt-10 flex flex-wrap gap-4">
              <button
                onClick={() => navigate("/candidate/register")}
                className="flex items-center gap-2 rounded-xl bg-violet-600 px-7 py-4 font-semibold transition hover:bg-violet-500"
              >
                Start Interview
                <ArrowRight size={19} />
              </button>

              <button
                onClick={() => navigate("/recruiter/login")}
                className="rounded-xl border border-white/20 px-7 py-4 font-semibold transition hover:bg-white/10"
              >
                Recruiter Portal
              </button>
            </div>

            <div className="mt-12 flex flex-wrap gap-7 text-sm text-slate-400">
              <span className="flex items-center gap-2">
                <ShieldCheck className="text-emerald-400" size={18} />
                Secure interviews
              </span>

              <span className="flex items-center gap-2">
                <BrainCircuit className="text-violet-400" size={18} />
                Adaptive AI
              </span>
            </div>
          </div>

          {/* INTERVIEW PREVIEW */}
          <div className="relative">
            <div className="absolute -inset-8 rounded-full bg-violet-600/20 blur-3xl" />

            <div className="relative rounded-3xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-5">
                <div>
                  <p className="font-semibold">Live Interview</p>
                  <p className="mt-1 text-xs text-slate-400">
                    Python Full Stack Developer
                  </p>
                </div>

                <span className="flex items-center gap-2 rounded-full bg-red-500/10 px-3 py-1.5 text-xs text-red-400">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
                  LIVE
                </span>
              </div>

              <div className="my-6 flex aspect-video items-center justify-center rounded-2xl bg-gradient-to-br from-violet-950 to-slate-800">
                <div className="text-center">
                  <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-violet-500/20">
                    <Video size={36} className="text-violet-300" />
                  </div>

                  <p className="font-semibold">Candidate Interview</p>

                  <p className="mt-2 text-sm text-slate-400">
                    Video interview preview
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-violet-400/20 bg-violet-500/10 p-5">
                <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-violet-300">
                  <Sparkles size={15} />
                  AI Interview Question
                </p>

                <p className="leading-7 text-slate-200">
                  How does FastAPI handle incoming HTTP requests, and
                  what role does Pydantic play in request validation?
                </p>

                <div className="mt-5 flex items-center justify-between text-xs text-slate-400">
                  <span className="flex items-center gap-2">
                    <Mic size={15} />
                    Voice enabled
                  </span>

                  <span>Question 04 / 06</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURES */}
        <section
          id="features"
          className="border-t border-white/10 bg-slate-900/50 px-6 py-24"
        >
          <div className="mx-auto max-w-7xl">
            <div className="mx-auto mb-16 max-w-2xl text-center">
              <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-violet-400">
                Platform Features
              </p>

              <h2 className="text-3xl font-bold sm:text-4xl">
                Everything you need for smarter hiring
              </h2>

              <p className="mt-5 leading-7 text-slate-400">
                A complete interview experience designed for candidates
                and recruiters.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              {features.map((feature) => {
                const Icon = feature.icon;

                return (
                  <div
                    key={feature.title}
                    className="rounded-2xl border border-white/10 bg-slate-900 p-7 transition hover:-translate-y-1 hover:border-violet-500/50"
                  >
                    <div className="mb-6 inline-flex rounded-xl bg-violet-500/10 p-3 text-violet-400">
                      <Icon size={25} />
                    </div>

                    <h3 className="mb-3 text-lg font-semibold">
                      {feature.title}
                    </h3>

                    <p className="text-sm leading-7 text-slate-400">
                      {feature.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section id="how-it-works" className="px-6 py-24">
          <div className="mx-auto max-w-5xl text-center">
            <h2 className="text-3xl font-bold sm:text-4xl">
              From interview to insights
            </h2>

            <p className="mt-5 text-slate-400">
              One intelligent workflow. Three simple stages.
            </p>

            <div className="mt-14 grid gap-8 md:grid-cols-3">
              {steps.map((step) => (
                <div
                  key={step.number}
                  className="rounded-2xl border border-white/10 p-7"
                >
                  <p className="mb-5 text-3xl font-bold text-violet-400">
                    {step.number}
                  </p>

                  <h3 className="mb-3 text-lg font-semibold">
                    {step.title}
                  </h3>

                  <p className="text-sm leading-7 text-slate-400">
                    {step.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer
        id="about"
        className="border-t border-white/10 px-6 py-8 text-center text-sm text-slate-500"
      >
        © 2026 InterviewAI. Intelligent interviews, better insights.
      </footer>
    </div>
  );
}
