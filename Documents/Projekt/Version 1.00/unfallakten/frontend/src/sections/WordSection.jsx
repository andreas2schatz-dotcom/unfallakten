import React, { useState, useEffect } from "react";
import RaMicroSachstandsCard from './RaMicroSachstandsCard.jsx';
import StaDialog from "../components/StaDialog.jsx";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { fmtEuro } from "../config/utils.js";
import { Card, Toast } from "../components/common.jsx";
import {
  beteiligte as apiBeteiligte,
  word as apiWord,
} from "../api.js";

function WordSection({ akte, st, dispatch }) {
  const [loading,    setL]   = useState({});
  const [done,       setD]   = useState({});
  const [fehler,     setF]   = useState({});
  const [toast,      setT]   = useState("");
  const [staOffen,   setStaOffen] = useState(false);

  // Beteiligte laden wenn noch nicht im State
  useEffect(() => {
    if (st.beteiligte && st.beteiligte.length > 0) return;
    apiBeteiligte.liste(akte.id)
      .then(res => {
        const liste = res?.beteiligte || [];
        if (liste.length > 0) {
          dispatch({ type: "SET_BETEILIGTE", akteId: akte.id, beteiligte: liste });
        }
      })
      .catch(() => {});
  }, [akte.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Adressat-Dropdown: voreingestellt auf GHPV-Beteiligten
  const beteiligte_alle = st.beteiligte || [];
  // GHPV = gegnerische Haftpflichtversicherung, Fallback: erster Gegner
  const ghpv = beteiligte_alle.find(b =>
    ["GHPV","GHV","GBEV"].includes((b.kuerzel || "").toUpperCase())
  ) || beteiligte_alle.find(b => b.rolle === "gegner");
  // id kann null sein (RA-Micro-Fallback) → dann kein adressat_id mitsenden
  const [adressatId, setAdressatId] = useState(ghpv?.id ?? null);

  // Adressaten-Optionen: alle Gegner + Versicherungen
  // Adressaten: alle Gegner + Beteiligte mit Versicherung/Kürzel
  const adressatOptionen = beteiligte_alle.filter(b =>
    b.rolle === "gegner" ||
    (b.versicherung && b.versicherung.trim()) ||
    (b.kuerzel && b.kuerzel.trim())
  );

  const gen = async (typ, label) => {
    setL(p => ({...p,[typ]:true}));
    setD(p => ({...p,[typ]:false}));
    setF(p => ({...p,[typ]:null}));
    try {
      await apiWord.generieren(akte.id, typ, typ === "forderungsschreiben" ? (adressatId || null) : null);
      setD(p => ({...p,[typ]:true}));
      setT(`✓ ${label} erstellt.`);
      // Sofort-Download nach Generierung
      await apiWord.vorschau(akte.id, typ);
    } catch(err) {
      const msg = err?.message || String(err);
      setF(p => ({...p,[typ]: msg.slice(0,200)}));
      setT(`Fehler beim Erstellen: ${msg.slice(0,100)}`);
    } finally {
      setL(p => ({...p,[typ]:false}));
    }
  };

  const download = async (typ, label) => {
    try {
      await apiWord.vorschau(akte.id, typ);
    } catch(err) {
      setT(`Download fehlgeschlagen: ${String(err).slice(0,100)}`);
    }
  };

  const gegner    = st.beteiligte?.find(b => b.rolle==="gegner");
  const mandant   = st.beteiligte?.find(b => b.rolle==="mandant");
  // PRD-14: Brutto aus Backend-Berechnung (Single Source of Truth)
  const _ws_sd    = st.schaden || {};
  const liveBrutto = _ws_sd.abrechnungsberechnung?.gesamt_brutto
    ?? _ws_sd.gesamt_brutto
    ?? 0;
  const netto     = (st.schaden?.gesamt_brutto ?? liveBrutto) * (akte.hq/100);
  const gesamtReg = (st.abrechnungen||[]).reduce((s,ab) => s + (parseFloat(ab.gesamt_reguliert)||0), 0);

  const docs = [
    { typ:"forderungsschreiben",  label:"Forderungsschreiben",  icon:"⚖️", an:gegner?.versicherung||"Versicherung",  desc:"Schadensersatzforderung an den Haftpflichtversicherer gemäß §§ 7, 17, 18 StVG, § 115 VVG mit vollständiger Schadensaufstellung." },
    { typ:"abrechnungsuebersicht",label:"Abrechnungsübersicht", icon:"📊", an:mandant?.name||"Mandant",             desc:"Mandanteninformation über den aktuellen Regulierungsstand mit übersichtlicher Schadenaufstellung." },
  ];

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setT("")} />}
      {staOffen && (
        <StaDialog
          az={akte.az || akte.id}
          onClose={(generated) => { setStaOffen(false); if (generated) setT("✓ Sachstandsanfrage generiert."); }}
        />
      )}
      <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {/* Info-Banner */}
        <div style={{ background:T.navyDark, borderRadius:12, padding:"1rem 1.4rem", border:`1px solid ${T.accentTrim}`, display:"flex", alignItems:"center", gap:14, flexWrap:"wrap" }}>
          <div style={{ color:T.white }}>{Ic.word}</div>
          <div style={{ flex:1 }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem", fontWeight:600, color:T.white }}>Dokumente werden automatisch aus den Aktendaten generiert</div>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:"rgba(255,255,255,0.48)", marginTop:2 }}>Kanzlei-Design (Navy/Terrakotta) · DIN 5008 · Haftungsquote {akte.hq} %</div>
          </div>
          <div style={{ display:"flex", gap:16, flexShrink:0 }}>
            {[{l:"Forderung",v:fmtEuro(netto)},{l:"Reguliert",v:fmtEuro(gesamtReg)},{l:"Offen",v:fmtEuro(Math.max(0,netto-gesamtReg))}].map((s,i) => (
              <div key={i} style={{ textAlign:"center" }}>
                <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"1.025rem", fontWeight:600, color:T.white }}>{s.v}</div>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.795rem", color:"rgba(255,255,255,0.44)", marginTop:1 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Dokument-Kacheln */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(290px,1fr))", gap:"1.25rem" }}>
          {docs.map(doc => {
            const isL = loading[doc.typ];
            const isD = done[doc.typ];
            const err = fehler[doc.typ];
            return (
              <Card key={doc.typ} style={{ padding:"1.4rem", display:"flex", flexDirection:"column", gap:14, transition:"transform 0.15s,box-shadow 0.15s" }}
                onMouseEnter={e => { e.currentTarget.style.transform="translateY(-2px)"; e.currentTarget.style.boxShadow="0 8px 24px rgba(0,0,0,0.09)"; }}
                onMouseLeave={e  => { e.currentTarget.style.transform=""; e.currentTarget.style.boxShadow=""; }}>

                {/* Kachel-Kopf */}
                <div style={{ display:"flex", alignItems:"flex-start", gap:12 }}>
                  <div style={{ width:44, height:44, borderRadius:10, background:T.navy, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.475rem", flexShrink:0 }}>{doc.icon}</div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1rem", fontWeight:700, color:T.navy }}>{doc.label}</div>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem", color:T.textFaint, marginTop:2 }}>An: {doc.an}</div>
                  </div>
                  {/* Download-Icon nach erfolgreicher Generierung */}
                  {isD && !err && (
                    <button title={`${doc.label} erneut herunterladen`}
                      onClick={() => download(doc.typ, doc.label)}
                      style={{ flexShrink:0, display:"flex", alignItems:"center", gap:5, padding:"5px 10px", background:T.greenBg, border:`1px solid ${T.green}44`, borderRadius:7, cursor:"pointer", color:T.green, fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem", fontWeight:600, whiteSpace:"nowrap" }}>
                      {Ic.download} .docx
                    </button>
                  )}
                </div>

                {/* Beschreibung */}
                <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem", color:T.textMuted, lineHeight:1.65, margin:0 }}>{doc.desc}</p>

                {/* Fehlermeldung */}
                {err && (
                  <div style={{ background:T.redBg, border:`1px solid ${T.red}33`, borderRadius:7, padding:"8px 12px", fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", color:T.red }}>
                    ⚠ {err}
                  </div>
                )}

                {/* Adressat-Dropdown nur für Forderungsschreiben */}
                {doc.typ === "forderungsschreiben" && adressatOptionen.length > 0 && (
                  <div>
                    <label style={{ display:"block", fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600, color:T.textMuted, marginBottom:5, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                      Adressat
                    </label>
                    <select
                      value={adressatId ?? ""}
                      onChange={e => setAdressatId(e.target.value ? parseInt(e.target.value) : null)}
                      style={{ width:"100%", padding:"7px 10px", borderRadius:7, border:`1.5px solid ${T.border}`,
                        background:T.surface, color:T.text, fontFamily:"'Figtree',sans-serif",
                        fontSize:"0.875rem", cursor:"pointer", outline:"none" }}>
                      {adressatOptionen.map((b, idx) => {
                        const basis = b.versicherung || b.firma ||
                          `${b.vorname||""} ${b.name||""}`.trim() || `Beteiligter ${idx+1}`;
                        const rolle = b.kuerzel ? b.kuerzel.toUpperCase()
                          : b.rolle === "gegner" ? "Gegner" : b.rolle || "";
                        // id=null → RA-Micro-Eintrag, adressat_id nicht mitsenden (word_service lädt selbst)
                        return <option key={b.id ?? `ra_${idx}`} value={b.id ?? ""}>{basis}{rolle ? ` (${rolle})` : ""}</option>;
                      })}
                    </select>
                  </div>
                )}

                {/* Aktions-Button */}
                <div style={{ marginTop:"auto" }}>
                  <button onClick={() => gen(doc.typ, doc.label)} disabled={isL}
                    style={{ width:"100%", display:"flex", alignItems:"center", justifyContent:"center", gap:7, padding:"9px 14px",
                      background: err ? T.red : isD ? T.greenBg : T.navy,
                      color:      err ? T.white : isD ? T.green : T.white,
                      border:     isD && !err ? `1px solid ${T.green}33` : "none",
                      borderRadius:8, fontFamily:"'Figtree',sans-serif", fontSize:"0.965rem", fontWeight:600,
                      cursor:isL?"default":"pointer", opacity:isL?0.7:1, transition:"all 0.2s" }}>
                    {isL
                      ? <><div style={{ width:13, height:13, border:"2px solid rgba(255,255,255,0.3)", borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/> Erstelle …</>
                      : err
                        ? <>{Ic.refresh} Erneut versuchen</>
                        : isD
                          ? <>{Ic.refresh} Erneut generieren</>
                          : <>{Ic.word} Generieren &amp; Herunterladen</>}
                  </button>
                </div>

              </Card>
            );
          })}
        </div>

        {/* Sachstandsanfrage – beide Varianten nebeneinander */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(290px,1fr))", gap:"1.25rem" }}>

          {/* Intelligent (PRD-25d) */}
          <Card style={{ padding:"1.4rem", display:"flex", flexDirection:"column", gap:14 }}>
            <div style={{ display:"flex", alignItems:"flex-start", gap:12 }}>
              <div style={{ width:44, height:44, borderRadius:10, background:T.navy, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.3rem", flexShrink:0 }}>⚖️</div>
              <div style={{ flex:1 }}>
                <div style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1rem", fontWeight:700, color:T.navy }}>Sachstandsanfrage</div>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem", color:T.textFaint, marginTop:2 }}>Intelligent · Eskalationsstufen</div>
              </div>
            </div>
            <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem", color:T.textMuted, lineHeight:1.65, margin:0 }}>
              Analysiert die Aktenlage automatisch und schlägt die passende Eskalationsstufe vor.
              Text ist vor dem Generieren editierbar.
            </p>
            <div style={{ marginTop:"auto" }}>
              <button onClick={() => setStaOffen(true)}
                style={{ width:"100%", display:"flex", alignItems:"center", justifyContent:"center", gap:7, padding:"9px 14px",
                  background:T.navy, color:T.white, border:"none", borderRadius:8,
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.965rem", fontWeight:600,
                  cursor:"pointer", transition:"opacity 0.15s" }}
                onMouseEnter={e => e.currentTarget.style.opacity="0.85"}
                onMouseLeave={e => e.currentTarget.style.opacity="1"}>
                {Ic.word} Sachstandsanfrage erstellen
              </button>
            </div>
          </Card>

          {/* RA-Micro Wiedervorlage */}
          <RaMicroSachstandsCard akte={akte} inGrid />

        </div>

      </div>
    </>
  );
}


// ══════════════════════════════════════════════════════════════
//  UNFALLDETAILS-SECTION
// ══════════════════════════════════════════════════════════════


export default WordSection;
