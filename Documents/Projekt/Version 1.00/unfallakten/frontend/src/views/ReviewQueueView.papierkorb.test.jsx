import { describe, it, expect } from "vitest";
import { grundLabel } from "./ReviewQueueView.jsx";

describe("grundLabel (Papierkorb)", () => {
  it("uebersetzt bekannte Gruende", () => {
    expect(grundLabel("rauschen")).toBe("Rauschen");
    expect(grundLabel("spam")).toBe("Spam");
    expect(grundLabel("duplikat")).toBe("Duplikat");
  });

  it("faellt fuer unbekannte Gruende auf den Rohwert zurueck", () => {
    expect(grundLabel("xyz")).toBe("xyz");
  });

  it("liefert leeren String fuer null/undefined", () => {
    expect(grundLabel(null)).toBe("");
    expect(grundLabel(undefined)).toBe("");
  });
});
