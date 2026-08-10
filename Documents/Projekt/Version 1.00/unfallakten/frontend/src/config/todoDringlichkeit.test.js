import { describe, it, expect } from "vitest";
import { todoDringlichkeit } from "./utils.js";

const HEUTE = new Date("2026-08-10T12:00:00");

describe("todoDringlichkeit", () => {
  it("stuft nach Fälligkeit: <3 Tage rot, <7 orange, <14 gelb, sonst grau", () => {
    expect(todoDringlichkeit({ faellig_am: "2026-08-11" }, HEUTE)).toBe("rot");
    expect(todoDringlichkeit({ faellig_am: "2026-08-15" }, HEUTE)).toBe("orange");
    expect(todoDringlichkeit({ faellig_am: "2026-08-22" }, HEUTE)).toBe("gelb");
    expect(todoDringlichkeit({ faellig_am: "2026-09-30" }, HEUTE)).toBe("grau");
  });

  it("eskaliert Verjährungsfristen eine Stufe", () => {
    expect(todoDringlichkeit({ faellig_am: "2026-08-15", frist_typ: "verjaehrung" }, HEUTE)).toBe("rot");
    expect(todoDringlichkeit({ faellig_am: "2026-09-30", frist_typ: "verjaehrung" }, HEUTE)).toBe("gelb");
  });

  it("stuft ohne Fälligkeit nach Alter", () => {
    expect(todoDringlichkeit({ erstellt_am: "2026-08-09" }, HEUTE)).toBe("grau");
    expect(todoDringlichkeit({ erstellt_am: "2026-08-01" }, HEUTE)).toBe("orange");
    expect(todoDringlichkeit({ erstellt_am: "2026-07-01" }, HEUTE)).toBe("rot");
  });
});
