import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  AUTH_TYPES,
  HTTP_METHODS,
  createEndpoint,
  listEndpoints,
  updateEndpoint,
  type Endpoint,
} from "../api";
import { knownRoots, slugify } from "../slug";

interface LocationState {
  endpoint?: Endpoint;
}

export function ConnectorForm() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const location = useLocation();

  const [existing, setExisting] = useState<Endpoint | null>((location.state as LocationState)?.endpoint ?? null);
  const [loadingExisting, setLoadingExisting] = useState(isEdit && !existing);

  const [path, setPath] = useState(existing?.path ?? "");
  const [method, setMethod] = useState(existing?.method ?? "GET");
  const [authType, setAuthType] = useState<string>(existing?.auth_type ?? "none");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [file, setFile] = useState<File | null>(null);

  // Create-only: build the path from a root + a friendly endpoint name
  // instead of hand-typing/slugifying it. Edit mode keeps the direct Path
  // field above — edits are usually small, targeted changes, not
  // reassembling a path from scratch.
  const [root, setRoot] = useState("");
  const [endpointName, setEndpointName] = useState("");
  const [rootOptions, setRootOptions] = useState<string[]>([]);

  const normalizedRoot = root.startsWith("/") ? root : root ? `/${root}` : "";
  const computedPath = endpointName.trim()
    ? `${normalizedRoot.replace(/\/+$/, "")}/${slugify(endpointName)}`
    : normalizedRoot;

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (isEdit) return;
    listEndpoints()
      .then((all) => setRootOptions(knownRoots(all)))
      .catch(() => {
        // Non-fatal — the root field still works as a free-text input.
      });
  }, [isEdit]);

  // Refresh fallback: if we landed here directly (e.g. a page reload) with
  // no router state carrying the endpoint, fetch the list and find it —
  // there's no GET-by-id route, and re-fetching the whole list is cheap
  // for the connector counts this tool is meant for.
  useEffect(() => {
    if (!isEdit || existing) return;
    listEndpoints()
      .then((all) => {
        const found = all.find((e) => e.id === id);
        if (!found) {
          setError("Connector not found — it may have been deleted.");
          return;
        }
        setExisting(found);
        setPath(found.path);
        setMethod(found.method);
        setAuthType(found.auth_type);
        setDescription(found.description ?? "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingExisting(false));
  }, [isEdit, existing, id]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setFieldErrors({});

    try {
      if (isEdit && id) {
        await updateEndpoint(id, {
          path,
          method,
          auth_type: authType,
          description,
          file,
        });
      } else {
        const errors: Record<string, string> = {};
        if (!root.trim()) errors.root = "A root path is required";
        if (!file) errors.file = "A data file is required";
        if (Object.keys(errors).length) {
          setFieldErrors(errors);
          setSubmitting(false);
          return;
        }
        await createEndpoint({ path: computedPath, method, auth_type: authType, description, file });
      }
      navigate("/connectors");
    } catch (err) {
      const apiErr = err as { message?: string; fieldErrors?: { field: string; reason: string }[] };
      if (apiErr.fieldErrors?.length) {
        setFieldErrors(Object.fromEntries(apiErr.fieldErrors.map((fe) => [fe.field, fe.reason])));
      }
      setError(apiErr.message ?? "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (isEdit && loadingExisting) {
    return <p className="page-subtitle">Loading connector…</p>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>{isEdit ? "Edit connector" : "Build a new connector"}</h1>
        <p className="page-subtitle">
          {isEdit
            ? "Only the fields you change are updated."
            : "Upload a CSV, JSON, or XML file and register it as a mock endpoint."}
        </p>
      </div>

      <form className="card" onSubmit={handleSubmit} style={{ maxWidth: 560 }}>
        {error && <div className="error-banner">{error}</div>}

        {isEdit ? (
          <div className="field">
            <label htmlFor="path">Path</label>
            <input
              id="path"
              type="text"
              placeholder="/api/users"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              required
            />
            {fieldErrors.path && <div className="field-hint" style={{ color: "var(--color-danger)" }}>{fieldErrors.path}</div>}
          </div>
        ) : (
          <>
            <div className="field-row">
              <div className="field">
                <label htmlFor="root-path">Root</label>
                <input
                  id="root-path"
                  type="text"
                  placeholder="/api/Defender"
                  value={root}
                  onChange={(e) => setRoot(e.target.value)}
                  list="known-roots"
                  required
                />
                <datalist id="known-roots">
                  {rootOptions.map((r) => (
                    <option key={r} value={r} />
                  ))}
                </datalist>
                {fieldErrors.root && <div className="field-hint" style={{ color: "var(--color-danger)" }}>{fieldErrors.root}</div>}
              </div>

              <div className="field">
                <label htmlFor="endpoint-name">Endpoint name (optional)</label>
                <input
                  id="endpoint-name"
                  type="text"
                  placeholder="Vulnerability scanning"
                  value={endpointName}
                  onChange={(e) => setEndpointName(e.target.value)}
                />
              </div>
            </div>
            <div className="field">
              <div className="field-hint">
                Will register as: <span className="mono">{computedPath || "—"}</span>. Pick an existing root to
                nest a new endpoint under it, or type a new one. Leave the name blank to create the root itself.
              </div>
              {fieldErrors.path && <div className="field-hint" style={{ color: "var(--color-danger)" }}>{fieldErrors.path}</div>}
            </div>
          </>
        )}

        <div className="field-row">
          <div className="field">
            <label htmlFor="method">Method</label>
            <select id="method" value={method} onChange={(e) => setMethod(e.target.value)}>
              {HTTP_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            {fieldErrors.method && <div className="field-hint" style={{ color: "var(--color-danger)" }}>{fieldErrors.method}</div>}
          </div>

          <div className="field">
            <label htmlFor="auth">Auth type</label>
            <select id="auth" value={authType} onChange={(e) => setAuthType(e.target.value)}>
              {AUTH_TYPES.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label htmlFor="description">Description (optional)</label>
          <input
            id="description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="file">{isEdit ? "Replace data file (optional)" : "Data file"}</label>
          {isEdit && existing?.artifact_name && (
            <p className="field-hint" style={{ marginBottom: 6 }}>
              Current file: <strong>{existing.artifact_name}</strong>
              {existing.artifact_rows != null && ` (${existing.artifact_rows} rows)`}
            </p>
          )}
          <input
            id="file"
            type="file"
            accept=".csv,.json,.xml"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <div className="field-hint">CSV, JSON, or XML — up to 5MB.</div>
          {fieldErrors.file && <div className="field-hint" style={{ color: "var(--color-danger)" }}>{fieldErrors.file}</div>}
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Create connector"}
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate("/connectors")}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
