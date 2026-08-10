import { describe, it, expect } from "vitest";
import { summenAusPositionsstatus } from "./utils.js";

describe("summenAusPositionsstatus", () => {
  it("summiert gefordert/anerkannt/offen über alle Positionen", () => {
    const s = summenAusPositionsstatus({
      rep:  { gefordert: 8200, anerkannt: 6900, offen: 1300 },
      nutz: { gefordert: 1400, anerkannt: 1400, offen: 0 },
    });
    expect(s).toEqual({ gefordert: 9600, reguliert: 8300, offen: 1300 });
  });

  it("liefert null ohne Positionen", () => {
    expect(summenAusPositionsstatus({})).toBeNull();
    expect(summenAusPositionsstatus(null)).toBeNull();
  });
});
