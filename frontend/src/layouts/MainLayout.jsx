import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";
import RoleTour from "./RoleTour";
import { useAuth } from "../context/AuthContext";
import "./navigation-fix.css";

export default function MainLayout({ children }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [desktopNavCollapsed, setDesktopNavCollapsed] = useState(false);
  const { user } = useAuth();
  const location = useLocation();

  const closeMobileNavigation = useCallback(() => setMobileNavOpen(false), []);
  const toggleNavigation = useCallback(() => {
    if (window.matchMedia("(max-width: 900px)").matches) {
      setMobileNavOpen((open) => !open);
    } else {
      setDesktopNavCollapsed((collapsed) => !collapsed);
    }
  }, []);

  useEffect(() => {
    closeMobileNavigation();
  }, [location.pathname, closeMobileNavigation]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") closeMobileNavigation();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeMobileNavigation]);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 901px)");
    const resetMobileState = (event) => {
      if (event.matches) closeMobileNavigation();
    };
    media.addEventListener?.("change", resetMobileState);
    return () => media.removeEventListener?.("change", resetMobileState);
  }, [closeMobileNavigation]);

  return (
    <div className={`app-shell ${mobileNavOpen ? "nav-open" : ""} ${desktopNavCollapsed ? "nav-collapsed" : ""}`}>
      <button type="button" className="app-nav-scrim" onClick={closeMobileNavigation}
        aria-label="Close navigation menu" aria-hidden={!mobileNavOpen} tabIndex={mobileNavOpen ? 0 : -1} />
      <Sidebar onNavigate={closeMobileNavigation} />
      <div className="app-main">
        <Header navOpen={mobileNavOpen} onToggleNav={toggleNavigation} />
        <main className="app-content">{children}</main>
      </div>
      {user && <RoleTour role={user.role} />}
    </div>
  );
}