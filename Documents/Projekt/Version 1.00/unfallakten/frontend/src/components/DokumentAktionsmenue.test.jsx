import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DokumentAktionsmenue from './DokumentAktionsmenue.jsx';

const antwort = {
  akte_az: '285/26',
  dokument_id: 22,
  registry_version: 'abc',
  aktionen: [
    {
      aktion: 'stellungnahme.generieren',
      label: 'Stellungnahme zu diesem Abrechnungsschreiben',
      positions_scope: false,
      vorbedingung: 'Position gekuerzt',
      trigger_typ: 'abrechnung_eingegangen',
    },
    {
      aktion: 'beleg.zuordnen',
      label: 'Beleg zuordnen',
      positions_scope: true,
      vorbedingung: null,
      trigger_typ: 'rechnung_eingegangen',
    },
  ],
};

describe('DokumentAktionsmenue', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200, json: () => Promise.resolve(antwort),
    }));
  });
  afterEach(() => vi.restoreAllMocks());

  it('rendert Kebab-Button initial, kein Menü', () => {
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} />);
    expect(screen.getByLabelText(/aktionen/i)).toBeInTheDocument();
    expect(screen.queryByText(/stellungnahme/i)).not.toBeInTheDocument();
  });

  it('öffnet Menü und lädt Aktionen beim Klick auf Kebab', async () => {
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} />);
    fireEvent.click(screen.getByLabelText(/aktionen/i));
    expect(await screen.findByText(/stellungnahme zu diesem/i)).toBeInTheDocument();
    expect(screen.getByText(/beleg zuordnen/i)).toBeInTheDocument();
  });

  it('fetched den korrekten Endpoint mit dokument_id', async () => {
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} />);
    fireEvent.click(screen.getByLabelText(/aktionen/i));
    await screen.findByText(/stellungnahme/i);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/akten\/285(%2F|\/)26\/aktionen\?dokument_id=22$/),
      expect.any(Object),
    );
  });

  it('meldet Klick auf Aktion via onAktion mit trigger_typ', async () => {
    const onAktion = vi.fn();
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} onAktion={onAktion} />);
    fireEvent.click(screen.getByLabelText(/aktionen/i));
    const btn = await screen.findByText(/stellungnahme zu diesem/i);
    fireEvent.click(btn);
    expect(onAktion).toHaveBeenCalledWith(expect.objectContaining({
      aktion: 'stellungnahme.generieren',
      trigger_typ: 'abrechnung_eingegangen',
    }));
  });

  it('zeigt Leer-Zustand wenn keine Aktionen vorgeschlagen werden', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({ akte_az: '285/26', dokument_id: 22, aktionen: [] }),
    }));
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} />);
    fireEvent.click(screen.getByLabelText(/aktionen/i));
    await waitFor(() => {
      expect(screen.getByText(/keine vorschläge/i)).toBeInTheDocument();
    });
  });

  it('schließt Menü nach Klick auf Aktion', async () => {
    render(<DokumentAktionsmenue az="285/26" dokumentId={22} onAktion={() => {}} />);
    fireEvent.click(screen.getByLabelText(/aktionen/i));
    const btn = await screen.findByText(/stellungnahme zu diesem/i);
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.queryByText(/stellungnahme zu diesem/i)).not.toBeInTheDocument();
    });
  });
});
