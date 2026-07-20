import { describe, it, expect } from "vitest";
import { wortDiff } from "./wizardFuehrungLogik.js";

describe("wortDiff", () => {
  it("identische Texte ergeben ein einziges gleich-Segment", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
    ]);
  });

  it("Ergänzung am Ende wird als neu markiert", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt schnell")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "neu", text: "schnell" },
    ]);
  });

  it("Streichung wird als weg markiert", () => {
    expect(wortDiff("Der Kläger fährt schnell", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "weg", text: "schnell" },
    ]);
  });

  it("Ersetzung liefert weg vor neu", () => {
    expect(wortDiff("Der Beklagte zahlt", "Die Beklagte zahlt")).toEqual([
      { typ: "weg", text: "Der" },
      { typ: "neu", text: "Die" },
      { typ: "gleich", text: "Beklagte zahlt" },
    ]);
  });

  it("leerer Auto-Text: alles neu; beide leer: leeres Ergebnis", () => {
    expect(wortDiff("", "Neuer Text")).toEqual([{ typ: "neu", text: "Neuer Text" }]);
    expect(wortDiff("", "")).toEqual([]);
    expect(wortDiff(null, undefined)).toEqual([]);
  });

  it("Umlaute bleiben unangetastet", () => {
    expect(wortDiff("Kürzung übernommen", "Kürzung geprüft und übernommen")).toEqual([
      { typ: "gleich", text: "Kürzung" },
      { typ: "neu", text: "geprüft und" },
      { typ: "gleich", text: "übernommen" },
    ]);
  });

  it("Zeilenumbrüche bleiben im Segmenttext erhalten", () => {
    const seg = wortDiff("Absatz eins.\n\nAbsatz zwei.", "Absatz eins.\n\nAbsatz zwei.");
    expect(seg).toEqual([{ typ: "gleich", text: "Absatz eins.\n\nAbsatz zwei." }]);
  });

  it("Änderung nach Zeilenumbruch wird erkannt", () => {
    const seg = wortDiff("Satz eins.\nSatz zwei.", "Satz eins.\nSatz drei.");
    expect(seg).toEqual([
      { typ: "gleich", text: "Satz eins.\nSatz" },
      { typ: "weg", text: "zwei." },
      { typ: "neu", text: "drei." },
    ]);
  });
});
