import { describe, it, expect } from "vitest";
import { apiDashboard } from "./api.js";

describe("apiDashboard", () => {
  it("bietet keinen nachrichtenNeu-Aufruf mehr (Endpoint entfernt)", () => {
    expect(apiDashboard.nachrichtenNeu).toBeUndefined();
  });

  it("bietet weiterhin die Action-Board-Aufrufe", () => {
    for (const fn of ["termineHeute", "fristen", "wiedervorlagen"]) {
      expect(typeof apiDashboard[fn]).toBe("function");
    }
  });
});
