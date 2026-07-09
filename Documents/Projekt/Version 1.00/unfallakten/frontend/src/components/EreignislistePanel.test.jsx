import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EreignislistePanel from './EreignislistePanel.jsx';

const antwort = {
  akte_az: '285/26',
  position_key: 'reparaturkosten',
  ereignisse: [
    {
      ereignis_id: 1,
      ereignistyp: 'forderung_generiert',
      richtung: 'ausgehend',
      datum: '2026-04-20',
      dokument_id: 100,
      wirkung: 'gefordert',
      betrag: 6200.0,
      status: 'aktuell',
      herkunft: null,
      notiz: null,
    },
    {
      ereignis_id: 2,
      ereignistyp: 'abrechnung_eingegangen',
      richtung: 'eingehend',
      datum: '2026-05-14',
      dokument_id: null,
      wirkung: 'anerkannt',
      betrag: 3900.0,
      status: 'ersetzt',
      herkunft: 'wdm',
      notiz: null,
    },
    {
      ereignis_id: 3,
      ereignistyp: 'abrechnung_eingegangen',
      richtung: 'eingehend',
      datum: '2026-05-14',
      dokument_id: 101,
      wirkung: 'anerkannt',
      betrag: 4100.0,
      status: 'aktuell',
      herkunft: 'review_freigabe',
      notiz: null,
    },
  ],
};

describe('EreignislistePanel', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve(antwort),
    }));
  });

  afterEach(() => vi.restoreAllMocks());

  it('rendert nichts wenn positionKey null ist', () => {
    const { container } = render(
      <EreignislistePanel az="285/26" positionKey={null} onClose={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('rendert Kopfzeile mit position_key beim Öffnen', async () => {
    render(<EreignislistePanel az="285/26" positionKey="reparaturkosten" onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/reparaturkosten/i)).toBeInTheDocument();
    });
  });

  it('listet Ereignisse chronologisch mit Typ, Datum, Betrag', async () => {
    render(<EreignislistePanel az="285/26" positionKey="reparaturkosten" onClose={() => {}} />);

    await screen.findByText(/forderung_generiert/i);
    expect(screen.getAllByText(/abrechnung_eingegangen/i).length).toBe(2);
    expect(screen.getByText(/20\.04\.2026/)).toBeInTheDocument();
    expect(screen.getAllByText(/14\.05\.2026/).length).toBeGreaterThanOrEqual(1);
  });

  it('markiert ersetzte Ereignisse sichtbar (durchgestrichen + Tag)', async () => {
    render(<EreignislistePanel az="285/26" positionKey="reparaturkosten" onClose={() => {}} />);

    await screen.findByText(/forderung_generiert/i);
    const ersetztRow = screen.getByTestId('ereignis-2');
    expect(ersetztRow).toHaveTextContent(/ersetzt/i);
  });

  it('zeigt Herkunft "wdm" als Badge', async () => {
    render(<EreignislistePanel az="285/26" positionKey="reparaturkosten" onClose={() => {}} />);
    await screen.findByText(/forderung_generiert/i);
    const row = screen.getByTestId('ereignis-2');
    expect(row).toHaveTextContent(/wdm/i);
  });

  it('ruft onClose beim Klick auf Schließen-Button', async () => {
    const onClose = vi.fn();
    render(<EreignislistePanel az="285/26" positionKey="reparaturkosten" onClose={onClose} />);
    await screen.findByText(/forderung_generiert/i);
    fireEvent.click(screen.getByLabelText(/schließen/i));
    expect(onClose).toHaveBeenCalled();
  });

  it('rendert Meldung bei leerer Ereignisliste', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({
        akte_az: '285/26', position_key: 'x', ereignisse: [],
      }),
    }));
    render(<EreignislistePanel az="285/26" positionKey="x" onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/keine ereignisse/i)).toBeInTheDocument();
    });
  });
});
