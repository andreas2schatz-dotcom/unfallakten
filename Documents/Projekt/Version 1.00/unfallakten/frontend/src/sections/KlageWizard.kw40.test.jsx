import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  StepRw,
  StepZusammenfassung,
  StepGebuehren,
  ersetzeMandantDurchKlaeger,
  parseBetragOderNull,
} from "./KlageWizard.jsx";

vi.mock("../api.js", () => ({
  apiGebuehren: {
    analysieren: vi.fn(),
    speichern: vi.fn(),
  },
}));

// ── KW-40 Punkt 1: einwandeUebernehmen ersetzt statt haengt an ─────────────────

describe("StepRw – KW-40 Einwaende-Uebernahme ersetzt statt anzuhaengen", () => {
  const BASIS_PROPS = {
    hq: 100, onHq: vi.fn(),
    hqTyp: "gegnerisch", onHqTyp: vi.fn(),
    hb: "", onHb: vi.fn(),
    abrechnungen: [], weiblich: false,
    kuerzungsarten: [
      { id: 1, bezeichnung: "SV-Kosten", kategorie: "technisch_gutachten", textbaustein: "SV-Text" },
      { id: 2, bezeichnung: "Fahrzeugschaden-Kuerzung", kategorie: "fahrzeugschaden", textbaustein: "FZ-Text" },
    ],
    beklagte: [],
    onKiHaftung: vi.fn(), kiLaedt: false,
  };

  function uebernehmenMitAuswahl(bezeichnung) {
    fireEvent.click(screen.getByRole("button", { name: /Kürzungen & Einwände/i }));
    fireEvent.click(screen.getByText(bezeichnung));
    fireEvent.click(screen.getByRole("button", { name: /Text übernehmen/i }));
  }

  it("ersetzt den zuvor eingefuegten Block bei erneutem Uebernehmen (statt anzuhaengen)", () => {
    const onRwText = vi.fn();
    const { rerender } = render(<StepRw {...BASIS_PROPS} rwText="" onRwText={onRwText} />);

    uebernehmenMitAuswahl("SV-Kosten");
    expect(onRwText).toHaveBeenCalledTimes(1);
    const block1 = onRwText.mock.calls[0][0];
    expect(block1).toContain("SV-Kosten");

    rerender(<StepRw {...BASIS_PROPS} rwText={block1} onRwText={onRwText} />);
    uebernehmenMitAuswahl("Fahrzeugschaden-Kuerzung");

    expect(onRwText).toHaveBeenCalledTimes(2);
    const ergebnis = onRwText.mock.calls[1][0];
    expect(ergebnis).toContain("Fahrzeugschaden-Kuerzung");
    expect(ergebnis).not.toContain("SV-Kosten");
  });

  it("haengt an, wenn der zuvor eingefuegte Block nicht mehr im Text enthalten ist (Nutzer-Edit)", () => {
    const onRwText = vi.fn();
    const { rerender } = render(<StepRw {...BASIS_PROPS} rwText="" onRwText={onRwText} />);

    uebernehmenMitAuswahl("SV-Kosten");

    rerender(<StepRw {...BASIS_PROPS} rwText="Individuell bearbeiteter Text" onRwText={onRwText} />);
    uebernehmenMitAuswahl("Fahrzeugschaden-Kuerzung");

    const ergebnis = onRwText.mock.calls[1][0];
    expect(ergebnis.startsWith("Individuell bearbeiteter Text\n\n")).toBe(true);
    expect(ergebnis).toContain("Fahrzeugschaden-Kuerzung");
  });
});

// ── KW-40 Punkt 2: Kuerzungssumme klemmt negative Abzuege ──────────────────────

