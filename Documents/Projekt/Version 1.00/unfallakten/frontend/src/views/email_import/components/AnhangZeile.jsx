import React, { useState } from "react";
import T from "../../../config/theme.js";
import Ic from "../../../config/icons.jsx";
import { fmtSize } from "../../../config/utils.js";

function AnhangZeile({ name, groesse, isPdf, isImg, kannOeffnen, onClick }) {
  const [laedt, setLaedt] = useState(false);
  const handleClick = async () => {
    if (!onClick || !kannOeffnen) return;
    setLaedt(true);
    try { await onClick(); }
    catch { alert("Anhang konnte nicht geöffnet werden."); }
    finally { setLaedt(false); }
  };
  return (
    <div onClick={handleClick}
      onMouseEnter={ev => { if (kannOeffnen) ev.currentTarget.style.background = T.accentPale; }}
      onMouseLeave={ev => { ev.currentTarget.style.background = T.white; }}
      style={{ display:"flex", alignItems:"center", gap:10,
        background:T.white, border:`1px solid ${T.border}`, borderRadius:7,
        padding:"7px 12px", cursor:kannOeffnen?"pointer":"default" }}>
      <span style={{ color:isPdf?T.red:isImg?T.blue:T.textMuted, display:"flex", flexShrink:0 }}>
        {isPdf ? Ic.pdf : Ic.attach}
      </span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
          fontWeight:600, color:kannOeffnen?T.navy:T.text,
          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
          textDecoration:kannOeffnen?"underline":"none",
          textDecorationColor:"rgba(27,42,74,0.3)" }}>{name}</div>
        {groesse && <div style={{ fontFamily:"ui-monospace,monospace",
          fontSize:"0.78rem", color:T.textMuted }}>{fmtSize(groesse)}</div>}
      </div>
      {laedt && <div style={{ width:12, height:12, border:"2px solid rgba(0,0,0,0.15)",
        borderTopColor:T.navy, borderRadius:"50%",
        animation:"spin 0.7s linear infinite", flexShrink:0 }}/>}
      {!laedt && kannOeffnen && <span style={{ fontSize:"0.78rem", color:T.textMuted,
        fontFamily:"'Figtree',sans-serif", flexShrink:0 }}>
        {isPdf ? "PDF öffnen" : isImg ? "Bild öffnen" : "Öffnen"}</span>}
    </div>
  );
}

export default AnhangZeile;
