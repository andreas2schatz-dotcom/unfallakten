/**
 * GebuehrenSection – PRD-28
 * =========================
 * Tab "Gebühren" in der Aktendetailansicht.
 * Gebührenassistent für Nr. 2300 VV RVG (§ 14 RVG Faktor-Ermittlung).
 *
 * Drei Bereiche:
 *  A) Auto-Analyse-Status (erkannte Kriterien)
 *  B) Kurzbefragung (max. 5 Fragen, nur wenn fehlende_felder vorhanden)
 *  C) Ergebnis (VU-Regel, Faktor, Begründung, RVG-Tabelle, Aktionen)
 */

import React, { useState, useEffect, useCallback } from "react";
import T from "../config/theme.js";
import { Btn, Toast } from "../components/common.jsx";
import { apiGebuehren, dokumente as apiDokumente } from "../api.js";
import { fmtEuro } from "../config/utils.js";

// ── Konstanten ────────────────────────────────────────────────────────────────

const VERLETZUNGSGRAD_OPTIONEN = [
  { value: "keine",    label: "Kein Personenschaden" },
  { value: "leicht",   label: "Leicht (HWS, Prellung, AU ≤ 14 Tage)" },
  { value: "schwer",   label: "Schwer (Knochenbruch, OP, AU > 14 Tage)" },
  { value: "schwerst", label: "Schwerst (Querschnitt, SHT, Polytrauma, Dauerschaden)" },
];

const VU_FARBEN = {
  "VU-01": { bg: T.greenBg,  text: T.green  },
  "VU-02": { bg: "#f0fdf4",  text: "#16a34a" },
  "VU-03": { bg: T.amberBg,  text: T.amber  },
  "VU-04": { bg: T.amberBg,  text: T.amber  },
  "VU-05": { bg: T.amberMid,  text: "#d97706" },
  "VU-06": { bg: T.amberMid,  text: "#d97706" },
  "VU-07": { bg: T.amberMid,  text: "#d97706" },
  "VU-07b":{ bg: T.amberBg,  text: T.amber  },
  "VU-08": { bg: T.redBg,    text: T.red    },
  "VU-09": { bg: T.redBg,    text: T.red    },
  "VU-10": { bg: T.redBg,    text: T.red    },
  "VU-11": { bg: "#fdf2f8",  text: "#a21caf" },
  "VU-12": { bg: "#fdf2f8",  text: "#a21caf" },
};

// ── Hilfsfunktionen ───────────────────────────────────────────────────────────

function fmtFaktor(f) {
  return f != null ? String(Number(f)).replace(".", ",") : "–";
}

function KriteriumZeile({ label, wert, auto = true }) {
  const ok = wert === true || (typeof wert === "number" && wert > 0) ||
             (typeof wert === "string" && wert && wert !== "keine");
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8,
                  padding:"5px 0", borderBottom:`1px solid ${T.borderSoft}`,
                  fontSize:"0.88rem" }}>
      <span style={{ fontSize:"1rem", color: ok ? T.green : T.textFaint, width:20, textAlign:"center" }}>
        {ok ? "✓" : "·"}
      </span>
      <span style={{ color: T.textMid, flex:1 }}>{label}</span>
      <span style={{ color: ok ? T.text : T.textFaint, fontWeight: ok ? 600 : 400,
                     fontFamily:"ui-monospace,monospace", fontSize:"0.82rem" }}>
        {typeof wert === "boolean" ? (wert ? "Ja" : "Nein")
          : typeof wert === "number" ? wert
          : wert || "–"}
      </span>
      {auto && <span style={{ fontSize:"0.72rem", color:T.textFaint, marginLeft:4 }}>auto</span>}
    </div>
  );
}

