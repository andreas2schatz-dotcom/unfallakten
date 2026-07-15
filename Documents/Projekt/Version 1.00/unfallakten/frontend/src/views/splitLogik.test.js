// frontend/src/views/splitLogik.test.js
import { describe, it, expect } from "vitest";
import { gruppenAusSchnitten, schnittUmschalten, istAufteilbar } from "./splitLogik.js";

describe("gruppenAusSchnitten", () => {
  it("ohne Schnitt: eine Gruppe mit allen Seiten", () => {
    expect(gruppenAusSchnitten(5, [])).toEqual([[1, 2, 3, 4, 5]]);
  });
  it("ein Schnitt nach Seite 3", () => {
    expect(gruppenAusSchnitten(5, [3])).toEqual([[1, 2, 3], [4, 5]]);
  });
  it("mehrere Schnitte, unsortiert und dedupliziert", () => {
    expect(gruppenAusSchnitten(6, [4, 2, 2])).toEqual([[1, 2], [3, 4], [5, 6]]);
  });
  it("ignoriert Schnitte ausserhalb 1..N-1", () => {
    expect(gruppenAusSchnitten(3, [0, 3, 9])).toEqual([[1, 2, 3]]);
  });
});

describe("schnittUmschalten", () => {
  it("fuegt einen Schnitt hinzu (sortiert)", () => {
    expect(schnittUmschalten([3], 1)).toEqual([1, 3]);
  });
  it("entfernt einen vorhandenen Schnitt", () => {
    expect(schnittUmschalten([1, 3], 3)).toEqual([1]);
  });
});

describe("istAufteilbar", () => {
  it("true fuer datei", () => {
    expect(istAufteilbar({ payload_typ: "datei" })).toBe(true);
  });
  it("false fuer text", () => {
    expect(istAufteilbar({ payload_typ: "text" })).toBe(false);
  });
  it("false fuer null/undefined", () => {
    expect(istAufteilbar(null)).toBe(false);
  });
});
