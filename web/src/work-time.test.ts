import { describe, expect, it } from "vitest";
import { localInput, localToUtc } from "./work-time";

describe("horários no fuso da organização", () => {
  it("converte o fato informado em São Paulo para UTC", () => {
    expect(localToUtc("2026-11-15T10:24", "America/Sao_Paulo")).toBe(
      "2026-11-15T13:24:00.000Z",
    );
    expect(localInput("2026-11-15T13:24:00Z", "America/Sao_Paulo")).toBe(
      "2026-11-15T10:24",
    );
  });
  it("recusa horário inexistente ou ambíguo em horário de verão", () => {
    expect(localToUtc("2026-03-08T02:30", "America/New_York")).toBeNull();
    expect(localToUtc("2026-11-01T01:30", "America/New_York")).toBeNull();
  });
  it("preserva a virada de dia em fusos diferentes", () => {
    expect(localToUtc("2026-11-15T00:24", "Asia/Tokyo")).toBe(
      "2026-11-14T15:24:00.000Z",
    );
  });
});
