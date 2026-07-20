import { useState } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { apiGebuehren } from "../api.js";
import { StepGebuehren, StepAntraege, komponiereAntraege, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

vi.mock("../api.js", () => ({
  apiGebuehren: {
    analysieren: vi.fn(),
    speichern: vi.fn(),
  },
}));

const ANTRAEGE_MIT_PLATZHALTER =
  "1. Die Beklagte wird verurteilt, an den Kläger 1.000,00 € zu zahlen.\n\n" +
  "2. [Außergerichtliche Anwaltsgebühren – wird in Schritt 10 ergänzt]";

const BEKLAGTE_EINZEL = [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }];

function Wrapper({ spies = {}, beklagte = BEKLAGTE_EINZEL }) {
  const [rvgAussergData, setRvgAussergData] = useState(null);
  const [rvgAussergOv, setRvgAussergOv] = useState("");
  const [rvgBereitsGezahlt, setRvgBereitsGezahlt] = useState("");
  const [gebuehrenText, setGebuehrenText] = useState("");
  const [antraegeText, setAntraegeText] = useState(ANTRAEGE_MIT_PLATZHALTER);
  const [gespeichertGb, setGespeichertGb] = useState(null);

  return (
    <StepGebuehren
      akteId="44/22"
      swAusserg={10000}
      rvgAussergData={rvgAussergData}
      onRvgAussergData={(d) => { spies.onRvgAussergData?.(d); setRvgAussergData(d); }}
      rvgAussergOv={rvgAussergOv}
      onRvgAussergOv={(v) => { spies.onRvgAussergOv?.(v); setRvgAussergOv(v); }}
      rvgBereitsGezahlt={rvgBereitsGezahlt}
      onRvgBereitsGezahlt={(v) => setRvgBereitsGezahlt(v)}
      gebuehrenText={gebuehrenText}
      onGebuehrenText={(t) => { spies.onGebuehrenText?.(t); setGebuehrenText(t); }}
      beklagte={beklagte}
      weiblich={false}
      zinsenAb="rechtshaengigkeit"
      verzug=""
      antraegeText={antraegeText}
      onAntraegeText={setAntraegeText}
      gespeichertGb={gespeichertGb}
      onGespeichertGb={(g) => { spies.onGespeichertGb?.(g); setGespeichertGb(g); }}
    />
  );
}

const ANALYSE_RESPONSE = {
  vorschlag: { faktor: 1.5, vuregel_id: "VU-3", begruendung: "x", leitentscheidung: "y" },
  rvg: {
    gesamt: 1295.43, faktor: 1.5, gebuehr_netto: 1000,
    post_pauschale: 20, zwischen_netto: 1020, ust: 193.8, rvg_version: "2025",
  },
};

describe("StepGebuehren – KW-02 RVG-Faktor nicht ins Euro-Override-Feld", () => {
  beforeEach(() => {
    apiGebuehren.analysieren.mockReset();
    apiGebuehren.speichern.mockReset();
    apiGebuehren.analysieren.mockResolvedValue(ANALYSE_RESPONSE);
    apiGebuehren.speichern.mockResolvedValue({});
  });

  it("Analyse schreibt den Faktor NICHT ins Euro-Override-Feld", async () => {
    const spies = { onRvgAussergData: vi.fn(), onRvgAussergOv: vi.fn() };
    render(<Wrapper spies={spies} />);

    fireEvent.click(screen.getByText(/Kein Personenschaden/i));
    fireEvent.click(screen.getByRole("button", { name: /Analysieren/i }));

    await waitFor(() => expect(spies.onRvgAussergData).toHaveBeenCalled());

    expect(spies.onRvgAussergOv).not.toHaveBeenCalled();
    const [data] = spies.onRvgAussergData.mock.calls[0];
    expect(data.faktor).toBe(1.5);
  });

  it("Speichern übernimmt den Faktor aus der Analyse, nicht den Euro-Override-Betrag", async () => {
    render(<Wrapper />);

    fireEvent.click(screen.getByText(/Kein Personenschaden/i));
    fireEvent.click(screen.getByRole("button", { name: /Analysieren/i }));

    await screen.findByRole("button", { name: /Speichern/i });

    const overrideInput = screen.getAllByRole("spinbutton")[0];
    fireEvent.change(overrideInput, { target: { value: "1295.43" } });

    fireEvent.click(screen.getByRole("button", { name: /Speichern/i }));

    await waitFor(() => expect(apiGebuehren.speichern).toHaveBeenCalled());

    expect(apiGebuehren.speichern).toHaveBeenCalledWith(
      "44/22",
      expect.objectContaining({ faktor_final: 1.5 }),
    );
  });

  it("Regression: Euro-Override-Eingabe aktualisiert weiterhin den Gebühren-Antragstext", () => {
    const spies = { onGebuehrenText: vi.fn() };
    render(<Wrapper spies={spies} />);

    const overrideInput = screen.getAllByRole("spinbutton")[0];
    fireEvent.change(overrideInput, { target: { value: "500" } });

    expect(spies.onGebuehrenText).toHaveBeenCalled();
    const letzterText = spies.onGebuehrenText.mock.calls.at(-1)[0];
    expect(letzterText).toContain("500,00 €");
  });
});

