import { useState } from 'react';
import { apiKlage } from '../api.js';

export function KlageGesamtvorschau({ akteId, cfg, overrides, onEditAbschnitt }) {
  const [abschnitte, setAbschnitte] = useState(null);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState('');
  const [editKey, setEditKey] = useState(null);
  const [editText, setEditText] = useState('');

  async function laden() {
    setLaedt(true); setFehler('');
    try {
      const res = await apiKlage.vorschau(akteId, cfg, overrides);
      setAbschnitte(res.abschnitte || []);
    } catch (e) {
      setFehler(e?.message || 'Vorschau fehlgeschlagen.');
    } finally {
      setLaedt(false);
    }
  }

  function startEdit(ab) {
    setEditKey(ab.key);
    setEditText(ab.text);
  }

  async function speichereEdit(ab) {
    onEditAbschnitt(ab.override_feld, editText);
    setEditKey(null);
    await laden();
  }

  return (
    <div>
      <button type="button" onClick={laden} disabled={laedt}>
        {laedt ? 'Erzeuge Vorschau …' : 'Vorschau erzeugen'}
      </button>
      {fehler && <div role="alert" style={{ color: '#c0392b', marginTop: 8 }}>{fehler}</div>}
      {abschnitte && (
        <div style={{ marginTop: 12 }}>
          {abschnitte.map((ab) => (
            <section key={ab.key} style={{ borderBottom: '1px solid #e5e5e5', padding: '10px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <strong style={{ flex: 1 }}>{ab.titel}</strong>
                {ab.editierbar && editKey !== ab.key && (
                  <button type="button" onClick={() => startEdit(ab)}>✎ Bearbeiten</button>
                )}
                {!ab.editierbar && (
                  <span style={{ fontSize: '0.75rem', color: '#888' }}>
                    Änderbar über den zugehörigen Schritt
                  </span>
                )}
              </div>
              {editKey === ab.key ? (
                <div>
                  <textarea value={editText} onChange={(e) => setEditText(e.target.value)}
                    rows={Math.max(4, ab.text.split('\n').length + 1)} style={{ width: '100%' }} />
                  <button type="button" onClick={() => speichereEdit(ab)}>Übernehmen</button>
                  <button type="button" onClick={() => setEditKey(null)}>Abbrechen</button>
                </div>
              ) : (
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: '6px 0 0' }}>
                  {ab.text}
                </pre>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
