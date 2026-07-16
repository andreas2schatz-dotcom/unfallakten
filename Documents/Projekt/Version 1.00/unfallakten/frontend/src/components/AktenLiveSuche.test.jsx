import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AktenLiveSuche from './AktenLiveSuche.jsx';

// az = Anzeigeform mit SB-Kuerzel (RA-MICRO), az_roh = Basis-AZ (sAktenNummer).
// Ausgewaehlt werden muss der Basis-AZ, sonst entstehen Phantom-Akten.
const antwort = {
  treffer: [
    { az: '31/21AS', az_roh: '31/21', mandant: 'Riccio, Marco', kurzbezeichnung: 'Riccio ./. HUK', kennzeichen: 'OF-MU 1234' },
    { az: '31/22AS', az_roh: '31/22', mandant: 'Ricciotti, Anna', kurzbezeichnung: 'Ricciotti ./. Allianz', kennzeichen: null },
  ],
  anzahl: 2, suchmodus: 'name', ramicro_aktiv: true,
};

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

describe('AktenLiveSuche', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200, json: () => Promise.resolve(antwort),
    }));
  });
  afterEach(() => vi.restoreAllMocks());

  it('rendert Suchfeld, keine Anfrage bei leerem Feld', () => {
    render(<AktenLiveSuche onWaehle={() => {}} />);
    expect(screen.getByPlaceholderText(/mandant|akte|suchen/i)).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('debounced: fetch erst nach ca. 300ms nach Tippen', async () => {
    render(<AktenLiveSuche onWaehle={() => {}} />);
    const input = screen.getByPlaceholderText(/mandant|akte|suchen/i);
    fireEvent.change(input, { target: { value: 'Riccio' } });
    // vor Debounce: kein Call
    await sleep(50);
    expect(globalThis.fetch).not.toHaveBeenCalled();
    // nach Debounce: genau ein Call mit dem query
    await sleep(350);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/aktensuche?az=Riccio'),
      expect.any(Object),
    );
  });

  it('fetch nicht bei query < 2 Zeichen', async () => {
    render(<AktenLiveSuche onWaehle={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/mandant|akte|suchen/i), { target: { value: 'R' } });
    await sleep(500);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('zeigt Trefferliste nach erfolgreicher Suche', async () => {
    render(<AktenLiveSuche onWaehle={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/mandant|akte|suchen/i), { target: { value: 'Riccio' } });
    await waitFor(() => {
      expect(screen.getByText(/Riccio, Marco/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Ricciotti, Anna/)).toBeInTheDocument();
  });

  it('Klick auf Treffer ruft onWaehle mit Basis-AZ (az_roh) auf', async () => {
    const onWaehle = vi.fn();
    render(<AktenLiveSuche onWaehle={onWaehle} />);
    fireEvent.change(screen.getByPlaceholderText(/mandant|akte|suchen/i), { target: { value: 'Riccio' } });
    const treffer = await screen.findByText(/Riccio, Marco/);
    fireEvent.click(treffer.closest('[data-treffer]'));
    expect(onWaehle).toHaveBeenCalledWith('31/21');
  });

  it('leere Trefferliste → Hinweis-Meldung', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({ treffer: [], anzahl: 0, suchmodus: 'name', ramicro_aktiv: true }),
    }));
    render(<AktenLiveSuche onWaehle={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/mandant|akte|suchen/i), { target: { value: 'Nirgendwo' } });
    await waitFor(() => {
      expect(screen.getByText(/keine treffer/i)).toBeInTheDocument();
    });
  });
});
