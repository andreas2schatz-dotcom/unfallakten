/**
 * KlageWizard.jsx – PRD-24b / PRD-26
 * ─────────────────────────────────────────────────────────────────
 * 10-Step Modal-Wizard für die Klageschrift-Generierung.
 *
 * Step  1: Gericht             – Zuständiges Gericht auswählen + bestätigen
 * Step  2: Rubrum              – Parteien-Übersicht (read-only)
 * Step  3: Aktivlegitimation   – Fahrzeugeigentum + Live-Vorschau
 * Step  4: Unfallhergang       – Schilderung, auto-Ersatz Mandant→Kläger
 * Step  5: Schadenpositionen   – Checkboxen + Personenschaden
 * Step  6: Klageanträge        – Auto-Text + Feststellungsanträge
 * Step  7: Rechtl. Würdigung   – Dynamischer Textbaustein + Einwände
 * Step  8: Verzug & Kosten     – Gerichtl. RVG + editierbare Vorschau
 * Step  9: Außergerichtl. Geb. – RVG außergerichtl. SW + Gebührenantrag
 * Step 10: Zusammenfassung     – Abschließende Prüfung + Generieren
 */

import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";

// ── Konstanten ─────────────────────────────────────────────────────────────────

const STEPS = [
  { nr: 1,  label: "Gericht"   },
  { nr: 2,  label: "Rubrum"    },
  { nr: 3,  label: "Aktiv."    },
  { nr: 4,  label: "Unfall"    },
  { nr: 5,  label: "Schaden"   },
  { nr: 6,  label: "Anträge"   },
  { nr: 7,  label: "Würdigung" },
  { nr: 8,  label: "Verzug"    },
  { nr: 9,  label: "Gebühren"  },
  { nr: 10, label: "Generieren"},
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
    const datumStr = (!datum || datum === "unbekannt") ? null : datum;
    const beweisZusatz = datumStr ? `vom ${datumStr}, ` : "";
    return (
      basis +
      `der vorliegenden Freigabeerklärung der ${finTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: Freigabeerklärung ${beweisZusatz}Anlage K1`
    );
  }
  return (
    basis +
    `der ${bedingTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: ${bedingTyp} in Kopie, Anlage K1`
  );
}

/**
 * Kombinierter Sachverhalt-Text für Step 3:
 * Einleitung + Beklagten-Block + Aktivlegitimation + optional Auslandsunfall.
 * Spiegelt die backend-Logik (klage_service.py §1 Sachverhalt).
 */
