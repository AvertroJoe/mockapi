import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listEndpoints, type Endpoint } from "../api";

function copyToClipboard(text: string) {
  navigator.clipboard?.writeText(text);
}

export function Home() {
  const [endpoints, setEndpoints] = useState<Endpoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    listEndpoints()
      .then(setEndpoints)
      .catch((err) => setError(err.message));
  }, []);

  const serverAddress = `${window.location.protocol}//${window.location.host}`;
  const authCounts = (endpoints ?? []).reduce<Record<string, number>>((acc, ep) => {
    acc[ep.auth_type] = (acc[ep.auth_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <div className="page-header">
        <h1>Home</h1>
        <p className="page-subtitle">An overview of what this MockAPI server is currently serving.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="stat-grid">
        <div className="stat-card">
          <h3>Connectors served</h3>
          <div className="stat-value">{endpoints ? endpoints.length : "—"}</div>
        </div>
        <div className="stat-card">
          <h3>Unprotected</h3>
          <div className="stat-value">{endpoints ? authCounts.none ?? 0 : "—"}</div>
        </div>
        <div className="stat-card">
          <h3>Protected</h3>
          <div className="stat-value">
            {endpoints ? endpoints.length - (authCounts.none ?? 0) : "—"}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ marginBottom: 10 }}>Server address</h3>
        <p className="page-subtitle" style={{ marginBottom: 12 }}>
          Use this to point the CLI or a teammate's browser at this server.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <code
            className="mono"
            style={{
              background: "var(--color-bg)",
              padding: "8px 12px",
              borderRadius: "var(--radius)",
              flex: 1,
            }}
          >
            {serverAddress}
          </code>
          <button
            className="btn-secondary btn-sm"
            onClick={() => {
              copyToClipboard(serverAddress);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ marginBottom: 0 }}>Connectors</h3>
          <Link to="/connectors">Manage all →</Link>
        </div>
        {endpoints && endpoints.length === 0 && (
          <div className="empty-state">
            No connectors yet. <Link to="/connectors/new">Build your first one</Link>.
          </div>
        )}
        {endpoints && endpoints.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Method</th>
                <th>Path</th>
                <th>Auth</th>
                <th>Source file</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.slice(0, 8).map((ep) => (
                <tr key={ep.id}>
                  <td>
                    <span className="badge badge-accent">{ep.method}</span>
                  </td>
                  <td className="mono">{ep.path}</td>
                  <td>{ep.auth_type === "none" ? "—" : ep.auth_type}</td>
                  <td>{ep.artifact_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
