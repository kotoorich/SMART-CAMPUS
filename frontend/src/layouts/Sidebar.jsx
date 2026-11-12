import { LayoutDashboard, Users, UserCog, CalendarCheck, QrCode, GraduationCap, Settings, BookOpen, CalendarDays, Wallet, Megaphone, History, ClipboardList, Library } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = {
  admin: [
    { heading: "OVERVIEW", items: [{ to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
    { heading: "ACADEMICS", items: [
      { to: "/admin/academic", label: "Course oversight", icon: CalendarDays },
      { to: "/admin/grading-bands", label: "Grading bands", icon: ClipboardList },
      { to: "/admin/resources", label: "Learning resources", icon: Library },
      { to: "/admin/announcements", label: "Announcements", icon: Megaphone },
    ] },
    { heading: "PEOPLE", items: [
      { to: "/admin/students", label: "Students", icon: Users },
      { to: "/admin/faculty", label: "Lecturers", icon: UserCog },
    ] },
    { heading: "SYSTEM", items: [
      { to: "/admin/registration-settings", label: "Registration & fees", icon: Wallet },
      { to: "/admin/audit-log", label: "Audit log", icon: History },
    ] },
  ],
  faculty: [{ heading: "TEACHING WORKSPACE", items: [
    { to: "/faculty/dashboard", label: "Overview", icon: LayoutDashboard },
    { to: "/faculty/academic", label: "My courses & class lists", icon: BookOpen },
    { to: "/faculty/attendance", label: "Attendance sessions", icon: CalendarCheck },
    { to: "/faculty/announcements", label: "Announcements", icon: Megaphone },
  ] }],
  student: [{ heading: "MY ATTENDANCE", items: [
    { to: "/student/dashboard", label: "My dashboard", icon: LayoutDashboard },
    { to: "/student/courses", label: "Course registration", icon: BookOpen },
    { to: "/student/attendance", label: "Mark attendance", icon: QrCode },
    { to: "/student/announcements", label: "Announcements", icon: Megaphone },
  ] }],
};

export default function Sidebar({ onNavigate }) {
  const { user } = useAuth();
  if (!user) return null;
  const roleLabel = user.role === "faculty" ? "Lecturer" : user.role === "admin" ? "Administrator" : "Student";
  const groups = [...(NAV[user.role] || []), { heading: "PREFERENCES", items: [{ to: "/settings", label: "Settings", icon: Settings }] }];
  const initials = (user.name || "Campus User").split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();

  return (
    <aside className="campus-sidebar">
      <div className="sidebar-brand"><span className="sidebar-brand-mark"><GraduationCap size={20}/></span><span><strong>Smart Campus</strong><small>ATTENDANCE MANAGEMENT</small></span></div>
      <div className="sidebar-workspace"><span className="workspace-dot"/><span>{roleLabel} workspace</span></div>
      <nav className="sidebar-navigation" aria-label="Main navigation">
        {groups.map((group) => <section className="sidebar-group" key={group.heading}>
          <p>{group.heading}</p>
          {group.items.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end onClick={onNavigate} className={({ isActive }) => `sidebar-link ${isActive ? "is-active" : ""}`}><Icon size={17}/><span>{label}</span><span className="sidebar-link-indicator"/></NavLink>)}
        </section>)}
      </nav>
      <div className="sidebar-user"><span className="sidebar-avatar">{initials}</span><span className="sidebar-user-copy"><b>{user.name || "Campus User"}</b><small>{roleLabel}</small></span><span className="sidebar-user-status" title="Signed in"/></div>
    </aside>
  );
}
