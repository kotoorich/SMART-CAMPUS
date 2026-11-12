import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import RoleTour from "./RoleTour";
import { useAuth } from "../context/AuthContext";

export default function MainLayout({ children }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [desktopNavCollapsed, setDesktopNavCollapsed] = useState(false);
  const { user } = useAuth();

  const toggleNavigation = () => {
    if (window.matchMedia("(max-width: 900px)").matches) {
      setMobileNavOpen((open) => !open);
    } else {
      setDesktopNavCollapsed((collapsed) => !collapsed);
    }
  };

  const closeMobileNavigation = () => setMobileNavOpen(false);

  return (
    <div className={`app-shell ${mobileNavOpen ? "nav-open" : ""} ${desktopNavCollapsed ? "nav-collapsed" : ""}`}>
      <button
        type="button"
        className="app-nav-scrim"
        onClick={closeMobileNavigation}
        aria-label="Close navigation"
        tabIndex={mobileNavOpen ? 0 : -1}
      />
      <Sidebar onNavigate={closeMobileNavigation} />
      <div className="app-main">
        <Header navOpen={mobileNavOpen} onToggleNav={toggleNavigation} />
        <main className="app-content">{children}</main>
      </div>
      {user && <RoleTour role={user.role} />}
    </div>
  );
}