function RvgTabelle({ rvg }) {
  if (!rvg) return null;
  const zeilen = [
    ["Gegenstandswert",                        fmtEuro(rvg.streitwert || 0)],
    [`Geschäftsgebühr Nr. 2300 VV RVG  ×  ${fmtFaktor(rvg.faktor)}`,
                                               fmtEuro(rvg.gebuehr_netto)],
    ["Post und Telekommunikation Nr. 7002",    fmtEuro(rvg.post_pauschale)],
    ["Zwischensumme netto",                    fmtEuro(rvg.zwischen_netto)],
    ["19 % Umsatzsteuer",                      fmtEuro(rvg.ust)],
  ];
  return (
    <div style={{ border:`1px solid ${T.border}`, borderRadius:8, overflow:"hidden", marginTop:8 }}>
      {zeilen.map(([l, r]) => (
        <div key={l} style={{ display:"flex", justifyContent:"space-between",
                              padding:"6px 14px", borderBottom:`1px solid ${T.borderSoft}`,
                              fontSize:"0.87rem", color:T.textMid }}>
          <span>{l}</span>
          <span style={{ fontFamily:"ui-monospace,monospace" }}>{r}</span>
        </div>
      ))}
      <div style={{ display:"flex", justifyContent:"space-between",
                    padding:"8px 14px", background:T.navy, color:"#fff",
                    fontWeight:700, fontSize:"0.95rem" }}>
        <span>Gesamtbetrag (brutto)</span>
        <span style={{ fontFamily:"ui-monospace,monospace" }}>{fmtEuro(rvg.gesamt)}</span>
      </div>
    </div>
  );
}

// ── Hauptkomponente ───────────────────────────────────────────────────────────

