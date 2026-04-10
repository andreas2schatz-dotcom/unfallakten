import React, { useState } from "react";
import T from "../../../config/theme.js";

function FragebogenErstkontaktKarte({ eintrag, onAlsBearbeitet }) {
  const [laedt, setLaedt] = useState(false);

  const handleBearbeitet = async () => {
    setLaedt(true);
    try { await onAlsBearbeitet(eintrag.id); }
    finally { setLaedt(false); }
  };

  const datum = eintrag.empfangen_am
    ? new Date(eintrag.empfangen_am).toLocaleDateString("de-DE",
        { day:"2-digit", month:"2-digit", year:"numeric" })
    : "–";

  return (
    <div style={{
      background:T.white, border:`1px solid ${T.border}`, borderRadius:9,
      padding:"0.9rem 1rem", marginBottom:"0.5rem",
      boxShadow:"0 1px 4px rgba(0,0,0,0.04)",
    }}>
      {/* Name + Badge */}
      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:"0.35rem" }}>
        <div style={{
          fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem",
          fontWeight:700, color:T.navy, flex:1, minWidth:0,
          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
        }}>
          {eintrag.mandant_name || eintrag.absender_name || "Unbekannt"}
        </div>
        <span style={{
          background:T.amberBg, color:T.amber, border:`1px solid ${T.amber}44`,
          borderRadius:10, padding:"2px 8px",
          fontSize:"0.77rem", fontWeight:700, fontFamily:"ui-monospace,monospace",
          flexShrink:0,
        }}>NEU</span>
      </div>

      {/* E-Mail */}
      <div style={{
        fontFamily:"ui-monospace,monospace", fontSize:"0.82rem",
        color:T.textMuted, marginBottom:"0.45rem",
        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
      }}>
        {eintrag.mandant_email || eintrag.absender_email || "–"}
      </div>

      {/* Metazeile: KFZ · Unfalltag · Eingangsdatum */}
      <div style={{
        display:"flex", gap:12, marginBottom:"0.7rem",
        flexWrap:"wrap", alignItems:"center",
      }}>
        {eintrag.kfz_kennzeichen && (
          <span style={{
            fontFamily:"ui-monospace,monospace", fontSize:"0.84rem",
            color:T.navy, fontWeight:600,
            background:"rgba(27,42,74,0.06)", borderRadius:5,
            padding:"2px 7px",
          }}>{eintrag.kfz_kennzeichen}</span>
        )}
        {eintrag.schadentag && (
          <span style={{
            fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", color:T.textMid,
          }}>Unfall: {eintrag.schadentag}</span>
        )}
        <span style={{
          fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", color:T.textMuted,
          marginLeft:"auto",
        }}>{datum}</span>
      </div>

      {/* Buttons */}
      <div style={{ display:"flex", gap:7 }}>
        <button onClick={handleBearbeitet} disabled={laedt}
          style={{
            padding:"5px 12px", background:"none",
            border:`1px solid ${T.border}`, borderRadius:6,
            fontFamily:"'Figtree',sans-serif", fontSize:"0.84rem",
            color:T.textMid, cursor:laedt ? "default" : "pointer",
          }}>
          {laedt ? "…" : "Als bearbeitet"}
        </button>
        <button disabled
          title="Akte-Anlage – geplant in PRD-22d Session 5"
          style={{
            padding:"5px 12px",
            background:T.navy, border:"none", borderRadius:6,
            fontFamily:"'Figtree',sans-serif", fontSize:"0.84rem",
            fontWeight:600, color:"rgba(255,255,255,0.35)",
            cursor:"not-allowed",
          }}>
          Akte anlegen
        </button>
      </div>
    </div>
  );
}

export default FragebogenErstkontaktKarte;