describe("StepGebuehren – KW-06 Gesamtschuldner-Grammatik", () => {
  it("2 Beklagte -> Gebühren-Antragstext nutzt Gesamtschuldner-Formel", () => {
    const spies = { onGebuehrenText: vi.fn() };
    const beklagte = [
      { id: 1, name: "Muster", rolle_klage: "beklagter", checked: true },
      { id: 2, versicherung: "Test-Versicherung AG", rolle_klage: "beklagter", checked: true },
    ];
    render(<Wrapper spies={spies} beklagte={beklagte} />);

    const overrideInput = screen.getAllByRole("spinbutton")[0];
    fireEvent.change(overrideInput, { target: { value: "500" } });

    expect(spies.onGebuehrenText).toHaveBeenCalled();
    const letzterText = spies.onGebuehrenText.mock.calls.at(-1)[0];
    expect(letzterText).toContain("Die Beklagten werden als Gesamtschuldner verurteilt");
    expect(letzterText).not.toContain("(zu 1)");
  });
});

describe("komponiereAntraege", () => {
  it("ersetzt den Platzhalter durch den Gebuehren-Text", () => {
    const a = `1. Antrag X\n2. ${ANTRAEGE_PLACEHOLDER}\n3. Kosten`;
    expect(komponiereAntraege(a, "GEBUEHREN-SATZ")).toBe("1. Antrag X\n2. GEBUEHREN-SATZ\n3. Kosten");
  });
  it("ohne Gebuehren-Text bleibt der Platzhalter stehen", () => {
    const a = `Antrag ${ANTRAEGE_PLACEHOLDER}`;
    expect(komponiereAntraege(a, "")).toBe(a);
    expect(komponiereAntraege(a, null)).toBe(a);
  });
  it("ohne Platzhalter bleibt der Text unveraendert", () => {
    expect(komponiereAntraege("fertiger Text", "GEB")).toBe("fertiger Text");
  });
  it("leerer Antraege-Text bleibt leer", () => {
    expect(komponiereAntraege("", "GEB")).toBe("");
  });
});

