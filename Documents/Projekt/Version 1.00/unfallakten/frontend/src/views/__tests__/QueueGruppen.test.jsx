import { describe, test, expect } from 'vitest';
import { gruppiereQueue } from '../ReviewQueueView.jsx';

describe('gruppiereQueue', () => {
  test('Anhang wird unter seine E-Mail gruppiert', () => {
    const eintraege = [
      { id: 1, zustellung_id: 10, parent_zustellung_id: null, payload_typ: 'text' },
      { id: 2, zustellung_id: 11, parent_zustellung_id: 10, payload_typ: 'datei' },
      { id: 3, zustellung_id: 12, parent_zustellung_id: null, payload_typ: 'datei' },
    ];
    const gruppen = gruppiereQueue(eintraege);
    expect(gruppen).toHaveLength(2);
    expect(gruppen[0].eintrag.id).toBe(1);
    expect(gruppen[0].kinder.map(k => k.id)).toEqual([2]);
    expect(gruppen[1].eintrag.id).toBe(3);
    expect(gruppen[1].kinder).toEqual([]);
  });

  test('Anhang ohne sichtbare Eltern wird eigene Wurzel', () => {
    const gruppen = gruppiereQueue([
      { id: 9, zustellung_id: 90, parent_zustellung_id: 77, payload_typ: 'datei' },
    ]);
    expect(gruppen).toHaveLength(1);
    expect(gruppen[0].eintrag.id).toBe(9);
  });
});
