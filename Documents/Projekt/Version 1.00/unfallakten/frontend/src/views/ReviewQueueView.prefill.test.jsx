import { describe, it, expect } from "vitest";
import { initialeEreignisse } from "./ReviewQueueView.jsx";

describe("initialeEreignisse", () => {
  it("belegt mit dem Default vor", () => {
    expect(initialeEreignisse("rechnung_eingegangen")).toEqual([
      { typ: "rechnung_eingegangen" },
    ]);
  });
  it("liefert leere Liste ohne Default", () => {
    expect(initialeEreignisse(null)).toEqual([]);
    expect(initialeEreignisse(undefined)).toEqual([]);
  });
});
