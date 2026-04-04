import React, { useState, useEffect, useCallback } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { HAFTUNGSART_CFG, TIMELINE_FILTER, TIMELINE_TYPE_CFG, POSITION_LABELS_FE, positionKuerzungBetrag } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Card, CardHead, Btn, Toast } from "../components/common.jsx";
import {
  akten as apiAkten,
  forderungen as apiForderungen,
  ramicroAkte as apiRaMicroAkte,
  apiTodos,
  request,
  tokenStore,
} from "../api.js";

function InfoZeile({ label, value, mono=false, bold=false }) {
  if (!value) return null;
  return (
    <div style={{ display:"flex", gap:8, padding:"4px 0", borderBottom:`1px solid ${T.borderSoft}` }}>
      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:T.textFaint, width:110, flexShrink:0, paddingTop:1 }}>{label}</span>
      <span style={{ fontFamily: mono?"'IBM Plex Mono',monospace":"'IBM Plex Sans',sans-serif", fontSize:"0.875rem", color:T.text, fontWeight: bold?600:400 }}>{value}</span>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
────────────────────────────────────────────────────────────── */


function RechtsschutzKlappkachel({ beteiligte }) {
  const [offen, setOffen] = React.useState(false);
  if (!beteiligte || !beteiligte.length) return null;
  return (
    <div style={{ marginTop:6 }}>
      {/* Toggle-Zeile */}
      <button
        onClick={() => setOffen(o => !o)}
        style={{
          width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
          background: offen ? T.greenPale : T.surface,
          border:`1px solid ${offen ? T.green+"55" : T.border}`,
          borderRadius: offen ? "8px 8px 0 0" : 8,
          padding:"6px 12px", cursor:"pointer", transition:"all 0.18s",
        }}>
        <span style={{
          fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem", fontWeight:600,
          color: offen ? T.green : T.textMuted,
          textTransform:"uppercase", letterSpacing:"0.08em",
        }}>
          Rechtsschutzversicherung
        </span>
        <span style={{
          fontSize:"1rem", color: offen ? T.green : T.textMuted,
          transform: offen ? "rotate(180deg)" : "none",
          transition:"transform 0.2s",
          lineHeight:1,
        }}>⌄⌄</span>
      </button>
      {/* Ausgeklappter Inhalt */}
      {offen && (
        <div style={{
          border:`1px solid ${T.green}55`, borderTop:"none",
          borderRadius:"0 0 8px 8px",
          background: T.greenPale,
          padding:"10px 12px",
          animation:"fadeIn 0.15s ease",
        }}>
          <BeteiligterKachel
            titel="" farbe={T.green}
            beteiligte={beteiligte}
            zeigeBetreff zeigeAktenzeichen
          />
        </div>
      )}
    </div>
  );
}


