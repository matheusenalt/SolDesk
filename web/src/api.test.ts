import { afterEach, describe, expect, it, vi } from "vitest";
import { loadStatus } from "./api";

afterEach(() => vi.unstubAllGlobals());
describe("conexão real", () => {
  it("consulta a saúde e a identidade antes de informar conexão", async () => {
    const info = {
      product: "SolDesk",
      api_version: "1.0.0",
      instance_id: "test",
      mode: "community",
      capabilities: ["health"],
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok" })))
      .mockResolvedValueOnce(new Response(JSON.stringify(info)));
    vi.stubGlobal("fetch", fetchMock);
    expect(await loadStatus()).toEqual(info);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/health",
      "/api/v1/server-info",
    ]);
  });
  it("não indica sucesso com API indisponível", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 503 })),
    );
    await expect(loadStatus()).rejects.toThrow();
  });
  it("recusa identidade incompatível", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}")));
    await expect(loadStatus()).rejects.toThrow();
  });
});
