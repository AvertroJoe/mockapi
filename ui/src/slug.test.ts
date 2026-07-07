import { describe, expect, it } from "vitest";
import { deslugify, groupEndpoints, knownRoots, lastSegment, parentPath, slugify } from "./slug";

describe("slugify", () => {
  it("converts free text to a url-safe slug", () => {
    expect(slugify("Vulnerability scanning")).toBe("vulnerability-scanning");
  });

  it("collapses punctuation and repeated separators", () => {
    expect(slugify("  NIST!!  800--53 ")).toBe("nist-800-53");
  });

  it("returns an empty string for whitespace-only input", () => {
    expect(slugify("   ")).toBe("");
  });
});

describe("deslugify", () => {
  it("reverses slugify into a friendly label", () => {
    expect(deslugify("vulnerability-scanning")).toBe("Vulnerability Scanning");
    expect(deslugify("nist")).toBe("Nist");
  });
});

describe("lastSegment / parentPath", () => {
  it("splits a nested path", () => {
    expect(lastSegment("/api/Defender/nist")).toBe("nist");
    expect(parentPath("/api/Defender/nist")).toBe("/api/Defender");
  });

  it("handles a single-segment path", () => {
    expect(lastSegment("/Defender")).toBe("Defender");
    expect(parentPath("/Defender")).toBe("/");
  });
});

interface Ep {
  id: string;
  path: string;
}

function ep(id: string, path: string): Ep {
  return { id, path };
}

describe("groupEndpoints", () => {
  it("groups a root with its children", () => {
    const endpoints = [
      ep("1", "/api/Defender"),
      ep("2", "/api/Defender/vulnerability-scanning"),
      ep("3", "/api/Defender/nist"),
      ep("4", "/api/users"),
    ];

    const { groups, ungrouped } = groupEndpoints(endpoints);

    expect(groups).toHaveLength(1);
    expect(groups[0].parentPath).toBe("/api/Defender");
    expect(groups[0].root.id).toBe("1");
    expect(groups[0].children.map((c) => c.id)).toEqual(["3", "2"]); // sorted by path

    expect(ungrouped.map((e) => e.id)).toEqual(["4"]);
  });

  it("requires the shared parent to actually exist as an endpoint", () => {
    const endpoints = [ep("1", "/api/Defender/vulnerability-scanning"), ep("2", "/api/Defender/nist")];

    const { groups, ungrouped } = groupEndpoints(endpoints);

    expect(groups).toEqual([]);
    expect(ungrouped).toHaveLength(2);
  });

  it("does not group unrelated endpoints sharing a shallow ancestor", () => {
    const endpoints = [ep("1", "/api/Defender"), ep("2", "/api/users")];

    const { groups, ungrouped } = groupEndpoints(endpoints);

    expect(groups).toEqual([]);
    expect(ungrouped.map((e) => e.id)).toEqual(["1", "2"]);
  });

  it("groups a root with a single child", () => {
    const endpoints = [ep("1", "/api/Defender"), ep("2", "/api/Defender/nist")];

    const { groups, ungrouped } = groupEndpoints(endpoints);

    expect(groups).toHaveLength(1);
    expect(groups[0].children.map((c) => c.id)).toEqual(["2"]);
    expect(ungrouped).toEqual([]);
  });
});

describe("knownRoots", () => {
  it("returns every distinct existing path, sorted", () => {
    const endpoints = [ep("1", "/api/users"), ep("2", "/api/Defender")];
    expect(knownRoots(endpoints)).toEqual(["/api/Defender", "/api/users"]);
  });
});
