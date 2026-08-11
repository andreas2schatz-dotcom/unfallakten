import React from "react";
import T from "../config/theme.js";
import { fmtEuro } from "../config/utils.js";
import { Card, CardHead, Toast } from "./common.jsx";
import { forderungen as apiForderungen } from "../api.js";

export default function ForderungshistorieKarte({ akteId }) {
  const [schreiben, setSchreiben] = React.useState([]);
  const [laden, setLaden]         = React.useState(true);
  const [fehler, setFehler]       = React.useState(false);
  const [offen, setOffen]         = React.useState({});   // { nr: bool }
  const [toast, setToast]         = React.useState("");

  React.useEffect(() => {
    if (!akteId || !String(akteId).includes("/")) {
      setSchreiben([]); setLaden(false); setFehler(false);
      return;
    }
    // Ignore-Guard: verspätete Antwort einer vorherigen Akte darf den
    // State der aktuellen Akte nicht überschreiben
    let aktiv = true;
    setLaden(true);
    setFehler(false);
    apiForderungen.nachSchreiben(akteId)
      .then(r => { if (aktiv) setSchreiben(r?.schreiben || []); })
      .catch(() => { if (aktiv) { setSchreiben([]); setFehler(true); } })
      .finally(() => { if (aktiv) setLaden(false); });
    return () => { aktiv = false; };
  }, [akteId]);

  const toggleKlage = async (pos) => {
    const neuerFlag = !pos.fuer_klage;
    try {
      await apiForderungen.klageFlagSetzen(akteId, [pos.id], neuerFlag);
      setSchreiben(prev => prev.map(s => ({
        ...s,
        positionen: s.positionen.map(p =>
          p.id === pos.id ? { ...p, fuer_klage: neuerFlag } : p
        )
      })));
      setToast(neuerFlag ? "Für Klage vorgemerkt." : "Klage-Flag entfernt.");
    } catch { setToast("Fehler beim Speichern."); }
  };

  const setzeStatus = async (pos, status) => {
    try {
      const res = await apiForderungen.aktualisieren(akteId, pos.id, { status });
      setSchreiben(prev => prev.map(s => ({
        ...s,
        positionen: s.positionen.map(p =>
          p.id === pos.id ? { ...p, status: res?.position?.status || status } : p
        )
      })));
      setToast("Status aktualisiert.");
    } catch { setToast("Fehler beim Speichern."); }
  };

  const STATUS_STYLE = {
    gefordert:     { c: T.textMuted,   bg: T.surface,    label: "offen"         },
    teilreguliert: { c: T.amber,       bg: T.amberBg,    label: "teilreg."      },
    vollreguliert: { c: T.green,       bg: T.greenBg,    label: "✓ voll"        },
    gekuerzt:      { c: "#dc2626",     bg: T.redBg,    label: "gekürzt"       },
    abgelehnt:     { c: T.redText,     bg: "#fee2e2",    label: "abgelehnt"     },
  };

  if (laden) return (
    <Card style={{ padding: "1.2rem 1.4rem", color: T.textFaint, fontSize: "0.9rem" }}>
      Forderungshistorie wird geladen …
    </Card>
  );

  if (fehler) return (
    <Card style={{ padding: "1.2rem 1.4rem" }}>
      <CardHead title="Forderungshistorie" />
      <p style={{ color: T.redText, fontSize: "0.9rem", margin: 0 }} role="alert">
        Forderungshistorie konnte nicht geladen werden.
      </p>
    </Card>
  );

  if (schreiben.length === 0) return (
    <Card style={{ padding: "1.2rem 1.4rem" }}>
      <CardHead title="Forderungshistorie" />
      <p style={{ color: T.textFaint, fontSize: "0.9rem", margin: 0 }}>
        Noch kein Forderungsschreiben der Höhe nach erstellt. Positionen werden
        automatisch beim Generieren erfasst.
      </p>
    </Card>
  );

  const gesamtKlage = schreiben.flatMap(s => s.positionen)
    .filter(p => p.fuer_klage)
    .reduce((sum, p) => sum + (p.betrag_gefordert - p.betrag_reguliert), 0);

  return (
    <Card>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <CardHead title={`Forderungshistorie · ${schreiben.length} Schreiben`}
        action={gesamtKlage > 0
          ? <span style={{ fontSize:"0.82rem", color:"#dc2626", fontWeight:600 }}>
              🏛 Klagepotential: {fmtEuro(gesamtKlage)}
            </span>
          : null}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "0 1.4rem 1.4rem" }}>
        {schreiben.map(s => {
          const isOffen = offen[s.schreiben_nr] !== false; // default aufgeklappt
          const offenCount = s.positionen.filter(p => p.status === "gefordert").length;
          const klageCount = s.positionen.filter(p => p.fuer_klage).length;
          return (
            <div key={s.schreiben_nr} style={{ border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden" }}>
              {/* Header */}
              <div
                onClick={() => setOffen(p => ({ ...p, [s.schreiben_nr]: !isOffen }))}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                  background: T.surface, cursor: "pointer", userSelect: "none" }}>
                <span style={{ fontSize: "0.8rem", color: T.textMuted }}>▶</span>
                <span style={{ fontFamily: T.fontBody, fontWeight: 600,
                  color: T.navy, fontSize: "0.92rem" }}>
                  Forderungsschreiben Nr. {s.schreiben_nr}
                </span>
                <span style={{ fontFamily: T.fontBody, fontSize: "0.82rem",
                  color: T.textFaint }}>
                  {s.datum || "–"}
                </span>
                <span style={{ marginLeft: "auto", fontFamily: "ui-monospace,monospace",
                  fontSize: "0.88rem", fontWeight: 600, color: T.navy }}>
                  {fmtEuro(s.gesamt_gefordert)}
                </span>
                {offenCount > 0 &&
                  <span style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20,
                    background: T.surface, border: `1px solid ${T.border}`, color: T.textMuted }}>
                    {offenCount} offen
                  </span>}
                {klageCount > 0 &&
                  <span style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20,
                    background: T.redBg, color: "#dc2626", fontWeight: 600 }}>
                    {klageCount} Klage
                  </span>}
              </div>

              {/* Positionstabelle */}
              {isOffen && (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.855rem" }}>
                  <thead>
                    <tr style={{ background: T.surface }}>
                      {["Position", "Gefordert", "Reguliert", "Status", "Klage"].map((h, i) => (
                        <th key={h} style={{ padding: "7px 12px", textAlign: i === 0 ? "left" : "right",
                          fontSize: "0.74rem", fontWeight: 600, color: T.textMuted,
                          textTransform: "uppercase", letterSpacing: "0.05em",
                          borderTop: `1px solid ${T.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.positionen.map(pos => {
                      const st2 = STATUS_STYLE[pos.status] || STATUS_STYLE.gefordert;
                      return (
                        <tr key={pos.id} style={{ borderTop: `1px solid ${T.border}`,
                          background: pos.fuer_klage ? "#fff5f5" : "white" }}>
                          <td style={{ padding: "8px 12px", color: T.text, fontWeight: 500 }}>
                            {pos.position_label}
                            {pos.position_key === "restwert" &&
                              <span style={{ fontSize: 11, color: T.textFaint, marginLeft: 4 }}>(Abzug)</span>}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right",
                            fontFamily: "ui-monospace,monospace", color: T.text }}>
                            {fmtEuro(pos.betrag_gefordert)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right",
                            fontFamily: "ui-monospace,monospace",
                            color: pos.betrag_reguliert > 0 ? T.green : T.textFaint }}>
                            {pos.betrag_reguliert > 0 ? fmtEuro(pos.betrag_reguliert) : "—"}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            <select
                              value={pos.status}
                              onChange={e => setzeStatus(pos, e.target.value)}
                              style={{ fontSize: 11, padding: "2px 6px", borderRadius: 12,
                                background: st2.bg, color: st2.c, border: `1px solid ${st2.c}44`,
                                fontWeight: 600, cursor: "pointer", outline: "none" }}>
                              {Object.entries(STATUS_STYLE).map(([val, { label }]) => (
                                <option key={val} value={val}>{label}</option>
                              ))}
                            </select>
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            <button
                              onClick={() => toggleKlage(pos)}
                              title={pos.fuer_klage ? "Klage-Flag entfernen" : "Für Klage vormerken"}
                              style={{ padding: "3px 8px", borderRadius: 8, border: "none",
                                background: pos.fuer_klage ? T.redBg : T.surface,
                                color: pos.fuer_klage ? "#dc2626" : T.textFaint,
                                cursor: "pointer", fontSize: 13, fontWeight: pos.fuer_klage ? 700 : 400 }}>
                              {pos.fuer_klage ? "🏛 Klage" : "○"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: `2px solid ${T.border}`, background: T.surface }}>
                      <td style={{ padding: "8px 12px", fontWeight: 700, color: T.navy,
                        fontSize: "0.85rem" }}>Summe</td>
                      <td style={{ padding: "8px 12px", textAlign: "right",
                        fontFamily: "ui-monospace,monospace", fontWeight: 700, color: T.navy }}>
                        {fmtEuro(s.gesamt_gefordert)}
                      </td>
                      <td style={{ padding: "8px 12px", textAlign: "right",
                        fontFamily: "ui-monospace,monospace", fontWeight: 700, color: T.green }}>
                        {s.gesamt_reguliert > 0 ? fmtEuro(s.gesamt_reguliert) : "—"}
                      </td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
