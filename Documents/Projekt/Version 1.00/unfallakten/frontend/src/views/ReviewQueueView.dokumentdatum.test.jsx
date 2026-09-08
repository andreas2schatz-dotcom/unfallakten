import { describe, it, expect } from "vitest";
import { isoZuDe, deZuIso } from "./ReviewQueueView.jsx";

describe("Dokumentdatum-Umwandlung im Freigabe-Dialog", () => {
  it("wandelt ISO in die deutsche Anzeige", () => {
    expect(isoZuDe("2024-03-14")).toBe("14.03.2024");
  });

  it("liefert leer bei fehlendem Datum", () => {
    expect(isoZuDe(null)).toBe("");
    expect(isoZuDe("")).toBe("");
  });

  it("wandelt die deutsche Eingabe zurueck", () => {
    expect(deZuIso("14.03.2024")).toBe("2024-03-14");
  });

  it("laesst unvollstaendige Eingaben unveraendert", () => {
    expect(deZuIso("14.03.")).toBe("14.03.");
  });
});
