/**
 * KlageWizard.jsx – PRD-24b
 * ─────────────────────────────────────────────────────────────────
 * 7-Step Modal-Wizard für die Klageschrift-Generierung.
 *
 * Step 1: Rubrum              – Parteien-Übersicht
 * Step 2: Aktivlegitimation   – Fahrzeugeigentum + Live-Vorschau
 * Step 3: Unfallhergang       – Schilderung, auto-Ersatz Mandant→Kläger
 * Step 4: Schadenpositionen   – Checkboxen + Personenschaden
 * Step 5: Rechtl. Würdigung   – Dynamischer Textbaustein + editierbar
 * Step 6: Verzug & Kosten     – Bestätigung + editierbare Vorschau
 * Step 7: Zusammenfassung     – Abschließende Prüfung + Generieren
 */

import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";

// ── Konstanten ─────────────────────────────────────────────────────────────────

const STEPS = [
  { nr: 1, label: "Rubrum" },
  { nr: 2, label: "Aktivleg." },
  { nr: 3, label: "Unfall" },
  { nr: 4, label: "Schaden" },
  { nr: 5, label: "Würdigung" },
  { nr: 6, label: "Verzug" },
  { nr: 7, label: "Generieren" },
];

const PLEX = "'IBM Plex Sans', sans-serif";
const MONO = "'IBM Plex Mono', monospace";

// ── Hilfsfunktionen ────────────────────────────────────────────────────────────

function fmtEur(v) {
  return (v || 0).toLocaleString("de-DE", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }) + " €";
}

/**
 * Aktivlegitimations-Vorschautext (client-seitig, spiegelt klage_service).
 */
function buildVorschauText(typ, freigabe, datum, mkz, mandantIstFahrer, klaeger) {
  const mkzSatz = mkz ? ` mit dem amtlichen Kennzeichen ${mkz}` : "";
  const weiblich = klaeger.startsWith("Die");
  const eigen    = weiblich ? "Eigentümerin" : "Eigentümer";
  const pronAkk  = weiblich ? "sie" : "ihn";

  if (typ === "eigentum") {
    let text = `${klaeger} ist ${eigen} des Fahrzeugs${mkzSatz}.`;
    if (mandantIstFahrer) {
      text += `\n\nDa ${weiblich ? "sie" : "er"} das Fahrzeug auch selbst geführt hat, wird vermutet, dass ${pronAkk} das Recht zusteht, Schadensersatz geltend zu machen (§ 1006 BGB).`;
    }
    return text;
  }

  if (freigabe === "ungeklaert") return null;

  const finTyp      = typ === "finanziert" ? "Bank" : "Leasinggeberin";
  const eigentuemer = typ === "finanziert" ? "finanzierenden Bank" : "Leasinggeberin";
  const bedingTyp   = typ === "finanziert" ? "Finanzierungsbedingungen" : "Leasingbedingungen";
  const basis       = `Das Fahrzeug${mkzSatz} befindet sich im Eigentum der ${eigentuemer}. ${klaeger} ist jedoch aufgrund `;

  if (freigabe === "freigabe") {
    const datumStr = datum || "TT.MM.JJJJ";
    return (
      basis +
      `der vorliegenden Freigabeerklärung der ${finTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: Freigabeerklärung vom ${datumStr}, Anlage K1`
    );
  }
  return (
    basis +
    `der ${bedingTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: ${bedingTyp} in Kopie, Anlage K1`
  );
}

/**
 * Erstellt den Vorschautext für die Rechtliche Würdigung.
 */
function buildRwVorschau(haftungsbegruendung, haftungsquote, gesamtReguliert, weiblich) {
  const hq     = parseFloat(haftungsquote) || 100;
  const kl_dat = weiblich ? "der Klägerin" : "des Klägers";
  const lines  = [];

  lines.push(
    `Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall durch ` +
    `${(haftungsbegruendung || "").trim() || "sein schuldhaftes Verhalten"}. ` +
    `Die Haftungsquote beträgt ${Math.round(hq)} %.`
  );

  if (gesamtReguliert > 0) {
    lines.push(
      `Die Beklagte hat eine Teilregulierung in Höhe von ${fmtEur(gesamtReguliert)} vorgenommen. ` +
      `Die verbleibenden Kürzungen sind nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird.`
    );
  } else {
    lines.push(
      `Die Beklagte hat bislang keine Regulierung vorgenommen. ` +
      `Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.`
    );
  }

  if (hq < 100) {
    lines.push(
      `Die Mithaftungsquote ${kl_dat} beträgt ${Math.round(100 - hq)} %. ` +
      `Die Klageforderung wurde entsprechend gekürzt.`
    );
  }

  return lines.join("\n\n");
}

// ── Teilkomponenten ────────────────────────────────────────────────────────────

