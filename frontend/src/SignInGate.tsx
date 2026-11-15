import { useEffect, useState, type ReactNode } from "react";
import type { AuthService } from "./api/auth";

/** Renders children only after sign-in; no session data is requested or shown before (Req. 22.2). */
export function SignInGate({ auth, children }: {
  auth: AuthService; children: (user: string, signOut: () => void) => ReactNode;
}) {
  const [user, setUser] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    auth.currentUser().then((u) => { if (live) { setUser(u); setChecked(true); } });
    return () => { live = false; };
  }, [auth]);

  if (!checked) return <div className="signin-wrap"><p style={{ color: "var(--muted)" }}>Checking sign-in…</p></div>;
  if (user) {
    return <>{children(user, () => { void auth.signOut().then(() => setUser(null)); })}</>;
  }
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await auth.signIn(name, password);
      setPassword("");
      setUser((await auth.currentUser()) ?? name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    }
  };
  return (
    <div className="signin-wrap">
    <form onSubmit={submit} aria-label="Sign in" className="signin">
      <div className="crest" aria-hidden="true">⚖</div>
      <h1>Decision Tribunal</h1>
      <p className="lede">Three AI agents argue your investment idea. Code decides every rule. Simulation only.</p>
      <label>Email <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" /></label>
      <label>Password <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
      <button type="submit">Sign in</button>
      {error && <p role="alert" className="alert" style={{ marginTop: "1rem" }}>{error}</p>}
    </form>
    </div>
  );
}
