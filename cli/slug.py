"""
Path-slug helpers shared by the CLI's `endpoint create --root/--name` and
`endpoint list` grouping. The UI has its own TypeScript equivalent
(ui/src/slug.ts) — see issue #18: this stays a client-side/CLI-side
convenience on purpose, the admin API's own path validation is unchanged.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


def slugify(text: str) -> str:
    """Free text -> a URL-safe path segment.

    "Vulnerability scanning" -> "vulnerability-scanning"
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def deslugify(segment: str) -> str:
    """Best-effort reverse of slugify, for friendly display only.

    "vulnerability-scanning" -> "Vulnerability Scanning"
    """
    words = [w for w in segment.split("-") if w]
    return " ".join(w.capitalize() for w in words)


def last_segment(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else ""


def parent_path(path: str) -> str:
    """Everything but the last path segment.

    "/api/Defender/nist" -> "/api/Defender"
    "/api/Defender" -> "/api"
    "/Defender" -> "/"
    """
    trimmed = path.rstrip("/")
    idx = trimmed.rfind("/")
    return trimmed[:idx] or "/"


@dataclass
class EndpointGroup:
    parent_path: str
    root: Optional[dict]
    children: list = field(default_factory=list)


def group_endpoints(endpoints: list[dict]) -> tuple[list[EndpointGroup], list[dict]]:
    """Group endpoints that nest one level under a real, existing endpoint.

    Grouping requires the shared parent path to be a literal endpoint's own
    path — not just any shared path prefix. Two unrelated endpoints like
    "/api/Defender" and "/api/users" share the ancestor "/api", but "/api"
    isn't a deliberate root either of them was created under, it's just an
    incidental shallow prefix — grouping those would produce a false
    grouping out of nowhere. Requiring the parent to actually exist as an
    endpoint makes "is this a root?" unambiguous: it either was created at
    that exact path, or it wasn't.

    Returns (groups, ungrouped_endpoints), both sorted by path for stable,
    deterministic display.
    """
    by_path = {ep["path"]: ep for ep in endpoints}
    children_by_parent: dict[str, list[dict]] = {}
    for ep in endpoints:
        parent = parent_path(ep["path"])
        children_by_parent.setdefault(parent, []).append(ep)

    groups: list[EndpointGroup] = []
    grouped_ids: set[str] = set()

    for parent in sorted(children_by_parent):
        root = by_path.get(parent)
        if root is None:
            continue  # no literal endpoint at the parent path — nothing to root a group on
        children = sorted(children_by_parent[parent], key=lambda e: e["path"])
        groups.append(EndpointGroup(parent_path=parent, root=root, children=children))
        grouped_ids.add(root["id"])
        grouped_ids.update(c["id"] for c in children)

    ungrouped = sorted(
        (ep for ep in endpoints if ep["id"] not in grouped_ids), key=lambda e: e["path"]
    )
    return groups, ungrouped
