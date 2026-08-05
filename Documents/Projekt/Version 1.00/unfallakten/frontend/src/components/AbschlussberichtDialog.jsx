/**
 * AbschlussberichtDialog – Kuration + Vorschau + Generierung
 *
 * - Lädt das Übersichts-Objekt (GET abschluss-uebersicht)
 * - Kurationsfelder: schluss_typ (= Abschluss/Sachstand-Umschalter),
 *   schluss_text, verjaehrung_datum (nur vorbehalt_spaetfolgen),
 *   naechste_schritte_text (nur Sachstand)
 * - Leichte Vorschau aus dem Übersichts-Objekt (Summen, Positionen, Plausi)
 * - "Speichern + DOCX erzeugen" → PUT abschluss-status, dann Word-Flow
 */
import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import { abschluss as apiAbschluss, word as apiWord } from "../api.js";

const TYPEN = [
  { wert: "offen",                 label: "Noch offen (Sachstandsbericht)" },
  { wert: "endgueltig",            label: "Endgültig erledigt" },
  { wert: "vorbehalt_spaetfolgen", label: "Erledigt mit Vorbehalt Spätfolgen" },
  { wert: "restposten",            label: "Erledigt bis auf Restposten" },
];

const fmtE = (v) => v == null ? "–"
  : `${Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2 })} €`;

