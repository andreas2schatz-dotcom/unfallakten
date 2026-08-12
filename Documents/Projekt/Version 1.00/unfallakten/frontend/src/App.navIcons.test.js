import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const hier = dirname(fileURLToPath(import.meta.url));

describe("Sidebar-Navigation", () => {
  it("nutzt durchgehend SVG-Icons aus der Icon-Registry, keine Emoji", () => {
    const quelle = readFileSync(join(hier, "App.jsx"), "utf-8");
    const block  = quelle.slice(quelle.indexOf("const navItems = ["), quelle.indexOf("];", quelle.indexOf("const navItems = [")));
    expect(block).not.toEqual("");
    const zeilen = block.split("\n").filter((z) => z.includes("icon:"));
    expect(zeilen.length).toBeGreaterThanOrEqual(7);
    for (const z of zeilen) {
      expect(z, `Emoji-Icon in navItems: ${z.trim()}`).toMatch(/icon:\s*Ic\.[a-zA-Z]+/);
    }
  });
});
