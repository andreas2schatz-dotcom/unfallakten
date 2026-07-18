import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { antraegeBasis, AntraegeSync, TextVeraltetBadge, baueAntraegeText, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

const basisOpts = {
  positionen: [{ key: "a", betrag: 100, checked: true }], mitSG: false, sgMind: null,
  beklagte: [{ id: 1, checked: true, rolle_klage: "beklagter" }], weiblich: true,
  zinsenAb: "verzug", verzug: "2026-01-01", unfalldatum: "2026-01-01",
  mitFestSg: false, mitFestSach: false, hq: 100, hqTyp: "gegnerisch",
};

describe("antraegeBasis", () => {
  it("Positions-Abwahl aendert die Basis", () => {
    const b1 = antraegeBasis(basisOpts);
    const b2 = antraegeBasis({ ...basisOpts, positionen: [{ key: "a", betrag: 100, checked: false }] });
    expect(b1).not.toBe(b2);
  });
  it("Feststellungs-Checkbox aendert die Basis", () => {
    expect(antraegeBasis(basisOpts)).not.toBe(antraegeBasis({ ...basisOpts, mitFestSach: true }));
  });
  it("identische Eingaben, identische Basis", () => {
    expect(antraegeBasis(basisOpts)).toBe(antraegeBasis({ ...basisOpts }));
  });
});

function AntraegeSyncWrapper({ step, opts }) {
  const [antraegeText, setAntraegeText] = useState("");
  const [manuell, setManuell]           = useState(false);
  const [basisStand, setBasisStand]     = useState(null);
  return (
    <div>
      <AntraegeSync
        step={step}
        opts={opts}
        antraegeText={antraegeText}
        manuell={manuell}
        basisStand={basisStand}
        onAntraegeText={setAntraegeText}
        onAntraegeBasis={setBasisStand}
      />
      <div data-testid="text">{antraegeText}</div>
      <div data-testid="basis">{basisStand}</div>
      <button onClick={() => setManuell(true)}>manuell setzen</button>
    </div>
  );
}

describe("AntraegeSync", () => {
  it("regeneriert bei Basis-Aenderung, wenn nicht manuell", () => {
    const { rerender } = render(<AntraegeSyncWrapper step={6} opts={basisOpts} />);
    const text1 = screen.getByTestId("text").textContent;
    expect(text1).toContain(ANTRAEGE_PLACEHOLDER.slice(0, 10));

    const geaendert = { ...basisOpts, mitFestSach: true };
    rerender(<AntraegeSyncWrapper step={6} opts={geaendert} />);
    const text2 = screen.getByTestId("text").textContent;
    expect(text2).not.toBe(text1);
    expect(screen.getByTestId("basis").textContent).toBe(antraegeBasis(geaendert));
  });

  it("ueberschreibt manuell bearbeiteten Text NICHT", () => {
    const { rerender } = render(<AntraegeSyncWrapper step={6} opts={basisOpts} />);
    fireEvent.click(screen.getByText("manuell setzen"));
    const textVorAenderung = screen.getByTestId("text").textContent;

    const geaendert = { ...basisOpts, mitFestSach: true };
    rerender(<AntraegeSyncWrapper step={6} opts={geaendert} />);
    expect(screen.getByTestId("text").textContent).toBe(textVorAenderung);
  });

  it("generiert initial ab Step 6, nicht davor", () => {
    const { rerender } = render(<AntraegeSyncWrapper step={5} opts={basisOpts} />);
    expect(screen.getByTestId("text").textContent).toBe("");

    rerender(<AntraegeSyncWrapper step={6} opts={basisOpts} />);
    expect(screen.getByTestId("text").textContent).not.toBe("");
  });
});

describe("TextVeraltetBadge", () => {
  it("sichtbar=false rendert nichts", () => {
    const { container } = render(
      <TextVeraltetBadge sichtbar={false} onNeuGenerieren={() => {}} onBehalten={() => {}} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("Knoepfe feuern die Callbacks", () => {
    const onNeuGenerieren = vi.fn();
    const onBehalten      = vi.fn();
    render(<TextVeraltetBadge sichtbar={true} onNeuGenerieren={onNeuGenerieren} onBehalten={onBehalten} />);

    expect(screen.getByText(/Text veraltet/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Neu generieren/i));
    expect(onNeuGenerieren).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByText(/Behalten/i));
    expect(onBehalten).toHaveBeenCalledTimes(1);
  });
});
