import { describe, it, expect } from "vitest";
import { ocrQualitaet } from "./ReviewQueueView.jsx";

describe("ocrQualitaet (N-02 OCR-Qualitaets-Badge)", () => {
  it("liefert kein Badge bei guten Werten", () => {
    expect(ocrQualitaet({ ocr_ratio_salat: 0.02, ocr_quote_woerter: 0.5 }))
      .toBeNull();
  });

  it("liefert kein Badge ohne Daten", () => {
    expect(ocrQualitaet({})).toBeNull();
    expect(ocrQualitaet({ ocr_ratio_salat: null, ocr_quote_woerter: null }))
      .toBeNull();
  });

  it("meldet 'schlecht' bei hohem Zeichensalat", () => {
    const b = ocrQualitaet({ ocr_ratio_salat: 0.42, ocr_quote_woerter: 0.5 });
    expect(b.stufe).toBe("schlecht");
  });

  it("meldet 'schlecht' bei sehr niedriger Woerterbuch-Quote", () => {
    const b = ocrQualitaet({ ocr_ratio_salat: 0.01, ocr_quote_woerter: 0.05 });
    expect(b.stufe).toBe("schlecht");
  });

  it("meldet 'mittel' im Graubereich", () => {
    const b = ocrQualitaet({ ocr_ratio_salat: 0.2, ocr_quote_woerter: 0.5 });
    expect(b.stufe).toBe("mittel");
  });

  it("liefert einen erklaerenden Titel-Text", () => {
    const b = ocrQualitaet({ ocr_ratio_salat: 0.42, ocr_quote_woerter: 0.07 });
    expect(typeof b.titel).toBe("string");
    expect(b.titel.length).toBeGreaterThan(0);
  });
});
