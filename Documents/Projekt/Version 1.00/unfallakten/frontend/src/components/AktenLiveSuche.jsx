import React, { useEffect, useRef, useState } from 'react';
import T from '../config/theme.js';
import { API_BASE, tokenStore } from '../api.js';

const DEBOUNCE_MS = 300;
const MIN_QUERY = 2;

export default function AktenLiveSuche({ onWaehle, autoFocus = false, placeholder }) {
  const [query, setQuery] = useState('');
  const [treffer, setTreffer] = useState(null);
  const [laden, setLaden] = useState(false);
  const [fehler, setFehler] = useState(null);
  const timer = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (autoFocus && inputRef.current) inputRef.current.focus();
  }, [autoFocus]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const q = query.trim();
    if (q.length < MIN_QUERY) {
      setTreffer(null);
      setFehler(null);
      setLaden(false);
      return;
    }
    timer.current = setTimeout(async () => {
      setLaden(true); setFehler(null);
      try {
        const token = tokenStore.getAccess();
        const url = `${API_BASE}/aktensuche?az=${encodeURIComponent(q)}`;
        const res = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();
        setTreffer(Array.isArray(d.treffer) ? d.treffer : []);
      } catch (e) {
        setFehler(e.message || String(e));
        setTreffer([]);
      } finally {
        setLaden(false);
      }
    }, DEBOUNCE_MS);
    return () => timer.current && clearTimeout(timer.current);
  }, [query]);

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder={placeholder || 'Mandantenname oder Aktenzeichen suchen…'}
        style={{
          width: '100%', boxSizing: 'border-box',
          padding: '7px 10px', border: `1px solid ${T.border}`,
          borderRadius: 4, fontSize: T.textSm, fontFamily: T.fontBody,
          background: T.white,
        }}
      />

      {laden && (
        <div style={{
          marginTop: 6, fontSize: T.textXs, color: T.textMuted,
          padding: '4px 8px',
        }}>Suche läuft…</div>
      )}

      {fehler && (
        <div style={{
          marginTop: 6, padding: '6px 10px',
          background: T.redBg, color: T.redText, border: `1px solid ${T.redLight}`,
          borderRadius: 4, fontSize: T.textXs,
        }}>Suche fehlgeschlagen: {fehler}</div>
      )}

      {treffer != null && !laden && !fehler && treffer.length === 0 && (
        <div style={{
          marginTop: 6, padding: '8px 10px',
          background: T.surface, color: T.textMuted,
          border: `1px solid ${T.border}`, borderRadius: 4,
          fontSize: T.textXs, fontStyle: 'italic',
        }}>Keine Treffer für „{query}".</div>
      )}

      {treffer != null && treffer.length > 0 && (
        <div style={{
          marginTop: 6, maxHeight: 260, overflowY: 'auto',
          border: `1px solid ${T.border}`, borderRadius: 4,
          background: T.white,
        }}>
          {treffer.map((t, i) => (
            <button
              key={t.az_roh || t.az || i}
              data-treffer
              onClick={() => onWaehle && onWaehle(t.az)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 10px', border: 'none',
                borderBottom: i < treffer.length - 1 ? `1px solid ${T.borderSoft}` : 'none',
                background: 'transparent', cursor: 'pointer',
                fontFamily: T.fontBody, fontSize: T.textSm,
              }}
              onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <code style={{ color: T.navy, fontWeight: 600 }}>{t.az}</code>
                {t.kennzeichen && (
                  <span style={{ fontSize: T.textXs, color: T.textMuted, fontFamily: T.fontMono }}>
                    {t.kennzeichen}
                  </span>
                )}
              </div>
              <div style={{ color: T.text, marginTop: 2 }}>{t.mandant || t.kurzbezeichnung || '—'}</div>
              {t.kurzbezeichnung && t.mandant && t.kurzbezeichnung !== t.mandant && (
                <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 1 }}>
                  {t.kurzbezeichnung}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
