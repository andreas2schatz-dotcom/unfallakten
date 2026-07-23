/**
 * SchmerzensgelDialog – PRD-29: Schmerzensgeld-Ermittlungstool
 *
 * Modal mit 3 Bereichen:
 * 1. Verletzungsprofil (readonly, aus personenschaden)
 * 2. Recherche: Urteile per Claude web_search + Link schmerzensgeld.online
 * 3. Mindestbetrag + KI-Text generieren + Übernehmen
 *
 * Props:
 *   az          – Aktenzeichen
 *   kl_nom      – Nominativ-Bezeichnung Kläger/in z.B. "Die Klägerin"
 *   onClose     – Callback(null) = abbrechen
 *   onUebernehmen – Callback({ mitSG: true, sgMind: zahl, sgText: string })
 */

import React, { useState, useEffect, useRef } from "react";
import T from "../config/theme.js";
import { apiKlage, apiPersonenschaden } from "../api.js";

const _eur = (v) => {
  if (!v && v !== 0) return "–";
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v);
};

// ISO YYYY-MM-DD → DD.MM.YYYY (lässt deutsches Format unverändert)
const fmtD = (s) => {
  if (!s) return "";
  s = String(s).trim();
  if (s.length === 10 && s[4] === "-" && s[7] === "-")
    return `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}`;
  return s;
};

// Strukturierten Textvorschlag aus Profil-Daten generieren (kein KI)
function _bautVorschlag(profil, klNom, sgMindVal, urteil) {
  const fmtE = (v) => {
    const n = parseFloat(v) || 0;
    return n > 0
      ? new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n)
      : "";
  };

  const absaetze = [];

  // Absatz 1: Verletzungen
  if (profil.verletzungen_text) {
    absaetze.push(`${klNom} hat durch den Unfall folgende Verletzungen erlitten: ${profil.verletzungen_text}.`);
  } else {
    absaetze.push(`${klNom} hat durch den Unfall Verletzungen erlitten.`);
  }

  // Absatz 2: Krankenhaus + Arbeitsunfähigkeit
  const behandlung = [];
  if (profil.krankenhaus_von && profil.krankenhaus_bis) {
    let kh = `Vom ${fmtD(profil.krankenhaus_von)} bis ${fmtD(profil.krankenhaus_bis)} war ein stationärer Aufenthalt`;
    if (profil.krankenhaus_name) kh += ` im ${profil.krankenhaus_name}`;
    kh += " erforderlich.";
    behandlung.push(kh);
  }
  if (profil.krank_von && profil.krank_bis) {
    behandlung.push(`Eine Arbeitsunfähigkeit bestand vom ${fmtD(profil.krank_von)} bis ${fmtD(profil.krank_bis)}.`);
  }
  if (behandlung.length) absaetze.push(behandlung.join(" "));

  // Absatz 3: Dauerfolgen + Betragsbegründung
  const schluss = [];
  if (profil.dauerfolgen) {
    schluss.push(profil.dauerfolgen_text
      ? `Es bestehen unfallbedingte Dauerfolgen: ${profil.dauerfolgen_text}.`
      : "Es bestehen unfallbedingte Dauerfolgen.");
  }
  const betrag = parseFloat(sgMindVal) || 0;
  if (betrag > 0) {
    schluss.push(`Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen ein Schmerzensgeld von mindestens ${fmtE(betrag)}.`);
  } else {
    schluss.push("Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen ein angemessenes Schmerzensgeld.");
  }
  if (schluss.length) absaetze.push(schluss.join(" "));

  // Vergleichsurteil (optional)
  let text = absaetze.join("\n\n");
  if (urteil?.az) {
    const e = fmtE(urteil.betrag);
    const vgl = urteil.gericht
      ? `Vgl. ${urteil.gericht}, ${urteil.az}${e ? `: ${e}` : ""}`
      : `Vgl. ${urteil.az}${e ? `: ${e}` : ""}`;
    text += `\n\n${vgl}`;
  }
  return text;
}

