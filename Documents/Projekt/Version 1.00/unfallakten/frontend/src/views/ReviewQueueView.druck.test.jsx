import { describe, it, expect } from "vitest";
import { druckZiel } from "./ReviewQueueView.jsx";

describe("druckZiel (Druckbutton)", () => {
  it("liefert das PDF-Ziel fuer PDF-Dokumente", () => {
    const detail = { payload_typ: "pdf", parse: {} };
    const res = druckZiel(detail, "https://api/intake/dokument/7/pdf?token=abc");
    expect(res).toEqual({
      typ: "pdf",
      url: "https://api/intake/dokument/7/pdf?token=abc",
    });
  });

  it("liefert das Text-Ziel fuer E-Mail-Text-Dokumente", () => {
    const detail = { payload_typ: "text", parse: { text_gesamt: "Sehr geehrte Damen" } };
    const res = druckZiel(detail, "irrelevant");
    expect(res).toEqual({ typ: "text", text: "Sehr geehrte Damen" });
  });

  it("Text-Ziel ohne Text faellt auf leeren String zurueck", () => {
    const detail = { payload_typ: "text", parse: {} };
    const res = druckZiel(detail, "irrelevant");
    expect(res).toEqual({ typ: "text", text: "" });
  });

  it("behandelt fehlendes payload_typ als PDF", () => {
    const detail = { parse: {} };
    const res = druckZiel(detail, "https://api/pdf");
    expect(res).toEqual({ typ: "pdf", url: "https://api/pdf" });
  });
});
