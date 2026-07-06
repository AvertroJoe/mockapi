import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, clearToken, listEndpoints, setToken } from "./api";

describe("API error parsing", () => {
  beforeEach(() => {
    clearToken();
    setToken("test-token");
  });

  it("parses structured validation errors into fieldErrors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { errors: [{ field: "path", reason: "is reserved" }] } }),
        { status: 422 }
      )
    );

    await expect(listEndpoints()).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(422);
      expect(apiErr.fieldErrors).toEqual([{ field: "path", reason: "is reserved" }]);
      expect(apiErr.message).toBe("path: is reserved");
      return true;
    });
  });

  it("parses plain-string error details (404/409/etc.)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Endpoint not found" }), { status: 404 })
    );

    await expect(listEndpoints()).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.message).toBe("Endpoint not found");
      expect(apiErr.fieldErrors).toEqual([]);
      return true;
    });
  });

  it("falls back to a generic message for a non-JSON error body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("not json", { status: 500 }));

    await expect(listEndpoints()).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(500);
      return true;
    });
  });

  it("attaches the stored admin token as a Bearer header", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]", { status: 200 }));

    await listEndpoints();

    const headers = fetchSpy.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });
});
