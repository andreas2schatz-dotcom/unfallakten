import React, { useState, useEffect, useCallback } from "react";
import T from "../../config/theme.js";
import Ic from "../../config/icons.jsx";
import { IMPORT_STEPS, normalisiereLogEintrag } from "../../config/constants.js";
import { Card, Toast } from "../../components/common.jsx";
import { emailImport as apiEmail } from "../../api.js";
import EmailKarte from "./components/EmailKarte.jsx";
import EmailDetailView from "./EmailDetailView.jsx";

function gruppiereNachZeit(emails) {
  const heute   = new Date(); heute.setHours(0, 0, 0, 0);
  const gestern = new Date(heute); gestern.setDate(gestern.getDate() - 1);
  const woche   = new Date(heute); woche.setDate(woche.getDate() - 6);
  const gruppen = [
    { label:"Heute",       emails:[] },
    { label:"Gestern",     emails:[] },
    { label:"Diese Woche", emails:[] },
    { label:"Älter",       emails:[] },
  ];
  for (const e of emails) {
    const d = new Date(e.empfangen_am || 0); d.setHours(0, 0, 0, 0);
    if      (d >= heute)   gruppen[0].emails.push(e);
    else if (d >= gestern) gruppen[1].emails.push(e);
    else if (d >= woche)   gruppen[2].emails.push(e);
    else                   gruppen[3].emails.push(e);
  }
  return gruppen.filter(g => g.emails.length > 0);
}

