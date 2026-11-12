import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, LogOut, Menu, X } from "lucide-react";
import NotificationBell from "../components/NotificationBell";
import { LiveDot } from "../components/UI";
import { useRealtime } from "../hooks/useRealtime";

export default function Header({ onToggleNav, navOpen = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [confirm, setConfirm] = useState(false);
  const { status } = useRealtime();
  const handleLogout = () => { logout(); navigate("/login", { replace: true }); };
  const roleLabel = user?.role === "faculty" ? "Lecturer" : user?.role === "admin" ? "Administrator" : "Student";
  const homePath = `/${user?.role || "student"}/dashboard`;
  const isHome = location.pathname === homePath;
  const fallbackPath = location.pathname.startsWith("/profiles/")
    ? (user?.role === "admin" ? "/admin/students" : user?.role === "faculty" ? "/faculty/academic" : "/student/courses")
    : location.pathname === "/settings" ? homePath : homePath;
  const goBack = () => {
    if (window.history.state?.idx > 0) navigate(-1);
    else navigate(fallbackPath, { replace: true });
  };

  return <>
    <header className="app-header">
      <div className="app-header-left">
        <button className="app-header-menu" onClick={onToggleNav} aria-label={navOpen ? "Close navigation" : "Open navigation"} aria-expanded={navOpen}>{navOpen ? <X size={19} /> : <Menu size={19} />}</button>
        {!isHome && <button type="button" className="app-header-back" onClick={goBack} aria-label="Go back"><ArrowLeft size={17}/><span>Back</span></button>}
        <div className="app-header-welcome">
          <span className="text-sm text-gray-500">Welcome back,</span>
          <strong>{user?.name}</strong>
        </div>
      </div>
      <div className="app-header-right">
        <LiveDot status={status} />
        <div className="sc-role-pill">{roleLabel}</div>
        <NotificationBell />
        <button onClick={() => setConfirm(true)} className="logout-button"><LogOut size={16}/> Sign out</button>
      </div>
    </header>
    {confirm && <div className="sc-modal-backdrop" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget) setConfirm(false); }}><section className="sc-modal" role="dialog" aria-modal="true" aria-labelledby="logout-title"><button className="sc-modal-close" aria-label="Close" onClick={() => setConfirm(false)}><X size={18}/></button><div className="sc-modal-icon"><LogOut size={22}/></div><h2 id="logout-title">Sign out of Smart Campus?</h2><p>Your current session will end. You can sign in again at any time.</p><div className="sc-modal-actions"><button className="sc-button sc-button-secondary" onClick={() => setConfirm(false)}>Cancel</button><button className="sc-button sc-button-danger" onClick={handleLogout}>Sign out</button></div></section></div>}
  </>;
}
