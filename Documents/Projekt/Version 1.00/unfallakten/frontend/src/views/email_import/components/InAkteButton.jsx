import React, { useState } from "react";
import T from "../../../config/theme.js";
import Ic from "../../../config/icons.jsx";
import { request } from "../../../api.js";

function InAkteButton({ entry: e, onImportiert, onOpenAkte }) {
  const [laedt, setLaedt]         = useState(false);
  const [fehler, setFehler]       = useState(null);
  const [bestaetigen, setBestaetigen] = useState(false);

  if (!e.akte_az) return null;

  const doImport = async (erzwingen = false) => {
    setLaedt(true); setFehler(null); setBestaetigen(false);
    try {
      const res = await request(`/email/import/log/${e.id}/in-akte`, {
        method: "POST",
        body: JSON.stringify({ erzwingen }),
        headers: { "Content-Type": "application/json" },
      });
      if (res?.ok) {
        onImportiert(res);
        if (onOpenAkte) onOpenAkte(e);
      } else {
        setFehler(res?.fehler || "Unbekannter Fehler");
      }
    } catch (err) {
      setFehler(err?.message || "Fehler beim Import");
    } finally {
      setLaedt(false);
    }
  };

  if (e.in_akte_importiert) {
    return (
      <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
        <div style={{ display:"flex", alignItems:"center", gap:7,
          background:T.greenBg, border:`1px solid ${T.green}33`,
          borderRadius:7, padding:"6px 12px", fontFamily:"'Figtree',sans-serif",
          fontSize:"0.875rem", color:T.green }}>
          {Ic.check}
          <span style={{ flex:1 }}>In Akte importiert{e.in_akte_importiert_am ? ` · ${e.in_akte_importiert_am}` : ""}</span>
          <button onClick={() => setBestaetigen(true)} disabled={laedt}
            style={{ background:"none", border:`1px solid ${T.green}55`, borderRadius:5,
              padding:"2px 9px", fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
              color:T.green, cursor:"pointer", flexShrink:0 }}>
            ↺ Erneut
          </button>
        </div>
        {bestaetigen && (
          <div style={{ background:T.amberBg, border:`1px solid ${T.amber}44`,
            borderRadius:7, padding:"10px 12px", fontFamily:"'Figtree',sans-serif",
            fontSize:"0.855rem", color:T.textMid }}>
            <div style={{ fontWeight:600, marginBottom:6, color:T.amber }}>
              ⚠ Bereits importiert – erneut importieren?
            </div>
            <div style={{ marginBottom:10, fontSize:"0.835rem", color:T.textMuted }}>
              Anhänge und E-Mail-Datei werden erneut in den Dokumenten-Reiter der Akte gespeichert.
            </div>
            <div style={{ display:"flex", gap:8 }}>
              <button onClick={() => doImport(true)} disabled={laedt}
                style={{ padding:"5px 14px", background:T.amber, color:T.white,
                  border:"none", borderRadius:6, fontFamily:"'Figtree',sans-serif",
                  fontSize:"0.855rem", fontWeight:600, cursor:"pointer" }}>
                {laedt ? "Wird importiert …" : "Ja, erneut importieren"}
              </button>
              <button onClick={() => setBestaetigen(false)}
                style={{ padding:"5px 12px", background:"none", color:T.textMuted,
                  border:`1px solid ${T.border}`, borderRadius:6,
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", cursor:"pointer" }}>
                Abbrechen
              </button>
            </div>
          </div>
        )}
        {fehler && (
          <div style={{ fontSize:"0.845rem", color:T.red, fontFamily:"'Figtree',sans-serif" }}>{fehler}</div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
      <button onClick={() => doImport(false)} disabled={laedt}
        style={{ display:"flex", alignItems:"center", gap:7, padding:"6px 14px",
          background: laedt ? T.navyMid : T.navy, color:T.white,
          border:"none", borderRadius:7, fontFamily:"'Figtree',sans-serif",
          fontSize:"0.875rem", fontWeight:600,
          cursor: laedt ? "default" : "pointer", transition:"background 0.15s" }}>
        {laedt
          ? <><div style={{ width:12, height:12, border:"2px solid rgba(255,255,255,0.3)",
              borderTopColor:"white", borderRadius:"50%",
              animation:"spin 0.7s linear infinite" }}/> Wird importiert …</>
          : <>{Ic.attach} In Akte importieren</>}
      </button>
      {fehler && (
        <div style={{ fontSize:"0.845rem", color:T.red, fontFamily:"'Figtree',sans-serif" }}>{fehler}</div>
      )}
    </div>
  );
}

export default InAkteButton;
