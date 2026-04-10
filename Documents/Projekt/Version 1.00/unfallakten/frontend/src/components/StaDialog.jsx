/**
 * StaDialog – PRD-25d: Intelligente Sachstandsanfrage
 *
 * Öffnet als Modal über einer Akte.
 * - Zeigt Kontext: letztes Schreiben, Tage ohne Antwort, Versicherer
 * - Eskalationsstufe per [−] / [+] wählbar
 * - Editierbares Textfeld mit vorausgefülltem Stufentext
 * - Warnung vor Überschreiben bei manuellen Änderungen
 * - "Generieren + Word öffnen" → Download + Todo
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import T from "../config/theme.js";
import { apiSta } from "../api.js";

const STUFEN_LABEL = {
  1: { name: "Erinnerung",        farbe: T.green, frist: "14 Tage" },
  2: { name: "Mahnung",           farbe: T.amber, frist: "7 Tage"  },
  3: { name: "Klage-Ankündigung", farbe: T.red, frist: "5 Tage"  },
};

export default function StaDialog({ az, onClose }) {
  const [kontext,    setKontext]    = useState(null);
  const [stufe,      setStufe]      = useState(null);     // null bis geladen
  const [brieftext,  setBrieftext]  = useState("");
  const [dirty,      setDirty]      = useState(false);    // manuell bearbeitet?
  const [confirm,    setConfirm]    = useState(null);     // {zielStufe} wenn Warnung aktiv
  const [loading,    setLoading]    = useState(true);
  const [generating, setGenerating] = useState(false);
  const [fehler,     setFehler]     = useState(null);
  const [erfolg,     setErfolg]     = useState(false);
  const textareaRef = useRef(null);

  // Kontext laden (empfohlene Stufe)
  useEffect(() => {
    setLoading(true);
    setFehler(null);
    apiSta.kontext(az)
      .then(data => {
        setKontext(data);
        setStufe(data.stufe);
        setBrieftext(data.brieftext || "");
        setDirty(false);
      })
      .catch(e => setFehler(e?.message || "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [az]);

  // Neuen Text für eine Stufe laden (nach Bestätigung des Überschreibens)
  const ladeStufe = useCallback((neueStufe) => {
    setFehler(null);
    apiSta.kontext(az, neueStufe)
      .then(data => {
        setStufe(neueStufe);
        setBrieftext(data.brieftext || "");
        setDirty(false);
      })
      .catch(e => setFehler(e?.message || "Fehler beim Laden"));
  }, [az]);

  const versucheStufeWechsel = (zielStufe) => {
    if (zielStufe < 1 || zielStufe > 3) return;
    if (dirty) {
      setConfirm({ zielStufe });
    } else {
      ladeStufe(zielStufe);
    }
  };

  const bestaetigenUeberschreiben = () => {
    if (confirm) {
      ladeStufe(confirm.zielStufe);
      setConfirm(null);
    }
  };

  const generieren = async () => {
    if (!brieftext.trim()) return;
    setGenerating(true);
    setFehler(null);
    try {
      await apiSta.generieren(az, stufe, brieftext);
      setErfolg(true);
      setTimeout(() => onClose(true), 1500);
    } catch (e) {
      setFehler(e?.message || "Fehler beim Generieren");
    } finally {
      setGenerating(false);
    }
  };

  // Escape schließt Dialog
  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(false); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const stufeInfo = STUFEN_LABEL[stufe] || STUFEN_LABEL[1];

  return (
    // Backdrop
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose(false); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.55)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "1rem",
      }}
    >
      {/* Dialog-Box */}
      <div style={{
        background: T.surface,
        borderRadius: 14,
        width: "100%", maxWidth: 640,
        maxHeight: "90vh",
        display: "flex", flexDirection: "column",
        boxShadow: "0 24px 64px rgba(0,0,0,0.22)",
        overflow: "hidden",
      }}>

        {/* Header */}
        <div style={{
          padding: "1.1rem 1.4rem",
          borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: T.navy,
        }}>
          <div>
            <div style={{
              fontFamily: "'Bricolage Grotesque',sans-serif",
              fontSize: "1.05rem", fontWeight: 700, color: T.white,
            }}>
              Sachstandsanfrage
            </div>
            <div style={{
              fontFamily: "ui-monospace,monospace",
              fontSize: "0.8rem", color: "rgba(255,255,255,0.5)", marginTop: 2,
            }}>{az}</div>
          </div>
          <button onClick={() => onClose(false)} style={{
            background: "none", border: "none", cursor: "pointer",
            color: "rgba(255,255,255,0.5)", fontSize: "1.3rem", padding: "2px 6px",
            lineHeight: 1,
          }}>×</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem 1.4rem", display: "flex", flexDirection: "column", gap: "1rem" }}>

          {loading && (
            <div style={{ textAlign: "center", padding: "2rem", color: T.textMuted, fontFamily: "'Figtree',sans-serif" }}>
              Analysiere Akte…
            </div>
          )}

          {!loading && kontext && (
            <>
              {/* Kontext-Banner */}
              <div style={{
                background: T.navyDark,
                borderRadius: 10, padding: "0.85rem 1.1rem",
                border: `1px solid ${T.accentTrim}`,
              }}>
                {kontext.letztes_schreiben ? (
                  <>
                    <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", color: T.white, fontWeight: 600 }}>
                      Letztes Schreiben: {kontext.letztes_schreiben.typ_label} v. {kontext.letztes_schreiben.datum_fmt}
                    </div>
                    <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.82rem", color: "rgba(255,255,255,0.5)", marginTop: 3 }}>
                      {kontext.tage_ohne_antwort > 0
                        ? `${kontext.tage_ohne_antwort} Tage ohne Antwort`
                        : "Kein offenes Schreiben"}
                      {kontext.versicherer_name ? ` · ${kontext.versicherer_name}` : ""}
                      {kontext.sta_anzahl > 0 ? ` · ${kontext.sta_anzahl} STA bereits erstellt` : ""}
                    </div>
                  </>
                ) : (
                  <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", color: "rgba(255,255,255,0.6)" }}>
                    Kein ausgehendes Schreiben gefunden – allgemeine Sachstandsanfrage
                  </div>
                )}
              </div>

              {/* Stufen-Wähler */}
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", fontWeight: 600, color: T.text }}>
                  Eskalationsstufe:
                </span>
                <button
                  onClick={() => versucheStufeWechsel(stufe - 1)}
                  disabled={stufe <= 1}
                  style={{
                    width: 32, height: 32, borderRadius: 7, border: `1.5px solid ${T.border}`,
                    background: "none", cursor: stufe <= 1 ? "not-allowed" : "pointer",
                    color: stufe <= 1 ? T.textFaint : T.text,
                    fontFamily: "'Figtree',sans-serif", fontSize: "1.1rem", fontWeight: 700,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}
                >−</button>
                <div style={{
                  display: "flex", alignItems: "center", gap: 7,
                  padding: "5px 14px", borderRadius: 7,
                  width: 260, flexShrink: 0, boxSizing: "border-box",
                  background: stufeInfo.farbe + "18",
                  border: `1.5px solid ${stufeInfo.farbe}44`,
                }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: stufeInfo.farbe, flexShrink: 0 }} />
                  <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.915rem", fontWeight: 700, color: stufeInfo.farbe }}>
                    Stufe {stufe} – {stufeInfo.name}
                  </span>
                  <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.8rem", color: T.textMuted, marginLeft: "auto", flexShrink: 0 }}>
                    {stufeInfo.frist}
                  </span>
                </div>
                <button
                  onClick={() => versucheStufeWechsel(stufe + 1)}
                  disabled={stufe >= 3}
                  style={{
                    width: 32, height: 32, borderRadius: 7, border: `1.5px solid ${T.border}`,
                    background: "none", cursor: stufe >= 3 ? "not-allowed" : "pointer",
                    color: stufe >= 3 ? T.textFaint : T.text,
                    fontFamily: "'Figtree',sans-serif", fontSize: "1.1rem", fontWeight: 700,
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}
                >+</button>
                {dirty && (
                  <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.78rem", color: T.amber }}>
                    * bearbeitet
                  </span>
                )}
              </div>

              {/* Überschreiben-Warnung */}
              {confirm && (
                <div style={{
                  background: (T.amber) + "15",
                  border: `1px solid ${T.amber}44`,
                  borderRadius: 8, padding: "0.7rem 1rem",
                  display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                }}>
                  <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", color: T.text, flex: 1 }}>
                    Manuelle Änderungen verwerfen und Stufe {confirm.zielStufe} laden?
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button onClick={() => setConfirm(null)}
                      style={{ padding: "4px 12px", borderRadius: 6, border: `1px solid ${T.border}`, background: "none", cursor: "pointer", fontFamily: "'Figtree',sans-serif", fontSize: "0.845rem", color: T.text }}>
                      Nein
                    </button>
                    <button onClick={bestaetigenUeberschreiben}
                      style={{ padding: "4px 12px", borderRadius: 6, border: "none", background: T.amber, cursor: "pointer", fontFamily: "'Figtree',sans-serif", fontSize: "0.845rem", fontWeight: 600, color: "#fff" }}>
                      Ja, verwerfen
                    </button>
                  </div>
                </div>
              )}

              {/* Textfeld */}
              <div>
                <label style={{
                  display: "block", fontFamily: "'Figtree',sans-serif",
                  fontSize: "0.8rem", fontWeight: 600, color: T.textMuted,
                  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6,
                }}>
                  Brieftext (editierbar)
                </label>
                <textarea
                  ref={textareaRef}
                  value={brieftext}
                  onChange={e => { setBrieftext(e.target.value); setDirty(true); }}
                  rows={10}
                  style={{
                    width: "100%", boxSizing: "border-box",
                    padding: "0.75rem 1rem",
                    borderRadius: 8, border: `1.5px solid ${dirty ? (T.amber) + "88" : T.border}`,
                    fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem",
                    lineHeight: 1.65, color: T.text,
                    background: T.surface,
                    resize: "vertical", outline: "none",
                    transition: "border-color 0.15s",
                  }}
                />
              </div>
            </>
          )}

          {/* Fehler */}
          {fehler && (
            <div style={{
              background: (T.red) + "15",
              border: `1px solid ${T.red}44`,
              borderRadius: 8, padding: "0.75rem 1rem",
              fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem",
              color: T.red,
            }}>
              ⚠ {fehler}
            </div>
          )}

          {/* Erfolg */}
          {erfolg && (
            <div style={{
              background: (T.green) + "18",
              border: `1px solid ${T.green}44`,
              borderRadius: 8, padding: "0.75rem 1rem",
              fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem",
              color: T.green, fontWeight: 600,
            }}>
              ✓ Sachstandsanfrage generiert · 2-Wochen-Todo angelegt · Fenster schließt…
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: "0.9rem 1.4rem",
          borderTop: `1px solid ${T.border}`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          gap: 10,
        }}>
          <button onClick={() => onClose(false)} style={{
            padding: "8px 18px", borderRadius: 7,
            border: `1.5px solid ${T.border}`,
            background: "none", cursor: "pointer",
            fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem",
            color: T.textMuted,
          }}>
            Abbrechen
          </button>
          <button
            onClick={generieren}
            disabled={generating || loading || !brieftext.trim() || erfolg}
            style={{
              padding: "9px 20px", borderRadius: 7, border: "none",
              background: (generating || loading || !brieftext.trim() || erfolg)
                ? T.textFaint
                : T.accent,
              color: "#fff", cursor: (generating || loading || !brieftext.trim() || erfolg) ? "not-allowed" : "pointer",
              fontFamily: "'Bricolage Grotesque',sans-serif",
              fontSize: "0.925rem", fontWeight: 700,
              display: "flex", alignItems: "center", gap: 7,
              transition: "background 0.15s",
            }}
          >
            {generating ? "Generiert…" : "Generieren + Word öffnen →"}
          </button>
        </div>
      </div>
    </div>
  );
}
