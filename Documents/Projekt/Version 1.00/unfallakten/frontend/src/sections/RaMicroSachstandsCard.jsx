import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { Card } from "../components/common.jsx";
import {
  wiedervorlage as apiWV,
} from "../api.js";

function RaMicroSachstandsCard({ akte, inGrid = false }) {
  const [wv,      setWv]      = useState(null);   // gefundene Wiedervorlage
  const [ladeWv,  setLadeWv]  = useState(true);
  const [laedt,   setLaedt]   = useState(false);
  const [erstellt, setErstellt] = useState(false);
  const [fehler,  setFehler]  = useState(null);

  // Suche nach offener WV für dieses Aktenzeichen
  useEffect(() => {
    let aktiv = true;
    setLadeWv(true);
    apiWV.liste().then(res => {
      if (!aktiv) return;
      const treffer = (res?.wiedervorlagen || []).find(w =>
        w.aktenzeichen === akte.az || w.aktenzeichen?.startsWith(akte.az)
      );
      setWv(treffer || null);
    }).catch(() => setWv(null)).finally(() => { if (aktiv) setLadeWv(false); });
    return () => { aktiv = false; };
  }, [akte.az]);

  const generieren = async () => {
    if (!wv) return;
    setLaedt(true); setFehler(null);
    try {
      await apiWV.sachstandsanfrage(wv.guid, wv.aktenzeichen);
      setErstellt(true);
    } catch (e) {
      setFehler(e.message || "Fehler beim Generieren");
    } finally {
      setLaedt(false);
    }
  };

  return (
    <div style={inGrid ? {} : { marginTop:"1.25rem" }}>
      {/* Trennlinie mit Label – nur außerhalb Grid */}
      {!inGrid && (
        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:"1.1rem" }}>
          <div style={{ flex:1, height:1, background:T.border }} />
          <span style={{ fontFamily:T.fontBody, fontSize:"0.8rem", color:T.textFaint, fontWeight:500, letterSpacing:"0.08em", textTransform:"uppercase", whiteSpace:"nowrap" }}>
            RA-Micro Integration
          </span>
          <div style={{ flex:1, height:1, background:T.border }} />
        </div>
      )}

      <Card style={{ padding:"1.4rem", display:"flex", gap:16, alignItems:"flex-start", height:"100%", boxSizing:"border-box" }}>
        {/* Icon */}
        <div style={{ width:44, height:44, borderRadius:10, background:"linear-gradient(135deg,#1B2A4A,#2e4270)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.4rem", flexShrink:0 }}>
          📋
        </div>

        <div style={{ flex:1 }}>
          <div style={{ fontFamily:T.fontDisplay, fontSize:"1rem", fontWeight:700, color:T.navy, marginBottom:2 }}>
            Sachstandsanfrage
          </div>
          <div style={{ fontFamily:T.fontBody, fontSize:"0.835rem", color:T.textFaint, marginBottom:10 }}>
            Daten aus RA-Micro Wiedervorlage · Kanzlei-Briefformat
          </div>

          {ladeWv ? (
            <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:T.textMuted, display:"flex", alignItems:"center", gap:8 }}>
              <div style={{ width:12, height:12, border:`2px solid ${T.border}`, borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite" }} />
              Suche Wiedervorlage …
            </div>
          ) : !wv ? (
            <div style={{ display:"inline-flex", alignItems:"center", gap:7, background:T.amberBg, border:"1px solid #fcd34d", borderRadius:8, padding:"7px 13px", fontFamily:T.fontBody, fontSize:"0.875rem", color:T.amberText }}>
              <span>⚠️</span> Keine offene Wiedervorlage „Stellungnahme Gegner" in RA-Micro für {akte.az}
            </div>
          ) : (
            <div style={{ display:"flex", flexWrap:"wrap", gap:8, alignItems:"center" }}>
              {/* WV-Info-Chips */}
              <span style={{ background:T.accentPale, border:`1px solid ${T.accentTrim}`, borderRadius:6, padding:"3px 9px", fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMid }}>
                Fällig: {wv.datum ? new Date(wv.datum + "T00:00:00").toLocaleDateString("de-DE") : "–"}
              </span>
              {wv.gegner_hv_name && (
                <span style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:6, padding:"3px 9px", fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMid }}>
                  {wv.gegner_hv_name}
                </span>
              )}
              {wv.betreff1 && (
                <span style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:6, padding:"3px 9px", fontFamily:"ui-monospace,monospace", fontSize:"0.8rem", color:T.textMuted }}>
                  {wv.betreff1}
                </span>
              )}

              {fehler && (
                <div style={{ width:"100%", background:"#fff1f2", border:"1px solid #fca5a5", borderRadius:7, padding:"6px 12px", fontFamily:T.fontBody, fontSize:"0.85rem", color:"#9f1239" }}>
                  {fehler}
                </div>
              )}

              <button onClick={generieren} disabled={laedt}
                style={{ marginTop:4, display:"flex", alignItems:"center", gap:7,
                  padding:"9px 16px",
                  background: erstellt ? "#f0fdf4" : T.navy,
                  color:      erstellt ? T.greenText : T.white,
                  border:     erstellt ? "1.5px solid #6ee7b7" : "none",
                  borderRadius:8, fontFamily:T.fontBody, fontSize:"0.935rem", fontWeight:600,
                  cursor: laedt ? "default" : "pointer", opacity: laedt ? 0.7 : 1, transition:"all 0.2s",
                }}>
                {laedt
                  ? <><div style={{ width:13, height:13, border:"2px solid rgba(255,255,255,0.3)", borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/> Erstellen …</>
                  : erstellt
                  ? <><svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="7" fill={T.green}/><path d="M4 7L6 9L10 5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg> Erstellt – erneut generieren</>
                  : <>📄 Sachstandsanfrage generieren &amp; herunterladen</>}
              </button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}



export default RaMicroSachstandsCard;
