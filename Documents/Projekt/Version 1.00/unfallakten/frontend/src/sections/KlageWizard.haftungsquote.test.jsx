import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { apiGebuehren } from "../api.js";
import {
  berechneKlagebetrag,
  berechneSwAussergEffektiv,
  baueAntraegeText,
  buildRwVorschau,
  StepRw,
  StepSchaden,
  StepZusammenfassung,
  StepGebuehren,
} from "./KlageWizard.jsx";

vi.mock("../api.js", () => ({
  apiGebuehren: {
    analysieren: vi.fn(),
    speichern: vi.fn(),
  },
}));

describe("berechneKlagebetrag – KW-03 Fall A/B", () => {
  it("gegnerisch: Summe der Beträge (checked) unabhängig von hq", () => {
    const positionen = [
      { key: "a", betragOriginal: 1000, betrag: 1000, checked: true },
      { key: "b", betragOriginal: 500,  betrag: 500,  checked: true },
      { key: "c", betragOriginal: 999,  betrag: 999,  checked: false },
    ];
    expect(berechneKlagebetrag(positionen, 75, "gegnerisch")).toBe(1500);
  });

  it("eigen: Referenzzahlen 10.000 Original / 7.000 genettet bei 75 % -> 4.500", () => {
    const positionen = [
      { key: "fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true },
    ];
    expect(berechneKlagebetrag(positionen, 75, "eigen")).toBe(4500);
  });

  it("hq=100 (eigen): identisch zur ungequoteten Summe", () => {
    const positionen = [
      { key: "a", betragOriginal: 1000, betrag: 1000, checked: true },
    ];
    expect(berechneKlagebetrag(positionen, 100, "eigen")).toBe(1000);
  });

  it("max-0-Klammer: quotierter Anteil unter bereits geleisteten Zahlungen wird nicht negativ", () => {
    const positionen = [
      { key: "a", betragOriginal: 10000, betrag: 1000, checked: true },
    ];
    expect(berechneKlagebetrag(positionen, 10, "eigen")).toBe(0);
  });
});

describe("berechneSwAussergEffektiv – KW-03 Nr.-2300-Basis quotieren", () => {
  it("gegnerisch: Streitwert bleibt unverändert", () => {
    expect(berechneSwAussergEffektiv(10000, 75, "gegnerisch")).toBe(10000);
  });

  it("eigen mit 0<hq<100: Streitwert wird quotiert", () => {
    expect(berechneSwAussergEffektiv(10000, 75, "eigen")).toBe(7500);
  });

  it("eigen mit hq=100: keine Quotierung (Guard)", () => {
    expect(berechneSwAussergEffektiv(10000, 100, "eigen")).toBe(10000);
  });

  it("eigen mit hq=0: keine Quotierung (Guard)", () => {
    expect(berechneSwAussergEffektiv(10000, 0, "eigen")).toBe(10000);
  });
});

describe("baueAntraegeText – KW-03 quotierter Klagebetrag im Antragstext", () => {
  const GRUND_OPTS = {
    mitSG: false, sgMind: 0, beklagte: [], weiblich: false,
    zinsenAb: "rechtshaengigkeit", verzug: "", unfalldatum: "",
    mitFestSg: false, mitFestSach: false,
  };

  it("eigen: Antragstext nennt den quotierten Betrag (4.500,00 €)", () => {
    const text = baueAntraegeText({
      ...GRUND_OPTS,
      positionen: [{ key: "fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true }],
      hq: 75, hqTyp: "eigen",
    });
    expect(text).toContain("4.500,00 €");
  });

  it("gegnerisch: Antragstext nennt weiterhin die volle (ungequotete) Summe", () => {
    const text = baueAntraegeText({
      ...GRUND_OPTS,
      positionen: [{ key: "a", betragOriginal: 1000, betrag: 1000, checked: true }],
      hq: 75, hqTyp: "gegnerisch",
    });
    expect(text).toContain("1.000,00 €");
  });
});

describe("buildRwVorschau – KW-03 oeffneWizard-Initialtext (Review-Fix)", () => {
  it("hq=75 gegnerisch: enthält 'bestritten', NICHT 'wurde entsprechend gekürzt', Prozent '25' via pctStr", () => {
    const text = buildRwVorschau("sein schuldhaftes Verhalten", 75, 0, false, "gegnerisch");
    expect(text).toContain("bestritten");
    expect(text).not.toContain("wurde entsprechend gekürzt");
    expect(text).toContain("25 %");
  });
});

describe("buildRwVorschau – KW-36 hq=0-Guard bei hqTyp=eigen", () => {
  it("hq=0 mit hqTyp eigen erzeugt keinen Anrechnungs-Baustein (Regressions-Pin)", () => {
    const text = buildRwVorschau("", 0, 0, false, "eigen");
    expect(text).not.toMatch(/anrechnen|Mithaftungsquote von 0/);
  });
});

describe("buildRwVorschau – KW-03 alleinige-Haftung-Satz (hq=100, genus-/anzahlbewusst, Rückportierung)", () => {
  it("hq=100, ein männlicher Beklagter (natürliche Person): 'des Beklagten' / 'bei dem ... Beklagten'", () => {
    const beklagte = [
      { rolle_klage: "beklagter", checked: true, anrede: "Herr", firma: false, versicherung: false },
    ];
    const text = buildRwVorschau("", 100, 0, false, "gegnerisch", beklagte);
    expect(text).toContain("Die alleinige Haftung des Beklagten steht außer Frage.");
    expect(text).toContain("von dem bei dem Beklagten versicherten Fahrzeug verursacht.");
    expect(text).not.toContain("(zu 1)");
  });

  it("hq=100, Firma + 2 Beklagte: 'der Beklagten zu 1)' / 'bei der ... Beklagten zu 1)'", () => {
    const beklagte = [
      { rolle_klage: "beklagter", checked: true, anrede: "Herr", firma: "Mustermann GmbH", versicherung: false },
      { rolle_klage: "beklagter", checked: true, anrede: "Herr", firma: false, versicherung: false },
    ];
    const text = buildRwVorschau("", 100, 0, false, "gegnerisch", beklagte);
    expect(text).toContain("Die alleinige Haftung der Beklagten zu 1) steht außer Frage.");
    expect(text).toContain("von dem bei der Beklagten zu 1) versicherten Fahrzeug verursacht.");
  });
});

describe("StepRw – KW-03 Step-7-Fallauswahl Gegnerisch/Eigen", () => {
  const BASIS_PROPS = {
    hq: 75, onHq: vi.fn(),
    hqTyp: "gegnerisch", onHqTyp: vi.fn(),
    hb: "", onHb: vi.fn(),
    abrechnungen: [], weiblich: false,
    rwText: "", onRwText: vi.fn(),
    kuerzungsarten: [], beklagte: [],
    onKiHaftung: vi.fn(), kiLaedt: false,
  };

  it("zeigt die Fallauswahl nur bei hq < 100", () => {
    render(<StepRw {...BASIS_PROPS} hq={75} />);
    expect(screen.getByText(/Gegnerische Quote/i)).toBeInTheDocument();
    expect(screen.getByText(/Eigene Quote/i)).toBeInTheDocument();
  });

  it("versteckt die Fallauswahl bei hq = 100 (Vollhaftung)", () => {
    render(<StepRw {...BASIS_PROPS} hq={100} />);
    expect(screen.queryByText(/Gegnerische Quote/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Eigene Quote/i)).not.toBeInTheDocument();
  });

  it("Umschalten auf 'Eigene Quote' regeneriert die Vorschau mit 'anrechnen', ohne den alten Kürzungssatz", () => {
    const onRwText = vi.fn();
    const onHqTyp = vi.fn();
    render(<StepRw {...BASIS_PROPS} onRwText={onRwText} onHqTyp={onHqTyp} />);

    fireEvent.click(screen.getByText(/Eigene Quote/i));

    expect(onHqTyp).toHaveBeenCalledWith("eigen");
    const text = onRwText.mock.calls.at(-1)[0];
    expect(text).toContain("anrechnen");
    expect(text).not.toContain("wurde entsprechend gekürzt");
  });

  it("Umschalten auf 'Gegnerische Quote' regeneriert die Vorschau mit 'bestritten', ohne den alten Kürzungssatz", () => {
    const onRwText = vi.fn();
    const onHqTyp = vi.fn();
    render(<StepRw {...BASIS_PROPS} hqTyp="eigen" onRwText={onRwText} onHqTyp={onHqTyp} />);

    fireEvent.click(screen.getByText(/Gegnerische Quote/i));

    expect(onHqTyp).toHaveBeenCalledWith("gegnerisch");
    const text = onRwText.mock.calls.at(-1)[0];
    expect(text).toContain("bestritten");
    expect(text).not.toContain("wurde entsprechend gekürzt");
  });

  it("'Text neu generieren' ruft onEinwaendeReset auf (verwirft veralteten Einwaende-Block aus Schritt 8)", () => {
    const onEinwaendeReset = vi.fn();
    render(<StepRw {...BASIS_PROPS} onEinwaendeReset={onEinwaendeReset} />);

    fireEvent.click(screen.getByText(/Text neu generieren/i));

    expect(onEinwaendeReset).toHaveBeenCalled();
  });

  it("Umschalten der Fallauswahl ruft onEinwaendeReset auf (verwirft veralteten Einwaende-Block aus Schritt 8)", () => {
    const onEinwaendeReset = vi.fn();
    render(<StepRw {...BASIS_PROPS} onEinwaendeReset={onEinwaendeReset} />);

    fireEvent.click(screen.getByText(/Eigene Quote/i));

    expect(onEinwaendeReset).toHaveBeenCalled();
  });
});

describe("StepSchaden – KW-03 Klagebetrag-Badge mit Haftungsquote", () => {
  const BASIS_PROPS = {
    onTogglePos: vi.fn(), mitSG: false, onMitSG: vi.fn(),
    sgMind: 0, onSGMind: vi.fn(), abrechnungen: [], az: null, kl_nom: "Der Kläger",
  };

  it("eigen: Badge zeigt den quotierten Klagebetrag (4.500,00)", () => {
    render(<StepSchaden {...BASIS_PROPS}
      positionen={[{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true }]}
      hq={75} hqTyp="eigen" />);
    expect(screen.getAllByText(/4\.500,00/).length).toBeGreaterThan(0);
  });

  it("gegnerisch: Badge zeigt weiterhin die volle Summe (7.000,00)", () => {
    render(<StepSchaden {...BASIS_PROPS}
      positionen={[{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true }]}
      hq={75} hqTyp="gegnerisch" />);
    expect(screen.getAllByText(/7\.000,00/).length).toBeGreaterThan(0);
  });
});

describe("StepZusammenfassung – KW-03 Klagebetrag mit Haftungsquote", () => {
  const BASIS_PROPS = {
    gericht: { name: "Amtsgericht Offenbach" },
    beklagte: [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }],
    mitSG: false, sgMind: 0,
    rvgAussergData: null, rvgAussergOv: null,
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe",
    zinsenAb: "verzug", wizardVerzugDatum: null,
    laedt: false, onGenerieren: vi.fn(), fehler: null,
    lgGrenzwert: 0, swAusserg: 0, antraegeText: "",
  };

  it("eigen: zeigt den quotierten Klagebetrag (4.500,00)", () => {
    render(<StepZusammenfassung {...BASIS_PROPS}
      positionen={[{ key: "fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true }]}
      hq={75} hqTyp="eigen" />);
    expect(screen.getAllByText(/4\.500,00/).length).toBeGreaterThan(0);
  });

  it("gegnerisch: zeigt weiterhin die volle Summe (7.000,00)", () => {
    render(<StepZusammenfassung {...BASIS_PROPS}
      positionen={[{ key: "fahrzeugschaden", betragOriginal: 10000, betrag: 7000, checked: true }]}
      hq={75} hqTyp="gegnerisch" />);
    expect(screen.getAllByText(/7\.000,00/).length).toBeGreaterThan(0);
  });
});

describe("StepGebuehren – KW-03 quotierter Streitwert an die Gebühren-API", () => {
  it("gibt den (von KlageSection bereits quotierten) Streitwert unverändert an die Analyse-API weiter", async () => {
    apiGebuehren.analysieren.mockReset();
    apiGebuehren.analysieren.mockResolvedValue({
      vorschlag: { faktor: 1.3, vuregel_id: "VU-1", begruendung: "x", leitentscheidung: "y" },
      rvg: { gesamt: 100, faktor: 1.3, gebuehr_netto: 80, post_pauschale: 16, zwischen_netto: 96, ust: 18.24, rvg_version: "2025" },
    });

    const swQuotiert = berechneSwAussergEffektiv(10000, 75, "eigen");
    expect(swQuotiert).toBe(7500);

    render(<StepGebuehren
      swAusserg={swQuotiert}
      rvgAussergData={null} onRvgAussergData={vi.fn()}
      rvgAussergOv=""        onRvgAussergOv={vi.fn()}
      rvgBereitsGezahlt=""   onRvgBereitsGezahlt={vi.fn()}
      gebuehrenText=""       onGebuehrenText={vi.fn()}
      beklagte={[]}          weiblich={false}
      zinsenAb="rechtshaengigkeit" verzug=""
      antraegeText=""        onAntraegeText={vi.fn()}
      gespeichertGb={null}   onGespeichertGb={vi.fn()}
      akteId="1/26"
    />);

    fireEvent.click(screen.getByText(/Kein Personenschaden/i));
    fireEvent.click(screen.getByRole("button", { name: /Analysieren/i }));

    await waitFor(() => expect(apiGebuehren.analysieren).toHaveBeenCalled());
    expect(apiGebuehren.analysieren).toHaveBeenCalledWith(
      "1/26",
      expect.objectContaining({ streitwert: 7500 }),
    );
  });
});
