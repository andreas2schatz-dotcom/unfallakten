import { describe, it, expect } from "vitest";
import { sortiereGruppen } from "./ReviewQueueView.jsx";

describe("sortiereGruppen", () => {
  const gruppen = [
    { eintrag: { id: 1 }, kinder: [] },
    { eintrag: { id: 2 }, kinder: [] },
    { eintrag: { id: 3 }, kinder: [] },
  ];

  it("gibt die Liste unveraendert zurueck wenn absteigend=false", () => {
    const res = sortiereGruppen(gruppen, false);
    expect(res.map(g => g.eintrag.id)).toEqual([1, 2, 3]);
  });

  it("kehrt die Reihenfolge um wenn absteigend=true", () => {
    const res = sortiereGruppen(gruppen, true);
    expect(res.map(g => g.eintrag.id)).toEqual([3, 2, 1]);
  });

  it("veraendert das Eingabe-Array nicht (keine Mutation)", () => {
    const original = [...gruppen];
    sortiereGruppen(gruppen, true);
    expect(gruppen).toEqual(original);
  });
});
