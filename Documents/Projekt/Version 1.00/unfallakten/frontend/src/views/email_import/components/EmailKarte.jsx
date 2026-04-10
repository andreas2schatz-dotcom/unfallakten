import React, { useState } from "react";
import T from "../../../config/theme.js";
import Ic from "../../../config/icons.jsx";
import { MATCH_LABELS, EMAIL_TYP_LABELS } from "../../../config/constants.js";
import { emailImport as apiEmail } from "../../../api.js";
import AnhangZeile from "./AnhangZeile.jsx";
import InAkteButton from "./InAkteButton.jsx";
import RegulierungBestaetigenButton from "./RegulierungBestaetigenButton.jsx";

function EmailKarte({ entry: e, seite, onOpenAkte, zuordnungState: zs,
                      onOeffneZuordnung, onSchliessZuordnung, onSucheAkten, onZuordnen,
                      onInAkteImportiert, letzter }) {
  const [expanded, setExpanded]   = useState(false);
  const [anhaenge, setAnhaenge]   = useState(null);
  const [bodyText, setBodyText]   = useState(null);
  const [anhLaedt, setAnhLaedt]   = useState(false);

  const ladeAnhaenge = async () => {
    if (anhaenge !== null || anhLaedt) return;
    setAnhLaedt(true);
    try {
      const meta = await apiEmail.meta(e.id);
      setAnhaenge(meta?.anhaenge || []);
      setBodyText(meta?.body_text || "");
    } catch {
      setAnhaenge([]);
      setBodyText("");
    } finally {
      setAnhLaedt(false);
    }
  };

  const handleExpand = () => {
    const neu = !expanded;
    setExpanded(neu);
    if (neu) ladeAnhaenge();
  };

  const oeffneAnhang = async (dok) => {
    try {
      await apiEmail.anhangOeffnen(e.id, dok.index ?? 0, dok.name || dok.dateiname || "anhang");
    } catch {
      alert("Anhang konnte nicht geöffnet werden.");
    }
  };

  const mc  = e.match_methode ? MATCH_LABELS[e.match_methode] : null;
  const et  = (e.email_typ && e.email_typ !== "sonstiges")
              ? EMAIL_TYP_LABELS[e.email_typ] : null;
  const erkannt = e.erkannt_az || e.erkannt_kfz;

  return (
    <div style={{ borderBottom: letzter ? "none" : `1px solid ${T.borderSoft}` }}>
      <div
        onClick={handleExpand}
        style={{ padding:"11px 14px", cursor:"pointer", transition:"background 0.1s",
          background: expanded ? T.accentPale : "transparent" }}
        onMouseEnter={ev => { if (!expanded) ev.currentTarget.style.background = T.surface; }}
        onMouseLeave={ev => { if (!expanded) ev.currentTarget.style.background = "transparent"; }}>

        <div style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
          <div style={{ width:8, height:8, borderRadius:"50%", background: !e.als_gelesen ? T.blue : "transparent",
            flexShrink:0, marginTop:5 }}/>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:3, flexWrap:"wrap" }}>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem",
                fontWeight: e.als_gelesen ? 400 : 600, color:T.text,
                overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", maxWidth:280 }}>
                {e.von_name || e.absender || e.absender_email || "Unbekannt"}
              </span>
              {e.versicherer_name && (
                <span style={{ display:"inline-flex", alignItems:"center",
                  background:`${T.amber}18`, color:T.amber,
                  border:`1px solid ${T.amber}35`, borderRadius:10,
                  padding:"1px 8px", fontSize:"0.785rem", fontWeight:700,
                  flexShrink:0, fontFamily:"ui-monospace,monospace" }}>
                  {e.versicherer_kuerzel || e.versicherer_name}
                </span>
              )}
              {mc && (
                <span style={{ display:"inline-flex", alignItems:"center", background:`${mc.color}15`,
                  color:mc.color, border:`1px solid ${mc.color}30`, borderRadius:10,
                  padding:"1px 7px", fontSize:"0.795rem", fontWeight:600, flexShrink:0 }}>
                  {mc.label}
                </span>
              )}
              {et && (
                <span style={{ display:"inline-flex", alignItems:"center", gap:3,
                  background:`${et.color}12`, color:et.color,
                  border:`1px solid ${et.color}30`, borderRadius:10,
                  padding:"1px 8px", fontSize:"0.785rem", fontWeight:600, flexShrink:0 }}>
                  {et.icon} {et.label}
                </span>
              )}
              {erkannt && (
                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.845rem",
                  fontWeight:600, color:T.navy, flexShrink:0 }}>{erkannt}</span>
              )}
              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem",
                color:T.textMuted, marginLeft:"auto", flexShrink:0, whiteSpace:"nowrap" }}>
                {e.empfangen_am ? String(e.empfangen_am).slice(0,16) : ""}
              </span>
            </div>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
              color:T.textMid, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
              {e.betreff || <span style={{ color:T.textMuted, fontStyle:"italic" }}>(kein Betreff)</span>}
            </div>
            {(e.anhaenge_anzahl || 0) > 0 && (
              <div style={{ display:"flex", alignItems:"center", gap:5, marginTop:4 }}>
                <span style={{ color:T.textFaint, display:"flex" }}>{Ic.attach}</span>
                <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.845rem",
                  color:T.textMuted }}>{e.anhaenge_anzahl} Anhang</span>
              </div>
            )}
          </div>
          <svg viewBox="0 0 24 24" fill={T.textFaint} onClick={handleExpand} style={{ width:14, height:14, flexShrink:0, marginTop:3,
            transform: expanded ? "rotate(180deg)" : "none", transition:"transform 0.2s", cursor:"pointer" }}>
            <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
          </svg>
        </div>
      </div>

      {expanded && (
        <div style={{ padding:"0 14px 14px 32px", background:T.accentPale,
          borderTop:`1px solid ${T.border}` }}>

          {seite === "zugeordnet" && e.akte_az && (
            <div style={{ paddingTop:12 }}>
              <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
                <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>Akte:</span>
                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.945rem",
                  fontWeight:700, color:T.navy }}>{e.akte_az}</span>
                <button onClick={() => onOpenAkte(e)}
                  style={{ display:"flex", alignItems:"center", gap:5, padding:"5px 12px",
                    background:T.navy, color:T.white, border:"none", borderRadius:6,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                    fontWeight:600, cursor:"pointer" }}>
                  {Ic.akte} Akte öffnen
                </button>
                {e.manuell_zugeordnet ? (
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                    color:T.textMuted, fontStyle:"italic" }}>manuell zugeordnet</span>
                ) : null}
              </div>
              <InAkteButton entry={e} onImportiert={(res) => onInAkteImportiert(e.id, res)} onOpenAkte={onOpenAkte} />
              {e.email_typ === "regulierungsschreiben" && (
                <RegulierungBestaetigenButton entry={e} onOpenAkte={onOpenAkte} />
              )}
            </div>
          )}

          {seite === "nicht_zugeordnet" && (
            <div style={{ paddingTop:12 }}>
              {!zs?.offen ? (
                <div style={{ display:"flex", gap:8 }}>
                  <button onClick={() => onOeffneZuordnung(e.id)}
                    style={{ display:"flex", alignItems:"center", gap:6, padding:"6px 14px",
                      background:T.navy, color:T.white, border:"none", borderRadius:6,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                      fontWeight:600, cursor:"pointer" }}>
                    {Ic.search} Akte zuordnen
                  </button>
                  <button
                    style={{ display:"flex", alignItems:"center", gap:6, padding:"6px 14px",
                      background:T.white, color:T.textMuted, border:`1px solid ${T.border}`,
                      borderRadius:6, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                      fontWeight:600, cursor:"not-allowed", opacity:0.5 }}
                    title="Feature in Entwicklung">
                    {Ic.plus} Neue Akte anlegen
                  </button>
                </div>
              ) : (
                <div style={{ background:T.white, border:`1px solid ${T.border}`,
                  borderRadius:8, overflow:"hidden", maxWidth:420 }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8,
                    padding:"8px 12px", borderBottom:`1px solid ${T.border}` }}>
                    <span style={{ color:T.textFaint, display:"flex" }}>{Ic.search}</span>
                    <input
                      autoFocus
                      placeholder="AZ, Mandant oder KFZ suchen …"
                      value={zs?.suche || ""}
                      onChange={ev => onSucheAkten(e.id, ev.target.value)}
                      style={{ flex:1, border:"none", outline:"none", background:"transparent",
                        fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem", color:T.text }}
                    />
                    {zs?.laedt && (
                      <div style={{ width:12, height:12, border:"2px solid rgba(0,0,0,0.15)",
                        borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/>
                    )}
                    <button onClick={() => onSchliessZuordnung(e.id)}
                      style={{ background:"none", border:"none", cursor:"pointer",
                        color:T.textFaint, display:"flex", padding:2 }}>{Ic.x}</button>
                  </div>
                  {(zs?.treffer || []).length > 0 ? (
                    <div style={{ maxHeight:200, overflowY:"auto" }}>
                      {(zs.treffer || []).map((a, ai) => (
                        <button key={ai}
                          onClick={() => onZuordnen(e, a.az)}
                          style={{ width:"100%", textAlign:"left", padding:"9px 14px",
                            background:"transparent", border:"none", borderBottom:`1px solid ${T.borderSoft}`,
                            cursor:"pointer", fontFamily:"'Figtree',sans-serif",
                            fontSize:"0.925rem", color:T.text, display:"flex",
                            alignItems:"center", gap:10 }}
                          onMouseEnter={ev => ev.currentTarget.style.background = T.accentPale}
                          onMouseLeave={ev => ev.currentTarget.style.background = "transparent"}>
                          <span style={{ fontFamily:"ui-monospace,monospace", fontWeight:700,
                            color:T.navy, flexShrink:0 }}>{a.az}</span>
                          {a.label !== a.az && (
                            <span style={{ color:T.textMuted, overflow:"hidden",
                              textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                              {a.label.replace(a.az, "").replace(/^[\s–-]+/, "")}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  ) : zs?.suche?.length >= 2 && !zs?.laedt ? (
                    <div style={{ padding:"12px 14px", fontFamily:"'Figtree',sans-serif",
                      fontSize:"0.925rem", color:T.textMuted }}>
                      Keine Akte gefunden für „{zs.suche}"
                    </div>
                  ) : (
                    <div style={{ padding:"10px 14px", fontFamily:"'Figtree',sans-serif",
                      fontSize:"0.875rem", color:T.textMuted }}>
                      Mindestens 2 Zeichen eingeben …
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {seite === "zugeordnet" && (e.anhaenge_anzahl || 0) > 0 && (
            <div style={{ marginTop:10, display:"flex", alignItems:"center", gap:8,
              background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:7,
              padding:"7px 12px", fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.green }}>
              {Ic.check}
              <span>
                <strong>{e.anhaenge_anzahl} Anhang{e.anhaenge_anzahl > 1 ? "hänge" : ""}</strong> automatisch in Akte gespeichert
              </span>
            </div>
          )}

          {bodyText && (
            <div style={{ marginTop:12 }}>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                fontWeight:600, color:T.textMuted, textTransform:"uppercase",
                letterSpacing:"0.06em", marginBottom:6 }}>E-Mail-Text</div>
              <div style={{ background:T.white, border:`1px solid ${T.border}`,
                borderRadius:7, padding:"10px 12px",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                color:T.textMid, whiteSpace:"pre-wrap", maxHeight:180,
                overflowY:"auto", lineHeight:1.5 }}>
                {bodyText}
              </div>
            </div>
          )}

          {(e.anhaenge_anzahl || 0) > 0 && (
            <div style={{ marginTop:12 }}>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:6 }}>
                Anhänge ({e.anhaenge_anzahl})
              </div>
              {anhLaedt ? (
                <div style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 0",
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>
                  <div style={{ width:12, height:12, border:"2px solid rgba(0,0,0,0.15)",
                    borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/>
                  Lade Anhänge …
                </div>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                  {anhaenge === null
                    ? Array.from({ length: Number(e.anhaenge_anzahl)||0 }).map((_,ai) => (
                        <AnhangZeile key={ai} name={`Anhang ${ai+1}`} groesse={null}
                          isPdf={true} isImg={false} kannOeffnen={true}
                          onClick={() => oeffneAnhang({ index:ai })} />
                      ))
                    : (anhaenge||[]).map(dok => {
                        const isPdf = dok.ext==='pdf' || (dok.name||'').toLowerCase().endsWith('.pdf');
                        const isImg = ['jpg','jpeg','png'].includes(dok.ext||'');
                        return (
                          <AnhangZeile key={dok.index}
                            name={dok.name||`Anhang ${(dok.index||0)+1}`}
                            groesse={dok.groesse} isPdf={isPdf} isImg={isImg}
                            kannOeffnen={dok.oeffenbar}
                            onClick={() => oeffneAnhang(dok)} />
                        );
                      })
                  }
                </div>
              )}
            </div>
          )}

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"1rem", marginTop:12 }}>
            <div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:6 }}>
                E-Mail-Details
              </div>
              {[
                ["Von",      `${e.von_name || ""} ${e.absender ? `<${e.absender}>` : ""}`.trim()],
                ["Betreff",  e.betreff || "(kein Betreff)"],
                ["Empfangen",e.empfangen_am || "–"],
              ].map(([l,v]) => (
                <div key={l} style={{ display:"flex", gap:8, marginBottom:5 }}>
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                    color:T.textMuted, width:70, flexShrink:0 }}>{l}</span>
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                    color:T.text, wordBreak:"break-all" }}>{v}</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:6 }}>
                Parser-Ergebnis
              </div>
              {[
                ["Erkanntes AZ",   e.erkannt_az || "–"],
                ["Erkanntes KFZ",  e.erkannt_kfz || "–"],
                ["Match-Methode",  e.match_methode ? (MATCH_LABELS[e.match_methode]?.label || e.match_methode) : "Kein Match"],
              ].map(([l,v]) => (
                <div key={l} style={{ display:"flex", gap:8, marginBottom:5 }}>
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                    color:T.textMuted, width:110, flexShrink:0 }}>{l}</span>
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.895rem",
                    color:T.text, fontWeight: v !== "–" && v !== "Kein Match" ? 600 : 400 }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default EmailKarte;
