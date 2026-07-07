import { Fragment, type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deleteEndpoint, listEndpoints, type Endpoint } from "../api";
import { deslugify, groupEndpoints, lastSegment } from "../slug";

interface ConnectorRowProps {
  ep: Endpoint;
  pathContent: ReactNode;
  onDelete: (ep: Endpoint) => void;
  rowClassName?: string;
}

function ConnectorRow({ ep, pathContent, onDelete, rowClassName }: ConnectorRowProps) {
  return (
    <tr className={rowClassName}>
      <td>
        <span className="badge badge-accent">{ep.method}</span>
      </td>
      <td>{pathContent}</td>
      <td>
        {ep.auth_type === "none" ? (
          <span className="badge">none</span>
        ) : (
          <span className="badge badge-success">{ep.auth_type}</span>
        )}
      </td>
      <td>{ep.artifact_name ?? "—"}</td>
      <td>{ep.artifact_rows ?? "—"}</td>
      <td>{ep.description ?? "—"}</td>
      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
        <Link to={`/connectors/${ep.id}/edit`} state={{ endpoint: ep }} className="btn btn-secondary btn-sm">
          Edit
        </Link>{" "}
        <button className="btn-danger btn-sm" onClick={() => onDelete(ep)}>
          Delete
        </button>
      </td>
    </tr>
  );
}

export function Connectors() {
  const [endpoints, setEndpoints] = useState<Endpoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Endpoint | null>(null);
  const [deleting, setDeleting] = useState(false);

  function refresh() {
    listEndpoints()
      .then(setEndpoints)
      .catch((err) => setError(err.message));
  }

  useEffect(refresh, []);

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteEndpoint(pendingDelete.id);
      setPendingDelete(null);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div>
            <h1>Connectors</h1>
            <p className="page-subtitle">Every mock endpoint currently registered on this server.</p>
          </div>
          <Link to="/connectors/new" className="btn btn-primary">
            + Build new
          </Link>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
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
                <th>Rows</th>
                <th>Description</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const { groups, ungrouped } = groupEndpoints(endpoints);
                return (
                  <>
                    {groups.map((group) => (
                      <Fragment key={group.parentPath}>
                        <ConnectorRow
                          key={group.root.id}
                          ep={group.root}
                          rowClassName="row-root"
                          pathContent={<span className="mono">{group.root.path}</span>}
                          onDelete={setPendingDelete}
                        />
                        {group.children.map((child) => (
                          <ConnectorRow
                            key={child.id}
                            ep={child}
                            rowClassName="row-child"
                            pathContent={
                              <span className="mono child-path" title={child.path}>
                                &nbsp;&nbsp;└ {deslugify(lastSegment(child.path))}
                              </span>
                            }
                            onDelete={setPendingDelete}
                          />
                        ))}
                      </Fragment>
                    ))}
                    {ungrouped.map((ep) => (
                      <ConnectorRow
                        key={ep.id}
                        ep={ep}
                        pathContent={<span className="mono">{ep.path}</span>}
                        onDelete={setPendingDelete}
                      />
                    ))}
                  </>
                );
              })()}
            </tbody>
          </table>
        )}
      </div>

      {pendingDelete && (
        <div className="center-screen" style={{ position: "fixed", inset: 0, background: "rgb(0 0 0 / 0.35)" }}>
          <div className="card gate-card">
            <h2 style={{ marginBottom: 10 }}>Delete this connector?</h2>
            <p className="page-subtitle" style={{ marginBottom: 18 }}>
              <span className="mono">
                {pendingDelete.method} {pendingDelete.path}
              </span>{" "}
              and its data file will be permanently removed. This can't be undone.
            </p>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button className="btn-secondary" onClick={() => setPendingDelete(null)} disabled={deleting}>
                Cancel
              </button>
              <button className="btn-danger" onClick={confirmDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