export default function SchmerzensgelDialog({ az, kl_nom, onClose, onUebernehmen }) {
  // Phase 1: Analyse
  const [analyse,       setAnalyse]       = useState(null);
  const [ladeAnalyse,   setLadeAnalyse]   = useState(true);

  // Phase 2: Recherche
  const [treffer,       setTreffer]       = useState(null);    // null = noch nicht gesucht
  const [sgLink,        setSgLink]        = useState("");
  const [ladeRecherche, setLadeRecherche] = useState(false);
  const [gewUrteil,     setGewUrteil]     = useState(null);    // ausgewähltes Urteil

  // Phase 3: Text + Übernahme
  const [sgMind,        setSgMind]        = useState("");
  const [sgText,        setSgText]        = useState("");
  const [ladeText,      setLadeText]      = useState(false);
  const [speichern,     setSpeichern]     = useState(false);

  const [fehler,        setFehler]        = useState(null);
  const [kopiert,       setKopiert]       = useState(false);
  const textRef = useRef(null);

  // Verletzungsprofil + bereits gespeicherte SG-Daten laden
  useEffect(() => {
    setLadeAnalyse(true);
    apiKlage.sgAnalyse(az)
      .then(data => {
        setAnalyse(data);
        const gs = data.gespeichert || {};
        if (gs.sg_mindest) setSgMind(String(gs.sg_mindest));
        if (gs.sg_text)    setSgText(gs.sg_text);
        if (gs.sg_urteil_az) {
          setGewUrteil({
            gericht:     gs.sg_urteil_gericht || "",
            az:          gs.sg_urteil_az,
            betrag:      gs.sg_urteil_betrag || 0,
            kurzfassung: "",
          });
        }
      })
      .catch(e => setFehler(e?.message || "Fehler beim Laden"))
      .finally(() => setLadeAnalyse(false));
  }, [az]);

  // Urteile recherchieren
  const recherchieren = () => {
    if (!analyse?.profil) return;
    setLadeRecherche(true);
    setFehler(null);
    apiKlage.sgRecherche(az, analyse.profil)
      .then(data => {
        setTreffer(data.treffer || []);
        if (data.sg_link) setSgLink(data.sg_link);
        if (data.fehler && (!data.treffer || data.treffer.length === 0)) {
          setFehler(data.fehler);
        }
      })
      .catch(e => setFehler(e?.message || "Recherche fehlgeschlagen"))
      .finally(() => setLadeRecherche(false));
  };

  // Urteil auswählen
  const urteilWaehlen = (u) => {
    setGewUrteil(u);
    setSgMind(String(u.betrag || ""));
  };

  // KI-Text generieren
  const textGenerieren = () => {
    if (!analyse?.profil) return;
    setLadeText(true);
    setFehler(null);
    apiKlage.sgText(az, {
      profil:        analyse.profil,
      kl_nom:        kl_nom || "Der Kläger",
      sg_mind:       parseFloat(sgMind) || 0,
      urteil_gericht: gewUrteil?.gericht || "",
      urteil_az:     gewUrteil?.az || "",
      urteil_betrag: gewUrteil?.betrag || 0,
    })
      .then(data => {
        if (data.text) setSgText(data.text);
        else setFehler("Kein Text erhalten.");
      })
      .catch(e => setFehler(e?.message || "KI-Aufruf fehlgeschlagen"))
      .finally(() => setLadeText(false));
  };

  // Übernehmen: Daten in personenschaden speichern + Callback
  const uebernehmen = async () => {
    setSpeichern(true);
    setFehler(null);
    try {
      await apiPersonenschaden.speichern(az, {
        sg_mindest:        parseFloat(sgMind) || null,
        sg_text:           sgText || null,
        sg_urteil_gericht: gewUrteil?.gericht || null,
        sg_urteil_az:      gewUrteil?.az || null,
        sg_urteil_betrag:  gewUrteil?.betrag || null,
      });
      onUebernehmen({
        mitSG:  true,
        sgMind: parseFloat(sgMind) || 0,
        sgText: sgText || "",
      });
    } catch (e) {
      setFehler(e?.message || "Speichern fehlgeschlagen");
    } finally {
      setSpeichern(false);
    }
  };

  // ESC-Taste schließt Dialog
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const profil   = analyse?.profil || null;
  const fehlend  = analyse?.fehlende_felder || [];
  const hatDaten = profil && (profil.verletzungen_text || profil.krankenhaustage || profil.au_tage);

  const suchBegriffe = (() => {
    if (!profil) return "";
    const teile = [];
    if (profil.verletzungen_text) teile.push(profil.verletzungen_text);
    if (profil.krankenhaustage > 0) teile.push(`stationär ${profil.krankenhaustage} Tage`);
    if (profil.au_tage > 0) teile.push(`AU ${profil.au_tage} Tage`);
    if (profil.dauerfolgen && profil.dauerfolgen_text) teile.push(profil.dauerfolgen_text);
    return teile.join(", ");
  })();

  const suchBegriffeKopieren = () => {
    if (!suchBegriffe) return;
    navigator.clipboard.writeText(suchBegriffe).then(() => {
      setKopiert(true);
      setTimeout(() => setKopiert(false), 2000);
    });
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1100,
        background: "rgba(0,0,0,0.55)", backdropFilter: "blur(3px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "1rem",
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose(null); }}
    >
      <div style={{
        background: T.surface, borderRadius: 12, boxShadow: "0 8px 40px rgba(0,0,0,0.35)",
        width: "100%", maxWidth: 640, maxHeight: "90vh",
        display: "flex", flexDirection: "column",
        fontFamily: T.fontBody,
      }}>

        {/* Header */}
        <div style={{
          padding: "1rem 1.25rem 0.75rem",
          borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: "1rem", color: T.navy }}>
              Schmerzensgeld-Assistent
            </div>
            <div style={{ fontSize: "0.75rem", color: T.textFaint, fontFamily: "monospace" }}>
              {az}
            </div>
          </div>
          <button
            onClick={() => onClose(null)}
            style={{ background: "none", border: "none", cursor: "pointer",
                     fontSize: "1.25rem", color: T.textFaint, padding: "0.25rem 0.5rem" }}
          >×</button>
        </div>

        {/* Body */}
        <div style={{ overflowY: "auto", padding: "1rem 1.25rem", flex: 1 }}>

          {ladeAnalyse && (
            <div style={{ color: T.textFaint, fontSize: "0.85rem", textAlign: "center", padding: "2rem" }}>
              Lade Verletzungsdaten…
            </div>
          )}

          {!ladeAnalyse && (
            <>
              {/* ── Bereich 1: Verletzungsprofil ── */}
              <div style={{ marginBottom: "1rem" }}>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", color: T.textFaint,
                              textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  Verletzungsprofil
                </div>

                {fehlend.length > 0 && (
                  <div style={{
                    background: T.amberMid, border: `1px solid ${T.amber}`,
                    borderRadius: 6, padding: "0.5rem 0.75rem",
                    fontSize: "0.78rem", color: T.amberText, marginBottom: "0.5rem",
                  }}>
                    ⚠ Fehlende Angaben: <strong>{fehlend.join(", ")}</strong> — bitte im Personenschaden-Tab ergänzen.
                  </div>
                )}

                {hatDaten ? (
                  <div style={{
                    background: T.offWhite, borderRadius: 8,
                    padding: "0.75rem 1rem", fontSize: "0.83rem", color: T.text,
                    display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.3rem 1rem",
                  }}>
                    {profil.verletzungen_text && (
                      <div style={{ gridColumn: "1/-1" }}>
                        <span style={{ color: T.textFaint }}>Verletzungen: </span>
                        {profil.verletzungen_text}
                      </div>
                    )}
                    {(profil.krankenhaustage > 0 || profil.krankenhaus_von) && (
                      <div>
                        <span style={{ color: T.textFaint }}>Krankenhaus: </span>
                        {profil.krankenhaustage > 0 ? `${profil.krankenhaustage} Tage` : ""}
                        {profil.krankenhaus_von && profil.krankenhaus_bis
                          ? ` (${fmtD(profil.krankenhaus_von)} – ${fmtD(profil.krankenhaus_bis)})`
                          : ""}
                      </div>
                    )}
                    {(profil.au_tage > 0 || profil.krank_von) && (
                      <div>
                        <span style={{ color: T.textFaint }}>Arbeitsunfähigkeit: </span>
                        {profil.au_tage > 0 ? `${profil.au_tage} Tage` : ""}
                        {profil.krank_von && profil.krank_bis
                          ? ` (${fmtD(profil.krank_von)} – ${fmtD(profil.krank_bis)})`
                          : ""}
                      </div>
                    )}
                    {profil.dauerfolgen && (
                      <div style={{ gridColumn: "1/-1" }}>
                        <span style={{ color: T.textFaint }}>Dauerfolgen: </span>
                        {profil.dauerfolgen_text || "ja"}
                      </div>
                    )}
                    {profil.physiotherapie_anzahl > 0 && (
                      <div>
                        <span style={{ color: T.textFaint }}>Physiotherapie: </span>
                        {profil.physiotherapie_anzahl}× Sitzungen
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ fontSize: "0.82rem", color: T.textFaint, fontStyle: "italic" }}>
                    Keine Verletzungsdaten erfasst. Bitte im Personenschaden-Tab ergänzen.
                  </div>
                )}
              </div>

              {/* ── Bereich 2: Recherche ── */}
              <div style={{ marginBottom: "1rem" }}>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", color: T.textFaint,
                              textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  Vergleichsurteile
                </div>

                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                  <button
                    onClick={recherchieren}
                    disabled={ladeRecherche || !hatDaten}
                    style={{
                      padding: "0.4rem 0.9rem", borderRadius: 6, cursor: "pointer",
                      background: ladeRecherche ? T.surface : T.navy,
                      color: ladeRecherche ? T.textFaint : T.white,
                      border: "none", fontSize: "0.82rem", fontWeight: 600,
                      opacity: (!hatDaten) ? 0.5 : 1,
                    }}
                  >
                    {ladeRecherche ? "Suche läuft (~10s)…" : "🔍 Urteile recherchieren"}
                  </button>

                  <a
                    href="https://schmerzensgeld.online"
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      padding: "0.4rem 0.9rem", borderRadius: 6,
                      background: T.surface,
                      color: T.navy, border: `1px solid ${T.border}`,
                      fontSize: "0.82rem", textDecoration: "none", fontWeight: 500,
                      display: "inline-flex", alignItems: "center", gap: "0.3rem",
                    }}
                  >
                    schmerzensgeld.online ↗
                  </a>
                </div>

                {/* Suchbegriffe für schmerzensgeld.online */}
                {hatDaten && suchBegriffe && (
                  <div style={{
                    display: "flex", alignItems: "center", gap: "0.5rem",
                    marginBottom: "0.6rem",
                    background: T.offWhite, borderRadius: 6,
                    padding: "0.4rem 0.5rem 0.4rem 0.75rem",
                    border: `1px solid ${T.border}`,
                  }}>
                    <span style={{
                      fontSize: "0.75rem", color: T.textFaint, flex: 1,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      <span style={{ fontWeight: 600, color: T.text }}>Suchbegriffe:&nbsp;</span>
                      {suchBegriffe}
                    </span>
                    <button
                      onClick={suchBegriffeKopieren}
                      title="Suchbegriffe für schmerzensgeld.online in Zwischenablage kopieren"
                      style={{
                        padding: "0.25rem 0.65rem", borderRadius: 5,
                        background: kopiert ? T.green : T.surface,
                        color: kopiert ? "#fff" : T.navy,
                        border: `1px solid ${kopiert ? T.green : T.border}`,
                        cursor: "pointer", fontSize: "0.75rem", fontWeight: 600,
                        whiteSpace: "nowrap", flexShrink: 0,
                        transition: "background 0.15s, color 0.15s, border-color 0.15s",
                      }}
                    >
                      {kopiert ? "✓ Kopiert" : "📋 Kopieren"}
                    </button>
                  </div>
                )}

                {/* Trefferliste */}
                {treffer !== null && treffer.length === 0 && !fehler && (
                  <div style={{ fontSize: "0.8rem", color: T.textFaint, fontStyle: "italic" }}>
                    Keine passenden Urteile gefunden. Bitte manuell auf schmerzensgeld.online suchen.
                  </div>
                )}
                {treffer !== null && treffer.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    {treffer.map((u, i) => (
                      <div
                        key={i}
                        style={{
                          border: `1px solid ${gewUrteil?.az === u.az ? T.navy : T.border}`,
                          borderRadius: 6, padding: "0.5rem 0.75rem",
                          background: gewUrteil?.az === u.az
                            ? (T.blueBg) : T.surface,
                          fontSize: "0.8rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div>
                            <span style={{ fontWeight: 600, color: T.navy }}>
                              {u.gericht}{u.datum ? `, ${u.datum}` : ""}
                            </span>
                            {u.az && <span style={{ color: T.textFaint, marginLeft: "0.4rem" }}>– {u.az}</span>}
                          </div>
                          <span style={{ fontWeight: 700, color: T.green, whiteSpace: "nowrap", marginLeft: "0.5rem" }}>
                            {_eur(u.betrag)}
                          </span>
                        </div>
                        {u.kurzfassung && (
                          <div style={{ color: T.textFaint, marginTop: "0.2rem" }}>{u.kurzfassung}</div>
                        )}
                        <button
                          onClick={() => urteilWaehlen(u)}
                          style={{
                            marginTop: "0.35rem", padding: "0.2rem 0.6rem",
                            background: gewUrteil?.az === u.az ? T.navy : "transparent",
                            color: gewUrteil?.az === u.az ? "#fff" : T.navy,
                            border: `1px solid ${T.navy}`, borderRadius: 4,
                            cursor: "pointer", fontSize: "0.75rem",
                          }}
                        >
                          {gewUrteil?.az === u.az ? "✓ Ausgewählt" : "Auswählen"}
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Gewähltes Urteil (wenn aus DB geladen, nicht aus aktueller Suche) */}
                {gewUrteil && treffer === null && (
                  <div style={{
                    border: `1px solid ${T.navy}`, borderRadius: 6,
                    padding: "0.5rem 0.75rem", fontSize: "0.8rem",
                    background: T.blueBg,
                  }}>
                    <span style={{ color: T.textFaint }}>Gespeichertes Urteil: </span>
                    <strong>{gewUrteil.gericht} – {gewUrteil.az}</strong>
                    {gewUrteil.betrag > 0 && <span> → {_eur(gewUrteil.betrag)}</span>}
                    <button
                      onClick={() => setGewUrteil(null)}
                      style={{ marginLeft: "0.5rem", background: "none", border: "none",
                               cursor: "pointer", color: T.textFaint, fontSize: "0.75rem" }}
                    >✕ entfernen</button>
                  </div>
                )}
              </div>

              {/* ── Bereich 3: Betrag + Text ── */}
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", color: T.textFaint,
                              textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.5rem" }}>
                  Mindestbetrag &amp; Klagetext
                </div>

                {/* Mindestbetrag */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <label style={{ fontSize: "0.83rem", color: T.text, whiteSpace: "nowrap" }}>
                    Mindestbetrag:
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="500"
                    value={sgMind}
                    onChange={e => setSgMind(e.target.value)}
                    placeholder="0"
                    style={{
                      width: 120, padding: "0.35rem 0.5rem", borderRadius: 6,
                      border: `1px solid ${T.border}`, fontSize: "0.83rem",
                      fontFamily: "monospace",
                    }}
                  />
                  <span style={{ fontSize: "0.83rem", color: T.textFaint }}>€</span>
                </div>

                {/* Textgenerierung – zwei Optionen */}
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                  <button
                    onClick={() => profil && setSgText(_bautVorschlag(profil, kl_nom || "Der Kläger", sgMind, gewUrteil))}
                    disabled={!hatDaten}
                    style={{
                      padding: "0.4rem 0.9rem", borderRadius: 6, cursor: "pointer",
                      background: T.navy, color: "#fff",
                      border: "none", fontSize: "0.82rem", fontWeight: 600,
                      opacity: !hatDaten ? 0.45 : 1,
                    }}
                    title="Strukturierten Text aus den eingetragenen Verletzungsdaten erstellen — ohne KI"
                  >
                    Textvorschlag erstellen
                  </button>
                  <button
                    onClick={textGenerieren}
                    disabled={ladeText || !hatDaten}
                    style={{
                      padding: "0.4rem 0.9rem", borderRadius: 6, cursor: "pointer",
                      background: ladeText ? T.surface : T.amber,
                      color: ladeText ? T.textFaint : T.white,
                      border: "none", fontSize: "0.82rem", fontWeight: 600,
                      opacity: !hatDaten ? 0.45 : 1,
                    }}
                    title="Claude formuliert den Text juristisch — erfordert API-Verbindung"
                  >
                    {ladeText ? "KI generiert…" : "✨ KI-Text (optional)"}
                  </button>
                </div>

                <textarea
                  ref={textRef}
                  value={sgText}
                  onChange={e => setSgText(e.target.value)}
                  placeholder="Klicken Sie auf 'Textvorschlag erstellen' für einen sofortigen Vorschlag aus den Verletzungsdaten, oder '✨ KI-Text' für einen KI-formulierten Text."
                  rows={7}
                  style={{
                    width: "100%", padding: "0.6rem 0.75rem",
                    border: `1px solid ${sgText ? T.navy : T.border}`,
                    borderRadius: 6, fontSize: "0.82rem", resize: "vertical",
                    fontFamily: T.fontBody, lineHeight: 1.5,
                    background: T.surface, color: T.text,
                    boxSizing: "border-box",
                  }}
                />
                <div style={{ fontSize: "0.72rem", color: T.textFaint, marginTop: "0.3rem" }}>
                  Text kann manuell bearbeitet werden. KI-Texte bitte vor Übernahme prüfen.
                </div>
              </div>

              {/* Fehler */}
              {fehler && (
                <div style={{
                  marginTop: "0.75rem", padding: "0.5rem 0.75rem",
                  background: T.redBg, border: "1px solid #f87171",
                  borderRadius: 6, fontSize: "0.8rem", color: T.redText,
                }}>
                  {fehler}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: "0.75rem 1.25rem",
          borderTop: `1px solid ${T.border}`,
          display: "flex", justifyContent: "flex-end", gap: "0.5rem",
        }}>
          <button
            onClick={() => onClose(null)}
            style={{
              padding: "0.45rem 1rem", borderRadius: 6,
              background: "transparent", border: `1px solid ${T.border}`,
              cursor: "pointer", fontSize: "0.85rem", color: T.text,
            }}
          >
            Abbrechen
          </button>
          <button
            onClick={uebernehmen}
            disabled={speichern}
            style={{
              padding: "0.45rem 1.1rem", borderRadius: 6,
              background: T.navy, color: "#fff",
              border: "none", cursor: "pointer",
              fontSize: "0.85rem", fontWeight: 600,
              opacity: speichern ? 0.7 : 1,
            }}
          >
            {speichern ? "Speichern…" : "✓ Übernehmen"}
          </button>
        </div>
      </div>
    </div>
  );
}
