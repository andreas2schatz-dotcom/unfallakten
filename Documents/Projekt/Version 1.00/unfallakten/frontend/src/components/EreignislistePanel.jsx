import React, { useEffect, useState } from 'react';
import T from '../config/theme.js';
import { API_BASE, tokenStore } from '../api.js';

const RICHTUNG_ICON = {
  ausgehend: { z: '↗', bg: T.blueBg,     fg: T.blueText,  bd: T.blue },
  eingehend: { z: '↘', bg: T.greenBg,    fg: T.greenText, bd: T.greenLight },
  intern:    { z: '⏰', bg: T.accentPale, fg: T.accentDark, bd: T.accent },
};

function fmtDatum(iso) {
  if (!iso || typeof iso !== 'string') return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

function fmtEuro(v) {
  if (v == null) return '';
  return Number(v).toLocaleString('de-DE', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }) + ' €';
}

function EreignisZeile({ e }) {
  const ic = RICHTUNG_ICON[e.richtung] || RICHTUNG_ICON.intern;
  const ersetzt = e.status === 'ersetzt';
  return (
    <div
      data-testid={`ereignis-${e.ereignis_id}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '90px 30px 1fr auto',
        gap: 10,
        padding: '10px 4px',
        borderBottom: `1px solid ${T.borderSoft}`,
        alignItems: 'start',
        opacity: ersetzt ? 0.6 : 1,
      }}
    >
      <div style={{ fontFamily: T.fontMono, fontSize: '0.78rem', color: T.textMid, paddingTop: 3 }}>
        {fmtDatum(e.datum)}
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        width: 26, height: 26, borderRadius: '50%',
        background: ic.bg, color: ic.fg, border: `1px solid ${ic.bd}`,
        fontSize: '0.9rem',
      }} title={e.richtung}>{ic.z}</div>
      <div>
        <div style={{
          fontWeight: 600, color: T.text, fontSize: '0.88rem',
          textDecoration: ersetzt ? 'line-through' : 'none',
          textDecorationColor: T.textFaint,
        }}>
          {e.ereignistyp}
        </div>
        <div style={{
          fontSize: '0.75rem', color: T.textMuted, marginTop: 2,
          display: 'flex', gap: 8, flexWrap: 'wrap',
        }}>
          {e.wirkung && e.wirkung !== 'keine' && (
            <span>{e.wirkung}{e.betrag != null ? ` ${fmtEuro(e.betrag)}` : ''}</span>
          )}
          {e.dokument_id != null && <span>· Dokument #{e.dokument_id}</span>}
          {e.herkunft && (
            <span style={{
              color: e.herkunft === 'wdm' ? T.accentDark : T.textMuted,
              fontWeight: e.herkunft === 'wdm' ? 600 : 400,
            }}>· herkunft: {e.herkunft}</span>
          )}
        </div>
      </div>
      <span style={{
        fontSize: '0.65rem', textTransform: 'uppercase',
        letterSpacing: '0.09em', fontWeight: 700,
        padding: '3px 7px', borderRadius: 4,
        background: ersetzt ? T.surface : T.greenBg,
        color:      ersetzt ? T.textFaint : T.greenText,
        border: `1px solid ${ersetzt ? T.border : T.greenLight}`,
        whiteSpace: 'nowrap',
      }}>{e.status}</span>
    </div>
  );
}

export default function EreignislistePanel({ az, positionKey, onClose }) {
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);

  useEffect(() => {
    if (!positionKey || !az) return;
    let abgebrochen = false;
    setDaten(null); setFehler(null);
    const token = tokenStore.getAccess();
    fetch(
      `${API_BASE}/akten/${encodeURIComponent(az)}/positionen/${encodeURIComponent(positionKey)}/ereignisse`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    )
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
      .then(d => { if (!abgebrochen) setDaten(d); })
      .catch(e => { if (!abgebrochen) setFehler(e.message || String(e)); });
    return () => { abgebrochen = true; };
  }, [az, positionKey]);

  if (!positionKey) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 480, zIndex: 100,
      background: T.white, borderLeft: `1px solid ${T.border}`,
      boxShadow: '-8px 0 24px rgba(27,42,74,0.10)',
      padding: '18px 20px',
      overflowY: 'auto',
      fontFamily: T.fontBody,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12,
        paddingBottom: 12, borderBottom: `1px solid ${T.borderSoft}`, marginBottom: 12,
      }}>
        <div>
          <div style={{ fontFamily: T.fontDisplay, fontWeight: 600, fontSize: '1.05rem', color: T.navy }}>
            {positionKey}
          </div>
          <div style={{ fontSize: '0.78rem', color: T.textMuted, marginTop: 2 }}>
            Ebene 2 — chronologisch, aktuell/ersetzt sichtbar
          </div>
        </div>
        <button
          aria-label="Schließen"
          onClick={onClose}
          style={{
            background: 'transparent', border: 0, color: T.textFaint,
            fontSize: '1.4rem', cursor: 'pointer', lineHeight: 1,
          }}
        >×</button>
      </div>

      {fehler && (
        <div style={{ padding: 10, background: T.redBg, color: T.redText, border: `1px solid ${T.red}`, borderRadius: 6, fontSize: '0.85rem' }}>
          Ereignisse nicht geladen: {fehler}
        </div>
      )}
      {!daten && !fehler && (
        <div style={{ padding: 10, color: T.textMuted, fontSize: '0.85rem' }}>
          Lade Ereignisse…
        </div>
      )}
      {daten && daten.ereignisse.length === 0 && (
        <div style={{ padding: 16, color: T.textMuted, fontSize: '0.85rem', textAlign: 'center' }}>
          Keine Ereignisse für diese Position.
        </div>
      )}
      {daten && daten.ereignisse.map(e => <EreignisZeile key={e.ereignis_id} e={e} />)}

      <div style={{ marginTop: 12, color: T.textFaint, fontSize: '0.7rem', fontFamily: T.fontMono }}>
        <span style={{ color: T.blueText }}>↗ ausgehend</span>
        {' · '}
        <span style={{ color: T.greenText }}>↘ eingehend</span>
        {' · '}
        <span style={{ color: T.accentDark }}>⏰ system</span>
      </div>
    </div>
  );
}
