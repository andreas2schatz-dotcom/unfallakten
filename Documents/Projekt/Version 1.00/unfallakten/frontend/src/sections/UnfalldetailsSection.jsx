import React, { useState, useEffect, useRef } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { Card, CardHead, Btn, Toast } from "../components/common.jsx";
import { fmtDatumDe } from "../config/utils.js";
import {
  apiKlage,
} from "../api.js";

function datumZuIso(de) {
  const m = (de || "").match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  return m ? `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}` : "";
}
function isoZuDatum(iso) {
  if (!iso) return "";
  const [y, mo, d] = iso.split("-");
  return `${d}.${mo}.${y}`;
}
function pruefeUnfalldatum(de) {
  if (!de) return "";
  const m = de.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!m) return "Kein gültiges Datum (TT.MM.JJJJ)";
  const [, dd, mm, jjjj] = m;
  const t = +dd, mo = +mm, j = +jjjj;
  const dt = new Date(j, mo - 1, t);
  if (dt.getFullYear() !== j || dt.getMonth() !== mo - 1 || dt.getDate() !== t)
    return "Kein gültiges Datum";
  const heute = new Date();
  heute.setHours(0, 0, 0, 0);
  if (dt > heute) return "Datum liegt in der Zukunft";
  return "";
}

function UnfalldetailsSection({ akteId }) {
  const [daten, setDaten] = useState(null);
  const [laedt, setLaedt] = useState(true);
  const [speichert, setSpeichert] = useState(false);
  const [wdmLaedt, setWdmLaedt] = useState(false);
  const [toast, setToast] = useState("");
  const [wdmInfo, setWdmInfo] = useState(null);

  const leer = {
    schilderung:"", zeuge_1:"", zeuge_1_anschrift:"",
    zeuge_2:"", zeuge_2_anschrift:"", zeuge_3:"", zeuge_3_anschrift:"",
    ermittlungsakte_az:"", ermittlungsakte_behoerde:"", ermittlungsakte_ort:"",
    fahrer_mandant:"", fahrer_gegner:"",
    vorsteuerabzug: false, haftungsquote: 100, haftungsbegruendung:"",
    unfalldatum:"",
  };
  const [form, setForm] = useState(leer);
  const [datumFehler, setDatumFehler] = useState("");
  const pickerRef = useRef(null);

  const _applyUd = (ud) => {
    if (!ud) return;
    setForm({ ...leer, ...ud, vorsteuerabzug: !!ud.vorsteuerabzug });
    setDatumFehler(pruefeUnfalldatum(fmtDatumDe(ud.unfalldatum || "")));
    if (ud._wdm_vorhanden) {
      setWdmInfo({
        verzugab:   ud._wdm_verzugab    || "",
        gegner_kz:  ud._wdm_gegner_kz   || "",
        mandant_kz: ud._wdm_mandant_kz  || "",
        schadennr:  ud._wdm_schadennummer || "",
      });
    }
  };

  useEffect(() => {
    (async () => {
      setLaedt(true);
      try {
        const res = await apiKlage.unfalldetails(akteId);
        _applyUd(res?.unfalldetails);
      } catch {}
      setLaedt(false);
    })();
  }, [akteId]);

  // WDM-Daten explizit (neu) laden und Formular überschreiben
  const wdmLaden = async () => {
    setWdmLaedt(true);
    try {
      const res = await apiKlage.wdmLaden(akteId);
      const ud = res?.unfalldetails;
      if (ud) {
        _applyUd(ud);
        setToast("WDM-Daten aus RA-Micro übernommen.");
      } else {
        setToast("⚠ Keine WDM-Daten gefunden.");
      }
    } catch (e) {
      setToast("⚠ WDM konnte nicht geladen werden: " + (e?.message || ""));
    } finally {
      setWdmLaedt(false);
    }
  };

  const upd = (k, v) => setForm(p => ({...p, [k]: v}));

  const datumTippen = (v) => { setDatumFehler(""); upd("unfalldatum", v); };
  const datumBlur = () => {
    const norm = fmtDatumDe(form.unfalldatum);
    upd("unfalldatum", norm);
    setDatumFehler(pruefeUnfalldatum(norm));
  };
  const datumAusKalender = (iso) => {
    const de = isoZuDatum(iso);
    upd("unfalldatum", de);
    setDatumFehler(pruefeUnfalldatum(de));
  };

  const speichern = async () => {
    setSpeichert(true);
    try {
      await apiKlage.unfalldetailsSpeichern(akteId, form);
      setToast("Unfalldetails gespeichert.");
    } catch (e) {
      setToast(e?.message || "Fehler beim Speichern.");
    } finally { setSpeichert(false); }
  };

  const inS = { width:"100%", padding:"7px 10px", border:`1px solid ${T.border}`,
    borderRadius:7, fontFamily:T.fontBody, fontSize:"0.935rem",
    outline:"none", background:T.cardBg, boxSizing:"border-box" };
  const taS = { ...inS, minHeight:120, resize:"vertical" };
  const lbS = { display:"block", fontFamily:T.fontBody,
    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 };
  const calBtnStyle = { padding:"6px 9px", borderRadius:7, cursor:"pointer",
    border:`1px solid ${T.border}`, background:T.cardBg, color:T.textMuted,
    display:"flex", alignItems:"center", flexShrink:0 };
  const CalIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="3" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M1 7h14" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 1v3M11 1v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );


  if (laedt) return <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
    fontFamily:T.fontBody }}>Lade …</div>;

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}
      <div style={{ maxWidth:900, margin:"0 auto", padding:"1.75rem", display:"flex",
        flexDirection:"column", gap:"1.25rem" }}>

        {/* WDM-Info-Banner */}
        {wdmInfo && (
          <div style={{ background:`${T.blue}10`, border:`1px solid ${T.blue}30`,
            borderRadius:8, padding:"10px 14px", fontFamily:T.fontBody,
            fontSize:"0.875rem", color:T.blue, display:"flex", gap:8, alignItems:"flex-start" }}>
            <span style={{ flexShrink:0 }}>ℹ</span>
            <div>
              <strong>Felder aus RA-Micro vorbelegt.</strong> Leere Felder wurden automatisch aus WDM übernommen und können hier bearbeitet werden.
              {(wdmInfo.verzugab || wdmInfo.schadennr || wdmInfo.gegner_kz) && (
                <span style={{ color:T.textMuted, marginLeft:8 }}>
                  {[
                    wdmInfo.verzugab   && `Verzug: ${wdmInfo.verzugab}`,
                    wdmInfo.schadennr  && `Schaden-Nr: ${wdmInfo.schadennr}`,
                    wdmInfo.gegner_kz  && `Gegner-KZ: ${wdmInfo.gegner_kz}`,
                  ].filter(Boolean).join(" · ")}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Unfallschilderung */}
        <Card>
          <CardHead title="Unfallschilderung" />
          <div style={{ padding:"1rem 1.25rem" }}>
            <label style={lbS}>Unfalldatum</label>
            <div style={{ display:"flex", gap:6, alignItems:"center", position:"relative",
              maxWidth:240, marginBottom: datumFehler ? 4 : "1rem" }}>
              <input type="text" value={form.unfalldatum || ""}
                onChange={e => datumTippen(e.target.value)}
                onBlur={datumBlur}
                placeholder="TT.MM.JJJJ"
                style={{ ...inS, borderColor: datumFehler ? T.red : T.border }}/>
              <button type="button" onClick={() => pickerRef.current?.showPicker?.()}
                title="Kalender öffnen" style={calBtnStyle}>
                <CalIcon />
              </button>
              <input ref={pickerRef} type="date"
                value={datumZuIso(form.unfalldatum)}
                onChange={e => datumAusKalender(e.target.value)}
                style={{ position:"absolute", opacity:0, pointerEvents:"none", width:0, height:0, right:0 }}
                tabIndex={-1}/>
            </div>
            {datumFehler && (
              <div style={{ color:T.redText, fontFamily:T.fontBody,
                fontSize:"0.78rem", marginBottom:"1rem" }}>
                {datumFehler}
              </div>
            )}
            <label style={lbS}>Schilderung des Unfallhergangs</label>
            <textarea value={form.schilderung} onChange={e => upd("schilderung", e.target.value)}
              placeholder="Der Kläger befuhr die … in Richtung … Als an der dortigen Kreuzung …"
              style={taS}/>
          </div>
        </Card>

        {/* Zeugen */}
        <Card>
          <CardHead title="Zeugen" />
          <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"0.75rem" }}>
            {[1,2,3].map(i => (
              <div key={i} style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.75rem" }}>
                <div>
                  <label style={lbS}>Zeuge {i} – Name</label>
                  <input value={form[`zeuge_${i}`]} onChange={e => upd(`zeuge_${i}`, e.target.value)}
                    placeholder="Max Mustermann" style={inS}/>
                </div>
                <div>
                  <label style={lbS}>Zeuge {i} – Anschrift</label>
                  <input value={form[`zeuge_${i}_anschrift`]}
                    onChange={e => upd(`zeuge_${i}_anschrift`, e.target.value)}
                    placeholder="Musterstraße 1, 12345 Musterstadt" style={inS}/>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Ermittlungsakte */}
        <Card>
          <CardHead title="Ermittlungsakte" />
          <div style={{ padding:"1rem 1.25rem", display:"grid",
            gridTemplateColumns:"1fr 1fr 1fr", gap:"0.75rem" }}>
            <div>
              <label style={lbS}>AZ Ermittlungsakte</label>
              <input value={form.ermittlungsakte_az}
                onChange={e => upd("ermittlungsakte_az", e.target.value)}
                placeholder="123.006724.1" style={inS}/>
            </div>
            <div>
              <label style={lbS}>Behörde</label>
              <input value={form.ermittlungsakte_behoerde}
                onChange={e => upd("ermittlungsakte_behoerde", e.target.value)}
                placeholder="RP Kassel" style={inS}/>
            </div>
            <div>
              <label style={lbS}>Ort / PLZ</label>
              <input value={form.ermittlungsakte_ort}
                onChange={e => upd("ermittlungsakte_ort", e.target.value)}
                placeholder="34117 Kassel" style={inS}/>
            </div>
          </div>
        </Card>

        {/* Fahrer + Vorsteuer + Haftung */}
        <Card>
          <CardHead title="Weitere Unfalldaten" />
          <div style={{ padding:"1rem 1.25rem", display:"grid",
            gridTemplateColumns:"1fr 1fr", gap:"0.75rem" }}>
            <div>
              <label style={lbS}>Fahrer Mandantenfahrzeug</label>
              <input value={form.fahrer_mandant}
                onChange={e => upd("fahrer_mandant", e.target.value)}
                placeholder="Max Mustermann (Mandant selbst)" style={inS}/>
            </div>
            <div>
              <label style={lbS}>Fahrer Unfallgegner</label>
              <input value={form.fahrer_gegner}
                onChange={e => upd("fahrer_gegner", e.target.value)}
                placeholder="Hans Gegner" style={inS}/>
            </div>
            <div>
              <label style={lbS}>Haftungsquote Gegenseite (%)</label>
              <input type="number" min="0" max="100"
                value={form.haftungsquote}
                onChange={e => upd("haftungsquote", parseFloat(e.target.value)||100)}
                style={inS}/>
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:10, paddingTop:22 }}>
              <input type="checkbox" id="vst" checked={!!form.vorsteuerabzug}
                onChange={e => upd("vorsteuerabzug", e.target.checked)}
                style={{ width:16, height:16, cursor:"pointer" }}/>
              <label htmlFor="vst" style={{ fontFamily:T.fontBody,
                fontSize:"0.935rem", cursor:"pointer", color:T.text }}>
                Mandant ist vorsteuerabzugsberechtigt
              </label>
            </div>
            <div style={{ gridColumn:"1/-1" }}>
              <label style={lbS}>Haftungsbegründung (optional)</label>
              <input value={form.haftungsbegruendung}
                onChange={e => upd("haftungsbegruendung", e.target.value)}
                placeholder="Vorfahrtsverletzung § 8 StVO" style={inS}/>
            </div>
          </div>
        </Card>

        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          {/* WDM-Import-Button – nur bei Akten mit AZ-Format (enthält "/") */}
          {akteId?.includes("/") ? (
            <Btn variant="secondary" onClick={wdmLaden} disabled={wdmLaedt}>
              {wdmLaedt
                ? <><div style={{ width:12, height:12, border:"2px solid rgba(0,0,0,0.2)",
                    borderTopColor:T.navy, borderRadius:"50%",
                    animation:"spin 0.7s linear infinite", display:"inline-block",
                    marginRight:6 }}/>Lade WDM …</>
                : "🔍 RA-Micro WDM laden"}
            </Btn>
          ) : <div/>}
          <Btn onClick={speichern} disabled={speichert}>
            {speichert ? "Speichern …" : "Unfalldetails speichern"}
          </Btn>
        </div>
      </div>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════
//  KLAGE-SECTION
// ══════════════════════════════════════════════════════════════
// Vertretungshinweis je Rechtsform


export default UnfalldetailsSection;
