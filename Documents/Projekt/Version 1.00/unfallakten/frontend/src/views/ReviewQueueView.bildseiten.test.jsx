import { describe, it, expect } from "vitest";
import { bildseiten } from "./ReviewQueueView.jsx";

describe("bildseiten (N-04 Bildseiten-Badge)", () => {
  it("liefert null ohne Bildseiten", () => {
    expect(bildseiten({})).toBeNull();
    expect(bildseiten({ bildseiten_anzahl: 0 })).toBeNull();
    expect(bildseiten({ bildseiten_anzahl: null })).toBeNull();
  });

  it("liefert die Anzahl bei Bildseiten", () => {
    expect(bildseiten({ bildseiten_anzahl: 3 })).toBe(3);
  });
});