function buildSachverhaltText({
  klaeger, vorsteuer, unfalldatum, unfallort,
  beklagte, fahrGegnerName,
  aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer,
  auslandsunfall,
}) {
  const weiblich    = klaeger.startsWith("Die");
  const kl_bez      = weiblich ? "Klägerin" : "Kläger";
  const vst_adj     = vorsteuer
    ? `vorsteuerabzugsberechtigte${weiblich ? "" : "r"}`
    : `nicht vorsteuerabzugsberechtigte${weiblich ? "" : "r"}`;

  // ── Satz 1: Kläger + Unfall ──────────────────────────────────────────
  let text = `${klaeger} macht als ${vst_adj} ${kl_bez} Schadensersatzansprüche `;
  if (unfalldatum && unfallort) text += `am ${unfalldatum} in ${unfallort} `;
  else if (unfalldatum)         text += `am ${unfalldatum} `;
  else if (unfallort)           text += `in ${unfallort} `;
  text += "geltend.";

  // ── Beklagten-Block ───────────────────────────────────────────────────
  const gegner = (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked);

  const versicherungen = gegner.filter(b => b.versicherung || (b.firma && !b.ist_halter));
  const halter         = gegner.filter(b => b.ist_halter);
  const hatFahrer      = !!(fahrGegnerName && fahrGegnerName.trim());

  const gesamtAnzahl = versicherungen.length + (hatFahrer ? 1 : 0) + halter.length;
  const mehrere      = gesamtAnzahl > 1;
  let nr = 1;
  const bekSaetze = [];

  for (const v of versicherungen) {
    const nrStr = mehrere ? ` zu ${nr})` : "";
    const kz    = v.kfz_kennzeichen || "";
    let satz = `Die Beklagte${nrStr} ist die gegnerische Haftpflichtversicherung des unfallverursachenden Fahrzeugs`;
    if (kz) satz += ` mit dem amtlichen Kennzeichen ${kz}`;
    satz += ".";
    bekSaetze.push(satz);
    nr++;
  }

  if (hatFahrer) {
    const nrStr = mehrere ? ` zu ${nr})` : "";
    bekSaetze.push(`Der Beklagte${nrStr} war zum Unfallzeitpunkt der Fahrer des unfallverursachenden Fahrzeugs.`);
    nr++;
  }

  for (const h of halter) {
    const nrStr     = mehrere ? ` zu ${nr})` : "";
    const weiblichH = (h.anrede || "").toLowerCase() === "frau";
    const art       = weiblichH ? "Die" : "Der";
    const bez       = weiblichH ? "Halterin" : "Halter";
    bekSaetze.push(`${art} Beklagte${nrStr} ist die ${bez} des unfallverursachenden Fahrzeugs.`);
    nr++;
  }

  if (bekSaetze.length > 0) {
    text += "\n\n" + bekSaetze.join("\n");
  }

  // ── Aktivlegitimation ─────────────────────────────────────────────────
  const aktLegText = buildVorschauText(aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer, klaeger);
  if (aktLegText) {
    text += "\n\n" + aktLegText;
  }

  // ── Auslandsunfall ────────────────────────────────────────────────────
  if (auslandsunfall) {
    text += "\n\nWir machen auf die Entscheidung des EuGH vom 13.12.2007 – Az. C 463/06 –\nund die Vorlage des BGH im Verfahren vom 26.9.2006 zu VI ZR 200/05 aufmerksam. Der EuGH hat in der Entscheidung festgestellt, dass dem Geschädigten auch der Rechtsweg am Gericht seines Wohnortes eröffnet ist.";
  }

  return text;
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

function Fortschrittsbalken({ step, maxStep, onStepChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "1.5rem" }}>
      {STEPS.map((s, i) => {
        const aktiv     = s.nr === step;
        const erledigt  = s.nr < step;
        const klickbar  = s.nr <= maxStep && s.nr !== step;
        return (
          <React.Fragment key={s.nr}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div
                onClick={klickbar ? () => onStepChange(s.nr) : undefined}
                style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: erledigt ? T.navy : aktiv ? T.gold : T.surface,
                  border: `2px solid ${erledigt ? T.navy : aktiv ? T.gold : T.border}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: MONO, fontSize: "0.8rem", fontWeight: 700,
                  color: (erledigt || aktiv) ? "#fff" : T.textMuted,
                  transition: "all 0.25s",
                  boxShadow: aktiv ? `0 0 0 4px ${T.gold}28` : "none",
                  flexShrink: 0,
                  cursor: klickbar ? "pointer" : "default",
                }}>
                {erledigt ? "✓" : s.nr}
              </div>
              <div style={{
                fontFamily: PLEX, fontSize: "0.72rem", fontWeight: aktiv ? 700 : 400,
                color: aktiv ? T.gold : erledigt ? T.navy : T.textMuted,
                marginTop: 5, textAlign: "center", whiteSpace: "nowrap",
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

// ── Step 2: Rubrum ─────────────────────────────────────────────────────────────

function StepRubrum({ beklagte, onClose }) {
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
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span>ℹ Parteien-Überblick</span>
        <button
          onClick={() => {
            if (onClose) onClose();
            setTimeout(() => document.getElementById("karte-parteien")?.scrollIntoView({ behavior: "smooth" }), 150);
          }}
          style={{
            background: T.navy, color: "white", border: "none",
            borderRadius: 6, padding: "5px 14px", fontFamily: PLEX,
            fontSize: "0.8rem", cursor: "pointer", fontWeight: 600,
          }}
        >
          Parteien bearbeiten →
        </button>
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
                  ⚠ Vertreter fehlt –{" "}
                  <button
                    onClick={() => {
                      if (onClose) onClose();
                      setTimeout(() => document.getElementById("karte-parteien")?.scrollIntoView({ behavior: "smooth" }), 150);
                    }}
                    style={{ background: "none", border: "none", padding: 0, cursor: "pointer",
                      color: T.amber, fontFamily: PLEX, fontSize: "0.78rem",
                      textDecoration: "underline", fontWeight: 600 }}>
                    jetzt nachtragen →
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Step 3: Aktivlegitimation / Sachverhalt ────────────────────────────────────

function StepAktLeg({
  aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
  aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
  klaeger,
  // Neu: kombinierter Sachverhalt
  vorsteuer, unfalldatum, unfallort, beklagte, fahrGegnerName,
  auslandsunfall, onAuslandsunfall,
  sachverhaltText, onSachverhaltText,
}) {
  const brauchtFreigabe = aktLegTyp !== "eigentum";

  const prevAutoRef = useRef(null);

  useEffect(() => {
    const newAuto = buildSachverhaltText({
      klaeger, vorsteuer, unfalldatum, unfallort,
      beklagte, fahrGegnerName,
      aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer,
      auslandsunfall,
    });
    // nur überschreiben wenn Text noch nicht manuell bearbeitet wurde
    if (prevAutoRef.current === null || sachverhaltText === prevAutoRef.current) {
      if (onSachverhaltText) onSachverhaltText(newAuto);
    }
    prevAutoRef.current = newAuto;
  }, [aktLegTyp, aktLegFreigabe, aktLegDatum, mandantIstFahrer, auslandsunfall]); // eslint-disable-line

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 260px" }}>
        <AbschnittLabel text="Fahrzeugeigentum" />
        <RadioOption checked={aktLegTyp === "eigentum"}   onChange={() => onAktLegTyp("eigentum")}
          label="Eigentum des Klägers"
          sub={<span>Standardfall – § 1006 BGB wenn selbst gefahren{" "}
            <span title="§ 1006 BGB: Der Besitzer einer beweglichen Sache wird als deren Eigentümer vermutet. Hat der Mandant das Fahrzeug selbst geführt, stärkt dies die Aktivlegitimation und erleichtert die Darlegungslast erheblich."
              style={{ cursor: "help", color: T.textFaint, fontWeight: 600 }}>ℹ</span>
          </span>} />
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
                {aktLegDatum !== "unbekannt" && (
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
                )}
                <label style={{ display: "flex", alignItems: "center", gap: 6,
                  marginTop: 8, cursor: "pointer",
                  fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted }}>
                  <input type="checkbox"
                    checked={aktLegDatum === "unbekannt"}
                    onChange={e => onAktLegDatum(e.target.checked ? "unbekannt" : "")}
                    style={{ accentColor: T.navy, cursor: "pointer" }} />
                  Datum noch unbekannt
                </label>
              </div>
            )}
          </div>
        )}

        <div style={{ marginTop: "1.5rem" }}>
          <AbschnittLabel text="Besonderheiten" />
          <label style={{ display: "flex", alignItems: "center", gap: 8,
            fontFamily: PLEX, fontSize: "0.875rem", cursor: "pointer" }}>
            <input type="checkbox" checked={auslandsunfall} onChange={e => onAuslandsunfall(e.target.checked)}
              style={{ accentColor: T.navy, cursor: "pointer" }} />
            Auslandsunfall (Zuständigkeitstext einfügen)
          </label>
        </div>
      </div>

      <DokumentCard
        warnung={brauchtFreigabe && aktLegFreigabe === "ungeklaert"}
        editText={sachverhaltText}
        onEditText={onSachverhaltText}
      />
    </div>
  );
}

// ── Step 3: Unfallhergang ──────────────────────────────────────────────────────

function _buildUnfallAutoText(original, weiblich) {
  if (!original) return "";
  let t = original;
  t = t.replace(/\bder Mandantin\b/gi, "der Klägerin");
  t = t.replace(/\bdes Mandanten\b/gi, weiblich ? "der Klägerin" : "des Klägers");
  t = t.replace(/\bdem Mandanten\b/gi, weiblich ? "der Klägerin" : "dem Kläger");
  t = t.replace(/\bdie Mandantin\b/gi, "die Klägerin");
  t = t.replace(/\bden Mandanten\b/gi, weiblich ? "die Klägerin" : "den Kläger");
  t = t.replace(/\bMandantin\b/g, "Klägerin");
  t = t.replace(/\bMandant\b/g, weiblich ? "Klägerin" : "Kläger");
  return t;
}

function StepUnfall({ schilderungOriginal, klaeger, unfalltextEdit, onUnfalltextEdit }) {
  const weiblich = klaeger.startsWith("Die");
  const kl      = weiblich ? "Klägerin" : "Kläger";
  const klGen   = weiblich ? "der Klägerin" : "des Klägers";
  const klDat   = weiblich ? "der Klägerin" : "dem Kläger";
  const klAkk   = weiblich ? "die Klägerin" : "den Kläger";

  const ersetzungen = [
    [`Mandant${weiblich ? "in" : ""}`,  kl],
    ["des Mandanten",                   klGen],
    ["dem Mandanten",                   klDat],
    ["den Mandanten",                   klAkk],
    ["die Mandantin",                   "die Klägerin"],
    ["der Mandantin",                   "der Klägerin"],
    ...(!weiblich ? [["Mandantin", "Klägerin"]] : []),
  ];

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
          <div style={{ color: T.textMuted, lineHeight: 1.6 }}>
            {ersetzungen.map(([von, zu], i) => (
              <div key={i}>{von} → {zu}</div>
            ))}
          </div>
        </div>
        {schilderungOriginal && (
          <button
            onClick={() => onUnfalltextEdit(_buildUnfallAutoText(schilderungOriginal, weiblich))}
            style={{
              padding: "9px 12px", borderRadius: 8, cursor: "pointer",
              border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
              fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy,
            }}
          >
            ↺ Text zurücksetzen
          </button>
        )}
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

  // Regulierungsstand pro position_key aggregieren (über alle Abrechnungen)
  const regMap = {};
  (abrechnungen || []).forEach(ab => {
    (ab.positionen || []).forEach(rp => {
      const k = rp.position_key;
      if (k) regMap[k] = (regMap[k] || 0) + (parseFloat(rp.betrag_reguliert) || 0);
    });
  });

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
        {positionen.map(p => {
          const reg   = regMap[p.key] || 0;
          const offen = (p.betrag || 0) - reg;
          const vollReg = reg > 0 && offen <= 0.005;
          return (
            <label key={p.key} style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              padding: "8px 10px", borderRadius: 7, cursor: "pointer",
              border: `1px solid ${p.checked ? T.navy : T.borderSoft}`,
              background: p.checked ? `${T.navy}06` : T.white,
              marginBottom: 4, transition: "all 0.12s",
            }}>
              <input type="checkbox" checked={p.checked}
                onChange={() => onTogglePos(p.key)}
                style={{ accentColor: T.navy, cursor: "pointer", width: 16, height: 16, marginTop: 2 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: PLEX, fontSize: "0.875rem",
                  color: p.checked ? T.navy : T.text, fontWeight: p.checked ? 600 : 400 }}>
                  {p.label}
                </div>
                {vollReg && (
                  <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.green, marginTop: 1 }}>
                    vollständig reguliert
                  </div>
                )}
                {!vollReg && reg > 0 && (
                  <div style={{ fontFamily: MONO, fontSize: "0.72rem", color: T.textMuted, marginTop: 1 }}>
                    reguliert {fmtEur(reg)} · offen {fmtEur(offen)}
                  </div>
                )}
              </div>
              <span style={{ fontFamily: MONO, fontSize: "0.875rem",
                color: p.checked ? T.navy : T.textMuted, fontWeight: p.checked ? 700 : 400 }}>
                {fmtEur(p.betrag)}
              </span>
            </label>
          );
        })}
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

const EINLEITUNGS_VARIANTEN = [
  (z, eur) => `Die Beklagte${z} hat hier einen Abzug in Höhe von ${eur} vorgenommen.`,
  (z, eur) => `Die Beklagte${z} zog von dieser Position ${eur} ab.`,
  (z, eur) => `Auch hier behielt die Beklagte${z} ${eur} zu Unrecht ein.`,
  (z, eur) => `Weiterhin kürzte die Beklagte${z} diese Position um ${eur}.`,
  (_z, eur) => `Zusätzlich wurden hier ${eur} zu wenig gezahlt.`,
];
const EINLEITUNG_LETZT = (z, eur) =>
  `Schließlich kürzt die Beklagte${z} auch hier noch einen Betrag in Höhe von ${eur}.`;

function EinwandePanel({ abrechnungen, kuerzungsarten, beklagte, onUebernehmen, onClose }) {
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

    // "(zu 1)" nur wenn mehrere Beklagte in der Klageschrift
    const beklagteGef = (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked);
    const zuSuffix = beklagteGef.length > 1 ? " (zu 1)" : "";

    // Kürzungsbetrag je kuerzungsart_id aus Abrechnungspositionen
    const kuerzungMap = {};
    (abrechnungen || []).forEach(ab =>
      (ab.positionen || []).forEach(p => {
        if (p.kuerzungsart_id != null) {
          const abzug = (parseFloat(p.betrag_gefordert) || 0) - (parseFloat(p.betrag_reguliert) || 0);
          kuerzungMap[p.kuerzungsart_id] = (kuerzungMap[p.kuerzungsart_id] || 0) + abzug;
        }
      })
    );

    const alphabet = "abcdefghijklmnopqrstuvwxyz";
    const bloecke = selected.map((ka, i) => {
      const letter   = alphabet[i] || String(i + 1);
      const abzug    = kuerzungMap[ka.id] || 0;
      const eur      = fmtEur(abzug);
      const istLetzt = selected.length > 1 && i === selected.length - 1;
      const betragsatz = abzug > 0
        ? (istLetzt ? EINLEITUNG_LETZT(zuSuffix, eur) : EINLEITUNGS_VARIANTEN[i % 5](zuSuffix, eur))
        : "";
      return [
        `**${letter}) ${ka.bezeichnung}**`,
        betragsatz,
        (ka.standard_gegenargument || "").trim(),
      ].filter(Boolean).join("\n");
    });

    const gesamtKuerzung = selected.reduce((s, ka) => s + (kuerzungMap[ka.id] || 0), 0);
    const schlusssatz = gesamtKuerzung > 0
      ? `Insgesamt hat die Beklagte${zuSuffix} daher einen Betrag in Höhe von ${fmtEur(gesamtKuerzung)} zu Unrecht einbehalten.`
      : "";

    const lines = [
      "Die Beklagte hat folgende Positionen zu Unrecht nicht oder nicht vollständig reguliert:",
      "",
      ...bloecke,
      ...(schlusssatz ? ["", schlusssatz] : []),
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

function StepRw({ hq, onHq, hb, onHb, abrechnungen, weiblich,
                  rwText, onRwText, kuerzungsarten, beklagte,
                  onKiHaftung, kiLaedt }) {
  const gesamtReg = (abrechnungen || []).reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0);
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
        beklagte={beklagte}
        onUebernehmen={einwandeUebernehmen}
        onClose={() => setEinwandeOffen(false)}
      />
    )}
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 240px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Eingaben" />

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 6 }}>
            Haftungsquote (Gegner)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <input type="number" value={hq}
              onChange={e => onHq(Math.min(100, Math.max(0, parseFloat(e.target.value) || 0)))}
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
            {hq === 100 && (
              <span style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.green }}>
                Vollhaftung
              </span>
            )}
          </div>
          <input type="range" min="0" max="100" step="5" value={hq}
            onChange={e => onHq(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: hq < 100 ? T.amber : T.navy, cursor: "pointer" }} />
          <div style={{ display: "flex", justifyContent: "space-between",
            fontFamily: MONO, fontSize: "0.68rem", color: T.textFaint, marginTop: 2 }}>
            <span>0 %</span><span>50 %</span><span>100 %</span>
          </div>
        </div>

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Haftungsbegründung
          </div>
          <textarea value={hb} onChange={e => onHb(e.target.value)}
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

        <button onClick={onKiHaftung} disabled={kiLaedt || !onKiHaftung}
          style={{
            padding: "9px 12px", borderRadius: 8,
            cursor: kiLaedt ? "wait" : "pointer",
            border: `1.5px solid ${T.gold}`, background: `${T.gold}12`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: "#7a4f00",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            opacity: kiLaedt ? 0.7 : 1,
          }}>
          {kiLaedt ? (
            <>
              <div style={{
                width: 13, height: 13,
                border: "2px solid #7a4f0050",
                borderTopColor: "#7a4f00",
                borderRadius: "50%",
                animation: "spin 0.7s linear infinite",
              }} />
              KI analysiert …
            </>
          ) : "✦ KI-Vorschlag generieren"}
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

function buildVerzugAutoText(datum) {
  return datum
    ? `Verzug ist spätestens am ${datum} eingetreten.`
    : `Verzug ist mit Rechtshängigkeit eingetreten.`;
}

function StepVerzug({ zinsenAb, rvgData, rvgOverride, weiblich,
                      wizardVerzugDatum, onWizardVerzugDatum,
                      wizardVerzugText, onWizardVerzugText }) {
  const rvgGesamt  = rvgOverride ? parseFloat(rvgOverride) : (rvgData?.gesamt || 0);
  const prevAutoRef = useRef(wizardVerzugText);

  function handleDatumChange(val) {
    onWizardVerzugDatum(val);
    // Text nur neu generieren wenn er noch dem Auto-Text entspricht (kein manueller Edit)
    if (wizardVerzugText === prevAutoRef.current) {
      const neu = buildVerzugAutoText(val);
      prevAutoRef.current = neu;
      onWizardVerzugText(neu);
    }
  }

  function handleReset() {
    const neu = buildVerzugAutoText(wizardVerzugDatum);
    prevAutoRef.current = neu;
    onWizardVerzugText(neu);
  }

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 240px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Verzugsdatum" />

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Datum (leer = Rechtshängigkeit)
          </div>
          <input
            type="text"
            value={wizardVerzugDatum}
            onChange={e => handleDatumChange(e.target.value)}
            placeholder="TT.MM.JJJJ"
            style={{
              width: "100%", padding: "7px 10px", borderRadius: 7,
              border: `1.5px solid ${wizardVerzugDatum ? T.navy : T.amber}`,
              fontFamily: MONO, fontSize: "0.875rem",
              color: wizardVerzugDatum ? T.navy : T.textMuted,
              background: T.white, boxSizing: "border-box",
            }}
          />
          {!wizardVerzugDatum && (
            <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.amber, marginTop: 3 }}>
              Fallback: Rechtshängigkeit
            </div>
          )}
        </div>

        <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "0.75rem" }}>
          <AbschnittLabel text="Zinsen ab" />
          <div style={{
            fontFamily: MONO, fontSize: "0.875rem", fontWeight: 600,
            color: T.navy, marginTop: 2,
          }}>
            {zinsenAb === "verzug" ? "Verzugseintritt" : "Rechtshängigkeit"}
          </div>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: 4 }}>
            Einstellung aus Klage-Tab
          </div>
        </div>

        <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "0.75rem" }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, lineHeight: 1.7 }}>
            <div>RVG: <span style={{ fontFamily: MONO, color: T.navy }}>{fmtEur(rvgGesamt)}</span></div>
            <div style={{ marginTop: 4 }}>Schlussformel: automatisch.</div>
          </div>
        </div>

        <button
          onClick={handleReset}
          style={{
            padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy,
            marginTop: "auto",
          }}
        >
          ↺ Text zurücksetzen
        </button>
      </div>

      <DokumentCard editText={wizardVerzugText} onEditText={onWizardVerzugText} />
    </div>
  );
}

// ── Step 10: Zusammenfassung + Generieren ──────────────────────────────────────

function StepZusammenfassung({ gericht, beklagte, positionen, mitSG, sgMind,
                               rvgData, rvgOverride,
                               rvgAussergData, rvgAussergOv,
                               aktLegTyp, aktLegFreigabe,
                               zinsenAb, wizardVerzugDatum,
                               laedt, onGenerieren, fehler }) {
  const klagebetrag  = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);
  const rvgGesamt    = rvgOverride    ? parseFloat(rvgOverride)    : (rvgData?.gesamt        || 0);
  const rvgAussGes   = rvgAussergOv   ? parseFloat(rvgAussergOv)   : (rvgAussergData?.gesamt || 0);
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
          wert={wizardVerzugDatum ? `Verzugseintritt ${wizardVerzugDatum}` : "Rechtshängigkeit"} />
        <ZeileZusammenfassung icon="🏠" label="Aktivlegitimation"
          wert={aktLegFreigabe === "ungeklaert"
            ? `${aktLegLabel} – ⚠ ungeklärt`
            : `${aktLegLabel}${aktLegTyp !== "eigentum" ? ` · ${freigabeLabel}` : ""}`}
          warn={aktLegFreigabe === "ungeklaert"} />
        <ZeileZusammenfassung icon="💶" label="RVG gerichtlich" wert={fmtEur(rvgGesamt)} />
        <ZeileZusammenfassung icon="💶" label="RVG außergerichtlich"
          wert={rvgAussGes > 0 ? fmtEur(rvgAussGes) : "–"} warn={rvgAussGes === 0} />
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

// ── Step 1: Gericht ────────────────────────────────────────────────────────────

function StepGericht({ gericht, setGericht, gerichtSuche, setGSuche,
                       gerichtTreffer, setGTreffer, gerichtLaedt,
                       sucheGerichte, bestaetigt, setBestaetigt, onWeiter }) {
  return (
    <div style={{ maxWidth: 520 }}>
      <AbschnittLabel text="Zuständiges Gericht" />

      {gericht ? (
        <div style={{
          background: bestaetigt ? `${T.green}10` : `${T.amber}10`,
          border: `1.5px solid ${bestaetigt ? T.green : T.amber}`,
          borderRadius: 10, padding: "0.9rem 1.1rem", marginBottom: "1rem",
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div>
              <div style={{ fontFamily: PLEX, fontSize: "1rem", fontWeight: 700, color: T.navy }}>
                {gericht.name}
              </div>
              <div style={{ fontFamily: MONO, fontSize: "0.835rem", color: T.textMuted, marginTop: 2 }}>
                {[gericht.strasse, gericht.plz, gericht.ort].filter(Boolean).join(", ")}
              </div>
              {gericht.quelle && (
                <div style={{ fontFamily: PLEX, fontSize: "0.78rem", marginTop: 4,
                  color: bestaetigt ? T.green : T.amber }}>
                  {bestaetigt
                    ? "✓ Bestätigt"
                    : gericht.quelle === "akte"
                      ? "✓ In Akte gespeichert – bitte bestätigen"
                      : "⚡ Vorschlag nach Unfallort – bitte prüfen und bestätigen"}
                </div>
              )}
            </div>
            <button onClick={() => { setGericht(null); setGTreffer([]); setGSuche(""); setBestaetigt(false); }}
              style={{ background: "none", border: `1px solid ${T.border}`, borderRadius: 6,
                padding: "3px 10px", cursor: "pointer", color: T.textMuted,
                fontFamily: PLEX, fontSize: "0.825rem", flexShrink: 0 }}>
              ✕ Ändern
            </button>
          </div>
          {!bestaetigt && (
            <button onClick={onWeiter}
              style={{
                marginTop: "0.75rem", width: "100%",
                padding: "9px 0", borderRadius: 7, cursor: "pointer",
                border: "none", background: T.navy,
                fontFamily: PLEX, fontSize: "0.9rem", fontWeight: 700, color: "#fff",
              }}>
              ✓ Gericht bestätigen → weiter
            </button>
          )}
        </div>
      ) : (
        <div style={{ color: T.amber, fontFamily: PLEX, fontSize: "0.875rem", marginBottom: "0.75rem" }}>
          ⚠ Kein Gericht ausgewählt – bitte suchen.
        </div>
      )}

      {!gericht && (
        <div>
          <div style={{ display: "flex", gap: 8, alignItems: "center",
            background: T.white, border: `1px solid ${T.border}`, borderRadius: 8,
            padding: "6px 12px", marginBottom: "0.5rem" }}>
            <span style={{ color: T.textFaint }}>🔍</span>
            <input value={gerichtSuche} onChange={e => sucheGerichte(e.target.value)}
              placeholder="Gericht suchen (z.B. Frankfurt, Offenbach) …"
              autoFocus
              style={{ flex: 1, border: "none", outline: "none", background: "transparent",
                fontFamily: PLEX, fontSize: "0.935rem" }} />
            {gerichtLaedt && (
              <div style={{ width: 14, height: 14, border: `2px solid ${T.border}`,
                borderTopColor: T.navy, borderRadius: "50%",
                animation: "spin 0.7s linear infinite" }} />
            )}
          </div>
          {gerichtTreffer.length > 0 && (
            <div style={{ border: `1px solid ${T.border}`, borderRadius: 8,
              overflow: "hidden", maxHeight: 260, overflowY: "auto" }}>
              {gerichtTreffer.map((g, i) => (
                <div key={g.adressnr}
                  onClick={() => { setGericht(g); setGTreffer([]); setGSuche(""); setBestaetigt(false); }}
                  style={{ padding: "9px 14px", cursor: "pointer",
                    borderBottom: i < gerichtTreffer.length - 1 ? `1px solid ${T.borderSoft}` : "none",
                    background: T.white, transition: "background 0.1s" }}
                  onMouseEnter={e => e.currentTarget.style.background = T.surface}
                  onMouseLeave={e => e.currentTarget.style.background = T.white}>
                  <div style={{ fontFamily: PLEX, fontSize: "0.925rem", fontWeight: 600, color: T.navy }}>
                    {g.name}
                  </div>
                  <div style={{ fontFamily: MONO, fontSize: "0.825rem", color: T.textMuted }}>
                    {[g.strasse, g.plz, g.ort].filter(Boolean).join(", ")}
                  </div>
                </div>
              ))}
            </div>
          )}
          {gerichtSuche.length >= 2 && !gerichtLaedt && gerichtTreffer.length === 0 && (
            <div style={{ fontFamily: PLEX, fontSize: "0.875rem", color: T.textFaint, padding: "6px 0" }}>
              Keine Gerichte gefunden.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Step 6: Klageanträge ───────────────────────────────────────────────────────

const ALPHABET = "abcdefghijklmnopqrstuvwxyz";
const ANTRAEGE_PLACEHOLDER = "[Außergerichtliche Anwaltsgebühren – wird in Schritt 9 ergänzt]";

function baueAntraegeText(opts) {
  const { positionen, mitSG, sgMind, beklagte, weiblich, zinsenAb, verzug,
          unfalldatum, mitFestSg, mitFestSach } = opts;

  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);
  const beklagteGef = (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked);
  const nrSuffix    = beklagteGef.length > 1 ? " (zu 1)" : "";
  const kl_akk      = weiblich ? "die Klägerin"  : "den Kläger";  // Akkusativ: zahlen an…
  const kl_dat      = weiblich ? "der Klägerin"  : "dem Kläger";  // Dativ: verpflichtet…zu ersetzen
  const zinsDat     = zinsenAb === "verzug" && verzug ? `seit dem ${verzug}` : "seit Rechtshängigkeit";
  const udStr       = unfalldatum || "TT.MM.JJJJ";
  const fNr         = (n) => n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

  const antraege = [];

  // 1. Hauptantrag
  antraege.push(
    `Die Beklagte${nrSuffix} wird verurteilt, an ${kl_akk} ${fNr(klagebetrag)} ` +
    `nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz ` +
    `${zinsDat} zu zahlen.`
  );

  // 2. Schmerzensgeld
  if (mitSG) {
    if (sgMind > 0) {
      antraege.push(
        `Die Beklagte${nrSuffix} wird verurteilt, an ${kl_akk} ein angemessenes, ` +
        `vom Gericht festzulegendes Schmerzensgeld zu zahlen, wobei die Höhe nicht ` +
        `weniger als ${fNr(sgMind)} betragen sollte, nebst Zinsen von 5 Prozentpunkten ` +
        `über dem Basiszinssatz ${zinsDat}.`
      );
    } else {
      antraege.push(
        `Die Beklagte${nrSuffix} wird verurteilt, an ${kl_akk} ein angemessenes, ` +
        `vom Gericht nach billigem Ermessen festzulegendes Schmerzensgeld zu zahlen, ` +
        `nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz ${zinsDat}.`
      );
    }
  }

  // 3. Feststellungsantrag Personenschaden
  if (mitSG && mitFestSg) {
    antraege.push(
      `Es wird festgestellt, dass die Beklagte${nrSuffix} verpflichtet ist, ` +
      `${kl_dat} sämtliche künftigen materiellen und immateriellen Schäden zu ersetzen, ` +
      `die aus dem Unfallereignis vom ${udStr} noch entstehen werden, soweit Ansprüche ` +
      `nicht auf Sozialversicherungsträger oder sonstige Dritte übergegangen sind oder ` +
      `noch übergehen werden.`
    );
  }

  // 4. Feststellungsantrag Sachschaden
  if (mitFestSach) {
    antraege.push(
      `Es wird festgestellt, dass die Beklagte${nrSuffix} verpflichtet ist, ` +
      `${kl_dat} sämtliche weiteren materiellen Schäden zu ersetzen, die aus dem ` +
      `Unfallereignis vom ${udStr} noch entstehen werden.`
    );
  }

  // Platzhalter für RVG-Antrag (Step 9)
  antraege.push(ANTRAEGE_PLACEHOLDER);

  // Kostentragung
  antraege.push(`Die Beklagte${nrSuffix} trägt die Kosten des Rechtsstreits.`);

  return antraege.map((t, i) => `${i + 1}.\t${t}`).join("\n\n");
}

function StepAntraege({ positionen, mitSG, sgMind, beklagte, weiblich,
                        zinsenAb, verzug, unfalldatum,
                        mitFestSg, onMitFestSg, mitFestSach, onMitFestSach,
                        antraegeText, onAntraegeText }) {
  const klagebetrag   = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);
  const sgGesamt      = mitSG && sgMind > 0 ? klagebetrag + sgMind : klagebetrag;
  const zinsDat       = zinsenAb === "verzug" && verzug ? `seit dem ${verzug}` : "seit Rechtshängigkeit";
  const hatPlatzhalter = antraegeText?.includes(ANTRAEGE_PLACEHOLDER);

  function regenerieren() {
    onAntraegeText(baueAntraegeText({
      positionen, mitSG, sgMind, beklagte, weiblich,
      zinsenAb, verzug, unfalldatum, mitFestSg, mitFestSach,
    }));
  }

  // Initial generieren wenn noch leer
  useEffect(() => {
    if (!antraegeText) regenerieren();
  }, []); // eslint-disable-line

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 250px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Antragsauswahl" />

        <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem",
          border: `1px solid ${T.borderSoft}` }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
            marginBottom: "0.5rem" }}>Gerichtlicher Streitwert</div>
          <div style={{ fontFamily: MONO, fontSize: "1.1rem", fontWeight: 700, color: T.navy }}>
            {fmtEur(sgGesamt)}
          </div>
          {mitSG && sgMind > 0 && (
            <div style={{ fontFamily: PLEX, fontSize: "0.75rem", color: T.textMuted, marginTop: 2 }}>
              Sachschaden {fmtEur(klagebetrag)} + SG {fmtEur(sgMind)}
            </div>
          )}
          <div style={{ fontFamily: PLEX, fontSize: "0.75rem", color: T.textMuted, marginTop: 4 }}>
            Zinsen {zinsDat}
          </div>
        </div>

        {[
          { label: "Hauptantrag Sachschaden",    aktiv: true,    fest: true },
          { label: "Schmerzensgeld-Antrag",       aktiv: mitSG,   fest: true,  hidden: !mitSG },
          { label: "Feststellungsantrag Personenschaden", aktiv: mitSG && mitFestSg, fest: false,
            hidden: !mitSG, onChange: () => onMitFestSg(!mitFestSg) },
          { label: "Feststellungsantrag Sachschaden",     aktiv: mitFestSach, fest: false,
            onChange: () => onMitFestSach(!mitFestSach) },
          { label: "Kostentragung",              aktiv: true,    fest: true },
        ].filter(x => !x.hidden).map((x, i) => (
          <label key={i} style={{ display: "flex", alignItems: "center", gap: 10,
            cursor: x.fest ? "default" : "pointer",
            opacity: x.fest ? 0.7 : 1 }}>
            <input type="checkbox" checked={x.aktiv}
              onChange={x.onChange || (() => {})}
              disabled={x.fest}
              style={{ accentColor: T.navy, cursor: x.fest ? "default" : "pointer",
                width: 15, height: 15 }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem",
              color: x.aktiv ? T.navy : T.textMuted, fontWeight: x.aktiv ? 600 : 400 }}>
              {x.label}
            </span>
          </label>
        ))}

        <button onClick={regenerieren}
          style={{ padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy, marginTop: "auto" }}>
          ↻ Anträge neu generieren
        </button>

        {hatPlatzhalter ? (
          <div style={{ background: `${T.amber}12`, border: `1px solid ${T.amber}50`,
            borderRadius: 7, padding: "0.5rem 0.75rem",
            fontFamily: PLEX, fontSize: "0.76rem", color: "#92400e" }}>
            ⏳ RVG-Antrag: Platzhalter aktiv – wird in Schritt 9 ersetzt.
          </div>
        ) : (
          <div style={{ background: `${T.green}10`, border: `1px solid ${T.green}40`,
            borderRadius: 7, padding: "0.5rem 0.75rem",
            fontFamily: PLEX, fontSize: "0.76rem", color: T.green }}>
            ✓ RVG-Antrag eingefügt (Schritt 9).
          </div>
        )}
      </div>

      <DokumentCard editText={antraegeText} onEditText={onAntraegeText} />
    </div>
  );
}

// ── Step 9: Außergerichtliche Gebühren ─────────────────────────────────────────

function StepGebuehren({ swAusserg, rvgAussergData, onRvgAussergData,
                         rvgAussergOv, onRvgAussergOv,
                         gebuehrenText, onGebuehrenText,
                         beklagte, weiblich,
                         zinsenAb, verzug,
                         antraegeText, onAntraegeText }) {
  const beklagteGef = (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked);
  const nrSuffix    = beklagteGef.length > 1 ? " (zu 1)" : "";
  const kl_akk      = weiblich ? "die Klägerin" : "den Kläger";  // Akkusativ: zahlen an…
  const zinsDat     = zinsenAb === "verzug" && verzug ? `seit dem ${verzug}` : "seit Rechtshängigkeit";
  const rvgGesamt   = rvgAussergOv ? parseFloat(rvgAussergOv) : (rvgAussergData?.gesamt || 0);

  function baueGebuehrenAntrag(betrag) {
    const b = betrag || rvgGesamt;
    return (
      `Die Beklagte${nrSuffix} wird verurteilt, an ${kl_akk} weitere ` +
      `${b.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} € ` +
      `nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz ` +
      `${zinsDat} zu zahlen.`
    );
  }

  useEffect(() => {
    if (!gebuehrenText && rvgGesamt > 0) {
      onGebuehrenText(baueGebuehrenAntrag(rvgGesamt));
    }
  }, [rvgGesamt]); // eslint-disable-line

  // Platzhalter in antraegeText ersetzen sobald gebuehrenText gesetzt
  useEffect(() => {
    if (!gebuehrenText || !antraegeText) return;
    if (antraegeText.includes(ANTRAEGE_PLACEHOLDER)) {
      onAntraegeText(antraegeText.replace(ANTRAEGE_PLACEHOLDER, gebuehrenText));
    }
  }, [gebuehrenText]); // eslint-disable-line

  const fNr = (v) => (v || 0).toLocaleString("de-DE",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Vorgerichtliche Kosten" />

        <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem",
          border: `1px solid ${T.borderSoft}` }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
            marginBottom: "0.6rem" }}>Gegenstandswert (außergerichtl.)</div>
          <div style={{ fontFamily: MONO, fontSize: "1rem", fontWeight: 700, color: T.navy }}>
            {fNr(swAusserg)}
          </div>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: 3 }}>
            Summe aller Schadenpositionen
          </div>
        </div>

        {rvgAussergData && (
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.text, lineHeight: 1.8,
            background: T.white, border: `1px solid ${T.borderSoft}`, borderRadius: 8,
            padding: "0.6rem 0.85rem" }}>
            {[
              { l: `Geschäftsgebühr §§ 13, 14 Nr. 2300 VV RVG (${rvgAussergData.faktor})`, v: rvgAussergData.gebuehr_netto },
              { l: "Post u. Telekommunikation Nr. 7002 VV RVG", v: rvgAussergData.post_pauschale },
              { l: "Zwischensumme netto", v: rvgAussergData.zwischen_netto, faint: true },
              { l: "19 % Umsatzsteuer", v: rvgAussergData.ust },
              { l: "Gesamtbetrag", v: rvgAussergData.gesamt, bold: true },
            ].map((z, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between",
                fontWeight: z.bold ? 700 : 400, color: z.faint ? T.textFaint : z.bold ? T.navy : T.text,
                borderTop: z.bold ? `1px solid ${T.border}` : "none",
                marginTop: z.bold ? 4 : 0, paddingTop: z.bold ? 4 : 0 }}>
                <span style={{ flex: 1, paddingRight: 8, fontSize: "0.75rem" }}>{z.l}</span>
                <span style={{ fontFamily: MONO, fontSize: "0.8rem", whiteSpace: "nowrap" }}>{fNr(z.v)}</span>
              </div>
            ))}
          </div>
        )}

        {!rvgAussergData && (
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amber }}>
            ⚠ RVG wird beim Öffnen berechnet.
          </div>
        )}

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Betrag überschreiben (optional)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="number" min="0" step="0.01"
              value={rvgAussergOv}
              onChange={e => {
                onRvgAussergOv(e.target.value);
                if (e.target.value) onGebuehrenText(baueGebuehrenAntrag(parseFloat(e.target.value)));
              }}
              placeholder={rvgAussergData ? rvgAussergData.gesamt.toFixed(2) : ""}
              style={{ width: 120, padding: "6px 8px",
                border: `1.5px solid ${T.border}`, borderRadius: 7,
                fontFamily: MONO, fontSize: "0.9rem", outline: "none",
                background: T.white, color: T.navy }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>€</span>
          </div>
        </div>

        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint }}>
          Text erscheint als Klageantrag. Wird automatisch in Schritt 6 eingefügt.
        </div>
      </div>

      <DokumentCard editText={gebuehrenText} onEditText={onGebuehrenText} />
    </div>
  );
}

// ── Hauptkomponente ────────────────────────────────────────────────────────────

export default function KlageWizard({
  step, onStepChange, onClose,
  wizardMaxStep, onMaxStep,
  // Step 1 (Gericht)
  gericht, setGericht, gerichtSuche, setGSuche,
  gerichtTreffer, setGTreffer, gerichtLaedt,
  sucheGerichte, gerichtBestaetigt, setGerichtBestaetigt,
  onGerichtBestaetigen,
  // Step 3 (Aktivlegitimation / Sachverhalt)
  aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
  aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
  sachverhaltText, onSachverhaltText,
  auslandsunfall, onAuslandsunfall,
  fahrGegnerName, mandantVorsteuer,
  unfallort,
  // Step 4 (Unfallhergang)
  schilderungOriginal,
  wizardUnfallText, onWizardUnfallText,
  // Step 5 (Schadenpositionen)
  abrechnungen,
  positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind,
  // Step 6 (Klageanträge)
  unfalldatum,
  wizardMitFestSg, onMitFestSg,
  wizardMitFestSach, onMitFestSach,
  wizardAntraegeText, onAntraegeText,
  // Step 7 (Rechtliche Würdigung)
  wizardHq, onWizardHq, wizardHb, onWizardHb,
  wizardRwText, onWizardRwText, kuerzungsarten,
  onKiHaftung, kiLaedt,
  // Step 8 (Verzug)
  wizardVerzugText, onWizardVerzugText,
  wizardVerzugDatum, onWizardVerzugDatum,
  // Step 9 (Außergerichtl. Gebühren)
  swAusserg,
  wizardRvgAussergData, onRvgAussergData,
  wizardRvgAussergOv, onRvgAussergOv,
  wizardGebuehrenText, onGebuehrenText,
  // Shared
  beklagte, rvgData, rvgOverride, zinsenAb, verzug,
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
    if (step === 1 && !gerichtBestaetigt) return false;
    if (step === 5 && positionen.filter(p => p.checked).length === 0) return false;
    return true;
  };
  const weiter = () => {
    if (!kannWeiter()) return;
    const next = step + 1;
    onStepChange(next);
    if (next > wizardMaxStep) onMaxStep(next);
  };
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
          height: "92vh", overflow: "hidden",
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
              <div style={{ fontFamily: PLEX, fontSize: "1.25rem", fontWeight: 700, color: T.navy }}>
                Klageschrift zusammenstellen
              </div>
              <div style={{ fontFamily: PLEX, fontSize: "0.875rem", color: T.textMuted, marginTop: 3 }}>
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
            <Fortschrittsbalken step={step} maxStep={wizardMaxStep} onStepChange={onStepChange} />

            {step === 1 && (
              <StepGericht
                gericht={gericht}             setGericht={setGericht}
                gerichtSuche={gerichtSuche}   setGSuche={setGSuche}
                gerichtTreffer={gerichtTreffer} setGTreffer={setGTreffer}
                gerichtLaedt={gerichtLaedt}   sucheGerichte={sucheGerichte}
                bestaetigt={gerichtBestaetigt} setBestaetigt={setGerichtBestaetigt}
                onWeiter={onGerichtBestaetigen}
              />
            )}

            {step === 2 && (
              <StepRubrum beklagte={beklagte} onClose={onClose} />
            )}

            {step === 3 && (
              <StepAktLeg
                aktLegTyp={aktLegTyp}         onAktLegTyp={onAktLegTyp}
                aktLegFreigabe={aktLegFreigabe} onAktLegFreigabe={onAktLegFreigabe}
                aktLegDatum={aktLegDatum}       onAktLegDatum={onAktLegDatum}
                mandantIstFahrer={mandantIstFahrer}
                mandantKz={mandantKz}
                klaeger={klaeger}
                sachverhaltText={sachverhaltText}
                onSachverhaltText={onSachverhaltText}
                vorsteuer={mandantVorsteuer}
                unfalldatum={unfalldatum}
                unfallort={unfallort}
                beklagte={beklagte}
                fahrGegnerName={fahrGegnerName}
                auslandsunfall={auslandsunfall}
                onAuslandsunfall={onAuslandsunfall}
              />
            )}

            {step === 4 && (
              <StepUnfall
                schilderungOriginal={schilderungOriginal}
                klaeger={klaeger}
                unfalltextEdit={wizardUnfallText}
                onUnfalltextEdit={onWizardUnfallText}
              />
            )}

            {step === 5 && (
              <StepSchaden
                abrechnungen={abrechnungen}
                positionen={positionen}   onTogglePos={onTogglePos}
                mitSG={mitSG}             onMitSG={onMitSG}
                sgMind={sgMind}           onSGMind={onSGMind}
              />
            )}

            {step === 6 && (
              <StepAntraege
                positionen={positionen}   mitSG={mitSG}   sgMind={sgMind}
                beklagte={beklagte}       weiblich={weiblich}
                zinsenAb={zinsenAb}       verzug={verzug}
                unfalldatum={unfalldatum}
                mitFestSg={wizardMitFestSg}   onMitFestSg={onMitFestSg}
                mitFestSach={wizardMitFestSach} onMitFestSach={onMitFestSach}
                antraegeText={wizardAntraegeText} onAntraegeText={onAntraegeText}
              />
            )}

            {step === 7 && (
              <StepRw
                hq={wizardHq}             onHq={onWizardHq}
                hb={wizardHb}             onHb={onWizardHb}
                abrechnungen={abrechnungen}
                weiblich={weiblich}
                rwText={wizardRwText}     onRwText={onWizardRwText}
                kuerzungsarten={kuerzungsarten}
                beklagte={beklagte}
                onKiHaftung={onKiHaftung} kiLaedt={kiLaedt}
              />
            )}

            {step === 8 && (
              <StepVerzug
                zinsenAb={zinsenAb}
                rvgData={rvgData}         rvgOverride={rvgOverride}
                weiblich={weiblich}
                wizardVerzugDatum={wizardVerzugDatum}
                onWizardVerzugDatum={onWizardVerzugDatum}
                wizardVerzugText={wizardVerzugText}
                onWizardVerzugText={onWizardVerzugText}
              />
            )}

            {step === 9 && (
              <StepGebuehren
                swAusserg={swAusserg}
                rvgAussergData={wizardRvgAussergData} onRvgAussergData={onRvgAussergData}
                rvgAussergOv={wizardRvgAussergOv}     onRvgAussergOv={onRvgAussergOv}
                gebuehrenText={wizardGebuehrenText}   onGebuehrenText={onGebuehrenText}
                beklagte={beklagte}                   weiblich={weiblich}
                zinsenAb={zinsenAb}                   verzug={verzug}
                antraegeText={wizardAntraegeText}     onAntraegeText={onAntraegeText}
              />
            )}

            {step === 10 && (
              <StepZusammenfassung
                gericht={gericht}           beklagte={beklagte}
                positionen={positionen}     mitSG={mitSG}          sgMind={sgMind}
                rvgData={rvgData}           rvgOverride={rvgOverride}
                rvgAussergData={wizardRvgAussergData} rvgAussergOv={wizardRvgAussergOv}
                aktLegTyp={aktLegTyp}       aktLegFreigabe={aktLegFreigabe}
                zinsenAb={zinsenAb}         wizardVerzugDatum={wizardVerzugDatum}
                laedt={laedt}               onGenerieren={onGenerieren}
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

            {step === 1 && !gerichtBestaetigt && (
              <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amber }}>
                ⚠ Bitte Gericht bestätigen
              </div>
            )}
            {step === 5 && positionen.filter(p => p.checked).length === 0 && (
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