export default function BussgeldEmailView({ onOpenAkte }) {
  const [log, setLog]             = useState([]);
  const [laedt, setLaedt]         = useState(true);
  const [importing, setImporting] = useState(false);
  const [importStep, setStep]     = useState(-1);
  const [toast, setToast]         = useState("");
  const [geoeffneteEmail, setGeoeffneteEmail] = useState(null);

  useEffect(() => {
    apiEmail.log({ limit: 200, konto: "bussgeld" })
      .then(d => { if (d?.log) setLog(d.log.map(normalisiereLogEintrag)); })
      .catch(() => {})
      .finally(() => setLaedt(false));
  }, []);

  const startImport = async () => {
    if (importing) return;
    setImporting(true); setStep(0);
    let step = 0;
    const tick = () => new Promise(r => {
      step++;
      setStep(step < IMPORT_STEPS.length ? step : step);
      setTimeout(r, 400 + Math.random() * 160);
    });
    const animPromise = (async () => { for (let i = 0; i < IMPORT_STEPS.length; i++) await tick(); })();
    const apiPromise  = apiEmail.starten({ konto: "bussgeld" });
    try {
      const [, res] = await Promise.all([animPromise, apiPromise]);
      if (res?.details) {
        apiEmail.log({ limit: 200, konto: "bussgeld" })
          .then(d => { if (d?.log) setLog(d.log.map(normalisiereLogEintrag)); })
          .catch(() => {});
        setToast(`Import: ${res.details.filter(e => e.betreff).length} neue E-Mail(s).`);
      } else {
        setToast("Import fehlgeschlagen. Bitte IMAP-Konfiguration prüfen.");
      }
    } catch (err) {
      await animPromise.catch(() => {});
      setToast(`Import fehlgeschlagen: ${err?.message || "Unbekannter Fehler"}`);
    }
    setImporting(false); setStep(-1);
  };

  const handleOpenEmail = useCallback((entry) => setGeoeffneteEmail(entry), []);
  const handleEmailZurueck = useCallback(() => setGeoeffneteEmail(null), []);
  const handleEmailGeloescht = useCallback((logId) => {
    setLog(prev => prev.filter(e => e.id !== logId));
  }, []);
  const onInAkteImportiert = useCallback((logId, res) => {
    setLog(prev => prev.map(e => e.id === logId
      ? { ...e, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : e
    ));
    setGeoeffneteEmail(prev => prev?.id === logId
      ? { ...prev, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : prev
    );
  }, []);

  const handleOpenAkteViaEntry = (entry) => {
    if (!entry.akte_az || !onOpenAkte) return;
    onOpenAkte({ az: entry.akte_az, id: entry.akte_az, az_roh: entry.akte_az,
                 brutto: 0, hq: 100, unfalldatum: "", unfallort: "" });
  };

  return (
    <>
      <style>{`@keyframes spin { to{transform:rotate(360deg)} } @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}

      {geoeffneteEmail ? (
        <EmailDetailView
          entry={geoeffneteEmail}
          onBack={handleEmailZurueck}
          onOpenAkte={handleOpenAkteViaEntry}
          onInAkteImportiert={onInAkteImportiert}
          onGeloescht={handleEmailGeloescht}
        />
      ) : (
        <>
          <div style={{ display:"flex", gap:10, alignItems:"center", justifyContent:"flex-end", marginBottom:"1.25rem" }}>
            <button onClick={startImport} disabled={importing}
              style={{ display:"flex", alignItems:"center", gap:8, padding:"9px 20px",
                background: importing ? T.navyMid : T.navy, color:T.white, border:"none",
                borderRadius:8, fontFamily:T.fontBody, fontSize:"0.975rem",
                fontWeight:600, cursor: importing ? "default" : "pointer",
                position:"relative", overflow:"hidden", minWidth:210 }}>
              {importing
                ? <><div style={{ width:14, height:14, border:"2px solid rgba(255,255,255,0.3)",
                    borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/>
                    {IMPORT_STEPS[importStep] || "…"}</>
                : <>{Ic.refresh} Jetzt importieren</>}
              <div style={{ position:"absolute", bottom:0, left:0, right:0, height:2,
                background:`linear-gradient(90deg,${T.accent},${T.accentLight})` }}/>
            </button>
          </div>

          <div style={{ display:"flex", gap:"0.75rem", marginBottom:"1.25rem" }}>
            {[
              { label:"Gesamt",     v: log.length,                                      c: T.navy  },
              { label:"Zugeordnet", v: log.filter(e => e.status === "zugeordnet").length, c: T.green },
            ].map((k,i) => (
              <div key={i} style={{ background:k.c + "0d", borderRadius:10, padding:"0.75rem 1.1rem",
                border:`1.5px solid ${k.c}30`, minWidth:120 }}>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:700,
                  letterSpacing:"0.1em", textTransform:"uppercase", color:k.c, marginBottom:5, opacity:0.8 }}>{k.label}</div>
                <div style={{ fontFamily:T.fontDisplay, fontSize:"2rem",
                  fontWeight:800, color:k.c, lineHeight:1 }}>{k.v}</div>
              </div>
            ))}
          </div>

          {laedt ? (
            <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
              {[1,2,3].map(i => (
                <div key={i} style={{ background:T.cardBg, border:`1px solid ${T.border}`,
                  borderRadius:9, padding:"1rem 1.1rem", animation:"pulse 1.4s ease-in-out infinite" }}>
                  <div style={{ display:"flex", gap:10, alignItems:"center" }}>
                    <div style={{ width:32, height:32, borderRadius:"50%", background:T.offWhite }}/>
                    <div style={{ flex:1 }}>
                      <div style={{ height:12, borderRadius:4, background:T.offWhite, marginBottom:6, width:"45%" }}/>
                      <div style={{ height:10, borderRadius:4, background:T.offWhite, width:"30%" }}/>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : log.length === 0 ? (
            <div style={{ background:T.cardBg, border:`1px solid ${T.border}`, borderRadius:10,
              padding:"3rem", textAlign:"center",
              fontFamily:T.fontBody, fontSize:"0.955rem", color:T.textMuted }}>
              Noch keine E-Mails importiert
            </div>
          ) : (
            gruppiereNachZeit(log).map(gruppe => (
              <div key={gruppe.label} style={{ marginBottom:"1.25rem" }}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:"0.55rem" }}>
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.775rem",
                    fontWeight:700, color:T.textMuted, letterSpacing:"0.08em",
                    textTransform:"uppercase", flexShrink:0 }}>{gruppe.label}</span>
                  <div style={{ flex:1, height:1, background:T.border }}/>
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.77rem",
                    color:T.textMuted, flexShrink:0 }}>{gruppe.emails.length}</span>
                </div>
                <Card>
                  {gruppe.emails.map((e, i) => (
                    <EmailKarte
                      key={e.id ?? i}
                      entry={e}
                      seite={e.status === "zugeordnet" ? "zugeordnet" : "nicht_zugeordnet"}
                      onOpenAkte={handleOpenAkteViaEntry}
                      onOpenEmail={handleOpenEmail}
                      onInAkteImportiert={onInAkteImportiert}
                      letzter={i === gruppe.emails.length - 1}
                    />
                  ))}
                </Card>
              </div>
            ))
          )}
        </>
      )}
    </>
  );
}