describe("StepRw – KW-40 Kuerzungssumme klemmt negative Abzuege", () => {
  const abrechnungen = [
    {
      positionen: [
        // reguliert > gefordert -> negativer Abzug, darf die Summe nicht senken
        { kuerzungsart_id: 1, betrag_gefordert: 100, betrag_reguliert: 150 },
        { kuerzungsart_id: 2, betrag_gefordert: 200, betrag_reguliert: 50 },
      ],
    },
  ];
  const kuerzungsarten = [
    { id: 1, bezeichnung: "Ueberzahlt",  kategorie: "sonstiger_schaden", textbaustein: "" },
    { id: 2, bezeichnung: "Unterzahlt",  kategorie: "sonstiger_schaden", textbaustein: "" },
  ];

  it("reguliert > gefordert senkt die Kuerzungssumme nicht", () => {
    const onRwText = vi.fn();
    render(<StepRw hq={100} onHq={vi.fn()} hqTyp="gegnerisch" onHqTyp={vi.fn()}
      hb="" onHb={vi.fn()} abrechnungen={abrechnungen} weiblich={false}
      rwText="" onRwText={onRwText} kuerzungsarten={kuerzungsarten} beklagte={[]}
      onKiHaftung={vi.fn()} kiLaedt={false} />);

    // Beide Kuerzungsarten sind bereits aus dem Regulierungsschreiben vorausgewaehlt (aktiveIds)
    fireEvent.click(screen.getByRole("button", { name: /Kürzungen & Einwände/i }));
    fireEvent.click(screen.getByRole("button", { name: /Text übernehmen/i }));

    const text = onRwText.mock.calls[0][0];
    // Nur die echte Kuerzung (150,00 €) darf im Schlusssatz stehen, nicht 100,00 € (150 + (-50))
    expect(text).toContain("150,00");
    expect(text).not.toMatch(/100,00\s?€/);
  });
});

// ── KW-40 Punkt 3: ersetzeMandantDurchKlaeger Artikel-Faelle ───────────────────

describe("ersetzeMandantDurchKlaeger – KW-40 Artikel-Faelle", () => {
  it("Der Mandant wird bei weiblich zu Die Klaegerin", () => {
    expect(ersetzeMandantDurchKlaeger("Der Mandant fuhr los.", true)).toBe("Die Klägerin fuhr los.");
  });

  it("Der Mandant wird bei maskulin zu Der Klaeger", () => {
    expect(ersetzeMandantDurchKlaeger("Der Mandant fuhr los.", false)).toBe("Der Kläger fuhr los.");
  });

  it("Dem Mandanten wird bei weiblich zu Der Klaegerin", () => {
    expect(ersetzeMandantDurchKlaeger("Dem Mandanten wurde geholfen.", true)).toBe("Der Klägerin wurde geholfen.");
  });

  it("Dem Mandanten wird bei maskulin zu Dem Klaeger", () => {
    expect(ersetzeMandantDurchKlaeger("Dem Mandanten wurde geholfen.", false)).toBe("Dem Kläger wurde geholfen.");
  });

  it("Den Mandanten wird bei weiblich zu Die Klaegerin (Akkusativ)", () => {
    expect(ersetzeMandantDurchKlaeger("Den Mandanten traf keine Schuld.", true)).toBe("Die Klägerin traf keine Schuld.");
  });

  it("Den Mandanten wird bei maskulin zu Den Klaeger (Akkusativ)", () => {
    expect(ersetzeMandantDurchKlaeger("Den Mandanten traf keine Schuld.", false)).toBe("Den Kläger traf keine Schuld.");
  });

  it("nacktes Mandant bleibt als Fallback erhalten", () => {
    expect(ersetzeMandantDurchKlaeger("laut Mandant", false)).toBe("laut Kläger");
  });
});

// ── KW-40 Punkt 5: NaN-Guard rvgAussergOv ──────────────────────────────────────

describe("parseBetragOderNull – KW-40", () => {
  it("liefert null bei leerem/nicht-numerischem Wert", () => {
    expect(parseBetragOderNull("")).toBeNull();
    expect(parseBetragOderNull("abc")).toBeNull();
    expect(parseBetragOderNull(null)).toBeNull();
  });

  it("liefert die geparste Zahl bei gueltigem Wert", () => {
    expect(parseBetragOderNull("123.45")).toBe(123.45);
  });
});

