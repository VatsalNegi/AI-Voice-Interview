
import {
  ClipboardList,
  CheckCircle2,
  Clock3,
  CalendarClock,
  TrendingUp,
} from "lucide-react";

export default function StatsCards({ statistics }) {
  const stats = [
    {
      title: "Total Interviews",
      value: statistics?.total_interviews ?? 0,
      icon: ClipboardList,
      color: "indigo",
    },
    {
      title: "Completed",
      value: statistics?.completed_interviews ?? 0,
      icon: CheckCircle2,
      color: "emerald",
    },
    {
      title: "In Progress",
      value: statistics?.in_progress_interviews ?? 0,
      icon: Clock3,
      color: "blue",
    },
    {
      title: "Pending",
      value: statistics?.not_started_interviews ?? 0,
      icon: CalendarClock,
      color: "amber",
    },
  ];

  const colorClasses = {
    indigo: "bg-indigo-500/10 text-indigo-400",
    emerald: "bg-emerald-500/10 text-emerald-400",
    blue: "bg-blue-500/10 text-blue-400",
    amber: "bg-amber-500/10 text-amber-400",
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {stats.map(({ title, value, icon: Icon, color }) => (
        <div
          key={title}
          className="rounded-2xl border border-white/10 bg-[#101827] p-5 transition hover:border-white/20"
        >
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">{title}</p>
            <div className={`rounded-xl p-2.5 ${colorClasses[color]}`}>
              <Icon size={19} />
            </div>
          </div>

          <p className="mt-5 text-3xl font-bold tracking-tight text-white">
            {value}
          </p>
        </div>
      ))}

      <div className="rounded-2xl border border-white/10 bg-[#101827] p-5 sm:col-span-2 xl:col-span-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-violet-500/10 p-2.5 text-violet-400">
            <TrendingUp size={20} />
          </div>

          <div>
            <p className="text-sm text-slate-400">Average Interview Score</p>
            <p className="mt-1 text-2xl font-bold text-white">
              {Number(statistics?.average_score ?? 0).toFixed(1)}
              <span className="ml-1 text-sm font-medium text-slate-500">
                / 100
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
