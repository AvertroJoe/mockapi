export interface Endpoint {
  id: string;
  path: string;
  method: string;
  artifact_id: string;
  auth_type: "none" | "api_key" | "basic" | "jwt";
  description: string | null;
  created_at: string;
  artifact_name: string | null;
  artifact_rows: number | null;
}

export interface Artifact {
  id: string;
  name: string;
  filename: string;
  format: "csv" | "json" | "xml";
  row_count: number | null;
  created_at: string;
}

export interface EndpointWithArtifact {
  endpoint: Omit<Endpoint, "artifact_name" | "artifact_rows">;
  artifact: Artifact;
}

export const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] as const;
export const AUTH_TYPES = ["none", "api_key", "basic", "jwt"] as const;

const TOKEN_KEY = "mockapi_admin_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  fieldErrors: { field: string; reason: string }[];

  constructor(status: number, message: string, fieldErrors: { field: string; reason: string }[] = []) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

/** Parses the two error shapes the backend can return:
 *  - structured validation errors: {"detail": {"errors": [{"field","reason"}]}}
 *  - plain-string errors (404/409/etc.): {"detail": "..."}
 */
async function toApiError(resp: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    // non-JSON body — fall through with a generic message
  }

  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && Array.isArray((detail as { errors?: unknown }).errors)) {
    const errors = (detail as { errors: { field: string; reason: string }[] }).errors;
    const message = errors.map((e) => `${e.field}: ${e.reason}`).join("; ");
    return new ApiError(resp.status, message, errors);
  }
  if (typeof detail === "string") {
    return new ApiError(resp.status, detail);
  }
  return new ApiError(resp.status, `Request failed with status ${resp.status}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(path, { ...init, headers });
  if (!resp.ok) {
    throw await toApiError(resp);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function ping(): Promise<{ status: string }> {
  return request("/health");
}

export async function listEndpoints(): Promise<Endpoint[]> {
  return request("/admin/endpoints");
}

export async function deleteEndpoint(id: string): Promise<void> {
  await request(`/admin/endpoints/${id}`, { method: "DELETE" });
}

export interface ConnectorFields {
  path: string;
  method: string;
  auth_type: string;
  description?: string;
  file?: File | null;
}

export async function createEndpoint(fields: ConnectorFields): Promise<EndpointWithArtifact> {
  const form = new FormData();
  form.set("path", fields.path);
  form.set("method", fields.method);
  form.set("auth_type", fields.auth_type);
  if (fields.description) form.set("description", fields.description);
  if (fields.file) form.set("file", fields.file);

  return request("/admin/endpoints", { method: "POST", body: form });
}

export async function updateEndpoint(
  id: string,
  fields: Partial<ConnectorFields>
): Promise<EndpointWithArtifact> {
  const form = new FormData();
  if (fields.path !== undefined) form.set("path", fields.path);
  if (fields.method !== undefined) form.set("method", fields.method);
  if (fields.auth_type !== undefined) form.set("auth_type", fields.auth_type);
  if (fields.description !== undefined) form.set("description", fields.description);
  if (fields.file) form.set("file", fields.file);

  return request(`/admin/endpoints/${id}`, { method: "PATCH", body: form });
}