function WrapperSegment({ gemountet = true, antraegeTextInitial = "", rvgAussergOvInitial = "500" }) {
  const [gebuehrenText, setGebuehrenText] = useState("");
  const [gebuehrenManuell, setGebuehrenManuell] = useState(false);
  const [antraegeText, setAntraegeText] = useState(antraegeTextInitial);
  const [rvgAussergOv, setRvgAussergOv] = useState(rvgAussergOvInitial);
  const [rvgBereitsGezahlt, setRvgBereitsGezahlt] = useState("");

  return gemountet ? (
    <>
      <StepGebuehren
        akteId="44/22"
        swAusserg={10000}
        rvgAussergData={null}
        onRvgAussergData={() => {}}
        rvgAussergOv={rvgAussergOv}
        onRvgAussergOv={setRvgAussergOv}
        rvgBereitsGezahlt={rvgBereitsGezahlt}
        onRvgBereitsGezahlt={setRvgBereitsGezahlt}
        gebuehrenText={gebuehrenText}
        onGebuehrenText={setGebuehrenText}
        beklagte={BEKLAGTE_EINZEL}
        weiblich={false}
        zinsenAb="rechtshaengigkeit"
        verzug=""
        antraegeText={antraegeText}
        onAntraegeText={setAntraegeText}
        gespeichertGb={null}
        onGespeichertGb={() => {}}
        gebuehrenManuell={gebuehrenManuell}
        onGebuehrenManuell={setGebuehrenManuell}
      />
      <div data-testid="antraege-preview">{antraegeText}</div>
    </>
  ) : <div data-testid="leer" />;
}

describe("StepGebuehren – KW-24 Segment-Komposition", () => {
  it("bereitsGezahlt-Aenderung regeneriert den Gebuehren-Text", () => {
    render(<WrapperSegment />);

    const bereitsGezahltInput = screen.getAllByRole("spinbutton")[1];
    fireEvent.change(bereitsGezahltInput, { target: { value: "100" } });

    expect(screen.getByRole("textbox").value).toContain("400,00 €");
  });

  it("manueller Edit wird beim Remount NICHT ueberschrieben", () => {
    const { rerender } = render(<WrapperSegment gemountet={true} />);

    expect(screen.getByRole("textbox").value).not.toBe("");

    fireEvent.change(screen.getByRole("textbox"), { target: { value: "MANUELL TEXT" } });
    expect(screen.getByRole("textbox").value).toBe("MANUELL TEXT");

    rerender(<WrapperSegment gemountet={false} />);
    expect(screen.getByTestId("leer")).toBeTruthy();

    rerender(<WrapperSegment gemountet={true} />);
    expect(screen.getByRole("textbox").value).toBe("MANUELL TEXT");
  });

  it("antraegeText behaelt den Platzhalter — keine Einbrennung", () => {
    const antraegeInitial = `1. Antrag X\n2. ${ANTRAEGE_PLACEHOLDER}`;
    render(<WrapperSegment antraegeTextInitial={antraegeInitial} />);

    expect(screen.getByRole("textbox").value).not.toBe("");
    expect(screen.getByTestId("antraege-preview").textContent).toContain(ANTRAEGE_PLACEHOLDER);
  });
});

const POSITIONEN_STEP6 = [
  { key: "fahrzeugschaden", label: "Fahrzeugschaden", betrag: 1000, checked: true },
];

function renderStepAntraege(extraProps = {}) {
  return render(
    <StepAntraege
      positionen={POSITIONEN_STEP6} mitSG={false} sgMind={0}
      beklagte={BEKLAGTE_EINZEL} weiblich={false}
      zinsenAb="rechtshaengigkeit" verzug=""
      unfalldatum=""
      mitFestSg={false} onMitFestSg={() => {}}
      mitFestSach={false} onMitFestSach={() => {}}
      antraegeText={ANTRAEGE_MIT_PLATZHALTER} onAntraegeText={() => {}}
      hq={100} hqTyp="gegnerisch"
      {...extraProps}
    />
  );
}

describe("StepAntraege – KW-24 Folgefix: Status-Banner nutzt komponierten Text", () => {
  it("Platzhalter + vorhandener Gebuehren-Text -> kein Warnbanner, gruener Status", () => {
    renderStepAntraege({ gebuehrenText: "GEB" });

    expect(screen.queryByText(/Platzhalter aktiv/i)).not.toBeInTheDocument();
    expect(screen.getByText(/RVG-Antrag eingefügt/i)).toBeInTheDocument();
  });

  it("Platzhalter ohne Gebuehren-Text -> Warnbanner bleibt", () => {
    renderStepAntraege({ gebuehrenText: null });

    expect(screen.getByText(/Platzhalter aktiv/i)).toBeInTheDocument();
  });
});