export default function GebuehrenSection({ akteId, akte }) {
  const [laden, setLaden]                 = useState(true);
  const [kriterien, setKriterien]         = useState(null);
  const [vorschlag, setVorschlag]         = useState(null);
  const [gespeichert, setGespeichert]     = useState(null);
  const [rvg, setRvg]                     = useState(null);

  // Befragungs-State
  const [antworten, setAntworten]         = useState({});
  const [befragungFertig, setBefragungFertig] = useState(false);

  // Ergebnis-State (editierbar)
  const [faktorFinal, setFaktorFinal]     = useState("");
  const [begruendungText, setBegruendungText] = useState("");

  const [speichern, setSpeichern]         = useState(false);
  const [wordLaden, setWordLaden]         = useState(false);
  const [wordDok, setWordDok]             = useState(null);  // { dok_id, dateiname }
  const [toast, setToast]                 = useState(null);

  const showToast = (msg, typ = "success") => {
    setToast({ msg, typ });
    setTimeout(() => setToast(null), 3500);
  };

  // ── Daten laden ────────────────────────────────────────────────────────────
  const ladeGebuehren = useCallback(async () => {
    setLaden(true);
    try {
      const data = await apiGebuehren.laden(akteId);
      setKriterien(data.kriterien);
      setVorschlag(data.vorschlag);
      setRvg(data.rvg);
      setGespeichert(data.gespeichert);

      const finalFaktor = data.gespeichert?.faktor_final ?? data.vorschlag?.faktor ?? 1.3;
      setFaktorFinal(String(finalFaktor).replace(".", ","));
      setBegruendungText(data.gespeichert?.begruendung ?? data.vorschlag?.begruendung ?? "");

      // Wenn alle Felder vorhanden: Befragung übersprungen
      if ((data.kriterien?.fehlende_felder || []).length === 0) {
        setBefragungFertig(true);
      }
    } catch (e) {
      showToast("Fehler beim Laden: " + e.message, "error");
    } finally {
      setLaden(false);
    }
  }, [akteId]);

  useEffect(() => { ladeGebuehren(); }, [ladeGebuehren]);

  // ── Faktor-Input → RVG live neu berechnen ─────────────────────────────────
  const faktorNumeric = parseFloat((faktorFinal || "1.3").replace(",", ".")) || 1.3;

  const rvgMitFaktor = rvg ? {
    ...rvg,
    faktor:        faktorNumeric,
    gebuehr_netto: Math.round((rvg.grundgebuehr ?? 0) * faktorNumeric * 100) / 100,
    get post_pauschale() { return Math.min(20, Math.round(this.gebuehr_netto * 0.20 * 100) / 100); },
    get zwischen_netto() { return Math.round((this.gebuehr_netto + this.post_pauschale) * 100) / 100; },
    get ust()            { return Math.round(this.zwischen_netto * 0.19 * 100) / 100; },
    get gesamt()         { return Math.round((this.zwischen_netto + this.ust) * 100) / 100; },
  } : null;

  // ── Befragung abschließen → Neu analysieren ────────────────────────────────
  const befragungAbschliessen = async () => {
    try {
      const streitwert = rvg?.streitwert || 0;
      const data = await apiGebuehren.analysieren(akteId, {
        ...antworten,
        streitwert,
        faktor: faktorNumeric,
      });
      setKriterien(data.kriterien);
      setVorschlag(data.vorschlag);
      setRvg(data.rvg);
      const neuerFaktor = data.vorschlag?.faktor ?? 1.3;
      setFaktorFinal(String(neuerFaktor).replace(".", ","));
      setBegruendungText(data.vorschlag?.begruendung ?? "");
      setBefragungFertig(true);
    } catch (e) {
      showToast("Analyse fehlgeschlagen: " + e.message, "error");
    }
  };

  // ── Speichern ──────────────────────────────────────────────────────────────
  const handleSpeichern = async () => {
    setSpeichern(true);
    try {
      const aktiveKriterien = { ...(kriterien || {}), ...antworten };
      await apiGebuehren.speichern(akteId, {
        kriterien:       aktiveKriterien,
        vuregel_id:      vorschlag?.vuregel_id,
        faktor_vorschlag:vorschlag?.faktor,
        faktor_final:    faktorNumeric,
        begruendung:     begruendungText,
      });
      showToast("Gespeichert ✓");
      setGespeichert({ faktor_final: faktorNumeric, begruendung: begruendungText,
                       vuregel_id: vorschlag?.vuregel_id });
    } catch (e) {
      showToast("Speichern fehlgeschlagen: " + e.message, "error");
    } finally {
      setSpeichern(false);
    }
  };

  // ── Word generieren ────────────────────────────────────────────────────────
  const handleWord = async () => {
    if (!gespeichert) { showToast("Bitte zuerst speichern.", "error"); return; }
    setWordLaden(true);
    try {
      const data = await apiGebuehren.word(akteId);
      setWordDok({ dok_id: data.dok_id, dateiname: data.dateiname });
      // Download sofort auslösen
      await apiDokumente.download(akteId, data.dok_id, data.dateiname);
      showToast("Kostennote generiert ✓");
    } catch (e) {
      showToast("Word-Generierung fehlgeschlagen: " + e.message, "error");
    } finally {
      setWordLaden(false);
    }
  };

  const handleWordDownload = async () => {
    if (!wordDok) return;
    try {
      await apiDokumente.download(akteId, wordDok.dok_id, wordDok.dateiname);
    } catch (e) {
      showToast("Download fehlgeschlagen: " + e.message, "error");
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (laden) return (
    <div style={{ padding:"3rem", textAlign:"center", color:T.textFaint, fontSize:"0.9rem" }}>
      <div style={{ width:28, height:28, border:`3px solid ${T.accentTrim}`,
                    borderTopColor:T.accent, borderRadius:"50%",
                    animation:"spin 0.8s linear infinite", margin:"0 auto 12px" }} />
      Gebühren-Analyse läuft …
    </div>
  );

  const fehlend = kriterien?.fehlende_felder || [];
  const hatPS   = kriterien?.hat_personenschaden || false;
  const vuregel = vorschlag?.vuregel_id || "VU-01";
  const vuFarbe = VU_FARBEN[vuregel] || { bg: T.surface, text: T.textMid };

  return (
    <div style={{ padding:"1.5rem", maxWidth:760, margin:"0 auto" }}>
      {toast && <Toast msg={toast.msg} typ={toast.typ} onClose={() => setToast(null)} />}

      {/* ── Bereich A: Auto-Analyse ─────────────────────────────────────── */}
      <div style={{ background:T.surface, border:`1px solid ${T.border}`,
                    borderRadius:10, padding:"1rem 1.25rem", marginBottom:"1.25rem" }}>
        <div style={{ fontWeight:700, color:T.navy, fontSize:"0.9rem",
                      marginBottom:"0.6rem", letterSpacing:"0.03em" }}>
          Automatisch erkannte Kriterien
        </div>
        {kriterien && <>
          <KriteriumZeile label="Haftungsquote"
            wert={`${kriterien.haftungsquote ?? 100} %`} />
          <KriteriumZeile label="Haftung bestritten"
            wert={kriterien.haftung_streitig} />
          <KriteriumZeile label="Auslandsbezug"
            wert={kriterien.auslandsbezug} />
          <KriteriumZeile label="Todesfall"
            wert={kriterien.todesfall} />
          <KriteriumZeile label="Verletzungsgrad"
            wert={kriterien.verletzungsgrad !== "keine" ? kriterien.verletzungsgrad : false} />
          <KriteriumZeile label="Abrechnungsart"
            wert={kriterien.totalschaden ? "Totalschaden" : "Reparatur / Fiktiv"} />
          <KriteriumZeile label="Schadenspositionen"
            wert={kriterien.schadenspositionen_count} />
          <KriteriumZeile label="Schriftsätze / Dokumente"
            wert={kriterien.schriftsaetze_count} />
          <KriteriumZeile label="Regulierungsdauer"
            wert={`${kriterien.regulierungsdauer_monate ?? 0} Monate`} />
          {kriterien.au_tage > 0 &&
            <KriteriumZeile label="AU-Tage" wert={kriterien.au_tage} />}
          {kriterien.stationaerer_aufenthalt &&
            <KriteriumZeile label="Stationärer Aufenthalt" wert={true} />}
          {kriterien.dauerschaden &&
            <KriteriumZeile label="Dauerfolgen / Dauerschaden" wert={true} />}
        </>}
      </div>

      {/* ── Bereich B: Kurzbefragung ────────────────────────────────────── */}
      {!befragungFertig && fehlend.length > 0 && (
        <div style={{ background:T.amberBg, border:`1px solid ${T.amber}44`,
                      borderRadius:10, padding:"1rem 1.25rem", marginBottom:"1.25rem" }}>
          <div style={{ fontWeight:700, color:T.amberText, fontSize:"0.9rem", marginBottom:"0.75rem" }}>
            Kurzbefragung – noch {fehlend.length} Angabe{fehlend.length !== 1 ? "n" : ""} nötig
          </div>

          {fehlend.includes("verletzungsgrad") && hatPS && (
            <div style={{ marginBottom:"0.75rem" }}>
              <label style={labelStyle}>Verletzungsgrad des Mandanten?</label>
              <div style={{ display:"flex", flexWrap:"wrap", gap:8, marginTop:6 }}>
                {VERLETZUNGSGRAD_OPTIONEN.map(o => (
                  <button key={o.value}
                    onClick={() => setAntworten(a => ({ ...a, verletzungsgrad: o.value }))}
                    style={{ ...optionBtnStyle,
                      background: antworten.verletzungsgrad === o.value ? T.navy : T.surface,
                      color:      antworten.verletzungsgrad === o.value ? "#fff" : T.textMid,
                      borderColor:antworten.verletzungsgrad === o.value ? T.navy : T.border,
                    }}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <Btn onClick={befragungAbschliessen}
               disabled={fehlend.includes("verletzungsgrad") && hatPS && !antworten.verletzungsgrad}
               style={{ marginTop:8 }}>
            Analysieren →
          </Btn>
        </div>
      )}

      {/* ── Bereich C: Ergebnis ─────────────────────────────────────────── */}
      {(befragungFertig || fehlend.length === 0) && vorschlag && (
        <>
          {/* VU-Regel Badge + Faktor */}
          <div style={{ display:"flex", alignItems:"center", gap:12,
                        marginBottom:"1rem", flexWrap:"wrap" }}>
            <div style={{ background:vuFarbe.bg, color:vuFarbe.text,
                          border:`1.5px solid ${vuFarbe.text}33`,
                          borderRadius:20, padding:"4px 14px",
                          fontWeight:700, fontSize:"0.88rem", letterSpacing:"0.04em" }}>
              {vuregel}
            </div>
            <div style={{ fontWeight:700, fontSize:"1.4rem", color:T.navy,
                          fontFamily:"'Figtree',sans-serif" }}>
              Faktor {fmtFaktor(faktorNumeric)}
            </div>
            <div style={{ color:T.textMuted, fontSize:"0.85rem" }}>
              Nr. 2300 VV RVG · § 14 RVG
            </div>
            {gespeichert && (
              <span style={{ marginLeft:"auto", color:T.green, fontSize:"0.8rem", fontWeight:600 }}>
                ✓ Gespeichert
              </span>
            )}
          </div>

          {/* Faktor Override */}
          <div style={{ marginBottom:"1rem" }}>
            <label style={labelStyle}>Faktor anpassen (§ 14 RVG)</label>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginTop:6 }}>
              {[1.3, 1.5, 1.8, 2.0, 2.3, 2.5].map(f => (
                <button key={f}
                  onClick={() => setFaktorFinal(String(f).replace(".", ","))}
                  style={{ ...optionBtnStyle, padding:"4px 12px",
                    background: Math.abs(faktorNumeric - f) < 0.01 ? T.navy : T.surface,
                    color:      Math.abs(faktorNumeric - f) < 0.01 ? "#fff" : T.textMid,
                    borderColor:Math.abs(faktorNumeric - f) < 0.01 ? T.navy : T.border,
                  }}>
                  {String(f).replace(".", ",")}
                </button>
              ))}
              <input
                type="text"
                value={faktorFinal}
                onChange={e => setFaktorFinal(e.target.value)}
                placeholder="z.B. 1,7"
                style={{ width:70, padding:"4px 8px", border:`1px solid ${T.border}`,
                         borderRadius:6, fontFamily:"ui-monospace,monospace",
                         fontSize:"0.88rem", textAlign:"center" }}
              />
            </div>
          </div>

          {/* RVG-Tabelle */}
          <RvgTabelle rvg={rvgMitFaktor} />

          {/* Begründung */}
          <div style={{ marginTop:"1.25rem" }}>
            <label style={labelStyle}>
              Begründung des Faktors
              <span style={{ fontWeight:400, color:T.textFaint, marginLeft:6, fontSize:"0.8rem" }}>
                (editierbar, erscheint in der Kostennote)
              </span>
            </label>
            <textarea
              value={begruendungText}
              onChange={e => setBegruendungText(e.target.value)}
              rows={5}
              style={{ width:"100%", marginTop:6, padding:"8px 12px",
                       border:`1px solid ${T.border}`, borderRadius:8,
                       fontSize:"0.88rem", lineHeight:1.55, color:T.text,
                       background:T.surface, resize:"vertical",
                       fontFamily:"'Figtree',sans-serif", boxSizing:"border-box" }}
            />
            {vorschlag?.leitentscheidung && (
              <div style={{ marginTop:6, fontSize:"0.8rem", color:T.textMuted, fontStyle:"italic" }}>
                Leitentscheidung: {vorschlag.leitentscheidung}
              </div>
            )}
            {vorschlag?.toleranz && (
              <div style={{ marginTop:2, fontSize:"0.78rem", color:T.textFaint }}>
                Hinweis: {vorschlag.toleranz}
              </div>
            )}
          </div>

          {/* Aktionsleiste */}
          <div style={{ display:"flex", gap:10, marginTop:"1.5rem",
                        paddingTop:"1rem", borderTop:`1px solid ${T.border}`,
                        flexWrap:"wrap" }}>
            <Btn onClick={handleSpeichern} disabled={speichern}>
              {speichern ? "Speichert …" : gespeichert ? "Aktualisieren" : "Speichern"}
            </Btn>
            <Btn variant="secondary" onClick={handleWord} disabled={wordLaden}>
              {wordLaden ? "Generiert …" : "📄 Kostennote (Word)"}
            </Btn>
            {wordDok && (
              <Btn variant="secondary" onClick={handleWordDownload}
                   title={wordDok.dateiname}>
                ⬇ Erneut herunterladen
              </Btn>
            )}
            <Btn variant="secondary" onClick={ladeGebuehren}
                 title="Analyse neu berechnen">
              ↺ Neu analysieren
            </Btn>
          </div>
        </>
      )}
    </div>
  );
}

// ── Shared Styles ─────────────────────────────────────────────────────────────

const labelStyle = {
  display:"block", fontSize:"0.82rem", fontWeight:600,
  color:T.textMuted, letterSpacing:"0.04em", textTransform:"uppercase",
};

const optionBtnStyle = {
  padding:"5px 14px", border:`1px solid`, borderRadius:20,
  cursor:"pointer", fontSize:"0.83rem", fontWeight:600,
  fontFamily:"'Figtree',sans-serif", transition:"all 0.12s",
};
