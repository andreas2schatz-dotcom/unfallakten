import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PositionsDashboard from './PositionsDashboard.jsx';

const antwort = {
  akte_az: '285/26',
  registry_version: 'abc123',
  positionen: {
    reparaturkosten: {
      zustand: 'bestritten',
      gefordert: 6200.0,
      anerkannt: 4100.0,
      gekuerzt: 2100.0,
      abgelehnt: 0.0,
      offen: 2100.0,
      quote: 1.0,
      stand: '2026-06-30',
      eskalationsstufe: 2,
      checkliste: { erledigt: ['gutachten_eingegangen', 'forderung_generiert'], offen: ['fristsetzung_generiert'] },
      has_unbestaetigt: false,
      label: 'Reparaturkosten',
      kategorie: 'fahrzeugschaden',
      aggregation: 'fahrzeugschaden',
    },
    sonstiges: {
      zustand: 'anerkannt',
      gefordert: 65.0,
      anerkannt: 65.0,
      gekuerzt: 0.0,
      abgelehnt: 0.0,
      offen: 0.0,
      quote: 1.0,
      stand: '2026-06-30',
      eskalationsstufe: 1,
      checkliste: { erledigt: [], offen: [] },
      has_unbestaetigt: true,
      label: 'Sonstiger Schaden',
      kategorie: 'sonstiges',
      aggregation: 'nebenkosten',
    },
  },
};

describe('PositionsDashboard', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(antwort),
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('rendert je Position eine Zeile mit Zustand, Betraegen und Checkliste', async () => {
    render(<PositionsDashboard az="285/26" />);

    expect(await screen.findByText('Reparaturkosten')).toBeInTheDocument();
    expect(screen.getByText('Sonstiger Schaden')).toBeInTheDocument();

    const rep = screen.getByTestId('positionszeile-reparaturkosten');
    expect(rep).toHaveTextContent('bestritten');
    expect(rep).toHaveTextContent('6.200,00');
    expect(rep).toHaveTextContent('4.100,00');
    expect(rep).toHaveTextContent('2.100,00');
    expect(rep).toHaveTextContent(/2\s*\/\s*3/);
  });

  it('kennzeichnet has_unbestaetigt-Positionen sichtbar (WDM-Vorschlag)', async () => {
    render(<PositionsDashboard az="285/26" />);
    const sonst = await screen.findByTestId('positionszeile-sonstiges');
    expect(sonst).toHaveTextContent(/wdm|unbestätigt/i);
  });

  it('Toggle wechselt zwischen getrennt und aggregiert', async () => {
    render(<PositionsDashboard az="285/26" />);

    await screen.findByTestId('positionszeile-reparaturkosten');
    expect(screen.getByTestId('toggle-getrennt')).toHaveAttribute('data-active', 'true');

    fireEvent.click(screen.getByTestId('toggle-aggregiert'));

    await waitFor(() => {
      expect(screen.getByTestId('toggle-aggregiert')).toHaveAttribute('data-active', 'true');
    });
    expect(screen.getByTestId('aggregationszeile-fahrzeugschaden')).toBeInTheDocument();
    expect(screen.getByTestId('aggregationszeile-nebenkosten')).toBeInTheDocument();
  });

  it('rendert AbleitungBadge mit stand-Datum als Footer', async () => {
    const { container } = render(<PositionsDashboard az="285/26" />);
    await screen.findByTestId('positionszeile-reparaturkosten');
    expect(container.textContent).toMatch(/nach Aktenlage.*30\.06\.2026/);
  });

  it('ruft Klick-Callback mit position_key beim Klick auf Zeile auf', async () => {
    const onOeffneEreignisse = vi.fn();
    render(<PositionsDashboard az="285/26" onOeffneEreignisse={onOeffneEreignisse} />);
    const rep = await screen.findByTestId('positionszeile-reparaturkosten');
    fireEvent.click(rep);
    expect(onOeffneEreignisse).toHaveBeenCalledWith('reparaturkosten');
  });

  it('fetched vom richtigen Endpoint (AZ url-encoded)', async () => {
    render(<PositionsDashboard az="285/26" />);
    await screen.findByTestId('positionszeile-reparaturkosten');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/akten\/285(%2F|\/)26\/positionen\/status$/),
      expect.any(Object),
    );
  });

  it('rendert Ladezustand vor Daten', () => {
    render(<PositionsDashboard az="285/26" />);
    expect(screen.getByText(/wird geladen|lädt|lade/i)).toBeInTheDocument();
  });
});
