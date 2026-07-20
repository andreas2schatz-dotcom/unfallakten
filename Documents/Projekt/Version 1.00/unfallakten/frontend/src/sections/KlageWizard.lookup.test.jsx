import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SchliessenGuardDialog, StepRubrum, StepZusammenfassung } from "./KlageWizard.jsx";

// ── Bug 1: Schließen-Dialog bietet klar Verwerfen vs. Speichern ──────────────
describe("SchliessenGuardDialog", () => {
  it("zeigt drei klar benannte Wege", () => {
    render(<SchliessenGuardDialog onEntwurfSpeichern={vi.fn()} onClose={vi.fn()} onZurueck={vi.fn()} />);
    expect(screen.getByText(/Wizard schließen\?/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Zurück zum Wizard/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Verwerfen & schließen/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Speichern & schließen/ })).toBeInTheDocument();
  });

  it("Verwerfen & schließen schließt ohne zu speichern", () => {
    const onClose = vi.fn(), onEntwurfSpeichern = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern} onClose={onClose} onZurueck={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Verwerfen & schließen/ }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onEntwurfSpeichern).not.toHaveBeenCalled();
  });

  it("Speichern & schließen speichert erst, schließt nur bei Erfolg", async () => {
    const onClose = vi.fn(), onZurueck = vi.fn();
    const onEntwurfSpeichern = vi.fn().mockResolvedValue(true);
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern} onClose={onClose} onZurueck={onZurueck} />);
    fireEvent.click(screen.getByRole("button", { name: /Speichern & schließen/ }));
    await vi.waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onEntwurfSpeichern).toHaveBeenCalledTimes(1);
    expect(onZurueck).not.toHaveBeenCalled();
  });
});

// ── Feature 3: Vertreter-Lookup direkt im Wizard (Schritt 2) ─────────────────
describe("StepRubrum – In-Wizard-Vertreter-Lookup", () => {
  const KLAEGER = { id: 1, rolle_klage: "klaeger", name: "Mustermann", checked: true };
  const FIRMA_OHNE = { id: 7, rolle_klage: "beklagter", versicherung: "Test-Versicherung AG", checked: true };

  it("Firma ohne Vertreter: Lookup-Knopf ruft onVertreterLookup mit (id, name), schließt NICHT", () => {
    const onVertreterLookup = vi.fn(), onClose = vi.fn();
    render(<StepRubrum beklagte={[KLAEGER, FIRMA_OHNE]} onClose={onClose}
      onVertreterLookup={onVertreterLookup} vertreterLookup={{}} />);
    const btn = screen.getByRole("button", { name: /Lookup/ });
    fireEvent.click(btn);
    expect(onVertreterLookup).toHaveBeenCalledWith(7, "Test-Versicherung AG");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("laufender Lookup deaktiviert den Knopf", () => {
    render(<StepRubrum beklagte={[KLAEGER, FIRMA_OHNE]} onClose={vi.fn()}
      onVertreterLookup={vi.fn()} vertreterLookup={{ 7: { laden: true } }} />);
    expect(screen.getByRole("button", { name: /sucht/ })).toBeDisabled();
  });

  it("mit bestätigtem Vertreter erscheint keine Warnung", () => {
    const firmaMit = { ...FIRMA_OHNE, vertreter_name: "Stefan Daehne", vertreter_funktion: "Vorstand" };
    render(<StepRubrum beklagte={[KLAEGER, firmaMit]} onClose={vi.fn()}
      onVertreterLookup={vi.fn()} vertreterLookup={{}} />);
    expect(screen.queryByText(/Vertreter fehlt/)).toBeNull();
  });
});

// ── Feature 3: Lookup auch an der Schritt-11-Warnung ─────────────────────────
describe("StepZusammenfassung – Lookup an der Vertreter-Warnung", () => {
  const BASIS = {
    gericht: { name: "Amtsgericht Offenbach" },
    positionen: [{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betrag: 1000, checked: true }],
    mitSG: false, sgMind: 0, rvgAussergData: null, rvgAussergOv: null,
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", zinsenAb: "verzug",
    wizardVerzugDatum: null, laedt: false, onGenerieren: vi.fn(), fehler: null,
    lgGrenzwert: 0, swAusserg: 0,
    antraegeText: "1. Die Beklagte wird verurteilt, an den Kläger 1.000,00 € zu zahlen.",
  };

  it("Firma ohne Vertreter zeigt Lookup-Knopf, ruft onVertreterLookup", () => {
    const onVertreterLookup = vi.fn();
    render(<StepZusammenfassung {...BASIS}
      beklagte={[{ id: 9, rolle_klage: "beklagter", versicherung: "HUK AG", checked: true }]}
      onVertreterLookup={onVertreterLookup} vertreterLookup={{}} />);
    expect(screen.getByText(/Firmen ohne Vertreter/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Lookup/ }));
    expect(onVertreterLookup).toHaveBeenCalledWith(9, "HUK AG");
  });
});
