import { describe, it, expect } from "vitest";
import { baueRvgAussergOverride } from "./KlageSection.jsx";

describe("baueRvgAussergOverride – KW-40 expliziter NaN-Guard im Versand-Payload", () => {
  it("liefert null bei nicht-numerischem wizardRvgAussergOv (nicht NaN)", () => {
    const wert = baueRvgAussergOverride("abc");
    expect(wert).toBeNull();
    expect(Number.isNaN(wert)).toBe(false);
  });

  it("liefert null, wenn kein Override gesetzt ist (leerer String)", () => {
    expect(baueRvgAussergOverride("")).toBeNull();
  });

  it("liefert die geparste Zahl bei gueltigem Override", () => {
    expect(baueRvgAussergOverride("250.5")).toBe(250.5);
  });
});
