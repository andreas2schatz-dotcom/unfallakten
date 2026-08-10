import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { HAFTUNGSART_CFG, TIMELINE_FILTER, TIMELINE_TYPE_CFG, POSITION_LABELS_FE } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Card, Btn, Toast } from "../components/common.jsx";
import OnboardingFaecher from "./OnboardingFaecher.jsx";
import PositionsDashboard from "../components/PositionsDashboard.jsx";
import EreignislistePanel from "../components/EreignislistePanel.jsx";
import {
  akten as apiAkten,
  ramicroAkte as apiRaMicroAkte,
  apiTodos,
  request,
} from "../api.js";
import { ibanAnfrageMailto, vollmachtAnfrageMailto, vollmachtPdfLaden } from "./mandantAktionen.js";
import { berechneOnboardingChecks } from "./onboardingChecks.js";

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
          fontFamily:T.fontBody, fontSize:"0.78rem", fontWeight:600,
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
        }}>⌄</span>
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
            zeigeBetreff
          />
        </div>
      )}
    </div>
  );
}


function BeteiligterKachel({ titel, farbe, beteiligte, zeigeFirma=false, zeigeBetreff=false, zeigeAktenzeichen=false, nurEiner=false, ausklappbar=false, standardOffen=true, localStorageKey=null }) {
  const liste = nurEiner ? beteiligte.slice(0,1) : beteiligte;

  const [offen, setOffen] = useState(() => {
    if (!ausklappbar) return true;
    if (localStorageKey) {
      const saved = localStorage.getItem(localStorageKey);
      if (saved !== null) return saved === "true";
    }
    return standardOffen;
  });

  const toggle = () => {
    const neu = !offen;
    setOffen(neu);
    if (localStorageKey) localStorage.setItem(localStorageKey, String(neu));
  };

  if (!liste.length) return null;

  const mailtoLink = (b) => {
    if (!b.email) return null;
    const betreffs = [b.betreff1, b.betreff2, b.betreff3].filter(Boolean).join(" – ");
    return `mailto:${b.email}${betreffs ? `?subject=${encodeURIComponent(betreffs)}` : ""}`;
  };

  return (
    <div style={{ background:T.cardBg, border: titel ? `1px solid ${T.border}` : "none", borderRadius: titel ? 10 : 0, overflow:"hidden", boxShadow: titel ? "0 1px 4px rgba(0,0,0,0.04)" : "none" }}>
      {/* Kachel-Header – wird ausgeblendet wenn kein Titel (z.B. in RechtsschutzKlappkachel) */}
      {titel && (
        ausklappbar ? (
          <button
            onClick={toggle}
            style={{
              width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
              background: farbe + "18", borderBottom: offen ? `1px solid ${farbe}33` : "none",
              padding:"8px 14px", cursor:"pointer", border:"none", textAlign:"left",
            }}>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <div style={{ width:8, height:8, borderRadius:"50%", background:farbe, flexShrink:0 }} />
              <span style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600, color:farbe, textTransform:"uppercase", letterSpacing:"0.08em" }}>{titel}</span>
            </div>
            {liste.length > 1 && <span style={{ fontFamily:T.fontBody, fontSize:"0.78rem", color:T.textFaint }}>{liste.length} Einträge</span>}
            <span style={{ fontSize:"0.9rem", color:farbe, transform: offen ? "rotate(180deg)" : "none", transition:"transform 0.2s", lineHeight:1 }}>⌄</span>
          </button>
        ) : (
          <div style={{ background: farbe + "18", borderBottom:`1px solid ${farbe}33`, padding:"8px 14px", display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ width:8, height:8, borderRadius:"50%", background:farbe, flexShrink:0 }} />
            <span style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600, color:farbe, textTransform:"uppercase", letterSpacing:"0.08em" }}>{titel}</span>
            {liste.length > 1 && <span style={{ marginLeft:"auto", fontFamily:T.fontBody, fontSize:"0.78rem", color:T.textFaint }}>{liste.length} Einträge</span>}
          </div>
        )
      )}

      {/* Einträge */}
      {(!ausklappbar || offen) && liste.map((b, i) => (
        <div key={i} style={{ padding:"10px 14px", borderBottom: i < liste.length-1 ? `1px solid ${T.borderSoft}` : "none" }}>
          {/* Name / Firma */}
          <div style={{ fontFamily:T.fontBody, fontSize:"0.925rem", fontWeight:600, color:T.navy, marginBottom:3 }}>
            {zeigeFirma && b.name ? b.name : b.name || "–"}
            {b.kennzeichen && <span style={{ marginLeft:8, fontFamily:"ui-monospace,monospace", fontSize:"0.75rem", background:T.accentPale, color:T.navy, border:`1px solid ${T.accentTrim}`, borderRadius:4, padding:"1px 5px" }}>{b.kennzeichen}</span>}
          </div>

          {/* Betreffzeilen (fett) */}
          {zeigeBetreff && (b.betreff1 || b.betreff2 || b.betreff3) && (
            <div style={{ fontFamily:T.fontBody, fontSize:"0.855rem", fontWeight:600, color:T.textMid, marginBottom:4 }}>
              {[b.betreff1, b.betreff2, b.betreff3].filter(Boolean).join(" · ")}
            </div>
          )}

          {/* Aktenzeichen (fett, für Behörden) */}
          {zeigeAktenzeichen && b.betreff1 && (
            <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.855rem", fontWeight:700, color:T.navy, marginBottom:4 }}>
              {b.betreff1}
            </div>
          )}

          {/* Adressdetails */}
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            {b.strasse && <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted }}>{b.strasse}{b.plz || b.ort ? `, ${b.plz} ${b.ort}`.trim() : ""}</span>}
            {b.telefon  && <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted }}>☎ {b.telefon}</span>}
            {b.telefon2 && <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted }}>☎ {b.telefon2}</span>}
            {b.mobil    && <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted }}>📱 {b.mobil}</span>}
            {b.fax      && <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted }}>📠 {b.fax}</span>}
            {b.email && (
              <a href={mailtoLink(b)} style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.blue, textDecoration:"none" }}
                 onMouseEnter={e => e.target.style.textDecoration="underline"}
                 onMouseLeave={e => e.target.style.textDecoration="none"}>
                ✉ {b.email}
              </a>
            )}
            {/* Vorsteuerabzug nur bei Mandanten anzeigen */}
            {titel === "Mandant" && (
              <span style={{
                fontFamily:T.fontBody, fontSize:"0.8rem",
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
      <div style={{ fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600, color:T.textFaint, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:5 }}>
        Eigene Versicherung
      </div>
      {beteiligte.map((b, i) => (
        <div key={i} style={{ fontFamily:T.fontBody, fontSize:"0.855rem", color:T.textMid, marginBottom: i < beteiligte.length-1 ? 3 : 0 }}>
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
    <div style={{ display:"flex", alignItems:"center", gap:10, padding:"2rem", color:T.textFaint, fontFamily:T.fontBody }}>
      <div style={{ width:18, height:18, border:`2px solid ${T.accent}`, borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
      Lade RA-Micro Daten …
    </div>
  );

  if (fehler) return (
    <Card>
      <div style={{ padding:"1rem 1.4rem", display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:10 }}>
        <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:T.amber }}>
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

  const { beteiligte: b } = daten;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:"1.1rem" }}>

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
                  ausklappbar={true}
                  localStorageKey={`uebersicht-kachel-mandant-${azRoh}`}
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
                      ausklappbar={true}
                      localStorageKey={`uebersicht-kachel-weitere-${azRoh}`}
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
          ausklappbar={true}
          localStorageKey={`uebersicht-kachel-gegner-${azRoh}`}
        />

        {/* Behörden / Gerichte */}
        <BeteiligterKachel
          titel="Behörden / Gerichte" farbe={T.amber}
          beteiligte={b.behoerde}
          zeigeAktenzeichen zeigeBetreff={false}
          ausklappbar={true}
          localStorageKey={`uebersicht-kachel-behoerde-${azRoh}`}
        />

      </div>
    </div>
  );
}


function AktenTimeline({ abrechnungen, aktivitaeten, akteId, onAktivitaetenChange }) {
  const [filter, setFilter] = useState("alle");
  const [loeschend, setLoeschend] = useState(null); // id gerade gelöscht wird
  const [toast, setToast]         = useState("");

  const loescheAktivitaet = async (id) => {
    setLoeschend(id);
    try {
      await apiAkten.aktivitaetLoeschen(akteId, id);
      if (onAktivitaetenChange) onAktivitaetenChange();
    } catch (e) {
      setToast("Löschen fehlgeschlagen: " + (e?.message || e));
    } finally {
      setLoeschend(null);
    }
  };

  const regEntries = abrechnungen.map(ab => {
    const ha  = HAFTUNGSART_CFG[ab.haftungsart] || HAFTUNGSART_CFG.vollhaftung;
    const typ = ab.haftungsart === "ablehnung" ? "ablehnung" : "abrechnung";
    const abDatum = ab.datum || "";
    return {
      id: `ab-${ab.id}`, kategorie:"regulierung", typ,
      sortKey: abDatum.includes(".") ? abDatum.split(".").reverse().join("-") : abDatum,
      datum: abDatum,
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
      sortKey: (a.zeitstempel || a.zeit || "").replace(" ", "T"),
      datum,
      datumAnzeige,
      uhrzeitAnzeige,
      titel,
      zeile1: a.beschreibung || a.aktion || "",
      zeile2: "",
      dotColor: TIMELINE_TYPE_CFG.taetigkeit.dot,
    };
  });

  const alle = [...regEntries, ...aktEntries].sort(
    (a, b) => (b.sortKey || "").localeCompare(a.sortKey || "")
  );

  const sichtbar = filter === "alle" ? alle :
                   alle.filter(e => e.kategorie === filter);

  return (
    <>
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
                fontFamily:T.fontBody, fontWeight: filter===f.id ? 600 : 400,
                border:"1.5px solid " + (filter===f.id ? T.accent : T.border),
                background: filter===f.id ? T.accentPale : "transparent",
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
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    </>
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
  const effRep = repRN > 0 ? repRN : repN;
  const ist130 = repRN > 0 && wbw > 0 && repRN > nettoFzg && repRN <= 1.3 * wbw;
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


function TodoSection({ az, onTodoChange }) {
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
    rot:    { bg: T.redBg, border: T.redLight, dot: T.red, label: "Dringend" },
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
            fontFamily:T.fontBody, fontSize:"0.925rem",
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
              <span style={{ fontSize:"0.72rem", color:T.textMuted, fontFamily:"ui-monospace,monospace" }}>
                Fällig: {(() => { try { const [y,m,d] = todo.faellig_am.split("-"); return `${d}.${m}.${y}`; } catch { return todo.faellig_am; } })()}
                {todo.frist_typ === "verjaehrung" && " ⚠️ Verjährung"}
              </span>
            )}
            {istSystem && (
              <span style={{ fontSize:"0.72rem", color:T.textFaint }}>🔒 System</span>
            )}
            {todo.erledigt_am && (
              <span style={{ fontSize:"0.72rem", color:T.textFaint, fontFamily:"ui-monospace,monospace" }}>
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
              <div style={{ fontFamily:T.fontDisplay, fontSize:"1.15rem",
                fontWeight:700, color:T.navy }}>
                To-Dos
                {offen.length > 0 && (
                  <span style={{ marginLeft:8, fontSize:"0.825rem", background:T.redBg,
                    color:T.red, borderRadius:12, padding:"2px 8px", fontFamily:T.fontBody,
                    fontWeight:600, verticalAlign:"middle" }}>
                    {offen.length} offen
                  </span>
                )}
              </div>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.85rem",
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
            <div style={{ margin:"0 1.4rem 1rem", background:T.accentPale,
              border:`1px solid ${T.accentTrim}`, borderRadius:10, padding:"1rem 1.25rem" }}>
              <div style={{ marginBottom:"0.75rem" }}>
                <label style={{ fontFamily:T.fontBody, fontSize:"0.825rem",
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
                    borderRadius:7, fontFamily:T.fontBody, fontSize:"0.925rem",
                    color:T.text, background:T.surface, outline:"none", resize:"vertical",
                    lineHeight:1.5, boxSizing:"border-box" }}
                  onFocus={e => e.target.style.borderColor=T.accent}
                  onBlur={e => e.target.style.borderColor=T.border}
                />
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.75rem",
                marginBottom:"0.75rem" }}>
                <div>
                  <label style={{ fontFamily:T.fontBody, fontSize:"0.825rem",
                    fontWeight:600, color:T.textMid, textTransform:"uppercase",
                    letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                    Fällig am (optional)
                  </label>
                  <input type="date" value={neuesFaellig}
                    onChange={e => setNeuesFaellig(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`,
                      borderRadius:7, fontFamily:T.fontBody, fontSize:"0.9rem",
                      color:T.text, background:T.surface, outline:"none", boxSizing:"border-box" }}
                    onFocus={e => e.target.style.borderColor=T.accent}
                    onBlur={e => e.target.style.borderColor=T.border}
                  />
                </div>
                <div>
                  <label style={{ fontFamily:T.fontBody, fontSize:"0.825rem",
                    fontWeight:600, color:T.textMid, textTransform:"uppercase",
                    letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                    Fristtyp
                  </label>
                  <select value={neueFristTyp} onChange={e => setNeueFristTyp(e.target.value)}
                    style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`,
                      borderRadius:7, fontFamily:T.fontBody, fontSize:"0.9rem",
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
            fontFamily:T.fontBody }}>Lade To-Dos …</div>
        ) : todos.length === 0 ? (
          <Card>
            <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
              fontFamily:T.fontBody, fontSize:"0.925rem" }}>
              Keine To-Dos für diese Akte.
            </div>
          </Card>
        ) : (
          <Card>
            <div style={{ padding:"1rem 1.4rem" }}>
              {offen.length > 0 && (
                <>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.78rem",
                    fontWeight:600, color:T.textMuted, textTransform:"uppercase",
                    letterSpacing:"0.08em", marginBottom:8 }}>
                    Offen ({offen.length})
                  </div>
                  {offen.map(renderTodo)}
                </>
              )}
              {erledigt.length > 0 && (
                <>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.78rem",
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

function KlappAbschnitt({ titel, lsKey, children, standardOffen = true }) {
  const [offen, setOffen] = useState(() => {
    try {
      const v = localStorage.getItem(lsKey);
      return v !== null ? v === "true" : standardOffen;
    } catch { return standardOffen; }
  });
  const toggle = () => {
    const neu = !offen;
    setOffen(neu);
    try { localStorage.setItem(lsKey, String(neu)); } catch {}
  };
  return (
    <div>
      <button
        onClick={toggle}
        style={{
          width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
          background: offen ? T.accentPale : T.surface,
          border: `1px solid ${offen ? T.accentTrim : T.border}`,
          borderRadius: 8, padding:"8px 14px", cursor:"pointer", textAlign:"left",
          boxShadow:"0 1px 3px rgba(0,0,0,0.06)", marginBottom: offen ? 6 : 0,
          transition:"background 0.15s, border-color 0.15s",
        }}
      >
        <span style={{
          fontFamily:T.fontBody, fontSize:"0.825rem", fontWeight:600,
          color: offen ? T.accent : T.textMid,
          textTransform:"uppercase", letterSpacing:"0.08em",
        }}>{titel}</span>
        <span style={{
          fontSize:"1.1rem", color: offen ? T.accent : T.textFaint, lineHeight:1,
          transform: offen ? "rotate(180deg)" : "none",
          transition:"transform 0.2s",
        }}>⌄</span>
      </button>
      {offen && children}
    </div>
  );
}

const STRIP_TABS = [
  { id:"ramicro", label:"🏛 RA-Micro Beteiligte" },
  { id:"chronik", label:"🕒 Chronik" },
  { id:"notizen", label:"📝 Notizen" },
];

function AkkordeonStrip({ offene, onToggle }) {
  return (
    <div style={{
      borderTop:`2px solid ${T.border}`,
      display:"flex", flexWrap:"wrap",
    }}>
      {STRIP_TABS.map((tab, i) => (
        <button key={tab.id} onClick={() => onToggle(tab.id)}
          style={{
            flex:1, minWidth:130,
            padding:"9px 14px",
            fontFamily:T.fontBody, fontSize:".72rem",
            color: offene.includes(tab.id) ? T.accentDark : T.textFaint,
            background: offene.includes(tab.id) ? T.accentPale : T.surface,
            border:"none",
            borderRight: i < STRIP_TABS.length - 1 ? `1px solid ${T.border}` : "none",
            cursor:"pointer", textAlign:"left",
            display:"flex", alignItems:"center", gap:5,
            transition:"background .15s, color .15s",
          }}>
          {tab.label}
          <span style={{ marginLeft:"auto", fontSize:".75rem" }}>
            {offene.includes(tab.id) ? "▲" : "▾"}
          </span>
        </button>
      ))}
    </div>
  );
}

function TodoWvSpalten({ azRoh, todos = [] }) {
  const [wvListe, setWvListe] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const wvCall = azRoh && azRoh.includes("/")
      ? request(`/wiedervorlage/?az=${encodeURIComponent(azRoh)}&alle_gruende=true&alle_daten=true&limit=10`)
          .then(r => r?.wiedervorlagen || [])
          .catch(() => [])
      : Promise.resolve([]);

    wvCall.then(wRes => setWvListe(wRes)).finally(() => setLoading(false));
  }, [azRoh]);

  const offen = todos.filter(t => !t.erledigt);

  const dringlichkeit = (todo) => {
    const heute = new Date(); heute.setHours(0,0,0,0);
    if (todo.faellig_am) {
      const f = new Date(todo.faellig_am); f.setHours(0,0,0,0);
      const tage = Math.round((f - heute) / 86400000);
      const s = tage < 0 ? "rot" : tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
      return todo.frist_typ === "verjaehrung" ? ({rot:"rot",orange:"rot",gelb:"orange",grau:"gelb"}[s]||s) : s;
    }
    const alter = Math.round((heute - new Date(todo.erstellt_am)) / 86400000);
    return alter >= 15 ? "rot" : alter >= 8 ? "orange" : alter >= 4 ? "gelb" : "grau";
  };

  const DOT = { rot:"#ef4444", orange:"#f97316", gelb:"#eab308", grau:T.textFaint };

  const fmtD = (iso) => {
    if (!iso) return "";
    try { const [,m,d] = iso.split("-"); return `${d}.${m}.`; } catch { return ""; }
  };

  if (loading) return null;

  const hatWv = wvListe.length > 0;

  return (
    <div style={{
      display:"grid",
      gridTemplateColumns: hatWv ? "1fr 1px 1fr" : "1fr",
      padding:"12px 18px 14px", gap:0,
    }}>
      {/* Todos */}
      <div style={{ paddingRight: hatWv ? 16 : 0 }}>
        <div style={{ fontSize:".65rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".08em", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
          📋 To-Dos
          {offen.length > 0 && (
            <span style={{ background:T.redBg, color:T.red, borderRadius:10, padding:"1px 7px", fontSize:".62rem", fontWeight:700 }}>
              {offen.length} offen
            </span>
          )}
        </div>
        {offen.length === 0 ? (
          <div style={{ fontSize:".875rem", color:T.textFaint, fontFamily:T.fontBody }}>✅ Alle erledigt</div>
        ) : (
          offen.slice(0, 5).map(todo => {
            const d = dringlichkeit(todo);
            return (
              <div key={todo.id} style={{ display:"flex", alignItems:"flex-start", gap:7, padding:"5px 0", borderBottom:`1px solid ${T.borderSoft}` }}>
                <span style={{ width:8, height:8, borderRadius:"50%", background:DOT[d], flexShrink:0, marginTop:5 }} />
                <span style={{ fontFamily:T.fontBody, fontSize:".875rem", color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {todo.text}
                </span>
                {todo.faellig_am && (
                  <span style={{ fontFamily:T.fontMono, fontSize:".68rem", color:T.textFaint, flexShrink:0 }}>
                    {fmtD(todo.faellig_am)}
                  </span>
                )}
              </div>
            );
          })
        )}
        {offen.length > 5 && (
          <div style={{ fontSize:".78rem", color:T.textFaint, marginTop:5, fontFamily:T.fontBody }}>
            + {offen.length - 5} weitere …
          </div>
        )}
      </div>

      {/* Trennlinie */}
      {hatWv && <div style={{ background:T.border, width:1 }} />}

      {/* Wiedervorlagen */}
      {hatWv && (
        <div style={{ paddingLeft:16 }}>
          <div style={{ fontSize:".65rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".08em", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
            📅 Wiedervorlagen
            <span style={{ background:T.amberMid, color:T.amberText, borderRadius:10, padding:"1px 7px", fontSize:".62rem", fontWeight:700 }}>
              {wvListe.length} fällig
            </span>
          </div>
          {wvListe.slice(0, 4).map((wv, i) => (
            <div key={wv.guid || i} style={{
              background:T.amberMid, border:`1px solid ${T.amber}50`,
              borderRadius:6, padding:"6px 10px", marginBottom:5,
            }}>
              <div style={{ fontFamily:T.fontBody, fontSize:".78rem", fontWeight:700, color:T.amberText, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                {wv.grund || "Wiedervorlage"}
              </div>
              <div style={{ fontFamily:T.fontMono, fontSize:".68rem", color:T.amberText, marginTop:2 }}>
                fällig {fmtD(wv.datum)}{new Date(wv.datum).getFullYear()}
              </div>
            </div>
          ))}
          {wvListe.length > 4 && (
            <div style={{ fontSize:".72rem", color:T.textFaint }}>+ {wvListe.length - 4} weitere</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── PRD-18: Phasen-Strip ─────────────────────────────────────────────────────

const _PHASEN_ORDER = ["onboarding", "erstforderung", "regulierung", "stellungnahme", "abschluss"];

function berechnePhase({ akte, ibanCheck, schaden, abrechnungen, summen }) {
  const hatIban       = !!ibanCheck?.iban_vorhanden;
  const hatSchaden    = parseFloat(schaden?.gesamt_brutto || 0) > 0 || summen.gefordert > 0;
  const hatAbrechnung = (abrechnungen || []).length > 0;
  const hatKuerzung   = hatAbrechnung && summen.offen > 0.005;
  const vollreguliert = summen.gefordert > 0 && summen.reguliert >= summen.gefordert * 0.99;
  const statusKlage   = akte.status === "klage";
  const istAbschluss  = vollreguliert || akte.status === "abgeschlossen" || statusKlage;

  let aktiv;
  if (istAbschluss)                      aktiv = "abschluss";
  else if (hatAbrechnung && hatKuerzung) aktiv = "stellungnahme";
  else if (hatAbrechnung)                aktiv = "regulierung";
  else if (hatIban && hatSchaden)        aktiv = "erstforderung";
  else                                   aktiv = "onboarding";

  const aktivIdx     = _PHASEN_ORDER.indexOf(aktiv);
  const phasenFertig = Object.fromEntries(_PHASEN_ORDER.map((p, i) => [p, i < aktivIdx]));
  return { aktiv, istKlage: statusKlage, phasenFertig };
}

function PhasenStrip({ phase, onboarding = null, faecherOffen = false, onToggleFaecher = null }) {
  if (!phase) return null;
  const { aktiv, istKlage, phasenFertig } = phase;
  const PHASEN = [
    { id: "onboarding",    label: "Onboarding" },
    { id: "erstforderung", label: "Erstforderung" },
    { id: "regulierung",   label: "Regulierung" },
    { id: "stellungnahme", label: "Stellungnahme" },
    { id: "abschluss",     label: istKlage ? "⚖ Klage" : "Abschluss" },
  ];
  return (
    <div style={{ display:"flex", alignItems:"stretch", borderBottom:`1px solid ${T.border}`, overflow:"hidden" }}>
      {PHASEN.map((p, i) => {
        const fertig  = phasenFertig[p.id];
        const isAktiv = aktiv === p.id;
        const last    = i === PHASEN.length - 1;
        const bg    = fertig ? T.greenBg  : isAktiv ? T.blueBg  : T.cardBg;
        const color = fertig ? T.greenText : isAktiv ? T.accent   : T.textFaint;
        const icon  = fertig ? "✓"        : isAktiv ? "▶"        : "○";
        const mitFaecher = p.id === "onboarding" && isAktiv && onboarding;
        const inhalt = (
          <>
            <span>{icon}</span><span>{p.label}</span>
            {mitFaecher && (
              <span style={{ background:T.amberMid, color:T.amberText, borderRadius:10,
                padding:"0 6px", fontWeight:700 }}>
                {onboarding.erledigt}/{onboarding.pflichtAnzahl}
              </span>
            )}
            {mitFaecher && <span>{faecherOffen ? "▴" : "▾"}</span>}
          </>
        );
        const stil = {
          flex:1, display:"flex", alignItems:"center", justifyContent:"center",
          gap:4, padding:"6px 4px",
          background:bg, color,
          borderRight: last ? "none" : `1px solid ${T.border}`,
          fontSize:"0.68rem", fontWeight:600,
          letterSpacing:"0.04em", textTransform:"uppercase", whiteSpace:"nowrap",
          fontFamily:T.fontBody,
        };
        return mitFaecher ? (
          <button key={p.id} onClick={onToggleFaecher} style={{ ...stil, border:"none", cursor:"pointer",
            borderRight: last ? "none" : `1px solid ${T.border}` }}>
            {inhalt}
          </button>
        ) : (
          <div key={p.id} style={stil}>{inhalt}</div>
        );
      })}
    </div>
  );
}

const AktionsPill = ({ ok, label, aktionen }) => {
  const [offen, setOffen] = React.useState(false);
  const hatAktionen = ok === false && aktionen.length > 0;
  let bg, color, border;
  if (ok === true)       { bg = T.greenBg; color = T.greenText; border = T.greenLight; }
  else if (ok === false) { bg = T.redBg;   color = T.redText;   border = T.redLight;   }
  else                   { bg = T.surface; color = T.textFaint; border = T.border;     }
  return (
    <span style={{ position:"relative", display:"inline-flex" }}>
      <button
        onClick={() => hatAktionen && setOffen(o => !o)}
        style={{ display:"inline-flex", alignItems:"center", gap:4,
          fontSize:"0.7rem", fontWeight:600, padding:"3px 9px",
          borderRadius:20, border:`1px solid ${border}`, background:bg, color,
          whiteSpace:"nowrap", cursor: hatAktionen ? "pointer" : "default",
          fontFamily:T.fontBody }}>
        {label}{hatAktionen && " ▾"}
      </button>
      {offen && (
        <span style={{ position:"absolute", top:"calc(100% + 4px)", left:0, zIndex:60,
          background:T.cardBg, border:`1px solid ${T.border}`, borderRadius:8,
          boxShadow:"0 6px 18px rgba(0,0,0,.14)", padding:"6px 8px",
          display:"flex", gap:6, whiteSpace:"nowrap" }}>
          {aktionen}
        </span>
      )}
    </span>
  );
};

const aktionChip = {
  fontFamily:T.fontBody, fontSize:"0.72rem", fontWeight:600, padding:"3px 9px",
  borderRadius:6, border:`1px solid ${T.accentTrim}`, background:T.accentPale,
  color:T.accentDark, textDecoration:"none", cursor:"pointer",
};

function StatusBand({ ibanCheck, todos, hq, akteId, mandant, onFehler }) {
  const vollmacht = ibanCheck?.vollmacht_vorhanden;
  const iban      = ibanCheck?.iban_vorhanden;
  const rsv       = ibanCheck?.rechtsschutz_deckung;

  const Pill = ({ ok, warn, neutral, label }) => {
    let bg, color, border;
    if (ok === true)               { bg = T.greenBg;  color = T.greenText;  border = T.greenLight; }
    else if (warn)                 { bg = T.amberMid; color = T.amberText;  border = T.amber + "80"; }
    else if (neutral || ok !== false){ bg = T.surface; color = T.textFaint; border = T.border;     }
    else                           { bg = T.redBg;    color = T.redText;    border = T.redLight;   }
    return (
      <span style={{
        display:"inline-flex", alignItems:"center", gap:4,
        fontSize:"0.7rem", fontWeight:600, padding:"3px 9px",
        borderRadius:20, border:`1px solid ${border}`,
        background:bg, color, whiteSpace:"nowrap",
      }}>{label}</span>
    );
  };

  const heute = new Date(); heute.setHours(0,0,0,0);
  const fristTodo = (todos || []).find(t => !t.erledigt && (t.frist_typ === "gericht" || t.frist_typ === "gerichtlich"));
  const verjTodo  = (todos || []).find(t => !t.erledigt && t.frist_typ === "verjaehrung");

  const tageBis = (iso) => {
    if (!iso) return null;
    const d = new Date(iso); d.setHours(0,0,0,0);
    return Math.round((d - heute) / 86400000);
  };

  const fristTage = fristTodo ? tageBis(fristTodo.faellig_am) : null;
  const verjTage  = verjTodo  ? tageBis(verjTodo.faellig_am)  : null;

  const fmtDatum = (iso) => {
    if (!iso) return "";
    try { const [y,m,d] = iso.split("-"); return `${d}.${m}.${y}`; } catch { return iso; }
  };

  return (
    <div style={{
      background:T.surface, borderTop:`1px solid ${T.border}`,
      padding:"7px 18px", display:"flex", alignItems:"center",
      flexWrap:"wrap", gap:0,
    }}>
      <div style={{ display:"flex", gap:7, alignItems:"center", paddingRight:14, marginRight:14, borderRight:`1px solid ${T.border}`, flexWrap:"wrap" }}>
        <span style={{ fontSize:".62rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".07em" }}>Checks</span>
        <AktionsPill ok={vollmacht}
          label={vollmacht === true ? "✓ Vollmacht" : vollmacht === false ? "✗ Vollmacht fehlt" : "○ Vollmacht"}
          aktionen={vollmacht === false ? [
            <a key="anf" href={vollmachtAnfrageMailto(ibanCheck, mandant)} style={aktionChip}>✉ anfordern</a>,
            <button key="pdf" style={aktionChip}
              onClick={() => akteId && vollmachtPdfLaden(akteId).catch(e => onFehler && onFehler(`Vollmacht-Fehler: ${e.message}`))}>
              ↓ PDF generieren
            </button>,
          ] : []} />
        <AktionsPill ok={iban}
          label={iban === true ? "✓ IBAN" : iban === false ? "✗ IBAN fehlt" : "○ IBAN"}
          aktionen={iban === false ? [
            <a key="anf" href={ibanAnfrageMailto(ibanCheck, mandant)} style={aktionChip}>✉ IBAN anfordern</a>,
          ] : []} />
        <Pill ok={rsv === true} neutral={rsv === false}
          label={rsv === true ? "✓ RSV" : "○ Keine RSV"} />
      </div>

      <div style={{ display:"flex", gap:7, alignItems:"center", flexWrap:"wrap" }}>
        {fristTage !== null && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", fontWeight: fristTage <= 7 ? 700 : 400,
            padding:"3px 9px", borderRadius:20, whiteSpace:"nowrap",
            border:`1px solid ${fristTage <= 7 ? T.redLight : T.border}`,
            background: fristTage <= 7 ? T.redBg : T.surface,
            color: fristTage <= 7 ? T.redText : T.textFaint,
          }}>§3a-Frist: {fristTage < 0 ? "überschritten" : `${fristTage} Tage`}</span>
        )}
        {verjTage !== null && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", fontWeight: verjTage <= 14 ? 700 : 400,
            padding:"3px 9px", borderRadius:20, whiteSpace:"nowrap",
            border:`1px solid ${verjTage <= 60 ? T.amber + "80" : T.border}`,
            background: verjTage <= 14 ? T.redBg : verjTage <= 60 ? T.amberMid : T.surface,
            color: verjTage <= 14 ? T.redText : verjTage <= 60 ? T.amberText : T.textFaint,
          }}>Verjährung: {fmtDatum(verjTodo.faellig_am)}</span>
        )}
        {hq !== null && hq !== undefined && hq < 100 && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", padding:"3px 9px", borderRadius:20,
            border:`1px solid ${T.amber}80`, background:T.amberMid, color:T.amberText,
            whiteSpace:"nowrap",
          }}>HQ {hq} %</span>
        )}
      </div>
    </div>
  );
}

function TodoInlineForm({ az, onDone }) {
  const [text, setText]       = React.useState("");
  const [faellig, setFaellig] = React.useState("");
  const [busy, setBusy]       = React.useState(false);
  const [toast, setToast]     = React.useState("");

  const speichern = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await apiTodos.erstelle(az, { text: text.trim(), faellig_am: faellig || null, frist_typ: "" });
      onDone();
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
        <input
          type="text" value={text} onChange={e => setText(e.target.value)}
          placeholder="To-Do Text …"
          style={{
            flex:1, minWidth:200, padding:"6px 10px",
            border:`1.5px solid ${T.border}`, borderRadius:6,
            fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
            background:T.cardBg || "#ffffff", outline:"none",
          }}
          onFocus={e => e.target.style.borderColor = T.accent}
          onBlur={e => e.target.style.borderColor = T.border}
          onKeyDown={e => { if (e.key === "Enter") speichern(); if (e.key === "Escape") onDone(); }}
          autoFocus
        />
        <input
          type="date" value={faellig} onChange={e => setFaellig(e.target.value)}
          style={{
            padding:"6px 10px", border:`1.5px solid ${T.border}`, borderRadius:6,
            fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
            background:T.cardBg || "#ffffff", outline:"none",
          }}
        />
        <Btn variant="gold" size="sm" onClick={speichern} disabled={busy || !text.trim()}>
          {busy ? "…" : "✓ Anlegen"}
        </Btn>
        <Btn variant="secondary" size="sm" onClick={onDone}>Abbrechen</Btn>
      </div>
    </>
  );
}

const PWA_VORLAGEN = [
  {
    key: "iban_anfrage",
    label: "Bitte IBAN mitteilen",
    text: "für die Weiterleitung eingegangener Zahlungen benötigen wir noch Ihre Bankverbindung (IBAN). Bitte teilen Sie uns diese baldmöglichst mit.",
  },
  {
    key: "regulierung_eingegangen",
    label: "Regulierungszahlung eingegangen",
    text: "wir möchten Sie informieren, dass eine Zahlung der Gegenseite bei uns eingegangen ist. Wir werden diese nach Prüfung an Sie weiterleiten.",
  },
  {
    key: "sachstand",
    label: "Sachstandsmitteilung",
    text: "wir möchten Sie über den aktuellen Stand Ihrer Akte informieren.",
  },
  { key: "freitext", label: "Freitext", text: "" },
];

function PwaNachrichtModal({ az, mandantName, onClose }) {
  const [vorlageKey, setVorlageKey] = React.useState("iban_anfrage");
  const [text, setText]             = React.useState(PWA_VORLAGEN[0].text);
  const [senden, setSenden]         = React.useState(false);
  const [toast, setToast]           = React.useState("");

  const waehleVorlage = (key) => {
    setVorlageKey(key);
    const v = PWA_VORLAGEN.find(v => v.key === key);
    if (v) setText(v.text);
  };

  const absenden = async () => {
    if (!text.trim()) { setToast("Bitte einen Text eingeben."); return; }
    setSenden(true);
    try {
      await apiAkten.pwaMessage(az, text.trim(), vorlageKey);
      setToast("Nachricht gespeichert.");
      setTimeout(onClose, 1200);
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    } finally {
      setSenden(false);
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{
        position:"fixed", inset:0, background:"rgba(0,0,0,.45)",
        zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center",
      }} onClick={onClose}>
        <div style={{
          background:T.offWhite, borderRadius:12, padding:"1.5rem",
          width:"min(520px,96vw)", boxShadow:"0 8px 32px rgba(0,0,0,.18)",
          fontFamily:T.fontBody,
        }} onClick={e => e.stopPropagation()}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"1rem" }}>
            <span style={{ fontFamily:T.fontDisplay, fontWeight:700, fontSize:"1rem", color:T.navy }}>
              💬 Nachricht an Mandant
            </span>
            {mandantName && (
              <span style={{ fontSize:"0.78rem", color:T.textMuted }}>{mandantName}</span>
            )}
          </div>

          <label style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:4 }}>
            Vorlage
          </label>
          <select value={vorlageKey} onChange={e => waehleVorlage(e.target.value)}
            style={{ width:"100%", padding:"7px 10px", borderRadius:7, border:`1.5px solid ${T.border}`,
              fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text, background:T.surface,
              marginBottom:"0.75rem", outline:"none" }}>
            {PWA_VORLAGEN.map(v => (
              <option key={v.key} value={v.key}>{v.label}</option>
            ))}
          </select>

          <label style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:4 }}>
            Nachrichtentext
          </label>
          <textarea value={text} onChange={e => setText(e.target.value)} rows={5}
            style={{ width:"100%", padding:"8px 10px", borderRadius:7, border:`1.5px solid ${T.border}`,
              fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text, background:T.surface,
              resize:"vertical", outline:"none", boxSizing:"border-box", marginBottom:"1rem" }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e => e.target.style.borderColor = T.border}
          />

          <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
            <Btn variant="secondary" onClick={onClose}>Abbrechen</Btn>
            <Btn variant="primary" onClick={absenden} disabled={senden}>
              {senden ? "…" : "📤 Senden"}
            </Btn>
          </div>
        </div>
      </div>
    </>
  );
}

function UebersichtSection({ akte, st, dispatch, onNavigate, posDaten = null,
  kpiSummen = { gefordert: 0, reguliert: 0, offen: 0, quelle: "alt" }, mandantChecks = null }) {
  const [notizen, setNotizen] = useState(st.notizen || "");
  const [nChanged, setNC]     = useState(false);
  const [toast, setToast]     = useState("");
  const [stripOffene, setStripOffene] = useState([]);
  const [todosState,  setTodosState]  = useState([]);
  const [ereignislisteKey, setEreignislisteKey] = useState(null);
  const [faecherOffen, setFaecherOffen] = useState(false);

  const azRoh = akte.az_roh || akte.az || "";

  React.useEffect(() => {
    if (!akte.az) return;
    apiTodos.liste(akte.az)
      .then(r => setTodosState(r?.todos || []))
      .catch(() => {});
  }, [akte.az]);

  const toggleStrip = (id) => {
    setStripOffene(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

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

  const schaden    = st.schaden || {};
  const abrechnungen = st.abrechnungen || [];

  const phase = berechnePhase({ akte, ibanCheck: mandantChecks, schaden, abrechnungen, summen: kpiSummen });

  const onboarding = berechneOnboardingChecks({
    akte, beteiligte: st?.beteiligte || [], schaden, dokumente: st?.dokumente || [],
  });
  const mandantBeteiligter = (st.beteiligte || []).find(b => (b.rolle || "").toLowerCase() === "mandant") || null;

  const azKlappKey = azRoh.replace(/\//g, "-");


  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}

      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
        <PhasenStrip phase={phase} onboarding={onboarding}
          faecherOffen={faecherOffen} onToggleFaecher={() => setFaecherOffen(o => !o)} />
        {faecherOffen && phase.aktiv === "onboarding" && (
          <OnboardingFaecher checks={onboarding} onNavigate={onNavigate} akteId={azRoh}
            mandantChecks={mandantChecks} mandant={mandantBeteiligter} onFehler={setToast} />
        )}
        <StatusBand ibanCheck={mandantChecks} todos={todosState} hq={akte.hq}
          akteId={azRoh} mandant={mandantBeteiligter} onFehler={setToast} />
      </div>

      {akte.az && (
        <PositionsDashboard
          az={akte.az}
          daten={posDaten}
          onOeffneEreignisse={(key) => setEreignislisteKey(key)}
        />
      )}
      <EreignislistePanel
        az={akte.az}
        positionKey={ereignislisteKey}
        onClose={() => setEreignislisteKey(null)}
      />

      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", background:T.cardBg, boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
        <TodoWvSpalten az={akte.az} azRoh={azRoh} todos={todosState} />
      </div>

      <div style={{ marginBottom:"1rem" }}>
        <AkkordeonStrip offene={stripOffene} onToggle={toggleStrip} />
      </div>

      {stripOffene.includes("ramicro") && azRoh.includes("/") && (
        <div style={{ marginBottom:"1rem" }}>
          <RaMicroAkteUebersicht azRoh={azRoh} />
        </div>
      )}

      {stripOffene.includes("chronik") && (
        <KlappAbschnitt titel="Akten-Chronik" lsKey={`uebersicht-chronik-${azKlappKey}`}>
          <AktenTimeline
            abrechnungen={abrechnungen}
            aktivitaeten={st.aktivitaeten || []}
            akteId={akte.id}
            onAktivitaetenChange={async () => {
              const data = await apiAkten.aktivitaeten(akte.id);
              if (data?.aktivitaeten)
                dispatch({ type:"SET_AKTIVITAETEN", akteId:akte.id, aktivitaeten:data.aktivitaeten });
            }}
          />
        </KlappAbschnitt>
      )}

      {stripOffene.includes("notizen") && (
        <Card style={{ padding:"0.6rem 1rem", display:"flex", flexDirection:"column", gap:5 }}>
          <textarea value={notizen} onChange={e => { setNotizen(e.target.value); setNC(true); }} rows={3}
            placeholder="Interne Notizen …"
            style={{ padding:"5px 8px", border:`1.5px solid ${T.border}`, borderRadius:6,
              fontSize:"0.875rem", color:T.text, background:T.surface, outline:"none", resize:"none",
              fontFamily:T.fontBody }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e => e.target.style.borderColor = T.border} />
          {nChanged && (
            <Btn variant="gold" size="sm" onClick={async () => {
              dispatch({ type:"SET_NOTIZEN", akteId:akte.id, notizen });
              setNC(false); setToast("Notizen gespeichert.");
              try { await apiAkten.aktualisieren(akte.id, { notizen }); } catch {}
            }}>{Ic.check} Speichern</Btn>
          )}
        </Card>
      )}
    </>
  );
}


export { RegulierungsTabelle, TodoSection, PwaNachrichtModal,
  AktenTimeline, StatusBand, RechtsschutzKlappkachel, TodoInlineForm };
export default UebersichtSection;
