import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  zeigeAktenanlageVorschlag, gruppenKey, vorgangFuerEintrag,
  AnlageChip, AktenanlageLeiste,
} from "./ReviewQueueView.jsx";

const GUTACHTEN_OHNE_AKTE = {
  id: 7, klasse: "gutachten", absender_kategorie: "gutachter",
  akte_kandidat_top: null, zustellung_id: 20, parent_zustellung_id: 10,
};

describe("zeigeAktenanlageVorschlag", () => {
  it("true bei Gutachten + Gutachter-Identifier + keinen Kandidaten", () => {
    expect(zeigeAktenanlageVorschlag(GUTACHTEN_OHNE_AKTE)).toBe(true);
  });
  it("false bei vorhandenem Kandidaten", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE,
      akte_kandidat_top: { akte_az: "44/22" },
    })).toBe(false);
  });
  it("false ohne Gutachter-Identifier", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE, absender_kategorie: null })).toBe(false);
  });
  it("false bei anderer Klasse", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE, klasse: "rechnung" })).toBe(false);
  });
});

describe("gruppenKey / vorgangFuerEintrag", () => {
  const queue = [
    { id: 7, zustellung_id: 20, parent_zustellung_id: 10 },
    { id: 8, zustellung_id: 21, parent_zustellung_id: 10 },
    { id: 9, zustellung_id: 30, parent_zustellung_id: null },
  ];
  const vorgaenge = [{ id: 1, intake_dokument_id: 7, status: "akte_erkannt",
                       erkanntes_az: "310/26" }];
  it("gruppenKey nimmt parent vor eigener zustellung", () => {
    expect(gruppenKey(queue[0])).toBe(10);
    expect(gruppenKey(queue[2])).toBe(30);
  });
  it("findet Vorgang fuer Traeger-Eintrag", () => {
    expect(vorgangFuerEintrag(queue[0], vorgaenge, queue).id).toBe(1);
  });
  it("findet Vorgang fuer Geschwister derselben Gruppe", () => {
    expect(vorgangFuerEintrag(queue[1], vorgaenge, queue).id).toBe(1);
  });
  it("null fuer fremde Eintraege", () => {
    expect(vorgangFuerEintrag(queue[2], vorgaenge, queue)).toBeNull();
  });
});

describe("AnlageChip", () => {
  it("laeuft-Zustand", () => {
    render(<AnlageChip vorgang={{ status: "laeuft", warnung: false }} />);
    expect(screen.getByText(/Aktenanlage läuft/)).toBeTruthy();
  });
  it("erkannt-Zustand mit AZ", () => {
    render(<AnlageChip vorgang={{ status: "akte_erkannt",
                                  erkanntes_az: "310/26" }} />);
    expect(screen.getByText(/310\/26/)).toBeTruthy();
  });
  it("Warnung bei langer Laufzeit", () => {
    render(<AnlageChip vorgang={{ status: "laeuft", warnung: true }} />);
    expect(screen.getByText(/ungewöhnlich lange/)).toBeTruthy();
  });
});

describe("AktenanlageLeiste", () => {
  it("unsichtbar ohne Vorgaenge", () => {
    const { container } = render(
      <AktenanlageLeiste vorgaenge={[]} ramicroVerfuegbar={true}
        onSpringe={() => {}} onOeffneAkte={() => {}} onAbbrechen={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
  it("zeigt Zaehler und Offline-Hinweis", () => {
    render(<AktenanlageLeiste
      vorgaenge={[{ id: 1, status: "laeuft", mandant_name: "Zejli",
                    intake_dokument_id: 7, warnung: false },
                  { id: 2, status: "akte_erkannt", mandant_name: "Maier",
                    erkanntes_az: "311/26", intake_dokument_id: null }]}
      ramicroVerfuegbar={false}
      onSpringe={() => {}} onOeffneAkte={() => {}} onAbbrechen={() => {}} />);
    expect(screen.getByText(/1 Aktenanlage läuft/)).toBeTruthy();
    expect(screen.getByText(/1 Akte erkannt/)).toBeTruthy();
    expect(screen.getByText(/RA-MICRO nicht erreichbar/)).toBeTruthy();
    expect(screen.getByText("öffnen")).toBeTruthy();
  });
});
