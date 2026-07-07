/**
 * Path-slug helpers for the "root + name" connector builder (issue #18).
 * Mirrors cli/slug.py — kept client-side on purpose, the admin API's own
 * path validation is unchanged.
 */

export function slugify(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Best-effort reverse of slugify, for friendly display only. */
export function deslugify(segment: string): string {
  return segment
    .split("-")
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export function lastSegment(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? "";
}

/** Everything but the last path segment. "/api/Defender/nist" -> "/api/Defender". */
export function parentPath(path: string): string {
  const trimmed = path.replace(/\/+$/, "");
  const idx = trimmed.lastIndexOf("/");
  return trimmed.slice(0, idx) || "/";
}

export interface EndpointLike {
  id: string;
  path: string;
}

export interface EndpointGroup<T extends EndpointLike> {
  parentPath: string;
  root: T;
  children: T[];
}

/**
 * Group endpoints that nest one level under a real, existing endpoint.
 *
 * Grouping requires the shared parent path to be a literal endpoint's own
 * path — two unrelated endpoints like "/api/Defender" and "/api/users"
 * share the ancestor "/api", but "/api" isn't a deliberate root either was
 * created under, so treating that as a group would be a false positive.
 * Requiring the parent to actually exist makes "is this a root?"
 * unambiguous.
 */
export function groupEndpoints<T extends EndpointLike>(
  endpoints: T[]
): { groups: EndpointGroup<T>[]; ungrouped: T[] } {
  const byPath = new Map(endpoints.map((e) => [e.path, e]));
  const childrenByParent = new Map<string, T[]>();
  for (const ep of endpoints) {
    const parent = parentPath(ep.path);
    const list = childrenByParent.get(parent) ?? [];
    list.push(ep);
    childrenByParent.set(parent, list);
  }

  const groups: EndpointGroup<T>[] = [];
  const groupedIds = new Set<string>();

  for (const parent of [...childrenByParent.keys()].sort()) {
    const root = byPath.get(parent);
    if (!root) continue;
    const children = [...childrenByParent.get(parent)!].sort((a, b) => a.path.localeCompare(b.path));
    groups.push({ parentPath: parent, root, children });
    groupedIds.add(root.id);
    children.forEach((c) => groupedIds.add(c.id));
  }

  const ungrouped = endpoints
    .filter((e) => !groupedIds.has(e.id))
    .sort((a, b) => a.path.localeCompare(b.path));

  return { groups, ungrouped };
}

/** Every existing endpoint's own path is a valid root to nest a new child under. */
export function knownRoots<T extends EndpointLike>(endpoints: T[]): string[] {
  return [...new Set(endpoints.map((e) => e.path))].sort();
}
