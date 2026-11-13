import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import NavBar from "./components/NavBar";
import WakeBanner from "./components/WakeBanner";
import AdminPage from "./pages/AdminPage";
import AuthPage from "./pages/AuthPage";
import Workspace from "./pages/Workspace";

function RequireAuth({ children, adminOnly = false }: { children: ReactNode; adminOnly?: boolean }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  // Hiding the page is only for convenience; the backend refuses admin APIs for normal users anyway.
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  const { user, checking } = useAuth();

  if (checking) {
    return (
      <>
        <WakeBanner />
        <div className="splash">Loading your workspace…</div>
      </>
    );
  }

  return (
    <>
      <WakeBanner />
      {user && <NavBar />}
      <Routes>
        <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
        <Route path="/signup" element={<GuestOnly><AuthPage mode="signup" /></GuestOnly>} />
        <Route path="/" element={<RequireAuth><Workspace /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth adminOnly><AdminPage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
