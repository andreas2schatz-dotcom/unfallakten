import React, { useState } from "react";
import T from "../../../config/theme.js";
import Ic from "../../../config/icons.jsx";
import { emailImport as apiEmail } from "../../../api.js";

function RegulierungBestaetigenButton({ entry: e, onOpenAkte }) {
  const [laedt, setLaedt]   = useState(false);
  const [fertig, setFertig] = useState(false);
  const [fehler, setFehler] = useState(null);

  if (fertig) {
    return (
      <div style={{ display:"flex", alignItems:"center", gap:7, marginTop:8,
        background:T.greenBg, border:`1px solid ${T.green}33`,
        borderRadius:7, padding:"6px 12px", fontFamily:"'Figtree',sans-serif",
        fontSize:"0.875rem", color:T.green }}>
        {Ic.check} Regulierung als Abrechnung übernommen
      </div>
    );
  }

  const bestaetigen = async () => {
    setLaedt(true); setFehler(null);
    try {
      const res = await apiEmail.regulierungBestaetigen(e.id);
      if (res?.ok) {
        setFertig(true);
        if (onOpenAkte) onOpenAkte(e);
      } else {
        setFehler(res?.fehler || "Unbekannter Fehler");
      }
    } catch (err) {
      setFehler(err?.message || "Fehler");
    } finally {
      setLaedt(false);
    }
  };

  return (
    <div style={{ marginTop:8 }}>
      <button onClick={bestaetigen} disabled={laedt}
        style={{ display:"flex", alignItems:"center", gap:7, padding:"6px 14px",
          background: laedt ? T.navyMid : T.green, color:T.white,
          border:"none", borderRadius:7, fontFamily:"'Figtree',sans-serif",
          fontSize:"0.875rem", fontWeight:600,
          cursor: laedt ? "default" : "pointer", transition:"background 0.15s" }}>
        {laedt
          ? <><div style={{ width:12, height:12, border:"2px solid rgba(255,255,255,0.3)",
              borderTopColor:"white", borderRadius:"50%",
              animation:"spin 0.7s linear infinite" }}/> Wird übernommen …</>
          : <>📄 Als Regulierung übernehmen</>}
      </button>
      {fehler && (
        <div style={{ marginTop:5, fontFamily:"'Figtree',sans-serif",
          fontSize:"0.845rem", color:T.red }}>{fehler}</div>
      )}
    </div>
  );
}

export default RegulierungBestaetigenButton;
