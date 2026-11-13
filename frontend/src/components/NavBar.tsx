import { NavLink } from "react-router-dom";
import { useAuth, useCurrentUser } from "../auth";

export default function NavBar() {
  const { logout } = useAuth();
  const user = useCurrentUser();
  return (
    <header className="nav">
      <div className="nav-inner">
        <span className="brand">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="7" />
            <path d="M8 16.5l5 5 11-11" />
          </svg>
          TaskPilot
        </span>
        <nav className="nav-links">
          <NavLink to="/" end>My tasks</NavLink>
          {user.role === "admin" && <NavLink to="/admin">Admin</NavLink>}
        </nav>
        <div className="nav-user">
          <span className="nav-name">{user.name}</span>
          <span className={`role-badge role-${user.role}`}>{user.role === "admin" ? "Admin" : "User"}</span>
          <button className="btn-quiet" onClick={logout}>Log out</button>
        </div>
      </div>
    </header>
  );
}
