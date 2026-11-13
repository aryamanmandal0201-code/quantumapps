import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { login, signup } = useAuth();
  const isSignup = mode === "signup";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    if (isSignup && password.length < 8) {
      setError("Use at least 8 characters for your password.");
      return;
    }
    setBusy(true);
    try {
      if (isSignup) await signup(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <section className="auth-intro">
        <h1>Tell it what needs doing.</h1>
        <p>
          TaskPilot keeps your to-do list by conversation. Type “Add the monthly report for Friday” or
          “What’s due this week?” and watch the list update beside the chat.
        </p>
        <ol className="auth-demo" aria-label="Example conversation">
          <li className="you">Mark the report done and add a task to start the next one</li>
          <li className="log">update_task, add_task</li>
          <li className="bot">Done. The report is marked complete and “Start next month’s report” is on your list.</li>
        </ol>
      </section>

      <form className="auth-card" onSubmit={handleSubmit} noValidate>
        <h2>{isSignup ? "Create your account" : "Log in"}</h2>
        {isSignup && (
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" />
          </label>
        )}
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={isSignup ? "new-password" : "current-password"}
          />
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn-primary" disabled={busy || !email || !password || (isSignup && !name.trim())}>
          {busy ? "Please wait…" : isSignup ? "Create account" : "Log in"}
        </button>
        <p className="auth-switch">
          {isSignup ? (
            <>Already have an account? <Link to="/login">Log in</Link></>
          ) : (
            <>New here? <Link to="/signup">Create an account</Link></>
          )}
        </p>
      </form>
    </main>
  );
}
