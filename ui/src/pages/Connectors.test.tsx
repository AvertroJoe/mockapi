import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Connectors } from "./Connectors";
import type { Endpoint } from "../api";

const { listEndpointsMock } = vi.hoisted(() => ({ listEndpointsMock: vi.fn() }));

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, listEndpoints: listEndpointsMock, deleteEndpoint: vi.fn() };
});

function ep(overrides: Partial<Endpoint>): Endpoint {
  return {
    id: overrides.id ?? "id",
    path: overrides.path ?? "/api/x",
    method: "GET",
    artifact_id: "artifact",
    auth_type: "none",
    description: null,
    created_at: "2026-01-01T00:00:00Z",
    artifact_name: "data.csv",
    artifact_rows: 1,
    ...overrides,
  };
}

async function renderConnectors() {
  render(
    <MemoryRouter>
      <Connectors />
    </MemoryRouter>
  );
  // Wait for the async listEndpoints().then(setEndpoints) to resolve.
  await screen.findByRole("table");
}

describe("Connectors grouping", () => {
  it("shows a root and its children nested, and an unrelated endpoint flat", async () => {
    listEndpointsMock.mockResolvedValue([
      ep({ id: "1", path: "/api/Defender" }),
      ep({ id: "2", path: "/api/Defender/vulnerability-scanning" }),
      ep({ id: "3", path: "/api/Defender/nist" }),
      ep({ id: "4", path: "/api/users" }),
    ]);

    await renderConnectors();

    expect(screen.getByText("/api/Defender")).toBeInTheDocument();
    expect(screen.getByText("/api/users")).toBeInTheDocument();
    // Children render de-slugified, not as their raw path.
    expect(screen.getByText(/Nist/)).toBeInTheDocument();
    expect(screen.getByText(/Vulnerability Scanning/)).toBeInTheDocument();
    expect(screen.queryByText("/api/Defender/nist")).not.toBeInTheDocument();
  });

  it("renders unrelated endpoints sharing a shallow ancestor as flat rows, not a group", async () => {
    listEndpointsMock.mockResolvedValue([
      ep({ id: "1", path: "/api/Defender" }),
      ep({ id: "2", path: "/api/users" }),
    ]);

    await renderConnectors();

    expect(screen.getByText("/api/Defender")).toBeInTheDocument();
    expect(screen.getByText("/api/users")).toBeInTheDocument();
    expect(screen.queryByText(/└/)).not.toBeInTheDocument();
  });
});
