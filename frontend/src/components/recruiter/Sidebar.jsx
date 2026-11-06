
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ClipboardList,
  LogOut,
  Mic2,
  UserCircle,
} from "lucide-react";

export default function Sidebar({ recruiter, onLogout }) {
  const links = [
    {
      label: "Dashboard",
      path: "/recruiter/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: "All Interviews",
      path: "/recruiter/dashboard",
      icon: ClipboardList,
    },
  ];

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/10 bg-[#0b1220] md:flex">
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
          <Mic2 size={22} />
        </div>

        <div>
          <h2 className="text-base font-bold text-white">VoiceHire AI</h2>
          <p className="text-xs text-slate-500">Recruiter Portal</p>
        </div>
      </div>

      <div className="px-4 py-7">
        <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Workspace
        </p>

        <nav className="space-y-2">
          {links.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={label}
              to={path}
              end
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${
                  isActive
                    ? "bg-indigo-500/15 text-indigo-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-auto border-t border-white/10 p-4">
        <div className="mb-4 flex items-center gap-3 rounded-xl bg-white/[0.04] p-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700 text-slate-200">
            <UserCircle size={23} />
          </div>

          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">
              {recruiter?.full_name || "Recruiter"}
            </p>
            <p className="truncate text-xs text-slate-500">
              {recruiter?.email || ""}
            </p>
          </div>
        </div>

        <button
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-slate-400 transition hover:bg-red-500/10 hover:text-red-300"
        >
          <LogOut size={18} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