function BeteiligterKachel({ titel, farbe, beteiligte, zeigeFirma=false, zeigeBetreff=false, zeigeAktenzeichen=false, nurEiner=false, akteId=null }) {
  const liste = nurEiner ? beteiligte.slice(0,1) : beteiligte;
  if (!liste.length) return null;

  // IBAN-Check: nur für Mandantenkachel
  const [ibanCheck, setIbanCheck] = useState(null); // null=lädt, {iban_vorhanden, mandant_email, ...}
  React.useEffect(() => {
    if (titel !== "Mandant" || !akteId || !akteId.includes("/")) return;
    request(`/ramicro/akte/mandant-checks?az=${encodeURIComponent(akteId)}`)
      .then(d => setIbanCheck(d))
      .catch(() => setIbanCheck({ iban_vorhanden: null }));
  }, [akteId, titel]);

  const ibanMailtoLink = () => {
    const mandant = liste[0];
    const email   = ibanCheck?.mandant_email || mandant?.email || "";
    const name    = ibanCheck?.mandant_name  || mandant?.name  || "Mandant";
    const anrede  = ["Herr","Herrn","Hr."].includes((mandant?.anrede||"").trim())
      ? `Sehr geehrter Herr ${name.split(" ").pop()},`
      : ["Frau","Fr."].includes((mandant?.anrede||"").trim())
        ? `Sehr geehrte Frau ${name.split(" ").pop()},`
        : `Sehr geehrte/r ${name},`;
    const betreff = encodeURIComponent("Bankverbindung für Ihre Akte");
    const body    = encodeURIComponent(
      `${anrede}\n\nfür die Geltendmachung Ihrer Schadensersatzansprüche benötigen wir noch Ihre Bankverbindung (IBAN).\n\nBitte teilen Sie uns Ihre IBAN baldmöglichst mit, damit wir eingegangene Zahlungen umgehend an Sie weiterleiten können.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
    );
    return `mailto:${email}?subject=${betreff}&body=${body}`;
  };

  const vollmachtMailtoLink = () => {
    const mandant = liste[0];
    const email   = ibanCheck?.mandant_email || mandant?.email || "";
    const name    = ibanCheck?.mandant_name  || mandant?.name  || "Mandant";
    const anrede  = ["Herr","Herrn","Hr."].includes((mandant?.anrede||"").trim())
      ? `Sehr geehrter Herr ${name.split(" ").pop()},`
      : ["Frau","Fr."].includes((mandant?.anrede||"").trim())
        ? `Sehr geehrte Frau ${name.split(" ").pop()},`
        : `Sehr geehrte/r ${name},`;
    const betreff = encodeURIComponent("Vollmacht – Bitte unterzeichnen und zurücksenden");
    const body    = encodeURIComponent(
      `${anrede}\n\nim Anhang erhalten Sie die Vollmacht für die Bearbeitung Ihrer Schadenssache.\n\nBitte unterzeichnen Sie diese und senden Sie uns die Vollmacht baldmöglichst zurück – per E-Mail, Post oder Fax.\n\nFür Rückfragen stehen wir Ihnen gerne zur Verfügung.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
    );
    return `mailto:${email}?subject=${betreff}&body=${body}`;
  };

  const mailtoLink = (b) => {
    if (!b.email) return null;
    const betreffs = [b.betreff1, b.betreff2, b.betreff3].filter(Boolean).join(" – ");
    return `mailto:${b.email}${betreffs ? `?subject=${encodeURIComponent(betreffs)}` : ""}`;
  };

  return (
    <div style={{ background:T.white, border: titel ? `1px solid ${T.border}` : "none", borderRadius: titel ? 10 : 0, overflow:"hidden", boxShadow: titel ? "0 1px 4px rgba(0,0,0,0.04)" : "none" }}>
      {/* Kachel-Header – wird ausgeblendet wenn kein Titel (z.B. in RechtsschutzKlappkachel) */}
      {titel && <div style={{ background: farbe + "18", borderBottom:`1px solid ${farbe}33`, padding:"8px 14px", display:"flex", alignItems:"center", gap:8 }}>
        <div style={{ width:8, height:8, borderRadius:"50%", background: farbe, flexShrink:0 }} />
        <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", fontWeight:600, color: farbe, textTransform:"uppercase", letterSpacing:"0.08em" }}>{titel}</span>
        {liste.length > 1 && <span style={{ marginLeft:"auto", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem", color:T.textFaint }}>{liste.length} Einträge</span>}
      </div>}

      {/* Einträge */}
      {liste.map((b, i) => (
        <div key={i} style={{ padding:"10px 14px", borderBottom: i < liste.length-1 ? `1px solid ${T.borderSoft}` : "none" }}>
          {/* Name / Firma */}
          <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.925rem", fontWeight:600, color:T.navy, marginBottom:3 }}>
            {zeigeFirma && b.name ? b.name : b.name || "–"}
            {b.kennzeichen && <span style={{ marginLeft:8, fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.75rem", background:T.goldPale, color:T.navy, border:`1px solid ${T.goldTrim}`, borderRadius:4, padding:"1px 5px" }}>{b.kennzeichen}</span>}
          </div>

          {/* Betreffzeilen (fett) */}
          {zeigeBetreff && (b.betreff1 || b.betreff2 || b.betreff3) && (
            <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.855rem", fontWeight:600, color:T.textMid, marginBottom:4 }}>
              {[b.betreff1, b.betreff2, b.betreff3].filter(Boolean).join(" · ")}
            </div>
          )}

          {/* Aktenzeichen (fett, für Behörden) */}
          {zeigeAktenzeichen && b.betreff1 && (
            <div style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.855rem", fontWeight:700, color:T.navy, marginBottom:4 }}>
              {b.betreff1}
            </div>
          )}

          {/* Adressdetails */}
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            {b.strasse && <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>{b.strasse}{b.plz || b.ort ? `, ${b.plz} ${b.ort}`.trim() : ""}</span>}
            {b.telefon  && <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>☎ {b.telefon}</span>}
            {b.telefon2 && <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>☎ {b.telefon2}</span>}
            {b.mobil    && <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>📱 {b.mobil}</span>}
            {b.fax      && <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>📠 {b.fax}</span>}
            {b.email && (
              <a href={mailtoLink(b)} style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.blue, textDecoration:"none" }}
                 onMouseEnter={e => e.target.style.textDecoration="underline"}
                 onMouseLeave={e => e.target.style.textDecoration="none"}>
                ✉ {b.email}
              </a>
            )}
            {/* IBAN-Check nur bei Mandanten */}
            {titel === "Mandant" && (
              <div style={{ marginTop:4, display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                {ibanCheck === null ? (
                  <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:T.textFaint }}>
                    ⟳ IBAN wird geprüft…
                  </span>
                ) : ibanCheck.iban_vorhanden ? (
                  <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                    color:"#16a34a", display:"flex", alignItems:"center", gap:4 }}>
                    <span style={{ fontSize:"0.9rem" }}>✅</span>
                    IBAN erfasst
                    {ibanCheck.geldinstitut && (
                      <span style={{ color:T.textFaint, fontSize:"0.77rem" }}>({ibanCheck.geldinstitut})</span>
                    )}
                  </span>
                ) : ibanCheck.iban_vorhanden === false ? (
                  <span style={{ display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                    <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                      color:T.red, display:"flex", alignItems:"center", gap:4 }}>
                      <span style={{ fontSize:"0.9rem" }}>❌</span>
                      IBAN nicht erfasst
                    </span>
                    {(ibanCheck.mandant_email || b.email) && (
                      <a href={ibanMailtoLink()}
                        style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.77rem",
                          padding:"2px 8px", background:T.blueBg,
                          border:`1px solid ${T.blue}55`, borderRadius:5,
                          color:T.navy, textDecoration:"none", whiteSpace:"nowrap",
                          cursor:"pointer", fontWeight:600 }}>
                        ✉ IBAN anfordern
                      </a>
                    )}
                  </span>
                ) : (
                  <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:T.textFaint }}>
                    ○ IBAN: keine RA-Micro-Verbindung
                  </span>
                )}
              </div>
            )}
            {/* Vollmacht-Check */}
            {titel === "Mandant" && (
              <div style={{ marginTop:4, display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                {ibanCheck === null ? (
                  <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:T.textFaint }}>
                    ⟳ Vollmacht wird geprüft…
                  </span>
                ) : ibanCheck.vollmacht_vorhanden ? (
                  <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                    color:"#16a34a", display:"flex", alignItems:"center", gap:4 }}>
                    <span style={{ fontSize:"0.9rem" }}>✅</span>
                    Vollmacht liegt vor
                  </span>
                ) : ibanCheck.vollmacht_vorhanden === false ? (
                  <span style={{ display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                    <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                      color:T.red, display:"flex", alignItems:"center", gap:4 }}>
                      <span style={{ fontSize:"0.9rem" }}>❌</span>
                      Vollmacht fehlt
                    </span>
                    {(ibanCheck.mandant_email || b.email) && (
                      <a href={vollmachtMailtoLink()}
                        style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.77rem",
                          padding:"2px 8px", background:"#fdf4ff",
                          border:"1px solid #d8b4fe", borderRadius:5,
                          color:"#6b21a8", textDecoration:"none", whiteSpace:"nowrap",
                          cursor:"pointer", fontWeight:600 }}>
                        ✉ Vollmacht anfordern
                      </a>
                    )}
                    {akteId && (
                      <button
                        onClick={async () => {
                          try {
                            const token = tokenStore.getAccess();
                            const base = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) || "";
                            const res = await fetch(`${base}/ramicro/akte/vollmacht?az=${encodeURIComponent(akteId)}`, {
                              headers: { Authorization: `Bearer ${token}` }
                            });
                            if (!res.ok) {
                              const err = await res.json().catch(() => ({}));
                              alert(`Fehler: ${err.fehler || err.typ || res.status}\n${err.pfad ? "Pfad: " + err.pfad : ""}`);
                              return;
                            }
                            const blob = await res.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `Vollmacht_${(akteId||"").replace("/","_")}.pdf`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            setTimeout(() => URL.revokeObjectURL(url), 5000);
                          } catch(e) {
                            alert(`Vollmacht-Fehler: ${e.message}`);
                          }
                        }}
                        style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.77rem",
                          padding:"2px 8px", background:"#f0fdf4",
                          border:"1px solid #86efac", borderRadius:5,
                          color:"#15803d", cursor:"pointer", fontWeight:600,
                          whiteSpace:"nowrap", outline:"none" }}>
                        ↓ Vollmacht generieren
                      </button>
                    )}
                  </span>
                ) : null}
              </div>
            )}
            {/* Vorsteuerabzug nur bei Mandanten anzeigen */}
            {titel === "Mandant" && (
              <span style={{
                fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                color: ["Y","J","JA","1"].includes((b.vorsteuer||"").toUpperCase()) ? T.amber : T.textFaint,
                marginTop:2, display:"flex", alignItems:"center", gap:4,
              }}>
                <span style={{ fontSize:"0.7rem" }}>
                  {["Y","J","JA","1"].includes((b.vorsteuer||"").toUpperCase()) ? "⚡" : "○"}
                </span>
                Vorsteuerabzug: <strong>{["Y","J","JA","1"].includes((b.vorsteuer||"").toUpperCase()) ? "Ja" : "Nein"}</strong>
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}


function EigeneVersicherungMini({ beteiligte }) {
  if (!beteiligte.length) return null;
  return (
    <div style={{ marginTop:8, background: T.surface, border:`1px solid ${T.border}`, borderRadius:7, padding:"7px 12px" }}>
      <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", fontWeight:600, color:T.textFaint, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:5 }}>
        Eigene Versicherung
      </div>
      {beteiligte.map((b, i) => (
        <div key={i} style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.855rem", color:T.textMid, marginBottom: i < beteiligte.length-1 ? 3 : 0 }}>
          <span style={{ fontWeight:600 }}>{b.name || b.firma}</span>
          {b.kennzeichen && <span style={{ marginLeft:6, fontSize:"0.78rem", color:T.textFaint }}>[{b.kennzeichen}]</span>}
          {b.telefon && <span style={{ marginLeft:8, color:T.textFaint, fontSize:"0.8rem" }}>☎ {b.telefon}</span>}
        </div>
      ))}
    </div>
  );
}


function RaMicroAkteUebersicht({ azRoh }) {
  const [daten, setDaten]   = useState(null);
  const [laden, setLaden]   = useState(true);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    setLaden(true); setFehler("");
    apiRaMicroAkte.laden(azRoh)
      .then(d => { setDaten(d); })
      .catch(e => setFehler(e?.message || "Fehler beim Laden der RA-Micro-Daten."))
      .finally(() => setLaden(false));
  }, [azRoh]);

  if (laden) return (
    <div style={{ display:"flex", alignItems:"center", gap:10, padding:"2rem", color:T.textFaint, fontFamily:"'IBM Plex Sans',sans-serif" }}>
      <div style={{ width:18, height:18, border:`2px solid ${T.gold}`, borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
      Lade RA-Micro Daten …
    </div>
  );

  if (fehler) return (
    <Card>
      <div style={{ padding:"1rem 1.4rem", display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:10 }}>
        <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.875rem", color:T.amber }}>
          ℹ RA-Micro Daten konnten nicht geladen werden — {fehler}
        </div>
        <Btn size="sm" variant="secondary" onClick={() => {
          setLaden(true); setFehler("");
          apiRaMicroAkte.laden(azRoh)
            .then(d => setDaten(d))
            .catch(e => setFehler(e?.message || "Fehler"))
            .finally(() => setLaden(false));
        }}>↻ Erneut laden</Btn>
      </div>
    </Card>
  );

  if (!daten) return null;

  const { stammdaten: s, beteiligte: b } = daten;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:"1.1rem" }}>

      {/* Stammdaten kompakt – zwei Zeilen, alle Felder nebeneinander */}
      <Card>
        <div style={{ padding:"0.7rem 1.4rem", display:"flex", flexWrap:"wrap", gap:"0.4rem 2rem", alignItems:"baseline" }}>
          {[
            { l:"AZ",         v:s.az,            mono:true,  bold:true  },
            { l:"SB",         v:s.sachbearbeiter, mono:true              },
            { l:"Unfalltag",  v:s.unfalltag,     mono:true              },
            { l:"KFZ",        v:s.kfz_mandant,   mono:true, bold:true   },
            { l:"KFZ Gegner", v:s.kfz_gegner,    mono:true              },
            { l:"Mandant",    v:s.mandant                                },
            { l:"Gegner",     v:s.gegner                                 },
            { l:"Kurzbezeichnung", v:s.kurzbezeichnung                  },
          ].filter(f => f.v).map(f => (
            <div key={f.l} style={{ display:"flex", alignItems:"baseline", gap:5 }}>
              <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", color:T.textFaint, whiteSpace:"nowrap" }}>{f.l}</span>
              <span style={{ fontFamily: f.mono ? "'IBM Plex Mono',monospace" : "'IBM Plex Sans',sans-serif", fontSize:"0.875rem", color:T.text, fontWeight: f.bold ? 700 : 400, whiteSpace:"nowrap" }}>{f.v}</span>
            </div>
          ))}
        </div>
        {s.bezeichnung && (
          <div style={{ padding:"0 1.4rem 0.6rem", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted }}>{s.bezeichnung}</div>
        )}
      </Card>

      {/* Beteiligten-Kacheln */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(300px,1fr))", gap:"0.9rem" }}>

        {/* Mandant + Rechtsschutz nebeneinander + angedockte eigene Versicherung */}
        {(b.mandant.length > 0 || b.rechtsschutz.length > 0) && (
          <div style={{ display:"contents" }}>
            {b.mandant.length > 0 && (
              <div>
                <BeteiligterKachel
                  titel="Mandant" farbe={T.navy}
                  beteiligte={b.mandant} nurEiner
                  zeigeBetreff zeigeAktenzeichen={false}
                  akteId={azRoh}
                />
                <EigeneVersicherungMini beteiligte={b.eigene_versicherung} />
                {b.rechtsschutz.length > 0 && (
                  <RechtsschutzKlappkachel beteiligte={b.rechtsschutz} />
                )}
                {b.weitere.length > 0 && (
                  <div style={{ marginTop:6 }}>
                    <BeteiligterKachel
                      titel="Weitere Beteiligte" farbe={T.textMuted}
                      beteiligte={b.weitere}
                      zeigeFirma zeigeBetreff
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Gegner */}
        <BeteiligterKachel
          titel="Gegner" farbe={T.red}
          beteiligte={b.gegner}
          zeigeBetreff zeigeAktenzeichen={false}
        />

        {/* Behörden / Gerichte */}
        <BeteiligterKachel
          titel="Behörden / Gerichte" farbe={T.amber}
          beteiligte={b.behoerde}
          zeigeAktenzeichen zeigeBetreff={false}
        />

      </div>
    </div>
  );
}




function ForderungshistorieKarte({ akteId }) {
  const [schreiben, setSchreiben] = React.useState([]);
  const [laden, setLaden]         = React.useState(true);
  const [offen, setOffen]         = React.useState({});   // { nr: bool }
  const [toast, setToast]         = React.useState("");

  React.useEffect(() => {
    if (!akteId || !String(akteId).includes("/")) { setLaden(false); return; }
    apiForderungen.nachSchreiben(akteId)
      .then(r => setSchreiben(r?.schreiben || []))
      .catch(() => {})
      .finally(() => setLaden(false));
  }, [akteId]);

  const toggleKlage = async (pos) => {
    const neuerFlag = !pos.fuer_klage;
    try {
      await apiForderungen.klageFlagSetzen(akteId, [pos.id], neuerFlag);
      setSchreiben(prev => prev.map(s => ({
        ...s,
        positionen: s.positionen.map(p =>
          p.id === pos.id ? { ...p, fuer_klage: neuerFlag } : p
        )
      })));
      setToast(neuerFlag ? "Für Klage vorgemerkt." : "Klage-Flag entfernt.");
    } catch { setToast("Fehler beim Speichern."); }
  };

  const setzeStatus = async (pos, status) => {
    try {
      const res = await apiForderungen.aktualisieren(akteId, pos.id, { status });
      setSchreiben(prev => prev.map(s => ({
        ...s,
        positionen: s.positionen.map(p =>
          p.id === pos.id ? { ...p, status: res?.position?.status || status } : p
        )
      })));
      setToast("Status aktualisiert.");
    } catch { setToast("Fehler beim Speichern."); }
  };

  const STATUS_STYLE = {
    gefordert:     { c: T.textMuted,   bg: T.surface,    label: "offen"         },
    teilreguliert: { c: T.amber,       bg: T.amberBg,    label: "teilreg."      },
    vollreguliert: { c: T.green,       bg: T.greenBg,    label: "✓ voll"        },
    gekuerzt:      { c: "#dc2626",     bg: "#fef2f2",    label: "gekürzt"       },
    abgelehnt:     { c: "#991b1b",     bg: "#fee2e2",    label: "abgelehnt"     },
  };

  if (laden) return (
    <Card style={{ padding: "1.2rem 1.4rem", color: T.textFaint, fontSize: "0.9rem" }}>
      Forderungshistorie wird geladen …
    </Card>
  );

  if (schreiben.length === 0) return (
    <Card style={{ padding: "1.2rem 1.4rem" }}>
      <CardHead title="Forderungshistorie" />
      <p style={{ color: T.textFaint, fontSize: "0.9rem", margin: 0 }}>
        Noch kein Forderungsschreiben der Höhe nach erstellt. Positionen werden
        automatisch beim Generieren erfasst.
      </p>
    </Card>
  );

  const gesamtKlage = schreiben.flatMap(s => s.positionen)
    .filter(p => p.fuer_klage)
    .reduce((sum, p) => sum + (p.betrag_gefordert - p.betrag_reguliert), 0);

  return (
    <Card>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <CardHead title={`Forderungshistorie · ${schreiben.length} Schreiben`}
        action={gesamtKlage > 0
          ? <span style={{ fontSize:"0.82rem", color:"#dc2626", fontWeight:600 }}>
              🏛 Klagepotential: {fmtEuro(gesamtKlage)}
            </span>
          : null}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "0 1.4rem 1.4rem" }}>
        {schreiben.map(s => {
          const isOffen = offen[s.schreiben_nr] !== false; // default aufgeklappt
          const offenCount = s.positionen.filter(p => p.status === "gefordert").length;
          const klageCount = s.positionen.filter(p => p.fuer_klage).length;
          return (
            <div key={s.schreiben_nr} style={{ border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden" }}>
              {/* Header */}
              <div
                onClick={() => setOffen(p => ({ ...p, [s.schreiben_nr]: !isOffen }))}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                  background: T.surface, cursor: "pointer", userSelect: "none" }}>
                <span style={{ fontSize: "0.8rem", color: T.textMuted }}>▶</span>
                <span style={{ fontFamily: "'IBM Plex Sans',sans-serif", fontWeight: 600,
                  color: T.navy, fontSize: "0.92rem" }}>
                  Forderungsschreiben Nr. {s.schreiben_nr}
                </span>
                <span style={{ fontFamily: "'IBM Plex Sans',sans-serif", fontSize: "0.82rem",
                  color: T.textFaint }}>
                  {s.datum || "–"}
                </span>
                <span style={{ marginLeft: "auto", fontFamily: "'IBM Plex Mono',monospace",
                  fontSize: "0.88rem", fontWeight: 600, color: T.navy }}>
                  {fmtEuro(s.gesamt_gefordert)}
                </span>
                {offenCount > 0 &&
                  <span style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20,
                    background: T.surface, border: `1px solid ${T.border}`, color: T.textMuted }}>
                    {offenCount} offen
                  </span>}
                {klageCount > 0 &&
                  <span style={{ fontSize: 11, padding: "2px 7px", borderRadius: 20,
                    background: "#fef2f2", color: "#dc2626", fontWeight: 600 }}>
                    {klageCount} Klage
                  </span>}
              </div>

              {/* Positionstabelle */}
              {isOffen && (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.855rem" }}>
                  <thead>
                    <tr style={{ background: "#f9fafb" }}>
                      {["Position", "Gefordert", "Reguliert", "Status", "Klage"].map((h, i) => (
                        <th key={h} style={{ padding: "7px 12px", textAlign: i === 0 ? "left" : "right",
                          fontSize: "0.74rem", fontWeight: 600, color: T.textMuted,
                          textTransform: "uppercase", letterSpacing: "0.05em",
                          borderTop: `1px solid ${T.border}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.positionen.map(pos => {
                      const st2 = STATUS_STYLE[pos.status] || STATUS_STYLE.gefordert;
                      return (
                        <tr key={pos.id} style={{ borderTop: `1px solid ${T.border}`,
                          background: pos.fuer_klage ? "#fff5f5" : "white" }}>
                          <td style={{ padding: "8px 12px", color: T.text, fontWeight: 500 }}>
                            {pos.position_label}
                            {pos.position_key === "restwert" &&
                              <span style={{ fontSize: 11, color: T.textFaint, marginLeft: 4 }}>(Abzug)</span>}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right",
                            fontFamily: "'IBM Plex Mono',monospace", color: T.text }}>
                            {fmtEuro(pos.betrag_gefordert)}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right",
                            fontFamily: "'IBM Plex Mono',monospace",
                            color: pos.betrag_reguliert > 0 ? T.green : T.textFaint }}>
                            {pos.betrag_reguliert > 0 ? fmtEuro(pos.betrag_reguliert) : "—"}
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            <select
                              value={pos.status}
                              onChange={e => setzeStatus(pos, e.target.value)}
                              style={{ fontSize: 11, padding: "2px 6px", borderRadius: 12,
                                background: st2.bg, color: st2.c, border: `1px solid ${st2.c}44`,
                                fontWeight: 600, cursor: "pointer", outline: "none" }}>
                              {Object.entries(STATUS_STYLE).map(([val, { label }]) => (
                                <option key={val} value={val}>{label}</option>
                              ))}
                            </select>
                          </td>
                          <td style={{ padding: "8px 12px", textAlign: "right" }}>
                            <button
                              onClick={() => toggleKlage(pos)}
                              title={pos.fuer_klage ? "Klage-Flag entfernen" : "Für Klage vormerken"}
                              style={{ padding: "3px 8px", borderRadius: 8, border: "none",
                                background: pos.fuer_klage ? "#fef2f2" : T.surface,
                                color: pos.fuer_klage ? "#dc2626" : T.textFaint,
                                cursor: "pointer", fontSize: 13, fontWeight: pos.fuer_klage ? 700 : 400 }}>
                              {pos.fuer_klage ? "🏛 Klage" : "○"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: `2px solid ${T.border}`, background: T.surface }}>
                      <td style={{ padding: "8px 12px", fontWeight: 700, color: T.navy,
                        fontSize: "0.85rem" }}>Summe</td>
                      <td style={{ padding: "8px 12px", textAlign: "right",
                        fontFamily: "'IBM Plex Mono',monospace", fontWeight: 700, color: T.navy }}>
                        {fmtEuro(s.gesamt_gefordert)}
                      </td>
                      <td style={{ padding: "8px 12px", textAlign: "right",
                        fontFamily: "'IBM Plex Mono',monospace", fontWeight: 700, color: T.green }}>
                        {s.gesamt_reguliert > 0 ? fmtEuro(s.gesamt_reguliert) : "—"}
                      </td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}


function AktenTimeline({ abrechnungen, aktivitaeten, akteId, onAktivitaetenChange }) {
  const [filter, setFilter] = useState("alle");
  const [loeschend, setLoeschend] = useState(null); // id gerade gelöscht wird

  const loescheAktivitaet = async (id) => {
    setLoeschend(id);
    try {
      await apiAkten.aktivitaetLoeschen(akteId, id);
      if (onAktivitaetenChange) onAktivitaetenChange();
    } catch (e) {
      alert("Löschen fehlgeschlagen: " + (e?.message || e));
    } finally {
      setLoeschend(null);
    }
  };

  const regEntries = abrechnungen.map(ab => {
    const ha  = HAFTUNGSART_CFG[ab.haftungsart] || HAFTUNGSART_CFG.vollhaftung;
    const typ = ab.haftungsart === "ablehnung" ? "ablehnung" : "abrechnung";
    return {
      id: `ab-${ab.id}`, kategorie:"regulierung", typ,
      datum: ab.datum || "",
      titel: ab.versicherung || "Abrechnungsschreiben",
      zeile1: "Reguliert: " + fmtEuro(ab.gesamt_reguliert) +
              (ab.gesamt_kuerzung > 0 ? "  ·  Kürzung: −" + fmtEuro(ab.gesamt_kuerzung) : ""),
      zeile2: ab.referenz_nr || "",
      dotColor: ha.color,
    };
  });

  const aktEntries = aktivitaeten.map((a, i) => {
    // Backend liefert: zeitstempel, aktion (Kurzcode), beschreibung (Lesetext)
    // Lesbarer Titel je Aktionstyp
    const aktionLabels = {
      pdf_import_gutachten:            "📄 Gutachten geparst",
      pdf_import_abrechnungsschreiben: "📄 Abrechnungsschreiben geparst",
      pdf_import_pruefbericht:         "📄 Prüfbericht geparst",
      pdf_import_unbekannt:            "📄 PDF-Dokument geparst",
      dokument_hochgeladen:            "📎 Dokument hochgeladen",
      login:                           "🔐 Anmeldung",
      akte_erstellt:                   "📁 Akte angelegt",
      beteiligter_angelegt:            "👤 Beteiligter angelegt",
      beteiligter_geaendert:           "👤 Beteiligter geändert",
      schaden_gespeichert:             "💶 Schaden gespeichert",
      schaden_aktualisiert:            "💶 Schaden aktualisiert",
      status_geaendert:                "🔄 Status geändert",
      notizen_geaendert:               "📝 Notizen geändert",
      haftungsquote_geaendert:         "⚖️ Haftungsquote geändert",
      wiedervorlage_erstellt:          "📅 Wiedervorlage erstellt",
      email_importiert:                "✉ E-Mail importiert",
    };
    const aktionCode = a.aktion || "";
    const titel = aktionLabels[aktionCode] || aktionCode.replace(/_/g, " ");
    // Datum: zeitstempel aus DB — SQLite: "2026-03-15 18:25:19", ISO: "2026-03-15T18:25:19"
    let datum = a.zeitstempel || a.zeit || "";
    let datumAnzeige = datum;
    let uhrzeitAnzeige = "";
    try {
      // SQLite-Format: Leerzeichen durch T ersetzen damit Date() es parst
      const d = new Date(datum.replace(" ", "T"));
      if (!isNaN(d)) {
        datumAnzeige  = d.toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric" });
        uhrzeitAnzeige = d.toLocaleTimeString("de-DE", { hour:"2-digit", minute:"2-digit" });
        datum = datumAnzeige + " " + uhrzeitAnzeige;
      }
    } catch { /* Originalformat behalten */ }
    return {
      id: "ak-" + (a.id ?? i), kategorie:"taetigkeit", typ:"taetigkeit",
      datum,
      datumAnzeige,
      uhrzeitAnzeige,
      titel,
      zeile1: a.beschreibung || a.aktion || "",
      zeile2: "",
      dotColor: TIMELINE_TYPE_CFG.taetigkeit.dot,
    };
  });

  const alle = [...regEntries, ...aktEntries].sort((a, b) => {
    const toSort = s => s.includes(".") ? s.split(".").reverse().join("-") : s;
    return toSort(b.datum).localeCompare(toSort(a.datum));
  });

  const sichtbar = filter === "alle" ? alle :
                   alle.filter(e => e.kategorie === filter);

  return (
    <Card>
      <div style={{ padding:"1rem 1.4rem 0", display:"flex", justifyContent:"space-between", alignItems:"center", flexWrap:"wrap", gap:8 }}>
        <div style={{ fontSize:"0.825rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em" }}>
          {"Akten-Chronik"}
          <span style={{ fontWeight:400, fontSize:"0.8rem", marginLeft:8, color:T.textFaint }}>{sichtbar.length} Einträge</span>
        </div>
        <div style={{ display:"flex", gap:4 }}>
          {TIMELINE_FILTER.map(f => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              style={{ padding:"4px 12px", borderRadius:20, fontSize:"0.83rem", cursor:"pointer",
                fontFamily:"'IBM Plex Sans',sans-serif", fontWeight: filter===f.id ? 600 : 400,
                border:"1.5px solid " + (filter===f.id ? T.gold : T.border),
                background: filter===f.id ? T.goldPale : "transparent",
                color: filter===f.id ? T.navy : T.textMuted, transition:"all 0.12s" }}>
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ padding:"0.75rem 1.4rem 1rem" }}>
        {sichtbar.length === 0 ? (
          <div style={{ padding:"2rem 0", textAlign:"center", color:T.textFaint, fontSize:"0.9rem" }}>
            {filter === "alle" ? "Noch keine Einträge." : "Keine Einträge für diesen Filter."}
          </div>
        ) : (
          <div style={{ position:"relative" }}>
            <div style={{ position:"absolute", left:11, top:8, bottom:8, width:1, background:T.border, zIndex:0 }} />
            <div style={{ display:"flex", flexDirection:"column", gap:0 }}>
              {sichtbar.map((e, idx) => {
                const cfg = TIMELINE_TYPE_CFG[e.typ] || TIMELINE_TYPE_CFG.taetigkeit;
                const isLast = idx === sichtbar.length - 1;
                const istAktivitaet = e.kategorie === "taetigkeit";
                const aktId = istAktivitaet ? parseInt(e.id.replace("ak-","")) : null;
                return (
                  <div key={e.id} style={{ display:"flex", gap:14, paddingBottom: isLast ? 0 : 16, position:"relative", zIndex:1 }}>
                    <div style={{ flexShrink:0, width:24, display:"flex", justifyContent:"center", paddingTop:3 }}>
                      <div style={{ width:10, height:10, borderRadius:"50%", background:e.dotColor, border:"2px solid " + T.offWhite, flexShrink:0 }} />
                    </div>
                    <div style={{ flex:1, minWidth:0, paddingBottom: isLast ? 0 : 4 }}>
                      <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:8, flexWrap:"wrap", marginBottom:2 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:7, flexWrap:"wrap" }}>
                          <span style={{ fontSize:"0.88rem", fontWeight:600, color:T.text }}>{e.titel}</span>
                          <span style={{ fontSize:"0.72rem", fontWeight:600, padding:"1px 7px", borderRadius:20,
                            background:cfg.badge, color:cfg.badgeText }}>{cfg.label}</span>
                        </div>
                        <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
                          <div style={{ textAlign:"right" }}>
                            <div style={{ fontSize:"0.8rem", color:T.textMuted, fontFamily:"monospace", fontWeight:500 }}>
                              {e.datumAnzeige || e.datum}
                            </div>
                            {e.uhrzeitAnzeige && (
                              <div style={{ fontSize:"0.75rem", color:T.textFaint, fontFamily:"monospace" }}>
                                {e.uhrzeitAnzeige} Uhr
                              </div>
                            )}
                          </div>
                          {istAktivitaet && aktId && (
                            <button
                              onClick={() => loescheAktivitaet(aktId)}
                              disabled={loeschend === aktId}
                              title="Eintrag löschen"
                              style={{
                                background: "none", border: "none", cursor: loeschend === aktId ? "wait" : "pointer",
                                padding: "2px 4px", borderRadius: 4, color: T.textFaint,
                                fontSize: "0.85rem", lineHeight:1,
                                transition: "color 0.15s",
                                opacity: loeschend === aktId ? 0.4 : 1,
                              }}
                              onMouseEnter={e2 => e2.currentTarget.style.color = "#c0392b"}
                              onMouseLeave={e2 => e2.currentTarget.style.color = T.textFaint}
                            >
                              🗑
                            </button>
                          )}
                        </div>
                      </div>
                      {e.zeile1 && <div style={{ fontSize:"0.845rem", color:T.textMuted, marginBottom:1 }}>{e.zeile1}</div>}
                      {e.zeile2 && <div style={{ fontSize:"0.8rem", color:T.textFaint }}>{e.zeile2}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}



function RegulierungsTabelle({
  schaden = {},
  abrechnungen = [],
  showCheckboxes = false,
  checked = {},
  onToggle,
  showKlageBadge = true,
}) {
  // ── Fahrzeugschaden-Logik (PRD-14: art aus Backend-Berechnung) ───────
  const _g  = k => parseFloat(schaden[k]) || 0;
  const repN  = _g("rep_gutachten_netto") || _g("reparaturkosten");
  const repRN = _g("rep_rechnung_netto");
  const wbw = _g("wiederbeschaffung"), rst = _g("restwert");
  const nettoFzg = wbw - rst;
  // art kommt aus Backend (abrechnungsberechnung) – Fallback auf gespeicherten Wert
  const art = schaden?.abrechnungsberechnung?.abrechnungsart
    || schaden?.abrechnungsart
    || null;

  let fahrzeugKeysSet;
  if (art === "totalschaden" || (!art && wbw > 0 && (effRep === 0 || (!ist130 && effRep > nettoFzg)))) {
    fahrzeugKeysSet = new Set(["wiederbeschaffung", "restwert"]);
  } else if (art === "konkret" || (!art && repRN > 0)) {
    fahrzeugKeysSet = new Set(["rep_rechnung_netto"]);
  } else if (art === "fiktiv" || (!art && repN > 0)) {
    fahrzeugKeysSet = new Set(["rep_gutachten_netto"]);
  } else if (wbw > 0) {
    fahrzeugKeysSet = new Set(["wiederbeschaffung", "restwert"]);
  } else {
    fahrzeugKeysSet = new Set(["rep_gutachten_netto"]);
  }

  const ALLE_FZG_KEYS = new Set(["wiederbeschaffung","restwert","rep_gutachten_netto","rep_rechnung_netto","rep_rechnung_brutto","reparaturkosten"]);
  const ABZUG_FELDER  = new Set(["restwert"]);

  const getFzgBetrag = (key) => {
    if (key === "rep_rechnung_netto")  return repRN;
    if (key === "rep_gutachten_netto") return repN;
    if (key === "wiederbeschaffung")   return wbw;
    if (key === "restwert")            return rst;
    return parseFloat(schaden[key]) || 0;
  };

  // ── posMap aus Abrechnungen ───────────────────────────────────
  const posMap = {};
  abrechnungen.slice().reverse().forEach(ab => {
    (ab.positionen || []).forEach(p => {
      // Remap sonstiges_wdm_X → extra_wdm_ssX (gleicher Key wie in schaden.wdm_extras_json)
      let key = p.position_key || p.art || "sonstiges";
      const _wm = /^sonstiges_wdm_(\d+)$/.exec(key);
      if (_wm) key = `extra_wdm_ss${_wm[1]}`;
      if (!posMap[key]) posMap[key] = { gefordert: 0, reguliert: 0, fuerKlage: false, eintraege: [] };
      posMap[key].gefordert = Math.max(posMap[key].gefordert, parseFloat(p.betrag_gefordert) || 0);
      if (ab.quelle === "manuell") {
        posMap[key].reguliert += parseFloat(p.betrag_reguliert) || 0;
      } else {
        posMap[key].reguliert = parseFloat(p.betrag_reguliert) || 0;
      }
      if (p.fuer_klage_vorgemerkt) posMap[key].fuerKlage = true;
      posMap[key].eintraege.push({
        betrag: parseFloat(p.betrag_reguliert) || 0,
        datum: ab.datum || "", versicherung: ab.versicherung || "",
        quelle: ab.quelle || "pdf",
      });
    });
  });

  // ── Zeilenliste aufbauen ──────────────────────────────────────
  const WEITERE = ["sv_kosten","wertminderung","nutzungsausfall","mietwagenkosten",
    "abschleppkosten","standkosten","anabmeldekosten","schmerzensgeld",
    "verdienstausfall","haushalt","unkostenpauschale","kostennb","sonstiges"];

  const alleKeys = [
    ...Array.from(fahrzeugKeysSet),
    ...WEITERE,
    // extra_* Keys werden separat als Extras-Zeilen gerendert
    ...Object.keys(posMap).filter(k => !ALLE_FZG_KEYS.has(k) && !WEITERE.includes(k) && !k.startsWith("extra_")),
  ];

  const rows = alleKeys.map(key => {
    const istAbzug  = ABZUG_FELDER.has(key);
    const betrag    = ALLE_FZG_KEYS.has(key) ? getFzgBetrag(key) : (parseFloat(schaden[key]) || posMap[key]?.gefordert || 0);
    const forderung = istAbzug ? -betrag : betrag;
    const reguliert = posMap[key]?.reguliert ?? null;
    const kuerzung  = reguliert != null ? Math.max(0, Math.abs(forderung) - reguliert) : null;
    const label     = POSITION_LABELS_FE[key] || key;
    const fuerKlage = posMap[key]?.fuerKlage || false;
    const eintraege = posMap[key]?.eintraege || [];
    return { key, label, forderung, betrag, istAbzug, reguliert, kuerzung, fuerKlage, eintraege };
  }).filter(r => r.betrag > 0 || (r.reguliert != null && r.reguliert > 0));

  // Extras
  const extras = (() => {
    if (schaden._extras?.length) return schaden._extras;
    try { const p = JSON.parse(schaden.wdm_extras_json || "[]"); return Array.isArray(p) ? p : []; } catch { return []; }
  })();
  extras.filter(e => (e.betrag||0) > 0).forEach(e => {
    rows.push({ key: `extra_${e.id}`, label: e.label || "Sonstiger Schaden",
      forderung: e.betrag, betrag: e.betrag, istAbzug: false,
      reguliert: posMap[`extra_${e.id}`]?.reguliert ?? null,
      kuerzung: null, fuerKlage: false,
      eintraege: posMap[`extra_${e.id}`]?.eintraege || [] });
  });

  const gesamtForderung = rows.reduce((s, r) => s + r.forderung, 0);
  const gesamtReguliert = rows.reduce((s, r) => s + (r.reguliert ?? 0), 0);
  const gesamtKuerzung  = rows.reduce((s, r) => s + (r.kuerzung ?? 0), 0);
  const hatRegulierung  = abrechnungen.length > 0;

  // Spalten je Modus
  const headers = showCheckboxes
    ? ["☑", "Position", "Forderung", "Reguliert", "Kürzung", "Status"]
    : ["Position", "Forderung", "Reguliert", "Kürzung", "Klage", "Status"];

  return (
    <div style={{ overflowX:"auto" }}>
      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.875rem" }}>
        <thead>
          <tr style={{ background:T.surface }}>
            {headers.map((h, i) => (
              <th key={h} style={{
                padding:"9px 12px",
                textAlign: (showCheckboxes ? i <= 1 : i === 0) ? "left" : "right",
                fontSize:"0.77rem", fontWeight:600, color:T.textMuted,
                textTransform:"uppercase", letterSpacing:"0.06em", whiteSpace:"nowrap",
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={6} style={{ padding:"2rem", textAlign:"center", color:T.textFaint }}>
              Noch keine Schadenpositionen oder Abrechnungen erfasst.
            </td></tr>
          ) : rows.map(r => {
            const hatKuerzung = r.kuerzung != null && r.kuerzung > 0.005;
            const vollReg     = r.reguliert != null && r.kuerzung != null && r.kuerzung <= 0.005;
            const nochOffen   = r.reguliert == null;
            const isChecked   = checked[r.key] ?? false;
            const tooltipText = r.eintraege.length > 0
              ? r.eintraege.map(e => `${e.datum||"–"} · ${e.versicherung||"–"} · ${fmtEuro(e.betrag)}`).join("\n")
              : "";

            return (
              <tr key={r.key}
                style={{ borderTop:`1px solid ${T.border}`,
                  background: (showCheckboxes ? isChecked : r.fuerKlage) ? "#2a1a001a" : "transparent",
                  cursor: showCheckboxes ? "pointer" : "default" }}
                onClick={showCheckboxes && onToggle ? () => onToggle(r.key) : undefined}>

                {/* Checkbox-Spalte (Klage-Tab) */}
                {showCheckboxes && (
                  <td style={{ padding:"9px 12px", textAlign:"center" }}
                    onClick={e => { e.stopPropagation(); if (onToggle) onToggle(r.key); }}>
                    <input type="checkbox" checked={isChecked}
                      onChange={() => onToggle && onToggle(r.key)}
                      style={{ accentColor:T.navy, width:15, height:15, cursor:"pointer" }} />
                  </td>
                )}

                {/* Position */}
                <td style={{ padding:"9px 12px", color: r.istAbzug ? T.red : T.text, fontWeight:500 }}>
                  {r.label}
                  {showKlageBadge && !showCheckboxes && r.fuerKlage && (
                    <span style={{ marginLeft:6, fontSize:11, background:T.amberBg,
                      color:T.amber, borderRadius:3, padding:"1px 5px", fontWeight:600 }}>KLAGE</span>
                  )}
                </td>

                {/* Forderung */}
                <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"monospace",
                  color: r.istAbzug ? T.red : T.text, fontWeight: r.istAbzug ? 600 : 400 }}>
                  {r.istAbzug ? `−${fmtEuro(r.betrag)}` : fmtEuro(r.forderung)}
                </td>

                {/* Reguliert */}
                <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"monospace",
                  color: nochOffen ? T.textFaint : vollReg ? T.green : T.amber }}>
                  {nochOffen ? "—" : (
                    <>
                      {fmtEuro(r.reguliert)}
                      {tooltipText && (
                        <span title={tooltipText}
                          style={{ marginLeft:4, cursor:"help", color:T.textFaint, fontSize:"0.75rem" }}>ℹ</span>
                      )}
                    </>
                  )}
                </td>

                {/* Kürzung */}
                <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"monospace",
                  fontWeight: hatKuerzung ? 700 : 400, color: hatKuerzung ? T.red : T.textFaint }}>
                  {hatKuerzung ? `−${fmtEuro(r.kuerzung)}` : "—"}
                </td>

                {/* Klage-Spalte (Übersicht) oder Status (beide) */}
                {!showCheckboxes && (
                  <td style={{ padding:"9px 12px", textAlign:"right", fontFamily:"monospace",
                    color: r.fuerKlage ? T.red : T.textFaint }}>
                    {r.fuerKlage && hatKuerzung ? fmtEuro(r.kuerzung) : "—"}
                  </td>
                )}

                {/* Status */}
                <td style={{ padding:"9px 12px", textAlign:"right" }}>
                  {nochOffen
                    ? <span style={{ fontSize:11, padding:"2px 7px", borderRadius:20, background:T.surface, color:T.textMuted, border:`1px solid ${T.border}` }}>offen</span>
                    : vollReg
                      ? <span style={{ fontSize:11, padding:"2px 7px", borderRadius:20, background:T.greenBg, color:T.green }}>✓ voll</span>
                      : <span style={{ fontSize:11, padding:"2px 7px", borderRadius:20, background:T.redBg, color:T.red }}>gekürzt</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr style={{ borderTop:`2px solid ${T.border}`, background:T.surface }}>
              {showCheckboxes && <td />}
              <td style={{ padding:"10px 12px", fontWeight:700, color:T.navy }}>Gesamt</td>
              <td style={{ padding:"10px 12px", textAlign:"right", fontFamily:"monospace", fontWeight:700, color:T.navy }}>{fmtEuro(gesamtForderung)}</td>
              <td style={{ padding:"10px 12px", textAlign:"right", fontFamily:"monospace", fontWeight:700, color:T.green }}>{hatRegulierung ? fmtEuro(gesamtReguliert) : "—"}</td>
              <td style={{ padding:"10px 12px", textAlign:"right", fontFamily:"monospace", fontWeight:700, color:gesamtKuerzung > 0 ? T.red : T.textFaint }}>
                {gesamtKuerzung > 0 ? `−${fmtEuro(gesamtKuerzung)}` : "—"}
              </td>
              {!showCheckboxes && <td style={{ padding:"10px 12px" }} />}
              <td style={{ padding:"10px 12px", textAlign:"right" }}>
                <span style={{ fontSize:12, fontWeight:700,
                  color: hatRegulierung && gesamtKuerzung <= 0.01 ? T.green : T.navy }}>
                  {hatRegulierung
                    ? `${Math.min(100, Math.round(gesamtReguliert / Math.max(gesamtForderung, 1) * 100))} %`
                    : "—"}
                </span>
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

// ── PRD-01: To-Do-System ────────────────────────────────────────────────────


function TodoSection({ akteId, az, onTodoChange }) {
  const [todos, setTodos]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [toast, setToast]       = useState("");
  const [neuerText, setNeuerText] = useState("");
  const [neuesFaellig, setNeuesFaellig] = useState("");
  const [neueFristTyp, setNeueFristTyp] = useState("");
  const [formOffen, setFormOffen] = useState(false);
  const [speichert, setSpeichert] = useState(false);

  const ladeTodos = React.useCallback(() => {
    setLoading(true);
    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Timeout beim Laden der To-Dos.")), 10000)
    );
    Promise.race([apiTodos.liste(az), timeout])
      .then(r => setTodos(r?.todos || []))
      .catch(e => setToast("To-Dos konnten nicht geladen werden: " + (e?.message || String(e))))
      .finally(() => setLoading(false));
  }, [az]);

  useEffect(() => { ladeTodos(); }, [ladeTodos]);

  // Dringlichkeit berechnen
  const dringlichkeit = (todo) => {
    const heute = new Date();
    heute.setHours(0, 0, 0, 0);
    if (todo.faellig_am) {
      const frist = new Date(todo.faellig_am);
      frist.setHours(0, 0, 0, 0);
      const tage = Math.round((frist - heute) / 86400000);
      const stufe = tage < 0 ? "rot" : tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
      return todo.frist_typ === "verjaehrung"
        ? { rot:"rot", orange:"rot", gelb:"orange", grau:"gelb" }[stufe] || stufe
        : stufe;
    }
    const erstellt = new Date(todo.erstellt_am);
    erstellt.setHours(0, 0, 0, 0);
    const alter = Math.round((heute - erstellt) / 86400000);
    if (alter >= 15) return "rot";
    if (alter >= 8)  return "orange";
    if (alter >= 4)  return "gelb";
    return "grau";
  };

  const FARBEN = {
    rot:    { bg: "#fef2f2", border: "#fca5a5", dot: "#ef4444", label: "Dringend" },
    orange: { bg: "#fff7ed", border: "#fdba74", dot: "#f97316", label: "Bald fällig" },
    gelb:   { bg: "#fefce8", border: "#fde047", dot: "#eab308", label: "In Bearbeitung" },
    grau:   { bg: T.surface, border: T.border,  dot: T.textFaint, label: "Neu" },
  };

  const toggleErledigt = async (todo) => {
    try {
      const r = await apiTodos.update(az, todo.id, { erledigt: !todo.erledigt });
      setTodos(prev => prev.map(t => t.id === todo.id ? r.todo : t));
      if (onTodoChange) onTodoChange();
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    }
  };

  const loescheTodo = async (todo) => {
    try {
      await apiTodos.loesche(az, todo.id);
      setTodos(prev => prev.filter(t => t.id !== todo.id));
      if (onTodoChange) onTodoChange();
    } catch (e) {
      setToast("Löschen fehlgeschlagen: " + (e?.message || String(e)));
    }
  };

  const speichereTodo = async () => {
    if (!neuerText.trim()) { setToast("Bitte Text eingeben."); return; }
    setSpeichert(true);
    try {
      const r = await apiTodos.erstelle(az, {
        text:       neuerText.trim(),
        faellig_am: neuesFaellig || null,
        frist_typ:  neueFristTyp || null,
        quelle:     "benutzer",
      });
      setTodos(prev => [r.todo, ...prev]);
      setNeuerText(""); setNeuesFaellig(""); setNeueFristTyp(""); setFormOffen(false);
      setToast("To-Do angelegt.");
      if (onTodoChange) onTodoChange();
    } catch (e) {
      setToast("Speichern fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setSpeichert(false);
    }
  };

  const offen  = todos.filter(t => !t.erledigt);
  const erledigt = todos.filter(t => t.erledigt);

  const renderTodo = (todo) => {
    const d = dringlichkeit(todo);
    const f = FARBEN[d];
    const istSystem = todo.quelle === "system";
    return (
      <div key={todo.id} style={{
        display:"flex", alignItems:"flex-start", gap:10,
        padding:"10px 14px",
        background: todo.erledigt ? "rgba(0,0,0,0.02)" : f.bg,
        border:`1px solid ${todo.erledigt ? T.border : f.border}`,
        borderRadius:8, marginBottom:6,
        opacity: todo.erledigt ? 0.6 : 1,
        transition:"all 0.15s",
      }}>
        {/* Erledigt-Checkbox */}
        <button onClick={() => toggleErledigt(todo)} title={todo.erledigt ? "Als offen markieren" : "Als erledigt markieren"}
          style={{ flexShrink:0, width:20, height:20, borderRadius:"50%",
            border:`2px solid ${todo.erledigt ? T.green : f.dot}`,
            background: todo.erledigt ? T.green : "transparent",
            cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center",
            marginTop:1, transition:"all 0.15s" }}>
          {todo.erledigt && <span style={{ color:"#fff", fontSize:11, lineHeight:1 }}>✓</span>}
        </button>

        {/* Inhalt */}
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{
            fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.925rem",
            color: todo.erledigt ? T.textFaint : T.text,
            textDecoration: todo.erledigt ? "line-through" : "none",
            lineHeight:1.4,
          }}>
            {todo.text}
          </div>
          <div style={{ display:"flex", gap:8, marginTop:4, flexWrap:"wrap", alignItems:"center" }}>
            {!todo.erledigt && (
              <span style={{ fontSize:"0.72rem", background:f.bg, color:f.dot,
                border:`1px solid ${f.border}`, borderRadius:4, padding:"1px 6px", fontWeight:600 }}>
                ● {f.label}
              </span>
            )}
            {todo.faellig_am && (
              <span style={{ fontSize:"0.72rem", color:T.textMuted, fontFamily:"'IBM Plex Mono',monospace" }}>
                Fällig: {(() => { try { const [y,m,d] = todo.faellig_am.split("-"); return `${d}.${m}.${y}`; } catch { return todo.faellig_am; } })()}
                {todo.frist_typ === "verjaehrung" && " ⚠️ Verjährung"}
              </span>
            )}
            {istSystem && (
              <span style={{ fontSize:"0.72rem", color:T.textFaint }}>🔒 System</span>
            )}
            {todo.erledigt_am && (
              <span style={{ fontSize:"0.72rem", color:T.textFaint, fontFamily:"'IBM Plex Mono',monospace" }}>
                Erledigt: {(() => { try { return todo.erledigt_am.slice(0,10).split("-").reverse().join("."); } catch { return ""; } })()}
              </span>
            )}
          </div>
        </div>

        {/* Löschen (nur manuelle) */}
        {!istSystem && (
          <button onClick={() => loescheTodo(todo)} title="To-Do löschen"
            style={{ flexShrink:0, background:"none", border:"none", cursor:"pointer",
              color:T.textFaint, fontSize:"0.85rem", padding:"2px 4px", lineHeight:1,
              opacity:0.6, transition:"opacity 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.opacity="1"}
            onMouseLeave={e => e.currentTarget.style.opacity="0.6"}>
            ✕
          </button>
        )}
      </div>
    );
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", flexDirection:"column", gap:"1rem" }}>

        {/* Header-Kachel */}
        <Card>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
            padding:"1rem 1.4rem" }}>
            <div>
              <div style={{ fontFamily:"'Plus Jakarta Sans',sans-serif", fontSize:"1.15rem",
                fontWeight:700, color:T.navy }}>
                To-Dos
                {offen.length > 0 && (
                  <span style={{ marginLeft:8, fontSize:"0.825rem", background:T.redBg,
                    color:T.red, borderRadius:12, padding:"2px 8px", fontFamily:"'IBM Plex Sans',sans-serif",
                    fontWeight:600, verticalAlign:"middle" }}>
                    {offen.length} offen
                  </span>
                )}
              </div>
              <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.85rem",
                color:T.textFaint, marginTop:2 }}>
                Aufgaben für diese Akte
              </div>
            </div>
            <Btn size="sm" onClick={() => setFormOffen(o => !o)}>
              {Ic.plus} Neues To-Do
            </Btn>
          </div>

          {/* Formular */}
          {formOffen && (
            <div style={{ margin:"0 1.4rem 1rem", background:T.goldPale,
              border:`1px solid ${T.goldTrim}`, borderRadius:10, padding:"1rem 1.25rem" }}>
              <div style={{ marginBottom:"0.75rem" }}>
                <label style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem",
                  fontWeight:600, color:T.textMid, textTransform:"uppercase",
                  letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                  Aufgabe *
                </label>
                <textarea
                  value={neuerText}
                  onChange={e => setNeuerText(e.target.value)}
                  rows={2}
                  placeholder="Was ist zu tun?"
                  style={{ width:"100%", padding:"8px 10px", border:`1.5px solid ${T.border}`,
                    borderRadius:7, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.925rem",
                    color:T.text, background:T.surface, outline:"none", resize:"vertical",
                    lineHeight:1.5, boxSizing:"border-box" }}
                  onFocus={e => e.target.style.borderColor=T.gold}
                  onBlur={e => e.target.style.borderColor=T.border}
                />
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.75rem",
                marginBottom:"0.75rem" }}>
                <div>
                  <label style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem",
                    fontWeight:600, color:T.textMid, textTransform:"uppercase",
                    letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                    Fällig am (optional)
                  </label>
                  <input type="date" value={neuesFaellig}
                    onChange={e => setNeuesFaellig(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`,
                      borderRadius:7, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.9rem",
                      color:T.text, background:T.surface, outline:"none", boxSizing:"border-box" }}
                    onFocus={e => e.target.style.borderColor=T.gold}
                    onBlur={e => e.target.style.borderColor=T.border}
                  />
                </div>
                <div>
                  <label style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem",
                    fontWeight:600, color:T.textMid, textTransform:"uppercase",
                    letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                    Fristtyp
                  </label>
                  <select value={neueFristTyp} onChange={e => setNeueFristTyp(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`,
                      borderRadius:7, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.9rem",
                      color:T.text, background:T.surface, outline:"none", cursor:"pointer",
                      boxSizing:"border-box" }}>
                    <option value="">Kein Fristtyp</option>
                    <option value="intern">Intern</option>
                    <option value="gericht">Gericht</option>
                    <option value="verjaehrung">⚠️ Verjährung</option>
                  </select>
                </div>
              </div>
              <div style={{ display:"flex", gap:8 }}>
                <Btn variant="gold" onClick={speichereTodo} disabled={speichert}>
                  {speichert ? "…" : `${Ic.check} Anlegen`}
                </Btn>
                <Btn variant="secondary" onClick={() => {
                  setFormOffen(false); setNeuerText(""); setNeuesFaellig(""); setNeueFristTyp("");
                }}>Abbrechen</Btn>
              </div>
            </div>
          )}
        </Card>

        {/* To-Do-Liste */}
        {loading ? (
          <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
            fontFamily:"'IBM Plex Sans',sans-serif" }}>Lade To-Dos …</div>
        ) : todos.length === 0 ? (
          <Card>
            <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
              fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.925rem" }}>
              Keine To-Dos für diese Akte.
            </div>
          </Card>
        ) : (
          <Card>
            <div style={{ padding:"1rem 1.4rem" }}>
              {offen.length > 0 && (
                <>
                  <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem",
                    fontWeight:600, color:T.textMuted, textTransform:"uppercase",
                    letterSpacing:"0.08em", marginBottom:8 }}>
                    Offen ({offen.length})
                  </div>
                  {offen.map(renderTodo)}
                </>
              )}
              {erledigt.length > 0 && (
                <>
                  <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem",
                    fontWeight:600, color:T.textFaint, textTransform:"uppercase",
                    letterSpacing:"0.08em", margin:`${offen.length > 0 ? "1rem" : 0} 0 8px` }}>
                    Erledigt ({erledigt.length})
                  </div>
                  {erledigt.map(renderTodo)}
                </>
              )}
            </div>
          </Card>
        )}
      </div>
    </>
  );
}

// ── PRD-16: To-Do-Kachel kompakt für Übersicht ─────────────────────────────


function TodoKachelKompakt({ az, akteId }) {
  const [todos, setTodos]     = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timeout = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Timeout")), 8000)
    );
    Promise.race([apiTodos.liste(az), timeout])
      .then(r => setTodos(r?.todos || []))
      .catch(() => setTodos([]))
      .finally(() => setLoading(false));
  }, [az]);

  const offen = todos.filter(t => !t.erledigt);
  if (loading) return null;

  const FARBEN = {
    rot:    { bg:"#fef2f2", border:"#fca5a5", dot:"#ef4444" },
    orange: { bg:"#fff7ed", border:"#fdba74", dot:"#f97316" },
    gelb:   { bg:"#fefce8", border:"#fde047", dot:"#eab308" },
    grau:   { bg:T.surface, border:T.border,  dot:T.textFaint },
  };

  const dringlichkeit = (todo) => {
    const heute = new Date(); heute.setHours(0,0,0,0);
    if (todo.faellig_am) {
      const frist = new Date(todo.faellig_am); frist.setHours(0,0,0,0);
      const tage = Math.round((frist - heute) / 86400000);
      const s = tage < 0 ? "rot" : tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
      return todo.frist_typ === "verjaehrung"
        ? ({rot:"rot",orange:"rot",gelb:"orange",grau:"gelb"}[s] || s) : s;
    }
    const alter = Math.round((heute - new Date(todo.erstellt_am)) / 86400000);
    return alter >= 15 ? "rot" : alter >= 8 ? "orange" : alter >= 4 ? "gelb" : "grau";
  };

  return (
    <Card style={{ borderLeft: offen.length > 0 ? `3px solid ${T.gold}` : undefined }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
        padding:"0.85rem 1.4rem 0.5rem" }}>
        <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem",
          fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.08em" }}>
          📋 To-Dos
          {offen.length > 0 && (
            <span style={{ marginLeft:8, background:T.redBg, color:T.red,
              borderRadius:10, padding:"1px 7px", fontSize:"0.78rem" }}>
              {offen.length} offen
            </span>
          )}
        </div>
      </div>
      <div style={{ padding:"0 1.4rem 0.85rem" }}>
        {offen.length === 0 ? (
          <div style={{ fontSize:"0.875rem", color:T.textFaint,
            fontFamily:"'IBM Plex Sans',sans-serif" }}>
            ✅ Alle To-Dos erledigt
          </div>
        ) : (
          offen.slice(0, 4).map(todo => {
            const d = dringlichkeit(todo);
            const f = FARBEN[d];
            return (
              <div key={todo.id} style={{
                display:"flex", alignItems:"center", gap:8,
                padding:"5px 0",
                borderBottom:`1px solid ${T.borderSoft}`,
              }}>
                <span style={{ width:8, height:8, borderRadius:"50%",
                  background:f.dot, flexShrink:0, display:"inline-block" }} />
                <span style={{ fontFamily:"'IBM Plex Sans',sans-serif",
                  fontSize:"0.875rem", color:T.text, flex:1,
                  overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {todo.text}
                </span>
                {todo.faellig_am && (
                  <span style={{ fontSize:"0.75rem", color:T.textFaint,
                    fontFamily:"'IBM Plex Mono',monospace", flexShrink:0 }}>
                    {(() => { try { const [y,m,d]=todo.faellig_am.split("-"); return `${d}.${m}.`; } catch{return "";} })()}
                  </span>
                )}
              </div>
            );
          })
        )}
        {offen.length > 4 && (
          <div style={{ fontSize:"0.8rem", color:T.textFaint, marginTop:5,
            fontFamily:"'IBM Plex Sans',sans-serif" }}>
            + {offen.length - 4} weitere …
          </div>
        )}
      </div>
    </Card>
  );
}


function UebersichtSection({ akte, st, dispatch }) {
  const [notizen, setNotizen] = useState(st.notizen || "");
  const [nChanged, setNC]     = useState(false);
  const [toast, setToast]     = useState("");

  // Aktivitäten beim ersten Rendern aus API laden
  useEffect(() => {
    apiAkten.aktivitaeten(akte.id)
      .then(data => {
        if (data?.aktivitaeten) {
          dispatch({ type: "SET_AKTIVITAETEN", akteId: akte.id, aktivitaeten: data.aktivitaeten });
        }
      })
      .catch(() => { /* Fehler ignorieren – Mock-Daten bleiben */ });
  }, [akte.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mandant    = st.beteiligte?.find(b => b.rolle === "mandant");
  const gegner     = st.beteiligte?.find(b => b.rolle === "gegner");
  const schaden    = st.schaden || {};
  const abrechnungen = st.abrechnungen || [];
  // PRD-14: Brutto aus Backend-Berechnung (Single Source of Truth)
  const _g  = k => parseFloat(schaden[k]) || 0;
  const _berechneterBruttoKK = schaden?.abrechnungsberechnung?.gesamt_brutto
    ?? schaden?.gesamt_brutto
    ?? 0;
  const brutto = _berechneterBruttoKK > 0 ? _berechneterBruttoKK
    : (schaden.gesamt_brutto || 0);
  const netto      = brutto * ((akte.hq || 100) / 100);

  // Alle Positionen aus allen Abrechnungen aggregieren
  // Manuell = kumulativ (Teilzahlungen), PDF/WDM = letzter Eintrag gewinnt
  const posMap = {};
  abrechnungen.slice().reverse().forEach(ab => {
    (ab.positionen || []).forEach(p => {
      const key = p.position_key || p.art || "sonstiges";
      if (!posMap[key]) posMap[key] = { gefordert: 0, reguliert: 0, kuerungenBetrag: 0, fuerKlage: false, eintraege: [] };
      posMap[key].gefordert = Math.max(posMap[key].gefordert, parseFloat(p.betrag_gefordert) || 0);
      if (ab.quelle === "manuell") {
        posMap[key].reguliert += parseFloat(p.betrag_reguliert) || 0;
      } else {
        posMap[key].reguliert = parseFloat(p.betrag_reguliert) || 0;
      }
      posMap[key].kuerungenBetrag = positionKuerzungBetrag(p);
      if (p.fuer_klage_vorgemerkt) posMap[key].fuerKlage = true;
      posMap[key].eintraege.push({
        betrag: parseFloat(p.betrag_reguliert) || 0,
        datum: ab.datum || "", versicherung: ab.versicherung || "",
        quelle: ab.quelle || "pdf", ab_id: ab.id,
      });
    });
  });

  // Schadenpositionen aus st.schaden als Forderungs-Basis (wenn noch keine Abrechnungen)
  const SCHADEN_POS_MAP = {
    rep_gutachten_netto:  "Reparaturkosten lt. Gutachten (netto)",
    rep_rechnung_netto:   "Reparaturkosten lt. Rechnung (netto)",
    rep_rechnung_brutto:  "Reparaturkosten lt. Rechnung (brutto)",
    reparaturkosten:      "Reparaturkosten",
    wiederbeschaffung:    "Wiederbeschaffungswert",
    restwert:             "Restwert (−)",
    wertminderung:        "Wertminderung",
    nutzungsausfall:      "Nutzungsausfallschaden",
    mietwagenkosten:      "Mietwagenkosten",
    sv_kosten:            "SV-/Gutachterkosten",
    abschleppkosten:      "Abschleppkosten",
    standkosten:          "Standkosten",
    anabmeldekosten:      "An-/Abmeldekosten",
    schmerzensgeld:       "Schmerzensgeld",
    verdienstausfall:     "Verdienstausfall",
    haushalt:             "Haushaltsführungsschaden",
    unkostenpauschale:    "Unkostenpauschale",
    sonstiges:            "Sonstiges",
  };
  const ABZUG_FELDER = new Set(["restwert"]);

  // Fahrzeug-Schlüssel je Abrechnungsart (PRD-14: aus Backend-Berechnung)
  const _art = schaden?.abrechnungsberechnung?.abrechnungsart
    || schaden?.abrechnungsart
    || null;
  const _pvRepN  = parseFloat(schaden?.rep_gutachten_netto || schaden?.reparaturkosten || 0);
  const _pvRepRN = parseFloat(schaden?.rep_rechnung_netto || 0);
  const _wbw2    = parseFloat(schaden?.wiederbeschaffung || 0);
  const _rst2    = parseFloat(schaden?.restwert || 0);

  // Welche Fahrzeug-Keys sollen in der Tabelle erscheinen?
  let _fahrzeugKeysSet;
  if (_art === "totalschaden") {
    _fahrzeugKeysSet = new Set(["wiederbeschaffung", "restwert"]);
  } else if (_art === "konkret") {
    _fahrzeugKeysSet = new Set(["rep_rechnung_netto"]);
  } else if (_art === "fiktiv") {
    _fahrzeugKeysSet = new Set(["rep_gutachten_netto"]);
  } else if (_wbw2 > 0) {
    _fahrzeugKeysSet = new Set(["wiederbeschaffung", "restwert"]);
  } else {
    _fahrzeugKeysSet = new Set(["rep_gutachten_netto"]); // Fallback
  }

  // Alle Fahrzeug-Keys die wir NICHT anzeigen wollen (unterdrücken)
  const _ALLE_FAHRZEUG_KEYS = new Set([
    "wiederbeschaffung","restwert","rep_gutachten_netto","rep_rechnung_netto",
    "rep_rechnung_brutto","reparaturkosten"
  ]);

  // Betrag für Fahrzeugschaden-Keys korrekt ermitteln
  const _getFahrzeugBetrag = (key) => {
    if (key === "rep_rechnung_netto")  return _pvRepRN;
    if (key === "rep_gutachten_netto") return _pvRepN;
    if (key === "wiederbeschaffung")   return _wbw2;
    if (key === "restwert")            return _rst2;
    return parseFloat(schaden?.[key]) || 0;
  };

  // Extras aus schaden._extras – muss VOR alleKeys stehen (für _extraCoveredKeys)
  const _rawExtras = (() => {
    if (schaden._extras && schaden._extras.length > 0) return schaden._extras;
    if (schaden.wdm_extras_json) {
      try { const p = JSON.parse(schaden.wdm_extras_json); if (Array.isArray(p)) return p; } catch {}
    }
    return [];
  })();
  // Keys die durch Extras abgedeckt sind (wdm_ss1 und sonstiges_wdm_1 sind dasselbe)
  const _extraCoveredKeys = new Set(_rawExtras.flatMap(e => {
    const slot = String(e.id || "").replace("wdm_ss", "");
    return slot && !isNaN(slot) ? [e.id, `sonstiges_wdm_${slot}`] : [e.id];
  }));

  // Alle Positions-Keys: Fahrzeug-Keys gefiltert + alle anderen > 0 + posMap-Keys
  const _nichtFahrzeugKeys = Object.keys(SCHADEN_POS_MAP).filter(k =>
    !_ALLE_FAHRZEUG_KEYS.has(k) && (schaden[k] || 0) > 0
  );
  const _posMapNichtFahrzeug = Object.keys(posMap).filter(k => !_ALLE_FAHRZEUG_KEYS.has(k));

  const alleKeys = new Set([
    ...[..._fahrzeugKeysSet].filter(k => _getFahrzeugBetrag(k) > 0),
    ..._nichtFahrzeugKeys,
    ..._posMapNichtFahrzeug.filter(k => !_extraCoveredKeys.has(k)),
    // Aus posMap auch Fahrzeug-Keys übernehmen wenn reguliert (für Regulierungshistorie)
    ...Object.keys(posMap).filter(k => _fahrzeugKeysSet.has(k)),
  ]);

  const posTableRows = [...alleKeys].map(key => {
    const istAbzug  = ABZUG_FELDER.has(key);
    const betrag    = _ALLE_FAHRZEUG_KEYS.has(key)
      ? _getFahrzeugBetrag(key)
      : (parseFloat(schaden[key]) || posMap[key]?.gefordert || 0);
    const forderung = istAbzug ? -betrag : betrag;
    const reguliert = posMap[key]?.reguliert ?? null;
    const kuerzung  = reguliert != null ? Math.max(0, Math.abs(forderung) - (reguliert ?? 0)) : null;
    const label     = POSITION_LABELS_FE[key] || SCHADEN_POS_MAP[key] || key;
    const fuerKlage = posMap[key]?.fuerKlage || false;
    return { key, label, forderung, betrag, istAbzug, reguliert, kuerzung, fuerKlage };
  }).filter(r => r.betrag > 0 || (r.reguliert != null && r.reguliert > 0));

  // Extras: Regulierungsstand mergen via posMap (wdm_ss1 direkt, sonstiges_wdm_1 als Fallback)
  const extraRows = _rawExtras.filter(e => (e.betrag||0) > 0).map(e => {
    const slot = String(e.id || "").replace("wdm_ss", "");
    const reg = posMap[e.id] || (slot && !isNaN(slot) ? posMap[`sonstiges_wdm_${slot}`] : null);
    const betrag = e.betrag;
    const reguliert = reg?.reguliert ?? null;
    const kuerzung  = reguliert != null ? Math.max(0, betrag - reguliert) : null;
    return {
      key: `extra_${e.id}`, label: e.label || "Sonstiger Schaden",
      forderung: betrag, betrag, istAbzug: false,
      reguliert, kuerzung, fuerKlage: reg?.fuerKlage || false,
    };
  });
  const alleRows = [...posTableRows, ...extraRows];

  const gesamtForderung = alleRows.reduce((s, r) => s + r.forderung, 0);
  const gesamtReguliert = alleRows.reduce((s, r) => s + (r.reguliert ?? 0), 0);
  const gesamtKuerzung  = alleRows.reduce((s, r) => s + (r.kuerzung ?? 0), 0);
  const klageSumme      = alleRows.filter(r => r.fuerKlage).reduce((s, r) => s + (r.kuerzung || 0), 0);
  const regGrad         = netto > 0 ? Math.min(100, Math.round(gesamtReguliert / netto * 100)) : 0;
  const hatRegulierung  = abrechnungen.length > 0;

  const InfoRow = ({ label, value }) => value ? (
    <div style={{ borderBottom:`1px solid ${T.borderSoft}`, padding:"6px 0", display:"flex", gap:12 }}>
      <span style={{ fontSize:"0.84rem", color:T.textFaint, width:110, flexShrink:0 }}>{label}</span>
      <span style={{ fontSize:"0.93rem", color:T.text }}>{value}</span>
    </div>
  ) : null;

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {/* ── RA-Micro Live-Daten (nur bei gültigem AZ-Format ZAHL/JJ) ── */}
        {(() => { const az = akte.az_roh || akte.az || ""; return az.includes("/") && az.length >= 4; })() && (
          <RaMicroAkteUebersicht azRoh={akte.az_roh || akte.az} />
        )}

        {/* ── Zeile 2: Notizen (volle Breite – Status jetzt im Header) ── */}
        <Card style={{ padding:"0.6rem 1rem", display:"flex", flexDirection:"column", gap:5 }}>
          <div style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em" }}>Notizen</div>
          <textarea value={notizen} onChange={e => { setNotizen(e.target.value); setNC(true); }} rows={2}
            placeholder="Interne Notizen …"
            style={{ padding:"5px 8px", border:`1.5px solid ${T.border}`, borderRadius:6, fontSize:"0.875rem", color:T.text, background:T.surface, outline:"none", resize:"none" }}
            onFocus={e => e.target.style.borderColor=T.gold} onBlur={e => e.target.style.borderColor=T.border} />
          {nChanged && <Btn variant="gold" size="sm" onClick={async () => { dispatch({ type:"SET_NOTIZEN", akteId:akte.id, notizen }); setNC(false); setToast("Notizen gespeichert."); try { await apiAkten.aktualisieren(akte.id, { notizen }); } catch {} }}>{Ic.check} Speichern</Btn>}
        </Card>

        {/* ── Zeile 3: Positions-Gegenüberstellung ── */}
        <Card style={{ background:"rgba(84,136,212,0.06)", border:"1px solid rgba(84,136,212,0.25)" }}>
          <CardHead title="Forderung vs. Regulierung – Positionsübersicht" />
          <RegulierungsTabelle
            schaden={schaden}
            abrechnungen={abrechnungen}
            showCheckboxes={false}
            showKlageBadge={true}
          />
          {/* Regulierungsgrad-Balken */}
          {hatRegulierung && (
            <div style={{ padding:"0.75rem 1.4rem 1rem" }}>
              <div style={{ height:8, background:T.border, borderRadius:4, overflow:"hidden" }}>
                <div style={{ height:"100%", width:`${regGrad}%`, background:regGrad>=100?`linear-gradient(90deg,${T.green},#34d399)`:`linear-gradient(90deg,${T.gold},${T.goldLight})`, borderRadius:4, transition:"width 0.8s" }} />
              </div>
              <div style={{ display:"flex", justifyContent:"space-between", marginTop:5, fontSize:"0.84rem", color:T.textMuted }}>
                <span>{regGrad} % reguliert · {abrechnungen.length} Schreiben</span>
                {klageSumme > 0 && <span style={{ color:T.red, fontWeight:600 }}>Klagepotential: {fmtEuro(klageSumme)}</span>}
              </div>
            </div>
          )}
        </Card>

        {/* ── Zeile 4: Forderungshistorie ── */}
        <ForderungshistorieKarte akteId={akte.id} />

        {/* ── Zeile 5: Kombinierte Verlaufs-Timeline ── */}
        <AktenTimeline
          abrechnungen={abrechnungen}
          aktivitaeten={st.aktivitaeten || []}
          akteId={akte.id}
          onAktivitaetenChange={async () => {
            const data = await apiAkten.aktivitaeten(akte.id);
            if (data?.aktivitaeten)
              dispatch({ type:"SET_AKTIVITAETEN", akteId: akte.id, aktivitaeten: data.aktivitaeten });
          }}
        />

        {/* ── To-Do-Kachel (kompakt, nur offene) ── */}
        <TodoKachelKompakt az={akte.az} akteId={akte.id} />

      </div>
    </>
  );
}


export { RegulierungsTabelle, TodoSection };
export default UebersichtSection;