function Fortschrittsbalken({ step }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "1.5rem" }}>
      {STEPS.map((s, i) => {
        const aktiv    = s.nr === step;
        const erledigt = s.nr < step;
        return (
          <React.Fragment key={s.nr}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div style={{
                width: 26, height: 26, borderRadius: "50%",
                background: erledigt ? T.navy : aktiv ? T.gold : T.surface,
                border: `2px solid ${erledigt ? T.navy : aktiv ? T.gold : T.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: MONO, fontSize: "0.72rem", fontWeight: 700,
                color: (erledigt || aktiv) ? "#fff" : T.textMuted,
                transition: "all 0.25s",
                boxShadow: aktiv ? `0 0 0 3px ${T.gold}28` : "none",
                flexShrink: 0,
              }}>
                {erledigt ? "✓" : s.nr}
              </div>
              <div style={{
                fontFamily: PLEX, fontSize: "0.65rem", fontWeight: aktiv ? 700 : 400,
                color: aktiv ? T.gold : erledigt ? T.navy : T.textMuted,
                marginTop: 4, textAlign: "center", whiteSpace: "nowrap",
                transition: "color 0.25s",
              }}>
                {s.label}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                height: 2, flex: 1, marginBottom: 16,
                background: erledigt ? T.navy : T.borderSoft,
                transition: "background 0.25s",
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function RadioOption({ checked, onChange, label, sub }) {
  return (
    <label style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      padding: "10px 12px", borderRadius: 8, cursor: "pointer",
      border: `1.5px solid ${checked ? T.navy : T.borderSoft}`,
      background: checked ? `${T.navy}08` : T.white,
      transition: "all 0.15s", marginBottom: 6,
    }}>
      <input type="radio" checked={checked} onChange={onChange}
        style={{ marginTop: 2, accentColor: T.navy, cursor: "pointer" }} />
      <div>
        <div style={{ fontFamily: PLEX, fontSize: "0.9rem", fontWeight: checked ? 600 : 400,
          color: checked ? T.navy : T.text }}>{label}</div>
        {sub && <div style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted, marginTop: 1 }}>{sub}</div>}
      </div>
    </label>
  );
}

/** Stilisierte Dokument-Card mit editierbarem Textarea. */
function DokumentCard({ text, warnung, editText, onEditText }) {
  if (warnung) {
    return (
      <div style={{
        flex: 1, background: `${T.amber}10`,
        border: `1.5px solid ${T.amber}50`, borderRadius: 10,
        padding: "1.25rem", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 8,
        minHeight: 200,
      }}>
        <div style={{ fontSize: "1.75rem" }}>⚠️</div>
        <div style={{ fontFamily: PLEX, fontSize: "0.875rem", fontWeight: 600,
          color: "#92400e", textAlign: "center", lineHeight: 1.5 }}>
          Aktivlegitimation nicht nachgewiesen
        </div>
        <div style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted, textAlign: "center" }}>
          Kein Text wird generiert. Bitte vor Einreichung klären.
        </div>
      </div>
    );
  }

  return (
    <div style={{
      flex: 1, background: "#fdfcf7",
      border: `1px solid #e8e4d4`,
      borderRadius: 10, padding: "1.25rem",
      boxShadow: "inset 0 1px 3px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.06)",
      position: "relative", overflow: "hidden",
      minHeight: 200, display: "flex", flexDirection: "column",
    }}>
      <div style={{
        position: "absolute", inset: 0, opacity: 0.04,
        backgroundImage: "repeating-linear-gradient(0deg, #000 0px, #000 1px, transparent 1px, transparent 24px)",
        pointerEvents: "none",
      }} />
      <div style={{ position: "relative", flex: 1, display: "flex", flexDirection: "column" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.68rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
          marginBottom: "0.75rem" }}>
          Vorschau Klageschrift
          <span style={{ fontWeight: 400, marginLeft: 8, textTransform: "none", letterSpacing: 0 }}>
            (editierbar)
          </span>
        </div>
        <textarea
          value={editText !== undefined ? (editText || "") : (text || "")}
          onChange={e => onEditText && onEditText(e.target.value)}
          placeholder="Kein Text für diesen Fall."
          style={{
            flex: 1, minHeight: 320,
            fontFamily: MONO, fontSize: "0.825rem", color: "#2d2a1e",
            lineHeight: 1.7, background: "transparent", border: "none",
            resize: "vertical", outline: "none", width: "100%",
            padding: 0, boxSizing: "border-box",
          }}
        />
      </div>
    </div>
  );
}

// ── Linke-Spalten-Wrapper ──────────────────────────────────────────────────────

function LinkeInfo({ kinder }) {
  return (
    <div style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: "1rem" }}>
      {kinder}
    </div>
  );
}

function AbschnittLabel({ text }) {
  return (
    <div style={{ fontFamily: PLEX, fontSize: "0.75rem", fontWeight: 700,
      color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
      marginBottom: "0.5rem" }}>
      {text}
    </div>
  );
}

// ── Step 1: Rubrum ─────────────────────────────────────────────────────────────

