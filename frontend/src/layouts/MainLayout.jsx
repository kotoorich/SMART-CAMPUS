import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import RoleTour from "./RoleTour";
import { useAuth } from "../context/AuthContext";

export default function MainLayout({ children }) {
  const [navOpen, setNavOpen] = useState(false);
  const { user } = useAuth();
  return (
    <div className={`app-shell ${navOpen ? "nav-open" : ""}`}>
      <div className="app-nav-scrim" onClick={() => setNavOpen(false)} />
      <Sidebar onNavigate={() => setNavOpen(false)} />
      <div className="app-main">
        <Header navOpen={navOpen} onToggleNav={() => setNavOpen((v) => !v)} />
        <main className="app-content">{children}</main>
      </div>
      {user && <RoleTour role={user.role} />}
    </div>
  );
}
