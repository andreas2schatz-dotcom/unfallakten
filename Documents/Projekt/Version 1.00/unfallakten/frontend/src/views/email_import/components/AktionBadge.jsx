import React, { useState } from "react";
import T from "../../../config/theme.js";
import { AKTION_LABELS } from "../../../config/constants.js";
import { emailImport as apiEmail } from "../../../api.js";

function AktionBadge({ az, aktion, onErledigt }) {
  const [laedt, setLaedt] = useState(false);
  if (!aktion?.aktiv) return null;
  const info = AKTION_LABELS[aktion.typ] || { label:"Aktion erforderlich", icon:"⚠️" };
  const erledigt = async () => {
    setLaedt(true);
    try { await apiEmail.aktionErledigt(az); if (onErledigt) onErledigt(); }
    catch {} finally { setLaedt(false); }
  };
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10,
      background:"rgba(245,158,11,0.15)", border:"1px solid rgba(245,158,11,0.4)",
      borderRadius:8, padding:"8px 14px", marginBottom:"0.75rem",
      fontFamily:"'IBM Plex Sans',sans-serif" }}>
      <span style={{ fontSize:"1.1rem" }}>{info.icon}</span>
      <div style={{ flex:1 }}>
        <div style={{ fontWeight:700, color:T.amber, fontSize:"0.925rem" }}>Aktion erforderlich</div>
        <div style={{ fontSize:"0.855rem", color:T.textMid }}>
          {info.label}{aktion.seit ? ` · seit ${String(aktion.seit).slice(0,16)}` : ""}
        </div>
      </div>
      <button onClick={erledigt} disabled={laedt}
        style={{ padding:"5px 12px", background:T.amber, color:T.white,
          border:"none", borderRadius:6, fontFamily:"'IBM Plex Sans',sans-serif",
          fontSize:"0.845rem", fontWeight:600, cursor:laedt?"default":"pointer" }}>
        {laedt ? "…" : "Als erledigt markieren"}
      </button>
    </div>
  );
}

export default AktionBadge;