export default function AbschlussberichtDialog({ az, onClose }) {
  const [ueb,        setUeb]        = useState(null);
  const [typ,        setTyp]        = useState("offen");
  const [text,       setText]       = useState("");
  const [verjaehrung, setVerjaehrung] = useState("");
  const [schritte,   setSchritte]   = useState("");
  const [loading,    setLoading]    = useState(true);
  const [busy,       setBusy]       = useState(false);
  const [fehler,     setFehler]     = useState(null);

  useEffect(() => {
    setLoading(true);
    apiAbschluss.uebersicht(az)
      .then(data => {
        setUeb(data);
        setTyp(data.schluss?.typ || "offen");
        setText(data.schluss?.text || "");
        setVerjaehrung(data.schluss?.verjaehrung_datum || "");
        setSchritte(data.schluss?.naechste_schritte_text || "");
      })
      .catch(e => setFehler(e?.message || "Fehler beim Laden"))
      .finally(() => setLoading(false));
  }, [az]);

  const speichernUndGenerieren = async () => {
    setBusy(true);
    setFehler(null);
    try {
      await apiAbschluss.statusSpeichern(az, {
        schluss_typ: typ,
        schluss_text: text,
        verjaehrung_datum: typ === "vorbehalt_spaetfolgen" ? verjaehrung : null,
        naechste_schritte_text: typ === "offen" ? schritte : null,
      });
      await apiWord.generieren(az, "abschlussbericht");
      await apiWord.vorschau(az, "abschlussbericht");
      onClose(true);
    } catch (e) {
      setFehler(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const istSachstand = typ === "offen";
  const modusLabel = istSachstand ? "Sachstandsbericht" : "Abschlussbericht";

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.55)",
                  display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000 }}
         onClick={() => onClose(false)}>
      <div style={{ background:T.surface, borderRadius:14, width:"min(860px, 94vw)",
                    maxHeight:"92vh", overflowY:"auto", padding:"1.6rem" }}
           onClick={e => e.stopPropagation()}>

        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:12 }}>
          <div style={{ fontFamily:T.fontDisplay, fontSize:"1.15rem", fontWeight:700, color:T.navy, flex:1 }}>
            Abschluss-/Sachstandsbericht · Az. {az}
          </div>
          <span style={{ padding:"3px 10px", borderRadius:20, fontSize:"0.8rem", fontWeight:600,
                         background: istSachstand ? T.amberBg : T.greenBg,
                         color: istSachstand ? T.amberText : T.green }}>
            {modusLabel}
          </span>
          <button onClick={() => onClose(false)}
                  style={{ border:"none", background:"none", fontSize:"1.2rem", cursor:"pointer", color:T.textMuted }}>✕</button>
        </div>

        {loading && <div style={{ padding:"2rem", color:T.textMuted }}>Lade Übersicht …</div>}
        {fehler && (
          <div style={{ background:T.redBg, border:`1px solid ${T.red}33`, borderRadius:7,
                        padding:"8px 12px", marginBottom:10, color:T.red, fontSize:"0.875rem" }}>
            ⚠ {fehler}
          </div>
        )}

        {ueb && !loading && (
          <>
            {ueb.plausi && ueb.plausi.differenz_ok === false && (
              <div style={{ background:T.amberBg, border:`1px solid ${T.amber}44`, borderRadius:7,
                            padding:"8px 12px", marginBottom:10, color:T.amberText, fontSize:"0.875rem" }}>
                ⚠ Zeilensumme ({fmtE(ueb.plausi.zeilensumme)}) weicht vom regulierten
                Gesamtbetrag ({fmtE(ueb.plausi.reguliert_gesamt)}) ab — bitte prüfen.
              </div>
            )}

            <div style={{ display:"flex", gap:14, marginBottom:14, flexWrap:"wrap" }}>
              {[
                { l:"Gefordert",       v: fmtE(ueb.summen.gefordert) },
                { l:"Gezahlt",         v: fmtE(ueb.summen.gezahlt) },
                { l:"Davon an Mandant", v: fmtE(ueb.summen.an_mandant) },
                { l:"Differenz",       v: fmtE(ueb.summen.differenz) },
              ].map((s,i) => (
                <div key={i} style={{ flex:1, minWidth:130, background:T.navyDark, borderRadius:10,
                                       padding:"10px 14px", textAlign:"center" }}>
                  <div style={{ fontFamily:"ui-monospace,monospace", fontWeight:600, color:T.white }}>{s.v}</div>
                  <div style={{ fontSize:"0.78rem", color:"rgba(255,255,255,0.5)" }}>{s.l}</div>
                </div>
              ))}
            </div>

            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.875rem", marginBottom:16 }}>
              <thead>
                <tr style={{ background:T.navy, color:T.white }}>
                  {["Position","gefordert","gezahlt","Differenz","Anmerkung"].map(h => (
                    <th key={h} style={{ padding:"6px 10px", textAlign: h==="Position"||h==="Anmerkung" ? "left":"right" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ueb.positionen.map(p => (
                  <tr key={p.key} style={{ borderBottom:`1px solid ${T.border}` }}>
                    <td style={{ padding:"5px 10px" }}>{p.label}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right" }}>{fmtE(p.gefordert)}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right" }}>{fmtE(p.gezahlt)}</td>
                    <td style={{ padding:"5px 10px", textAlign:"right",
                                 color: p.differenz > 0.005 ? T.red : T.text }}>
                      {p.differenz > 0.005 ? fmtE(p.differenz) : "–"}
                    </td>
                    <td style={{ padding:"5px 10px", color:T.textMuted }}>
                      {p.kuerzung_grund || (p.status === "offen" ? "noch offen"
                        : p.status === "voll" ? "vollständig" : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                            color:T.textMuted, marginBottom:5, textTransform:"uppercase" }}>
              Schluss-Status (schaltet Abschluss ↔ Sachstand)
            </label>
            <select value={typ} onChange={e => setTyp(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", borderRadius:7,
                             border:`1.5px solid ${T.border}`, marginBottom:12 }}>
              {TYPEN.map(t => <option key={t.wert} value={t.wert}>{t.label}</option>)}
            </select>

            {typ === "vorbehalt_spaetfolgen" && (
              <>
                <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                                color:T.textMuted, marginBottom:5 }}>Verjährung Spätfolgen</label>
                <input type="date" value={verjaehrung}
                       onChange={e => setVerjaehrung(e.target.value)}
                       style={{ padding:"7px 10px", borderRadius:7,
                                border:`1.5px solid ${T.border}`, marginBottom:12 }} />
              </>
            )}

            {istSachstand && (
              <>
                <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                                color:T.textMuted, marginBottom:5 }}>
                  Woran wir arbeiten / nächster Schritt
                </label>
                <textarea value={schritte} onChange={e => setSchritte(e.target.value)}
                          rows={3}
                          style={{ width:"100%", padding:"8px 10px", borderRadius:7,
                                   border:`1.5px solid ${T.border}`, marginBottom:12,
                                   fontFamily:T.fontBody }} />
              </>
            )}

            <label style={{ display:"block", fontSize:"0.8rem", fontWeight:600,
                            color:T.textMuted, marginBottom:5 }}>
              Schlusstext (anwaltlich kuratiert, erscheint im Schreiben)
            </label>
            <textarea value={text} onChange={e => setText(e.target.value)} rows={4}
                      style={{ width:"100%", padding:"8px 10px", borderRadius:7,
                               border:`1.5px solid ${T.border}`, marginBottom:16,
                               fontFamily:T.fontBody }} />

            <div style={{ display:"flex", gap:10, justifyContent:"flex-end" }}>
              <button onClick={() => onClose(false)} disabled={busy}
                      style={{ padding:"9px 16px", borderRadius:8, border:`1px solid ${T.border}`,
                               background:T.surface, cursor:"pointer" }}>
                Abbrechen
              </button>
              <button onClick={speichernUndGenerieren} disabled={busy}
                      style={{ padding:"9px 16px", borderRadius:8, border:"none",
                               background:T.navy, color:T.white, fontWeight:600,
                               cursor: busy ? "default" : "pointer", opacity: busy ? 0.7 : 1 }}>
                {busy ? "Erzeuge …" : `Speichern + ${modusLabel} (DOCX)`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
