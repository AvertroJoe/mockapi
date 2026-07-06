import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Layout } from "./Layout";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ signOut: vi.fn() }),
}));

function activeLinks(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Layout />
    </MemoryRouter>
  );
  return screen.getAllByRole("link").filter((link) => link.className.includes("active"));
}

describe("Layout nav highlighting", () => {
  // Regression test: NavLink applies its own "active" class based on prefix
  // matching regardless of a custom className, which can't distinguish
  // "/connectors/new" from "/connectors/<id>/edit" — both start with
  // "/connectors". This previously highlighted both "Connectors" and
  // "Build New" at once when on /connectors/new.
  it("highlights only Build New on /connectors/new, not Connectors too", () => {
    const active = activeLinks("/connectors/new");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent("Build New");
  });

  it("highlights only Connectors on /connectors", () => {
    const active = activeLinks("/connectors");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent("Connectors");
  });

  it("highlights Connectors (not Build New) when editing an existing connector", () => {
    const active = activeLinks("/connectors/abc-123/edit");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent("Connectors");
  });

  it("highlights only Home at the root", () => {
    const active = activeLinks("/");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent("Home");
  });
});
