import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";

export function TokenGate() {
  const { signIn, error } = useAuth();
  const [token, setTokenValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token.trim()) return;
    setSubmitting(true);
    await signIn(token.trim());
    setSubmitting(false);
  }

  return (
    <div className="center-screen">
      <div className="card gate-card">
        <div className="sidebar-brand" style={{ padding: 0, marginBottom: 18 }}>
          <span className="sidebar-brand-mark" />
          MockAPI
        </div>
        <h2 style={{ marginBottom: 6 }}>Admin token</h2>
        <p className="page-subtitle" style={{ marginBottom: 16 }}>
          Enter the server's <code>ADMIN_TOKEN</code> to manage connectors. This is stored only in
          your browser.
        </p>
        <form onSubmit={handleSubmit}>
          {error && <div className="error-banner">{error}</div>}
          <div className="field">
            <input
              type="password"
              autoFocus
              placeholder="Admin token"
              value={token}
              onChange={(e) => setTokenValue(e.target.value)}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={submitting} style={{ width: "100%" }}>
            {submitting ? "Checking…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
