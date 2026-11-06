
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  CheckCircle2,
  Clock,
  TrendingUp,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

import api from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import Sidebar from "../../components/recruiter/Sidebar";
import StatsCards from "../../components/recruiter/StatsCards";
import InterviewTable from "../../components/recruiter/InterviewTable";

export default function RecruiterDashboard() {
  const navigate = useNavigate();
  const { recruiter, logout } = useAuth();

  const [statistics, setStatistics] = useState(null);
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      setError("");

      const [statsResponse, interviewsResponse] = await Promise.all([
        api.get("/recruiter/dashboard"),
        api.get("/recruiter/interviews", {
          params: {
            search: search || undefined,
            status: status === "all" ? undefined : status,
            page,
            limit: 10,
          },
        }),
      ]);

      setStatistics(statsResponse.data);
      setInterviews(
        interviewsResponse.data.interviews ||
        interviewsResponse.data.items ||
        []
      );

      const total = interviewsResponse.data.total || 0;
      setTotalPages(Math.max(1, Math.ceil(total / 10)));
    } catch (err) {
      console.error("Dashboard loading error:", err);
      setError(
        err.response?.data?.detail ||
        "Unable to load dashboard. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [search, status, page]);

  const handleLogout = () => {
    logout();
    navigate("/recruiter/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#080d18] text-white">
      <Sidebar recruiter={recruiter} onLogout={handleLogout} />

      <main className="min-h-screen md:ml-64">
        <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080d18]/90 px-5 py-5 backdrop-blur-xl md:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Workspace / Overview</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight">
                Recruiter Dashboard
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                Monitor interviews and candidate performance.
              </p>
            </div>

            <button
              onClick={fetchDashboard}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-200 transition hover:bg-white/10 disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </header>

        <div className="space-y-8 p-5 md:p-8">
          {error && (
            <div className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
              <AlertCircle size={18} />
              {error}
            </div>
          )}

          <section>
            <div className="mb-5">
              <h2 className="text-lg font-semibold">Overview</h2>
              <p className="mt-1 text-sm text-slate-400">
                Your interview activity at a glance.
              </p>
            </div>

            {loading && !statistics ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center text-slate-400">
                Loading dashboard statistics...
              </div>
            ) : (
              <StatsCards statistics={statistics} />
            )}
          </section>

          <section>
            <InterviewTable
              interviews={interviews}
              loading={loading}
              search={search}
              setSearch={(value) => {
                setSearch(value);
                setPage(1);
              }}
              status={status}
              setStatus={(value) => {
                setStatus(value);
                setPage(1);
              }}
              page={page}
              totalPages={totalPages}
              setPage={setPage}
              onView={(sessionId) =>
                navigate(`/recruiter/interviews/${sessionId}`)
              }
              onRefresh={fetchDashboard}
            />
          </section>

          <footer className="border-t border-white/10 pt-5 text-center text-xs text-slate-500">
            AI Voice Interview Platform · Recruiter Workspace
          </footer>
        </div>
      </main>
    </div>
  );
}
