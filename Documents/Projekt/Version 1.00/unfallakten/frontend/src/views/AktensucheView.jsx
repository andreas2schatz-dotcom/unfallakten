import React, { useState } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { SUCHMODUS_LABEL } from "../config/constants.js";
import { Card, Btn } from "../components/common.jsx";
import {
  aktensuche as apiAktensuche,
} from "../api.js";

function AktensucheView({ onOpenAkte }) {
  const [az, setAz]         = useState("");
  const [kz, setKz]         = useState("");
  const [tag, setTag]       = useState("");
  const [loading, setLoad]  = useState(false);
  const [treffer, setTref]  = useState(null);
  const [suchmodus, setMod] = useState("");
  const [fehler, setFeh]    = useState("");
  const [ramicroAktiv, setRA] = useState(true);

  const suchen = async (feld) => {
    const azQ = az.trim(), kzQ = kz.trim(), tagQ = tag.trim();
    // Nur das gerade ausgefüllte / angesteuerte Feld auswerten
    const nutzAz  = feld === "az"  && azQ;
    const nutzKz  = feld === "kz"  && kzQ;
    const nutzTag = feld === "tag" && tagQ;
    if (!nutzAz && !nutzKz && !nutzTag) return;
    setLoad(true); setFeh(""); setTref(null); setMod("");
    try {
      let res;
      if (nutzKz)       res = await apiAktensuche.nachKennzeichen(kzQ);
      else if (nutzTag) res = await apiAktensuche.nachSchadentag(tagQ);
      else              res = await apiAktensuche.suchen(azQ);
      setTref(res.treffer || []);
      setMod(res.suchmodus || "");
      setRA(res.ramicro_aktiv !== false);
      if (res.hinweis) setFeh(res.hinweis);
    } catch (e) {
      setFeh(e?.message || "Fehler bei der Suche.");
      setTref([]);
    } finally {
      setLoad(false);
    }
  };

  const kachelStyle = {
    flex:1, background:T.white, border:`1px solid ${T.border}`,
    borderRadius:10, padding:"1rem 1.1rem",
    boxShadow:"0 1px 4px rgba(0,0,0,0.04)",
  };

  const labelStyle = {
    fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
    fontWeight:600, color:T.textMid, letterSpacing:"0.06em",
    textTransform:"uppercase", display:"block", marginBottom:6,
  };

  const inpStyle = {
    width:"100%", padding:"9px 11px", border:`1.5px solid ${T.border}`,
    borderRadius:7, fontFamily:"ui-monospace,monospace", fontSize:"0.975rem",
    color:T.text, background:T.white, outline:"none",
    boxSizing:"border-box", transition:"border-color 0.15s",
  };

  const hint = {
    marginTop:5, fontFamily:"'Figtree',sans-serif",
    fontSize:"0.75rem", color:T.textFaint, lineHeight:1.4,
  };

  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden", background:T.offWhite }}>

      {/* Header */}
      <div style={{ background:T.white, borderBottom:`1px solid ${T.border}`, padding:"1.1rem 1.75rem", flexShrink:0 }}>
        <h1 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.45rem", fontWeight:700, color:T.navy, margin:"0 0 3px" }}>
          Aktensuche
        </h1>
        <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", color:T.textMuted, margin:0 }}>
          Direktsuche in der RA-Micro Datenbank · Alle aktiven Akten
        </p>
      </div>

      {/* Drei Suchkacheln nebeneinander */}
      <div style={{ padding:"1.25rem 1.75rem", flexShrink:0, display:"flex", gap:"1rem" }}>

        {/* Kachel 1: AZ / Name */}
        <div style={kachelStyle}>
          <label style={labelStyle}>
            Aktenzeichen oder Name
          </label>
          <input
            value={az} onChange={e => setAz(e.target.value)}
            onKeyDown={e => e.key==="Enter" && suchen("az")}
            placeholder="42/25  ·  Müller"
            style={inpStyle}
            onFocus={e => e.target.style.borderColor=T.accent}
            onBlur={e  => e.target.style.borderColor=T.border}
          />
          <div style={hint}>Mit „/" → Aktenzeichen · Ohne „/" → Mandant &amp; Gegner</div>
          <div style={{ marginTop:"0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("az")} disabled={loading || !az.trim()} style={{ width:"100%" }}>
              {loading && suchmodus==="" ? "…" : "🔍 Suchen"}
            </Btn>
          </div>
        </div>

        {/* Kachel 2: KFZ */}
        <div style={kachelStyle}>
          <label style={labelStyle}>
            KFZ-Kennzeichen
          </label>
          <input
            value={kz} onChange={e => setKz(e.target.value)}
            onKeyDown={e => e.key==="Enter" && suchen("kz")}
            placeholder="OF-NM 444"
            style={inpStyle}
            onFocus={e => e.target.style.borderColor=T.accent}
            onBlur={e  => e.target.style.borderColor=T.border}
          />
          <div style={hint}>Sucht via WDM varM-KZ · Teileingabe möglich</div>
          <div style={{ marginTop:"0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("kz")} disabled={loading || !kz.trim()} style={{ width:"100%" }}>
              🔍 Suchen
            </Btn>
          </div>
        </div>

        {/* Kachel 3: Schadentag */}
        <div style={kachelStyle}>
          <label style={labelStyle}>
            Schadentag
          </label>
          <input
            type="date"
            value={tag} onChange={e => setTag(e.target.value)}
            onKeyDown={e => e.key==="Enter" && suchen("tag")}
            style={{ ...inpStyle, fontFamily:"'Figtree',sans-serif" }}
            onFocus={e => e.target.style.borderColor=T.accent}
            onBlur={e  => e.target.style.borderColor=T.border}
          />
          <div style={hint}>Alle Unfälle an diesem Tag · WDM varU-TAG</div>
          <div style={{ marginTop:"0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("tag")} disabled={loading || !tag.trim()} style={{ width:"100%" }}>
              🔍 Suchen
            </Btn>
          </div>
        </div>
      </div>

      {/* Hinweis / Fehler */}
      {fehler && (
        <div style={{ margin:"0 1.75rem 0.75rem", padding:"9px 14px",
          background: ramicroAktiv ? T.redBg : T.amberBg,
          border:`1px solid ${ramicroAktiv ? T.red : T.amber}44`,
          borderRadius:8, fontFamily:"'Figtree',sans-serif",
          fontSize:"0.855rem", color: ramicroAktiv ? T.red : T.amber }}>
          {ramicroAktiv ? "⚠" : "ℹ"} {fehler}
        </div>
      )}

      {/* Ergebnisliste */}
      {treffer !== null && (
        <div style={{ flex:1, overflowY:"auto", padding:"0 1.75rem 1.75rem" }}>
          {treffer.length === 0 && !fehler ? (
            <div style={{ textAlign:"center", padding:"3rem 0", color:T.textFaint, fontFamily:"'Figtree',sans-serif" }}>
              <div style={{ fontSize:"2.5rem", marginBottom:8 }}>🗂</div>
              <div style={{ fontSize:"1rem" }}>Keine aktiven Akten gefunden</div>
              {suchmodus && <div style={{ fontSize:"0.85rem", marginTop:4 }}>Suchmodus: {SUCHMODUS_LABEL[suchmodus]}</div>}
            </div>
          ) : treffer.length > 0 && (
            <Card>
              <div style={{ padding:"0.65rem 1.4rem", display:"flex", justifyContent:"space-between", alignItems:"center", borderBottom:`1px solid ${T.border}` }}>
                <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em" }}>
                    Ergebnisse
                  </span>
                  {suchmodus && (
                    <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", background:T.accentPale, color:T.navy, border:`1px solid rgba(160,107,74,0.3)`, borderRadius:10, padding:"1px 8px" }}>
                      {SUCHMODUS_LABEL[suchmodus]}
                    </span>
                  )}
                </div>
                <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem", color:T.textFaint }}>
                  {treffer.length} Treffer
                </span>
              </div>
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead>
                  <tr style={{ background:T.surface }}>
                    {["Aktenzeichen","Bezeichnung","Sachbearb.",""].map((h,i) => (
                      <th key={i} style={{ padding:"8px 14px", textAlign:"left", fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:600, color:T.textMuted, letterSpacing:"0.06em", textTransform:"uppercase", borderBottom:`1px solid ${T.border}`, whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {treffer.map((t, i) => (
                    <tr key={t.az + i}
                      style={{ borderBottom:`1px solid ${T.borderSoft}`, background:i%2===0?T.white:"#fafaf8", transition:"background 0.12s", cursor:"default" }}
                      onMouseEnter={e => e.currentTarget.style.background="#f6f4ef"}
                      onMouseLeave={e => e.currentTarget.style.background=i%2===0?T.white:"#fafaf8"}>
                      <td style={{ padding:"10px 14px", whiteSpace:"nowrap" }}>
                        <button onClick={() => onOpenAkte({ id:t.az_roh, az:t.az, az_roh:t.az_roh, status:t.status||"offen", unfalldatum:t.unfalldatum||"", unfallort:t.unfallort||"", hq:t.haftungsquote||100, brutto:0 })}
                          style={{ background:"none", border:"none", padding:0, cursor:"pointer", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", fontWeight:600, color:T.navy, textDecoration:"underline", textDecorationColor:"rgba(27,42,74,0.3)" }}>
                          {t.az}
                        </button>
                      </td>
                      <td style={{ padding:"10px 14px", maxWidth:380 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", fontWeight:600, color:T.textMid, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                             title={t.kurzbezeichnung}>
                          {t.kurzbezeichnung || t.mandant || "–"}
                        </div>
                        {(t.bezeichnung || t.kennzeichen) && (
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.795rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", marginTop:2 }}
                               title={[t.bezeichnung, t.kennzeichen].filter(Boolean).join(" · ")}>
                            {t.bezeichnung}
                            {t.bezeichnung && t.kennzeichen && <span style={{ margin:"0 4px", color:T.textFaint }}>·</span>}
                            {t.kennzeichen && <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.775rem", fontWeight:700, color:T.blue }}>{t.kennzeichen}</span>}
                          </div>
                        )}
                      </td>
                      <td style={{ padding:"10px 14px", whiteSpace:"nowrap" }}>
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.85rem", background:T.accentPale, color:T.navy, border:`1px solid ${T.accentTrim}`, borderRadius:5, padding:"2px 7px", fontWeight:600 }}>
                          {t.sachbearbeiter || "–"}
                        </span>
                      </td>
                      <td style={{ padding:"10px 10px", textAlign:"right" }}>
                        <Btn size="sm" variant="secondary"
                          onClick={() => onOpenAkte({ id:t.az_roh, az:t.az, az_roh:t.az_roh, status:t.status||"offen", unfalldatum:t.unfalldatum||"", unfallort:t.unfallort||"", hq:t.haftungsquote||100, brutto:0 })}>
                          Öffnen
                        </Btn>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* Leerzustand */}
      {treffer === null && !loading && (
        <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", flexDirection:"column", color:T.textFaint, fontFamily:"'Figtree',sans-serif", gap:10 }}>
          <div style={{ fontSize:"3rem" }}>🔍</div>
          <div style={{ fontSize:"1rem" }}>Suchfeld ausfüllen und „Suchen" klicken</div>
          <div style={{ fontSize:"0.83rem", color:T.textFaint, textAlign:"center", maxWidth:380, lineHeight:1.6 }}>
            <code style={{ background:T.surface, padding:"1px 5px", borderRadius:4 }}>42/25</code> Aktenzeichen &nbsp;·&nbsp;
            <code style={{ background:T.surface, padding:"1px 5px", borderRadius:4 }}>Müller</code> Name &nbsp;·&nbsp;
            <code style={{ background:T.surface, padding:"1px 5px", borderRadius:4 }}>OF-NM 444</code> Kennzeichen &nbsp;·&nbsp;
            Datum über Kalender
          </div>
        </div>
      )}
    </div>
  );
}


export default AktensucheView;
