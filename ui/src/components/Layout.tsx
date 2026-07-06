import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Home" },
  { to: "/connectors", label: "Connectors" },
  { to: "/connectors/new", label: "Build New" },
];

export function Layout() {
  const { signOut } = useAuth();
  const { pathname } = useLocation();

  // Using a plain Link (not NavLink) and computing "active" ourselves —
  // NavLink applies its own "active" class based on prefix matching
  // regardless of what's passed to `className`, which can't tell
  // "/connectors/new" (Build New) apart from "/connectors/<id>/edit"
  // (Connectors) since both start with "/connectors".
  function isActive(to: string): boolean {
    if (to === "/") return pathname === "/";
    if (to === "/connectors/new") return pathname === "/connectors/new";
    if (to === "/connectors") return pathname === "/connectors" || /^\/connectors\/[^/]+\/edit$/.test(pathname);
    return pathname === to;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark" />
          MockAPI
        </div>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={"nav-link" + (isActive(item.to) ? " active" : "")}
          >
            {item.label}
          </Link>
        ))}
        <div style={{ flex: 1 }} />
        <button className="btn-secondary btn-sm" onClick={signOut}>
          Sign out
        </button>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