describe("StepZusammenfassung – KW-40 NaN-Guard RVG-Override (Anzeige)", () => {
  const BASIS_PROPS = {
    gericht: { name: "Amtsgericht Offenbach" },
    beklagte: [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }],
    positionen: [{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betrag: 1000, checked: true }],
    mitSG: false, sgMind: 0,
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe",
    zinsenAb: "verzug", wizardVerzugDatum: null,
    laedt: false, onGenerieren: vi.fn(), fehler: null,
    lgGrenzwert: 0, swAusserg: 0,
    antraegeText: "1. Text ohne Platzhalter.",
    unfallort: "Offenbach", unfalldatum: "12.05.2026",
  };

  it("nicht-numerisches rvgAussergOv zeigt kein NaN und faellt auf rvgAussergData.gesamt zurueck", () => {
    render(<StepZusammenfassung {...BASIS_PROPS}
      rvgAussergOv="abc"
      rvgAussergData={{ gesamt: 250 }} />);

    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
    expect(screen.getByText(/250,00/)).toBeInTheDocument();
  });
});

describe("StepGebuehren – KW-40 NaN-Guard RVG-Override (Versand/gebuehrenText)", () => {
  it("nicht-numerisches rvgAussergOv erzeugt keinen 'NaN'-Text in gebuehrenText", () => {
    const onGebuehrenText = vi.fn();
    render(<StepGebuehren
      swAusserg={10000}
      rvgAussergData={{ gesamt: 250, faktor: 1.3, gebuehr_netto: 200, post_pauschale: 20, zwischen_netto: 220, ust: 30, rvg_version: "2025" }}
      onRvgAussergData={vi.fn()}
      rvgAussergOv="abc"
      onRvgAussergOv={vi.fn()}
      rvgBereitsGezahlt=""
      onRvgBereitsGezahlt={vi.fn()}
      gebuehrenText=""
      onGebuehrenText={onGebuehrenText}
      gebuehrenManuell={false}
      onGebuehrenManuell={vi.fn()}
      beklagte={[]}
      weiblich={false}
      zinsenAb="rechtshaengigkeit"
      verzug=""
      antraegeText=""
      onAntraegeText={vi.fn()}
      gespeichertGb={null}
      onGespeichertGb={vi.fn()}
      akteId="1/26"
    />);

    expect(onGebuehrenText).toHaveBeenCalled();
    const text = onGebuehrenText.mock.calls.at(-1)[0];
    expect(text).not.toMatch(/NaN/);
    expect(text).toContain("250,00");
  });
});

// ── KW-40 Punkt 6 (KW-30-FE): Step-10-Warnung Unfallort/-datum ─────────────────

describe("StepZusammenfassung – KW-30-FE Warnung bei fehlendem Unfallort/-datum", () => {
  const BASIS_PROPS = {
    gericht: { name: "Amtsgericht Offenbach" },
    beklagte: [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }],
    positionen: [{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betrag: 1000, checked: true }],
    mitSG: false, sgMind: 0,
    rvgAussergData: null, rvgAussergOv: null,
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe",
    zinsenAb: "verzug", wizardVerzugDatum: null,
    laedt: false, onGenerieren: vi.fn(), fehler: null,
    lgGrenzwert: 0, swAusserg: 0,
    antraegeText: "1. Text ohne Platzhalter.",
  };

  it("warnt bei fehlendem Unfallort, sperrt den Generieren-Button aber nicht", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} unfallort="" unfalldatum="12.05.2026" />);
    expect(screen.getByText(/Kein Unfallort/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Als Word generieren/i })).not.toBeDisabled();
  });

  it("warnt bei fehlendem Unfalldatum, sperrt den Generieren-Button aber nicht", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} unfallort="Offenbach" unfalldatum="" />);
    expect(screen.getByText(/Kein Unfalldatum/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Als Word generieren/i })).not.toBeDisabled();
  });

  it("keine Warnung, wenn Unfallort und -datum vorhanden sind", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} unfallort="Offenbach" unfalldatum="12.05.2026" />);
    expect(screen.queryByText(/Kein Unfallort/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Kein Unfalldatum/i)).not.toBeInTheDocument();
  });
});
