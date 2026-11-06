
import {
  Search,
  Eye,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
} from "lucide-react";

function formatDate(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function StatusBadge({ status }) {
  const normalized = (status || "pending").toLowerCase();

  const styles = {
    completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    in_progress: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    pending: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    not_started: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  };

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium ${
        styles[normalized] ||
        "border-slate-500/20 bg-slate-500/10 text-slate-400"
      }`}
    >
      {normalized.replaceAll("_", " ")}
    </span>
  );
}

export default function InterviewTable({
  interviews = [],
  loading,
  search,
  setSearch,
  status,
  setStatus,
  page,
  totalPages,
  setPage,
  onView,
  onRefresh,
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#101827]">
      <div className="flex flex-col gap-4 border-b border-white/10 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">
            Recent Interviews
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Review candidate interviews and their results.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-50"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      <div className="flex flex-col gap-3 border-b border-white/10 p-5 sm:flex-row">
        <div className="relative flex-1">
          <Search
            size={17}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
          />

          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search candidate, email, role..."
            className="w-full rounded-xl border border-white/10 bg-[#0b1220] py-2.5 pl-10 pr-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-indigo-500/60"
          />
        </div>

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="rounded-xl border border-white/10 bg-[#0b1220] px-4 py-2.5 text-sm text-slate-300 outline-none focus:border-indigo-500/60"
        >
          <option value="all">All statuses</option>
          <option value="not_started">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[850px] text-left">
          <thead className="bg-white/[0.02] text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-5 py-4 font-medium">Candidate</th>
              <th className="px-5 py-4 font-medium">Job Role</th>
              <th className="px-5 py-4 font-medium">Status</th>
              <th className="px-5 py-4 font-medium">Score</th>
              <th className="px-5 py-4 font-medium">Date</th>
              <th className="px-5 py-4 text-right font-medium">Action</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-white/5">
            {loading ? (
              <tr>
                <td colSpan="6" className="px-5 py-12 text-center text-sm text-slate-400">
                  Loading interviews...
                </td>
              </tr>
            ) : interviews.length === 0 ? (
              <tr>
                <td colSpan="6" className="px-5 py-14 text-center">
                  <ClipboardList
                    size={30}
                    className="mx-auto mb-3 text-slate-600"
                  />
                  <p className="text-sm font-medium text-slate-300">
                    No interviews found
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Interviews will appear here when candidates start applying.
                  </p>
                </td>
              </tr>
            ) : (
              interviews.map((interview) => (
                <tr
                  key={interview.session_id}
                  className="transition hover:bg-white/[0.025]"
                >
                  <td className="px-5 py-4">
                    <p className="font-medium text-white">
                      {interview.candidate?.name || "Unknown Candidate"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {interview.candidate?.email || "—"}
                    </p>
                  </td>

                  <td className="px-5 py-4 text-sm text-slate-300">
                    {interview.job_role || "—"}
                  </td>

                  <td className="px-5 py-4">
                    <StatusBadge status={interview.status} />
                  </td>

                  <td className="px-5 py-4 text-sm font-semibold text-white">
                    {interview.overall_score == null
                      ? "—"
                      : Number(interview.overall_score).toFixed(1)}
                  </td>

                  <td className="px-5 py-4 text-sm text-slate-400">
                    {formatDate(interview.created_at)}
                  </td>

                  <td className="px-5 py-4 text-right">
                    <button
                      onClick={() => onView(interview.session_id)}
                      className="inline-flex items-center gap-2 rounded-lg border border-indigo-500/20 bg-indigo-500/10 px-3 py-2 text-xs font-medium text-indigo-300 transition hover:bg-indigo-500/20"
                    >
                      <Eye size={14} />
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
        <p className="text-xs text-slate-500">
          Page {page} of {totalPages}
        </p>

        <div className="flex gap-2">
          <button
            disabled={page <= 1 || loading}
            onClick={() => setPage(page - 1)}
            className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>

          <button
            disabled={page >= totalPages || loading}
            onClick={() => setPage(page + 1)}
            className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