function StepRubrum({ beklagte }) {
  const klaeger   = (beklagte || []).filter(b => b.rolle_klage === "klaeger");
  const beklagteG = (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked);
  const mehrereK  = klaeger.length > 1;
  const mehrereB  = beklagteG.length > 1;

  return (
    <div>
      <div style={{
        background: T.surface, border: `1px solid ${T.borderSoft}`,
        borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1.25rem",
        fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted,
      }}>
        ℹ Parteien-Überblick. Änderungen: zurück zur Kachel „2. Parteien" im Klage-Tab.
      </div>

      <div style={{
        background: "#fdfcf7", border: `1px solid #e8e4d4`,
        borderRadius: 10, padding: "1.5rem",
        fontFamily: PLEX, fontSize: "0.925rem",
      }}>
        {/* Kläger */}
        {klaeger.length === 0 ? (
          <div style={{ color: T.amber }}>⚠ Kein Kläger erfasst.</div>
        ) : klaeger.map((b, i) => {
          const name   = b.vorname ? `${b.vorname} ${b.name}`.trim() : b.name || b.firma || "Mandant";
          const anschr = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
          const anrede = (b.anrede || "").toLowerCase();
          let rolleBez = mehrereK
            ? (anrede === "frau" ? `Klägerin zu ${i + 1})` : `Kläger zu ${i + 1})`)
            : (anrede === "frau" ? "Klägerin" : "Kläger");
          return (
            <div key={b.id} style={{ marginBottom: "0.75rem" }}>
              <div style={{ fontWeight: 700, color: T.navy }}>{name}</div>
              {anschr && <div style={{ fontSize: "0.85rem", color: T.textMuted }}>{anschr}</div>}
              <div style={{ fontSize: "0.8rem", fontStyle: "italic", color: T.textFaint, marginTop: 2 }}>
                – {rolleBez} –
              </div>
            </div>
          );
        })}

        {klaeger.length > 0 && (
          <div style={{ fontSize: "0.875rem", color: T.text, marginBottom: "0.75rem" }}>
            Prozessbevollmächtigte: Koch, Schatz &amp; Kollegen, Tulpenhofstr. 1, 63067 Offenbach
          </div>
        )}

        {klaeger.length > 0 && beklagteG.length > 0 && (
          <div style={{
            textAlign: "center", padding: "0.6rem 0", marginBottom: "0.75rem",
            fontSize: "0.875rem", letterSpacing: "0.15em", color: T.textFaint,
            borderTop: `1px solid ${T.borderSoft}`, borderBottom: `1px solid ${T.borderSoft}`,
            textTransform: "uppercase",
          }}>
            g e g e n
          </div>
        )}

        {beklagteG.length === 0 ? (
          <div style={{ color: T.amber, fontSize: "0.875rem" }}>⚠ Keine Beklagten ausgewählt.</div>
        ) : beklagteG.map((b, i) => {
          const name    = b.versicherung || b.firma || `${b.vorname || ""} ${b.name || ""}`.trim() || "Unbekannt";
          const anschr  = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
          const extras  = [b.schaden_nr ? `Schaden-Nr. ${b.schaden_nr}` : null, b.kfz_kennzeichen || null].filter(Boolean);
          const nr      = mehrereB ? ` zu ${i + 1})` : "";
          const vertr   = b.vertreter_name
            ? `, vertreten durch ${b.vertreter_funktion || "den Vorstand"} ${b.vertreter_name}`
            : "";
          return (
            <div key={b.id} style={{ marginBottom: i < beklagteG.length - 1 ? "0.75rem" : 0 }}>
              <div style={{ fontWeight: 600, color: T.navy }}>{name}{vertr}</div>
              {anschr && <div style={{ fontSize: "0.85rem", color: T.textMuted }}>{anschr}</div>}
              {extras.length > 0 && (
                <div style={{ fontSize: "0.8rem", color: T.textFaint }}>{extras.join(" · ")}</div>
              )}
              <div style={{ fontSize: "0.8rem", fontStyle: "italic", color: T.textFaint, marginTop: 2 }}>
                – Beklagte{b.anrede === "frau" ? "" : "r"}{nr} –
              </div>
              {(b.versicherung || b.firma) && !b.vertreter_name && (
                <div style={{ fontSize: "0.78rem", color: T.amber, marginTop: 2 }}>
                  ⚠ Vertreter fehlt – bitte im Klage-Tab nachtragen.
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 2: Aktivlegitimation ──────────────────────────────────────────────────

function StepAktLeg({ aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
                      aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
                      klaeger, aktLegTextOverride, onAktLegTextOverride }) {

  const brauchtFreigabe = aktLegTyp !== "eigentum";
  const vorschauText    = buildVorschauText(
    aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer, klaeger
  );

  useEffect(() => {
    if (onAktLegTextOverride) onAktLegTextOverride(vorschauText || "");
  }, [aktLegTyp, aktLegFreigabe, aktLegDatum, mandantIstFahrer]); // eslint-disable-line

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 260px" }}>
        <AbschnittLabel text="Fahrzeugeigentum" />
        <RadioOption checked={aktLegTyp === "eigentum"}   onChange={() => onAktLegTyp("eigentum")}
          label="Eigentum des Klägers" sub="Standardfall – § 1006 BGB wenn selbst gefahren" />
        <RadioOption checked={aktLegTyp === "finanziert"} onChange={() => onAktLegTyp("finanziert")}
          label="Finanziert" sub="Fahrzeug im Eigentum der Bank" />
        <RadioOption checked={aktLegTyp === "geleast"}    onChange={() => onAktLegTyp("geleast")}
          label="Geleast" sub="Fahrzeug im Eigentum der Leasinggeberin" />

        {brauchtFreigabe && (
          <div style={{ marginTop: "1.25rem" }}>
            <AbschnittLabel text="Nachweis der Aktivlegitimation" />
            <RadioOption checked={aktLegFreigabe === "freigabe"}
              onChange={() => onAktLegFreigabe("freigabe")}
              label="Freigabeerklärung liegt vor" />
            <RadioOption checked={aktLegFreigabe === "bedingungen"}
              onChange={() => onAktLegFreigabe("bedingungen")}
              label={aktLegTyp === "finanziert" ? "Aus Finanzierungsbedingungen" : "Aus Leasingbedingungen"} />
            <RadioOption checked={aktLegFreigabe === "ungeklaert"}
              onChange={() => onAktLegFreigabe("ungeklaert")}
              label="Noch nicht geklärt ⚠" />

            {aktLegFreigabe === "freigabe" && (
              <div style={{ marginTop: "1rem" }}>
                <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 6 }}>
                  Datum der Freigabeerklärung
                </div>
                <input type="date"
                  value={(() => {
                    if (!aktLegDatum) return "";
                    const m = aktLegDatum.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                    if (m) return `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
                    return aktLegDatum;
                  })()}
                  onChange={e => {
                    const v = e.target.value;
                    if (!v) { onAktLegDatum(""); return; }
                    const [y, mo, d] = v.split("-");
                    onAktLegDatum(`${d}.${mo}.${y}`);
                  }}
                  style={{
                    padding: "7px 10px", border: `1.5px solid ${T.border}`,
                    borderRadius: 7, fontFamily: MONO, fontSize: "0.875rem",
                    outline: "none", width: "100%", boxSizing: "border-box",
                    background: T.white, color: T.navy,
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      <DokumentCard
        text={vorschauText}
        warnung={brauchtFreigabe && aktLegFreigabe === "ungeklaert"}
        editText={aktLegTextOverride}
        onEditText={onAktLegTextOverride}
      />
    </div>
  );
}

// ── Step 3: Unfallhergang ──────────────────────────────────────────────────────

function StepUnfall({ schilderungOriginal, klaeger, unfalltextEdit, onUnfalltextEdit }) {
  const weiblich = klaeger.startsWith("Die");

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 220px", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <AbschnittLabel text="Quelle & Anpassung" />
        <div style={{
          background: T.surface, borderRadius: 8, padding: "0.75rem",
          fontFamily: PLEX, fontSize: "0.8rem", color: T.text,
          border: `1px solid ${T.borderSoft}`,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>Automatisch ersetzt:</div>
          <div style={{ color: T.textMuted, lineHeight: 1.7 }}>
            Mandant{weiblich ? "in" : ""} → {weiblich ? "Klägerin" : "Kläger"}<br />
            des Mandanten → {weiblich ? "der Klägerin" : "des Klägers"}<br />
            dem Mandanten → {weiblich ? "der Klägerin" : "dem Kläger"}<br />
            die Mandantin → die Klägerin
          </div>
        </div>
        {!schilderungOriginal && (
          <div style={{
            background: `${T.amber}12`, border: `1px solid ${T.amber}50`,
            borderRadius: 8, padding: "0.75rem",
            fontFamily: PLEX, fontSize: "0.8rem", color: "#92400e",
          }}>
            ⚠ Keine Unfallschilderung in Unfalldetails hinterlegt. Bitte Text manuell eingeben.
          </div>
        )}
        {schilderungOriginal && (
          <div style={{
            background: `${T.green}10`, border: `1px solid ${T.green}40`,
            borderRadius: 8, padding: "0.75rem",
            fontFamily: PLEX, fontSize: "0.8rem", color: T.green,
          }}>
            ✓ Schilderung aus Unfalldetails geladen.
          </div>
        )}
        <div style={{
          fontFamily: PLEX, fontSize: "0.76rem", color: T.textFaint, marginTop: "auto",
        }}>
          Dieser Text erscheint unter Abschnitt „2.) Unfallhergang" in der Klageschrift.
        </div>
      </div>

      <DokumentCard editText={unfalltextEdit} onEditText={onUnfalltextEdit} />
    </div>
  );
}

// ── Step 4: Schadenpositionen ──────────────────────────────────────────────────

function StepSchaden({ positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind, abrechnungen }) {
  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);

  return (
    <div>
      {(abrechnungen?.length || 0) > 0 && (
        <div style={{
          marginBottom: "1.25rem", padding: "0.75rem 1rem",
          background: T.surface, borderRadius: 8, border: `1px solid ${T.borderSoft}`,
        }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
            marginBottom: "0.5rem" }}>
            Bisheriger Regulierungsstand
          </div>
          {abrechnungen.map((ab, i) => (
            <div key={ab.id || i} style={{ display: "flex", justifyContent: "space-between",
              fontFamily: MONO, fontSize: "0.825rem", padding: "2px 0" }}>
              <span style={{ color: T.textMuted }}>{ab.versicherung || "Abrechnung"} · {ab.datum || ""}</span>
              <span style={{ color: T.navy, fontWeight: 600 }}>{fmtEur(parseFloat(ab.gesamt_reguliert) || 0)}</span>
            </div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between",
            borderTop: `1px solid ${T.border}`, marginTop: 4, paddingTop: 4,
            fontFamily: MONO, fontSize: "0.875rem", fontWeight: 700, color: T.navy }}>
            <span>Summe reguliert</span>
            <span>{fmtEur(abrechnungen.reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0))}</span>
          </div>
        </div>
      )}

      <div style={{ marginBottom: "1.25rem" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.75rem" }}>
          Klagepositionen – angehakt = eingeklagt
        </div>
        {positionen.map(p => (
          <label key={p.key} style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "8px 10px", borderRadius: 7, cursor: "pointer",
            border: `1px solid ${p.checked ? T.navy : T.borderSoft}`,
            background: p.checked ? `${T.navy}06` : T.white,
            marginBottom: 4, transition: "all 0.12s",
          }}>
            <input type="checkbox" checked={p.checked}
              onChange={() => onTogglePos(p.key)}
              style={{ accentColor: T.navy, cursor: "pointer", width: 16, height: 16 }} />
            <span style={{ flex: 1, fontFamily: PLEX, fontSize: "0.875rem",
              color: p.checked ? T.navy : T.text, fontWeight: p.checked ? 600 : 400 }}>
              {p.label}
            </span>
            <span style={{ fontFamily: MONO, fontSize: "0.875rem",
              color: p.checked ? T.navy : T.textMuted, fontWeight: p.checked ? 700 : 400 }}>
              {fmtEur(p.betrag)}
            </span>
          </label>
        ))}
      </div>

      <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem",
        border: `1px solid ${T.borderSoft}`, marginBottom: "1rem" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.5rem" }}>Klagebetrag</div>
        <div style={{ fontFamily: MONO, fontSize: "1.25rem", fontWeight: 700, color: T.navy }}>
          {fmtEur(klagebetrag + (mitSG ? sgMind : 0))}
        </div>
        {mitSG && sgMind > 0 && (
          <div style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted }}>
            Sachschaden {fmtEur(klagebetrag)} + SG {fmtEur(sgMind)}
          </div>
        )}
      </div>

      <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "1rem" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.75rem" }}>Personenschaden</div>
        {[
          { val: false, label: "Kein Personenschaden / nicht geltend gemacht" },
          { val: true,  label: "Schmerzensgeld geltend machen" },
        ].map(opt => (
          <label key={String(opt.val)}
            style={{ display: "flex", alignItems: "center", gap: 8,
              cursor: "pointer", fontFamily: PLEX, fontSize: "0.9rem",
              color: mitSG === opt.val ? T.navy : T.text, fontWeight: mitSG === opt.val ? 600 : 400,
              marginBottom: 6 }}>
            <input type="radio" checked={mitSG === opt.val}
              onChange={() => onMitSG(opt.val)}
              style={{ accentColor: T.navy, cursor: "pointer" }} />
            {opt.label}
          </label>
        ))}
        {mitSG && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
            <div style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>
              Mindestbetrag:
            </div>
            <input type="number" min="0" step="100" value={sgMind}
              onChange={e => onSGMind(parseFloat(e.target.value) || 0)}
              style={{
                width: 120, padding: "6px 10px",
                border: `1.5px solid ${T.border}`, borderRadius: 7,
                fontFamily: MONO, fontSize: "0.9rem", outline: "none",
                background: T.white, color: T.navy,
              }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>€</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Einwände & Kürzungen ───────────────────────────────────────────────────────

const KATEGORIE_ORDER  = ["fahrzeugschaden", "technisch_gutachten", "ersatzbeschaffung", "sonstiger_schaden"];
const KATEGORIE_LABELS = {
  fahrzeugschaden:     "Fahrzeugschaden",
  technisch_gutachten: "Technisches Gutachten / SV",
  ersatzbeschaffung:   "Ersatzbeschaffung",
  sonstiger_schaden:   "Sonstiger Schaden",
};
// Erweiterungspunkt: weitere Einwands-Kategorien hier ergänzen, sobald sie im
// Backend als eigene Kategorie in kuerzungsarten oder einer neuen Tabelle gepflegt werden.

function EinwandePanel({ abrechnungen, kuerzungsarten, onUebernehmen, onClose }) {
  // IDs der tatsächlich gekürzten Positionen (aus Regulierungsschreiben)
  const aktiveIds = new Set(
    (abrechnungen || []).flatMap(ab =>
      (ab.positionen || [])
        .filter(p => p.kuerzungsart_id != null)
        .map(p => Number(p.kuerzungsart_id))
    )
  );

  const [checked, setChecked] = useState(new Set(aktiveIds));

  function toggle(id) {
    setChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Kürzungsarten nach Kategorie gruppieren
  const gruppen = {};
  (kuerzungsarten || []).forEach(ka => {
    const kat = ka.kategorie || "sonstiges";
    if (!gruppen[kat]) gruppen[kat] = [];
    gruppen[kat].push(ka);
  });
  const alleKats = [
    ...KATEGORIE_ORDER.filter(k => gruppen[k]),
    ...Object.keys(gruppen).filter(k => !KATEGORIE_ORDER.includes(k)),
  ];

  function uebernehmen() {
    const selected = (kuerzungsarten || []).filter(ka => checked.has(ka.id));
    if (selected.length === 0) { onUebernehmen(""); return; }
    const lines = [
      "Die Beklagte hat folgende Positionen zu Unrecht nicht oder nicht vollständig reguliert:",
      "",
      ...selected.map(ka =>
        `${ka.bezeichnung}: ${(ka.standard_gegenargument || "").trim()}`
      ),
    ];
    onUebernehmen(lines.join("\n\n"));
  }

  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0,
        background: "rgba(10,20,50,0.45)",
        zIndex: 9100,
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "1rem",
      }}>
      <div style={{
        background: "#fff", borderRadius: 14,
        width: "100%", maxWidth: 660, maxHeight: "82vh",
        display: "flex", flexDirection: "column",
        boxShadow: "0 24px 70px rgba(0,0,0,0.32)",
        animation: "slideUp 0.2s cubic-bezier(0.16,1,0.3,1)",
      }}>

        {/* Header */}
        <div style={{
          padding: "1rem 1.25rem 0.875rem",
          borderBottom: `1px solid ${T.borderSoft}`,
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
          flexShrink: 0,
        }}>
          <div>
            <div style={{ fontFamily: PLEX, fontSize: "1rem", fontWeight: 700, color: T.navy }}>
              Einwände &amp; Kürzungen
            </div>
            <div style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted, marginTop: 3 }}>
              {aktiveIds.size > 0
                ? <><span style={{ color: T.gold, fontWeight: 600 }}>{aktiveIds.size}</span>
                    {" "}Kürzung{aktiveIds.size !== 1 ? "en" : ""} aus Regulierungsschreiben vorausgewählt</>
                : "Keine Kürzungen aus Regulierungsschreiben erfasst – manuelle Auswahl möglich"}
            </div>
          </div>
          <button onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer",
              fontSize: "1.2rem", color: T.textMuted, padding: "2px 6px", lineHeight: 1 }}>
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem" }}>
          {alleKats.map(kat => (
            <div key={kat} style={{ marginBottom: "1.25rem" }}>
              <div style={{ fontFamily: PLEX, fontSize: "0.68rem", fontWeight: 700,
                color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
                marginBottom: "0.5rem" }}>
                {KATEGORIE_LABELS[kat] || kat}
              </div>
              {(gruppen[kat] || []).map(ka => (
                <label key={ka.id} style={{
                  display: "flex", alignItems: "flex-start", gap: 10,
                  padding: "8px 10px", borderRadius: 8, cursor: "pointer",
                  border: `1px solid ${checked.has(ka.id) ? T.navy : T.borderSoft}`,
                  background: checked.has(ka.id) ? `${T.navy}06` : T.white,
                  marginBottom: 4, transition: "all 0.12s",
                }}>
                  <input type="checkbox" checked={checked.has(ka.id)}
                    onChange={() => toggle(ka.id)}
                    style={{ accentColor: T.navy, marginTop: 3, cursor: "pointer",
                      flexShrink: 0, width: 15, height: 15 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8,
                      fontFamily: PLEX, fontSize: "0.875rem",
                      fontWeight: checked.has(ka.id) ? 600 : 400,
                      color: checked.has(ka.id) ? T.navy : T.text }}>
                      {ka.bezeichnung}
                      {aktiveIds.has(ka.id) && (
                        <span style={{
                          fontSize: "0.68rem", fontWeight: 700,
                          background: `${T.gold}22`, color: "#8a5800",
                          padding: "1px 7px", borderRadius: 10,
                        }}>gekürzt</span>
                      )}
                    </div>
                    {ka.standard_gegenargument && (
                      <div style={{ fontFamily: PLEX, fontSize: "0.75rem",
                        color: T.textFaint, marginTop: 2, lineHeight: 1.55 }}>
                        {ka.standard_gegenargument}
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          padding: "0.75rem 1.25rem",
          borderTop: `1px solid ${T.borderSoft}`,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexShrink: 0, background: T.offWhite, borderRadius: "0 0 14px 14px",
        }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted }}>
            {checked.size} ausgewählt
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={onClose}
              style={{ padding: "8px 16px", borderRadius: 7, cursor: "pointer",
                border: `1.5px solid ${T.border}`, background: "#fff",
                fontFamily: PLEX, fontSize: "0.85rem", color: T.text }}>
              Abbrechen
            </button>
            <button onClick={uebernehmen}
              style={{ padding: "8px 18px", borderRadius: 7, cursor: "pointer",
                border: "none", background: T.navy,
                fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
              Text übernehmen →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Step 5: Rechtliche Würdigung ───────────────────────────────────────────────

function StepRw({ haftungsbegruendungInit, haftungsquoteInit, abrechnungen, weiblich,
                  rwText, onRwText, kuerzungsarten }) {
  const gesamtReg = (abrechnungen || []).reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0);
  const [hq, setHq] = useState(parseFloat(haftungsquoteInit) || 100);
  const [hb, setHb] = useState(haftungsbegruendungInit || "");
  const [einwandeOffen, setEinwandeOffen] = useState(false);

  function neuGenerieren() {
    onRwText(buildRwVorschau(hb, hq, gesamtReg, weiblich));
  }

  function einwandeUebernehmen(generierterText) {
    setEinwandeOffen(false);
    if (generierterText) {
      onRwText((rwText ? rwText + "\n\n" : "") + generierterText);
    }
  }

  return (
    <>
    {einwandeOffen && (
      <EinwandePanel
        abrechnungen={abrechnungen}
        kuerzungsarten={kuerzungsarten || []}
        onUebernehmen={einwandeUebernehmen}
        onClose={() => setEinwandeOffen(false)}
      />
    )}
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 240px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Eingaben" />

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Haftungsquote (Gegner)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="number" value={hq}
              onChange={e => setHq(parseFloat(e.target.value) || 0)}
              min="0" max="100" step="5"
              style={{
                width: 72, padding: "6px 8px",
                border: `1.5px solid ${T.border}`, borderRadius: 7,
                fontFamily: MONO, fontSize: "0.9rem", outline: "none",
                background: T.white, color: T.navy,
              }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.9rem", color: T.textMuted }}>%</span>
            {hq < 100 && (
              <span style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.amber }}>
                Teilhaftung
              </span>
            )}
          </div>
        </div>

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Haftungsbegründung
          </div>
          <textarea value={hb} onChange={e => setHb(e.target.value)}
            placeholder="z.B. Rotlichtverstoß, Überschreitung der Vorfahrt, …"
            rows={4}
            style={{
              width: "100%", padding: "8px 10px",
              border: `1.5px solid ${T.border}`, borderRadius: 7,
              fontFamily: PLEX, fontSize: "0.825rem", outline: "none",
              background: T.white, color: T.navy,
              resize: "none", boxSizing: "border-box", lineHeight: 1.5,
            }} />
        </div>

        <div style={{
          background: T.surface, borderRadius: 7, padding: "0.6rem 0.75rem",
          fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted,
          border: `1px solid ${T.borderSoft}`,
        }}>
          Regulierungsstand:{" "}
          <span style={{ color: gesamtReg > 0 ? T.navy : T.textFaint, fontWeight: 600 }}>
            {gesamtReg > 0 ? fmtEur(gesamtReg) : "keine"}
          </span>
        </div>

        <button onClick={neuGenerieren}
          style={{
            padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy,
          }}>
          ↻ Text neu generieren
        </button>

        <button onClick={() => setEinwandeOffen(true)}
          style={{
            padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.gold}`, background: `${T.gold}10`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: "#8a5800",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}>
          ⚔ Kürzungen &amp; Einwände
          {(abrechnungen || []).flatMap(ab =>
            (ab.positionen || []).filter(p => p.kuerzungsart_id != null)
          ).length > 0 && (
            <span style={{
              background: T.gold, color: "#fff", fontSize: "0.68rem", fontWeight: 700,
              padding: "1px 6px", borderRadius: 10,
            }}>
              {new Set((abrechnungen || []).flatMap(ab =>
                (ab.positionen || [])
                  .filter(p => p.kuerzungsart_id != null)
                  .map(p => p.kuerzungsart_id)
              )).size}
            </span>
          )}
        </button>

        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: "auto" }}>
          Text erscheint unter „3.) Rechtliche Würdigung". Rechts direkt editierbar.
        </div>
      </div>

      <DokumentCard editText={rwText} onEditText={onRwText} />
    </div>
    </>
  );
}

// ── Step 6: Verzug & Kosten ────────────────────────────────────────────────────

function StepVerzug({ verzug, zinsenAb, rvgData, rvgOverride, weiblich,
                      wizardVerzugText, onWizardVerzugText }) {
  const rvgGesamt = rvgOverride ? parseFloat(rvgOverride) : (rvgData?.gesamt || 0);

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 240px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Einstellungen (aus Klage-Tab)" />

        <div style={{
          background: T.surface, borderRadius: 8, padding: "0.75rem 1rem",
          fontFamily: PLEX, fontSize: "0.875rem", border: `1px solid ${T.borderSoft}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ color: T.textMuted }}>Verzugsdatum</span>
            <span style={{ fontFamily: MONO, fontWeight: 600, color: verzug ? T.navy : T.amber }}>
              {verzug || "nicht gesetzt"}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: T.textMuted }}>Zinsen ab</span>
            <span style={{ fontFamily: MONO, fontWeight: 600, color: T.navy }}>
              {zinsenAb === "verzug" ? "Verzugseintritt" : "Rechtshängigkeit"}
            </span>
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "0.75rem" }}>
          <AbschnittLabel text="Automatisch generiert" />
          <div style={{
            fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, lineHeight: 1.7,
          }}>
            <div>RVG (Gegenstandswert): <span style={{ fontFamily: MONO, color: T.navy }}>{fmtEur(rvgGesamt)}</span></div>
            <div style={{ marginTop: 4 }}>Schlussformel: wird automatisch eingefügt.</div>
          </div>
        </div>

        <div style={{
          fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: "auto",
        }}>
          Verzug-Text editierbar. RVG-Tabelle und Schlussformel sind unveränderlich berechnet.
        </div>
      </div>

      <DokumentCard editText={wizardVerzugText} onEditText={onWizardVerzugText} />
    </div>
  );
}

// ── Step 7: Zusammenfassung + Generieren ───────────────────────────────────────

function StepZusammenfassung({ gericht, beklagte, positionen, mitSG, sgMind,
                               rvgData, rvgOverride, aktLegTyp, aktLegFreigabe,
                               zinsenAb, verzug,
                               laedt, onGenerieren, fehler }) {
  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);
  const rvgGesamt   = rvgOverride ? parseFloat(rvgOverride) : (rvgData?.gesamt || 0);
  const klaeger     = beklagte?.filter(b => b.rolle_klage === "klaeger") || [];
  const beklagteG   = beklagte?.filter(b => b.rolle_klage !== "klaeger" && b.checked) || [];

  const firmenOhneVertreter = beklagteG.filter(b =>
    (b.versicherung || b.firma) && !b.vertreter_name
  );
  const keinPositionen = positionen.filter(p => p.checked).length === 0;
  const keinGericht    = !gericht;
  const gesperrt       = laedt || keinGericht || keinPositionen || firmenOhneVertreter.length > 0;

  const aktLegLabel = { eigentum: "Eigentum", finanziert: "Finanziert", geleast: "Geleast" }[aktLegTyp] || aktLegTyp;
  const freigabeLabel = { freigabe: "Freigabeerklärung", bedingungen: "Aus Bedingungen", ungeklaert: "⚠ Ungeklärt" }[aktLegFreigabe] || "";

  function ZeileZusammenfassung({ icon, label, wert, warn }) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10,
        padding: "8px 0", borderBottom: `1px solid ${T.borderSoft}` }}>
        <div style={{ width: 22, textAlign: "center", flexShrink: 0 }}>{icon}</div>
        <div style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted, flex: 1 }}>{label}</div>
        <div style={{ fontFamily: MONO, fontSize: "0.875rem", fontWeight: 600,
          color: warn ? T.amber : T.navy, textAlign: "right" }}>
          {wert}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ background: T.surface, borderRadius: 10, padding: "1rem 1.25rem",
        marginBottom: "1.25rem", border: `1px solid ${T.border}` }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
          marginBottom: "0.75rem" }}>
          Zusammenfassung
        </div>
        <ZeileZusammenfassung icon="📍" label="Gericht"
          wert={gericht ? gericht.name : "— nicht gewählt —"} warn={keinGericht} />
        <ZeileZusammenfassung icon="👤" label="Kläger"
          wert={klaeger.map(b => b.vorname ? `${b.vorname} ${b.name}` : b.name || b.firma || "–").join(", ") || "–"} />
        <ZeileZusammenfassung icon="⚔" label="Beklagte"
          wert={beklagteG.map(b => b.versicherung || b.firma || b.name || "–").join(", ") || "–"} />
        <ZeileZusammenfassung icon="⚖" label="Klagebetrag"
          wert={fmtEur(klagebetrag + (mitSG && sgMind > 0 ? sgMind : 0))} warn={keinPositionen} />
        <ZeileZusammenfassung icon="⏱" label="Zinsen ab"
          wert={zinsenAb === "verzug" && verzug ? `Verzugseintritt ${verzug}` : "Rechtshängigkeit"} />
        <ZeileZusammenfassung icon="🏠" label="Aktivlegitimation"
          wert={aktLegFreigabe === "ungeklaert"
            ? `${aktLegLabel} – ⚠ ungeklärt`
            : `${aktLegLabel}${aktLegTyp !== "eigentum" ? ` · ${freigabeLabel}` : ""}`}
          warn={aktLegFreigabe === "ungeklaert"} />
        <ZeileZusammenfassung icon="💶" label="RVG (Nebenforderung)" wert={fmtEur(rvgGesamt)} />
      </div>

      {(keinGericht || keinPositionen || firmenOhneVertreter.length > 0 || aktLegFreigabe === "ungeklaert") && (
        <div style={{ marginBottom: "1rem" }}>
          {keinGericht && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Kein Gericht gewählt.
          </div>}
          {keinPositionen && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Keine Schadenpositionen ausgewählt.
          </div>}
          {firmenOhneVertreter.length > 0 && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Firmen ohne Vertreter: {firmenOhneVertreter.map(b => b.versicherung || b.firma).join(", ")}
          </div>}
          {aktLegFreigabe === "ungeklaert" && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.amber,
            padding: "7px 12px", background: `${T.amber}12`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Aktivlegitimation ungeklärt – kein Text wird generiert.
          </div>}
        </div>
      )}

      {fehler && (
        <div style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.red,
          padding: "8px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: "1rem" }}>
          {fehler}
        </div>
      )}

      <button onClick={onGenerieren} disabled={gesperrt}
        style={{
          width: "100%", padding: "14px 0",
          background: gesperrt ? T.border : T.gold,
          color: gesperrt ? T.textMuted : "#fff",
          border: "none", borderRadius: 10, cursor: gesperrt ? "not-allowed" : "pointer",
          fontFamily: PLEX, fontSize: "1rem", fontWeight: 700,
          transition: "all 0.2s",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
        }}>
        {laedt ? (
          <>
            <div style={{
              width: 16, height: 16, border: "2.5px solid rgba(255,255,255,0.3)",
              borderTopColor: "#fff", borderRadius: "50%",
              animation: "spin 0.7s linear infinite",
            }} />
            Wird erstellt …
          </>
        ) : "📄 Als Word generieren"}
      </button>
    </div>
  );
}

// ── Hauptkomponente ────────────────────────────────────────────────────────────

export default function KlageWizard({
  step, onStepChange, onClose,
  // Step 2 (Aktivlegitimation)
  aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
  aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
  aktLegTextOverride, onAktLegTextOverride,
  // Step 3 (Unfallhergang)
  schilderungOriginal,
  wizardUnfallText, onWizardUnfallText,
  // Step 4 (Schadenpositionen)
  abrechnungen,
  positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind,
  // Step 5 (Rechtliche Würdigung)
  haftungsbegruendungInit, haftungsquoteInit,
  wizardRwText, onWizardRwText, kuerzungsarten,
  // Step 6 (Verzug & Kosten)
  wizardVerzugText, onWizardVerzugText,
  // Step 7 (Zusammenfassung) + shared
  gericht, beklagte, rvgData, rvgOverride, zinsenAb, verzug,
  // Generieren
  laedt, onGenerieren, fehler,
}) {
  const backdropRef = useRef(null);

  useEffect(() => {
    const handler = e => { if (e.key === "Escape" && !laedt) onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [laedt, onClose]);

  const klaegerObj = beklagte?.find(b => b.rolle_klage === "klaeger");
  const klaeger    = (klaegerObj?.anrede || "").toLowerCase() === "frau" ? "Die Klägerin" : "Der Kläger";
  const weiblich   = klaeger.startsWith("Die");

  const kannWeiter = () => {
    if (step === 4 && positionen.filter(p => p.checked).length === 0) return false;
    return true;
  };
  const weiter  = () => { if (kannWeiter()) onStepChange(step + 1); };
  const zurueck = () => onStepChange(step - 1);

  return (
    <>
      <div
        ref={backdropRef}
        onClick={e => { if (e.target === backdropRef.current && !laedt) onClose(); }}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(10, 20, 50, 0.55)",
          backdropFilter: "blur(3px)",
          zIndex: 9000,
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: "1rem",
          animation: "fadeIn 0.18s ease",
        }}>

        <div style={{
          background: "#fff", borderRadius: 16,
          width: "100%", maxWidth: 840,
          maxHeight: "92vh", overflow: "hidden",
          display: "flex", flexDirection: "column",
          boxShadow: "0 24px 80px rgba(0,0,0,0.28), 0 4px 16px rgba(0,0,0,0.12)",
          animation: "slideUp 0.22s cubic-bezier(0.16,1,0.3,1)",
        }}>

          {/* Header */}
          <div style={{
            padding: "1.25rem 1.5rem 1rem",
            borderBottom: `1px solid ${T.borderSoft}`,
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexShrink: 0,
          }}>
            <div>
              <div style={{ fontFamily: PLEX, fontSize: "1.1rem", fontWeight: 700, color: T.navy }}>
                Klageschrift zusammenstellen
              </div>
              <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginTop: 2 }}>
                Schritt {step} von {STEPS.length} – {STEPS[step - 1]?.label}
              </div>
            </div>
            <button onClick={() => !laedt && onClose()} disabled={laedt}
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: "1.3rem", color: T.textMuted, padding: "4px 8px",
                borderRadius: 6, lineHeight: 1, opacity: laedt ? 0.3 : 1,
              }}>✕</button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem" }}>
            <Fortschrittsbalken step={step} />

            {step === 1 && <StepRubrum beklagte={beklagte} />}

            {step === 2 && (
              <StepAktLeg
                aktLegTyp={aktLegTyp}         onAktLegTyp={onAktLegTyp}
                aktLegFreigabe={aktLegFreigabe} onAktLegFreigabe={onAktLegFreigabe}
                aktLegDatum={aktLegDatum}       onAktLegDatum={onAktLegDatum}
                mandantIstFahrer={mandantIstFahrer}
                mandantKz={mandantKz}
                klaeger={klaeger}
                aktLegTextOverride={aktLegTextOverride}
                onAktLegTextOverride={onAktLegTextOverride}
              />
            )}

            {step === 3 && (
              <StepUnfall
                schilderungOriginal={schilderungOriginal}
                klaeger={klaeger}
                unfalltextEdit={wizardUnfallText}
                onUnfalltextEdit={onWizardUnfallText}
              />
            )}

            {step === 4 && (
              <StepSchaden
                abrechnungen={abrechnungen}
                positionen={positionen}   onTogglePos={onTogglePos}
                mitSG={mitSG}             onMitSG={onMitSG}
                sgMind={sgMind}           onSGMind={onSGMind}
              />
            )}

            {step === 5 && (
              <StepRw
                haftungsbegruendungInit={haftungsbegruendungInit}
                haftungsquoteInit={haftungsquoteInit}
                abrechnungen={abrechnungen}
                weiblich={weiblich}
                rwText={wizardRwText}
                onRwText={onWizardRwText}
                kuerzungsarten={kuerzungsarten}
              />
            )}

            {step === 6 && (
              <StepVerzug
                verzug={verzug}           zinsenAb={zinsenAb}
                rvgData={rvgData}         rvgOverride={rvgOverride}
                weiblich={weiblich}
                wizardVerzugText={wizardVerzugText}
                onWizardVerzugText={onWizardVerzugText}
              />
            )}

            {step === 7 && (
              <StepZusammenfassung
                gericht={gericht}         beklagte={beklagte}
                positionen={positionen}   mitSG={mitSG}        sgMind={sgMind}
                rvgData={rvgData}         rvgOverride={rvgOverride}
                aktLegTyp={aktLegTyp}     aktLegFreigabe={aktLegFreigabe}
                zinsenAb={zinsenAb}       verzug={verzug}
                laedt={laedt}             onGenerieren={onGenerieren}
                fehler={fehler}
              />
            )}
          </div>

          {/* Footer Navigation */}
          <div style={{
            padding: "1rem 1.5rem",
            borderTop: `1px solid ${T.borderSoft}`,
            display: "flex", justifyContent: "space-between",
            alignItems: "center", flexShrink: 0,
            background: T.offWhite,
          }}>
            <button onClick={zurueck} disabled={step === 1}
              style={{
                padding: "9px 20px", borderRadius: 8, cursor: step === 1 ? "default" : "pointer",
                border: `1.5px solid ${T.border}`, background: "#fff",
                fontFamily: PLEX, fontSize: "0.875rem", color: step === 1 ? T.textFaint : T.text,
                fontWeight: 500, opacity: step === 1 ? 0.4 : 1,
              }}>
              ← Zurück
            </button>

            {step === 4 && positionen.filter(p => p.checked).length === 0 && (
              <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amber }}>
                ⚠ Bitte mindestens eine Position auswählen
              </div>
            )}

            {step < STEPS.length && (
              <button onClick={weiter} disabled={!kannWeiter()}
                style={{
                  padding: "9px 24px", borderRadius: 8,
                  cursor: kannWeiter() ? "pointer" : "not-allowed",
                  border: "none",
                  background: kannWeiter() ? T.navy : T.border,
                  fontFamily: PLEX, fontSize: "0.875rem",
                  color: kannWeiter() ? "#fff" : T.textMuted,
                  fontWeight: 600, transition: "all 0.15s",
                }}>
                Weiter →
              </button>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(24px) scale(0.98) }
          to   { opacity: 1; transform: translateY(0)    scale(1)    }
        }
        @keyframes spin { to { transform: rotate(360deg) } }
      `}</style>
    </>
  );
}
