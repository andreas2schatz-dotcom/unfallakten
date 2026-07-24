/**
 * KlageWizard.jsx – PRD-24b / PRD-26
 * ─────────────────────────────────────────────────────────────────
 * 11-Step Modal-Wizard für die Klageschrift-Generierung.
 *
 * Step  1: Gericht             – Zuständiges Gericht auswählen + bestätigen
 * Step  2: Rubrum              – Parteien-Übersicht (read-only)
 * Step  3: Aktivlegitimation   – Fahrzeugeigentum + Live-Vorschau
 * Step  4: Unfallhergang       – Schilderung, auto-Ersatz Mandant→Kläger
 * Step  5: Schadenpositionen   – Checkboxen + Personenschaden
 * Step  6: Klageanträge        – Auto-Text + Feststellungsanträge
 * Step  7: Rechtl. Würdigung   – Quote + Begründung + Vorschau der Grundhaftung
 * Step  8: Einwände            – Kürzungen der Versicherung + finaler Würdigungstext
 * Step  9: Verzug & Kosten     – Gerichtl. RVG + editierbare Vorschau
 * Step 10: Außergerichtl. Geb. – RVG außergerichtl. SW + Gebührenantrag
 * Step 11: Zusammenfassung     – Abschließende Prüfung + Generieren
 */

import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";
import { fmtEuro, fmtDatumDe } from "../config/utils.js";
import { KLAGE_KEY_MAP } from "../config/klagePositionKeys.js";
import { apiGebuehren, apiStandardtexte } from "../api.js";
import SchmerzensgelDialog from "../components/SchmerzensgelDialog.jsx";
import { formatGespeichertAm } from "./klageEntwurfLogik.js";
import { istPersonPartei, parteiAnzeigeName, organBezeichnung, kanonischeBeklagte } from "./parteiLogik.js";
import { wortDiff, schrittStatus, firmenOhneVertreter as ermittleFirmenOhneVertreter } from "./wizardFuehrungLogik.js";
import { ersetzePlatzhalter, genusKontext } from "./platzhalterLogik.js";
import { KlageGesamtvorschau } from "./KlageGesamtvorschau.jsx";
export { kanonischeBeklagte };

// ── Konstanten ─────────────────────────────────────────────────────────────────

const STEPS = [
  { nr: 1,  label: "Gericht"   },
  { nr: 2,  label: "Rubrum"    },
  { nr: 3,  label: "Aktiv."    },
  { nr: 4,  label: "Unfall"    },
  { nr: 5,  label: "Schaden"   },
  { nr: 6,  label: "Anträge"   },
  { nr: 7,  label: "Würdigung" },
  { nr: 8,  label: "Einwände"  },
  { nr: 9,  label: "Verzug"    },
  { nr: 10, label: "Gebühren"  },
  { nr: 11, label: "Generieren"},
];

const PLEX = T.fontBody;
const MONO = "ui-monospace,monospace";

// ── Hilfsfunktionen ────────────────────────────────────────────────────────────

export function anredeNorm(anrede) {
  const a = String(anrede || "").trim().toLowerCase();
  if (a === "1" || a === "herr" || a === "herrn") return "herr";
  if (a === "2" || a === "frau") return "frau";
  return "";
}

export function beklagtenGrammatik(beklagte) {
  const gef = kanonischeBeklagte(beklagte);
  if (gef.length > 1) {
    return { anzahl: gef.length, mehrere: true,
      nomGross: "Die Beklagten", hat: "haben",
      verurteilt: "Die Beklagten werden als Gesamtschuldner verurteilt",
      verpflichtet: "die Beklagten als Gesamtschuldner verpflichtet sind",
      kosten: "Die Beklagten tragen die Kosten des Rechtsstreits." };
  }
  const b = gef[0];
  const maennlich = !!b && !b.versicherung && !b.firma && anredeNorm(b.anrede) === "herr";
  if (maennlich) {
    return { anzahl: gef.length, mehrere: false,
      nomGross: "Der Beklagte", hat: "hat",
      verurteilt: "Der Beklagte wird verurteilt",
      verpflichtet: "der Beklagte verpflichtet ist",
      kosten: "Der Beklagte trägt die Kosten des Rechtsstreits." };
  }
  return { anzahl: gef.length, mehrere: false,
    nomGross: "Die Beklagte", hat: "hat",
    verurteilt: "Die Beklagte wird verurteilt",
    verpflichtet: "die Beklagte verpflichtet ist",
    kosten: "Die Beklagte trägt die Kosten des Rechtsstreits." };
}

export function versichererSuffix(beklagte) {
  const gef = kanonischeBeklagte(beklagte);
  if (gef.length <= 1) return "";
  const idx = gef.findIndex(b => b.versicherung || (b.firma && !b.ist_halter));
  return idx >= 0 ? ` zu ${idx + 1})` : "";
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
      `der vorliegenden Freigabeerklärung der ${finTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: Freigabeerklärung ${beweisZusatz}Anlage K 1`
    );
  }
  return (
    basis +
    `der ${bedingTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: ${bedingTyp} in Kopie, Anlage K 1`
  );
}

/**
 * Kombinierter Sachverhalt-Text für Step 3:
 * Einleitung + Beklagten-Block + Aktivlegitimation + optional Auslandsunfall.
 * Spiegelt die backend-Logik (klage_service.py §1 Sachverhalt).
 */
export function buildSachverhaltText({
  klaeger, vorsteuer, unfalldatum, unfallort,
  beklagte,
  aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer,
  auslandsunfall, auslandsunfallText,
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
  const gegner  = kanonischeBeklagte(beklagte);
  const mehrere = gegner.length > 1;
  const bekSaetze = gegner.map((b, i) => {
    const nrStr = mehrere ? ` zu ${i + 1})` : "";
    if (b.versicherung || (b.firma && !b.ist_halter)) {
      const kz = b.kfz_kennzeichen || "";
      let satz = `Die Beklagte${nrStr} ist die gegnerische Haftpflichtversicherung des unfallverursachenden Fahrzeugs`;
      if (kz) satz += ` mit dem amtlichen Kennzeichen ${kz}`;
      return satz + ".";
    }
    const istFirmaB = !!(b.versicherung || b.firma);
    const weiblichB = istFirmaB || anredeNorm(b.anrede) === "frau";
    const art = weiblichB ? "Die" : "Der";
    if (b.ist_halter) {
      return `${art} Beklagte${nrStr} ist ${weiblichB ? "die Halterin" : "der Halter"} des unfallverursachenden Fahrzeugs.`;
    }
    return `${art} Beklagte${nrStr} war zum Unfallzeitpunkt ${weiblichB ? "die Fahrerin" : "der Fahrer"} des unfallverursachenden Fahrzeugs.`;
  });

  if (bekSaetze.length > 0) {
    text += "\n\n" + bekSaetze.join("\n");
  }

  // ── Aktivlegitimation ─────────────────────────────────────────────────
  const aktLegText = buildVorschauText(aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer, klaeger);
  if (aktLegText) {
    text += "\n\n" + aktLegText;
  }

  // ── Auslandsunfall ────────────────────────────────────────────────────
  if (auslandsunfall && auslandsunfallText) {
    text += "\n\n" + auslandsunfallText;
  }

  return text;
}

/**
 * Prozentanzeige ohne int-Truncation: 66.666… -> "66,67", 50.0 -> "50".
 * Spiegelt backend/word/klage_service.py::_pct_str().
 */
function pctStr(wert) {
  const gerundet = Math.round(wert * 100) / 100;
  if (gerundet === Math.trunc(gerundet)) return String(Math.trunc(gerundet));
  return gerundet.toFixed(2).replace(/0+$/, "").replace(/\.$/, "").replace(".", ",");
}

/**
 * Rundet auf 2 Nachkommastellen (spiegelt backend round(x, 2)).
 */
function round2(x) {
  return Math.round(x * 100) / 100;
}

/**
 * Zentrale Klagebetrag-Berechnung (KW-03 Fall A/B) – spiegelt
 * backend/word/klage_service.py::generiere_klageschrift().
 * Fall B (hqTyp="eigen", 0<hq<100): erst die Positionssumme mit hq quotieren,
 * dann die bereits geleisteten Zahlungen abziehen (max(0, …)-Klammer).
 * Sonst: Summe der angehakten Beträge (100 %).
 */
export function berechneKlagebetrag(positionen, hq, hqTyp) {
  const checked = (positionen || []).filter(p => p.checked);
  const summeBetrag = checked.reduce((s, p) => s + (p.betrag || 0), 0);
  if (hqTyp === "eigen" && hq > 0 && hq < 100) {
    const gesamtVoll = checked.reduce((s, p) => s + (p.betragOriginal ?? p.betrag ?? 0), 0);
    const zahlungen  = round2(gesamtVoll - summeBetrag);
    return Math.max(0, round2(gesamtVoll * hq / 100 - zahlungen));
  }
  return summeBetrag;
}

/**
 * Zentrale Ableitung des effektiven außergerichtl. Streitwerts (Nr. 2300 VV RVG-Basis).
 * Fall B (hqTyp="eigen", 0<hq<100): der Streitwert wird mit hq quotiert.
 * Sonst: unverändert.
 */
export function berechneSwAussergEffektiv(swAusserg, hq, hqTyp) {
  if (hqTyp === "eigen" && hq > 0 && hq < 100) {
    return round2(swAusserg * hq / 100);
  }
  return swAusserg;
}

/**
 * KW-40: liefert die geparste Zahl oder null, wenn der Override leer bzw.
 * nicht-numerisch ist (statt NaN durchzureichen).
 */
export function parseBetragOderNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Erstellt den Vorschautext für die Rechtliche Würdigung.
 */
export function buildRwVorschau(haftungsbegruendung, haftungsquote, gesamtReguliert,
                                weiblich, hqTyp = "gegnerisch", beklagte = [], texte) {
  const hq     = parseFloat(haftungsquote) || 100;
  const kl_nom = weiblich ? "Die Klägerin" : "Der Kläger";
  const lines  = [];

  if (hq >= 100) {
    const gef = kanonischeBeklagte(beklagte);
    const insurerIdx = gef.findIndex(b => b.versicherung || (b.firma && !b.ist_halter));
    const refIdx = insurerIdx >= 0 ? insurerIdx : 0;
    const ref = gef[refIdx];
    const nrSuffix = gef.length > 1 ? ` zu ${refIdx + 1})` : "";
    const refMaennl = !!ref && !ref.versicherung && !ref.firma
                      && anredeNorm(ref.anrede) === "herr";
    const bek_gen_art = refMaennl ? "des" : "der";
    const bek_dat_pp  = refMaennl ? "bei dem" : "bei der";
    lines.push(
      `Die alleinige Haftung ${bek_gen_art} Beklagten${nrSuffix} steht außer Frage.` +
      ` Der Unfall wurde allein schuldhaft von dem ${bek_dat_pp} Beklagten${nrSuffix} versicherten Fahrzeug verursacht.`
    );
  } else {
    lines.push(ersetzePlatzhalter(texte.wuerdigung_grundhaftung, {
      HAFTUNGSBEGRUENDUNG: (haftungsbegruendung || "").trim() || "sein schuldhaftes Verhalten",
      HAFTUNGSQUOTE: pctStr(hq),
    }));
  }

  const gram = beklagtenGrammatik(beklagte);
  if (gesamtReguliert > 0) {
    lines.push(ersetzePlatzhalter(texte.wuerdigung_teilregulierung, {
      BEK_NOM: gram.nomGross, BEK_HAT: gram.hat, BETRAG: fmtEuro(gesamtReguliert),
    }));
  } else {
    lines.push(ersetzePlatzhalter(texte.wuerdigung_keine_regulierung, {
      BEK_NOM: gram.nomGross, BEK_HAT: gram.hat,
    }));
  }

  if (hq < 100) {
    if (hqTyp === "eigen") {
      lines.push(
        `${kl_nom} lässt sich eine Mithaftungsquote von ${pctStr(100 - hq)} % anrechnen. ` +
        `Die Klageforderung ist entsprechend gekürzt.`
      );
    } else {
      lines.push(ersetzePlatzhalter(texte.wuerdigung_alleinhaftung_bestritten, {
        MITHAFTUNGSQUOTE: pctStr(100 - hq),
      }));
    }
  }

  return lines.join("\n\n");
}

// ── Teilkomponenten ────────────────────────────────────────────────────────────

export function schrittBlockiert(nr, { gerichtBestaetigt, positionen }) {
  if (nr === 1 && !gerichtBestaetigt) return true;
  if (nr === 5 && !(positionen || []).some(p => p.checked)) return true;
  return false;
}

export function kannSpringen(ziel, step, ctx) {
  if (ziel <= step) return true;
  for (let k = step; k < ziel; k++) {
    if (schrittBlockiert(k, ctx)) return false;
  }
  return true;
}

export function Fortschrittsbalken({ step, maxStep, onStepChange, springenErlaubt, statusFuer }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "1.5rem" }}>
      {STEPS.map((s, i) => {
        const status    = statusFuer ? statusFuer(s.nr)
                          : { zustand: s.nr === step ? "aktiv" : s.nr < step ? "erledigt" : "offen", warnung: null };
        const aktiv     = status.zustand === "aktiv";
        const warnung   = status.zustand === "warnung";
        const erledigt  = status.zustand === "erledigt";
        const klickbar  = s.nr <= maxStep && s.nr !== step && (!springenErlaubt || springenErlaubt(s.nr));
        return (
          <React.Fragment key={s.nr}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, minWidth: 0 }}>
              <div
                onClick={klickbar ? () => onStepChange(s.nr) : undefined}
                title={status.warnung || undefined}
                style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: warnung ? `${T.amber}18` : erledigt ? T.navy : aktiv ? T.accent : T.surface,
                  border: `2px solid ${warnung ? T.amber : erledigt ? T.navy : aktiv ? T.accent : T.border}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: MONO, fontSize: "0.8rem", fontWeight: 700,
                  color: warnung ? T.amberText : (erledigt || aktiv) ? "#fff" : T.textMuted,
                  transition: "all 0.25s",
                  boxShadow: aktiv ? `0 0 0 4px ${T.accent}28` : "none",
                  flexShrink: 0,
                  cursor: klickbar ? "pointer" : "default",
                }}>
                {warnung ? "⚠" : erledigt ? "✓" : s.nr}
              </div>
              <div style={{
                fontFamily: PLEX, fontSize: "0.72rem", fontWeight: aktiv ? 700 : 400,
                color: aktiv ? T.accent : warnung ? T.amberText : erledigt ? T.navy : T.textMuted,
                marginTop: 5, textAlign: "center", whiteSpace: "nowrap",
                overflow: "hidden", width: "100%",
                transition: "color 0.25s",
              }}>
                {s.label}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                height: 2, flex: 1, marginBottom: 16,
                background: (erledigt || warnung) ? T.navy : T.borderSoft,
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
      background: checked ? `${T.navy}08` : T.cardBg,
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
          color: T.amberText, textAlign: "center", lineHeight: 1.5 }}>
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
          {onEditText && (
            <span style={{ fontWeight: 400, marginLeft: 8, textTransform: "none", letterSpacing: 0 }}>
              (editierbar)
            </span>
          )}
        </div>
        <textarea
          value={editText !== undefined ? (editText || "") : (text || "")}
          onChange={e => onEditText && onEditText(e.target.value)}
          readOnly={!onEditText}
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

export function DiffAnsicht({ autoText, aktuellerText }) {
  const segmente = wortDiff(autoText, aktuellerText);
  const stil = {
    neu:    { background: "#e2f3e2", color: "#1e6b1e", borderRadius: 3, padding: "0 2px", textDecoration: "underline" },
    weg:    { background: "#fbe3e3", color: "#a03030", textDecoration: "line-through", borderRadius: 3, padding: "0 2px" },
    gleich: {},
  };
  return (
    <div style={{
      flex: 1, background: "#fdfcf7", border: "1px solid #e8e4d4", borderRadius: 10,
      padding: "1.25rem", minHeight: 200, overflowY: "auto",
      fontFamily: MONO, fontSize: "0.825rem", color: "#2d2a1e", lineHeight: 1.7,
    }} data-testid="diff-ansicht">
      <div style={{ fontFamily: PLEX, fontSize: "0.68rem", color: T.textMuted, marginBottom: "0.75rem" }}>
        grün = Ihre Fassung ergänzt · rot durchgestrichen = im Automatik-Text, bei Ihnen entfallen
      </div>
      <div style={{ whiteSpace: "pre-wrap" }}>
        {segmente.map((s, i) => (
          <React.Fragment key={i}>
            {i > 0 && !s.text.startsWith("\n") && " "}
            <span data-difftyp={s.typ} style={stil[s.typ]}>{s.text}</span>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export function EditorMitDiff({ autoText, text, onText, warnung }) {
  const [zeigeDiff, setZeigeDiff] = useState(false);
  const geaendert = (text ?? "") !== (autoText ?? "");
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
      {geaendert && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 6 }}>
          <button onClick={() => setZeigeDiff(v => !v)}
            style={{ padding: "4px 10px", borderRadius: 6, cursor: "pointer",
              border: `1.5px solid ${T.border}`, background: T.cardBg,
              fontFamily: PLEX, fontSize: "0.76rem", fontWeight: 600, color: T.navy }}>
            {zeigeDiff ? "✎ Bearbeiten" : "⇄ Änderungen anzeigen"}
          </button>
        </div>
      )}
      {zeigeDiff && geaendert
        ? <DiffAnsicht autoText={autoText} aktuellerText={text} />
        : <DokumentCard warnung={warnung} editText={text} onEditText={onText} />}
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

/** Entfernt doppelten "Schadennummer:"-Prefix der aus RA-Micro kommen kann */
function _schadenNrBereinigt(raw) {
  if (!raw) return "";
  return raw.replace(/^Schadennummer:\s*/i, "").trim();
}

export function StepRubrum({ beklagte, onClose, onVertreterLookup, vertreterLookup }) {
  // checked=null → wie checked=true behandeln (Word-Verhalten: default True)
  const klaeger   = (beklagte || []).filter(b => b.rolle_klage === "klaeger");
  const beklagteG = kanonischeBeklagte(beklagte);
  const mehrereK  = klaeger.length > 1;
  const mehrereB  = beklagteG.length > 1;

  // Eine Rubrum-Zeile: Text links, Rolle rechts (wie im Word-Dokument)
  function RubrumZeile({ links, rolle, warn, onLookup, lookupLaeuft }) {
    return (
      <div style={{ marginBottom: "0.4rem" }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "baseline",
          gap: "1rem",
        }}>
          <span style={{ fontFamily: PLEX, fontSize: "0.9rem", color: T.navy }}>{links}</span>
          <span style={{
            fontFamily: PLEX, fontSize: "0.85rem", fontStyle: "italic",
            color: T.textFaint, whiteSpace: "nowrap", flexShrink: 0,
          }}>– {rolle} –</span>
        </div>
        {warn && (
          <div style={{ fontSize: "0.78rem", color: "#92400e", marginTop: 2,
            display: "flex", alignItems: "center", gap: 8 }}>
            <span>⚠ Vertreter fehlt</span>
            {onLookup ? (
              <button onClick={onLookup} disabled={lookupLaeuft}
                title="Vertretung online nachschlagen – ohne den Wizard zu verlassen"
                style={{ background: T.cardBg, border: `1px solid #92400e`, borderRadius: 5,
                  padding: "1px 8px", cursor: lookupLaeuft ? "wait" : "pointer",
                  color: "#92400e", fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600 }}>
                {lookupLaeuft ? "⟳ sucht …" : "🔍 Lookup"}
              </button>
            ) : (
              <button onClick={() => { if (onClose) onClose(); setTimeout(() => document.getElementById("karte-parteien")?.scrollIntoView({ behavior: "smooth" }), 150); }}
                style={{ background: "none", border: "none", padding: 0, cursor: "pointer",
                  color: "#92400e", fontFamily: PLEX, fontSize: "0.78rem", textDecoration: "underline", fontWeight: 600 }}>
                jetzt nachtragen →
              </button>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div style={{
        background: T.surface, border: `1px solid ${T.borderSoft}`,
        borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1.25rem",
        fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span>ℹ Vorschau entspricht dem Rubrum im Word-Dokument</span>
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
        fontFamily: PLEX, fontSize: "0.9rem",
      }}>
        {/* Kläger */}
        {klaeger.length === 0 ? (
          <div style={{ color: "#92400e" }}>⚠ Kein Kläger erfasst.</div>
        ) : klaeger.map((b, i) => {
          const name    = b.vorname ? `${b.vorname} ${b.name}`.trim() : b.name || b.firma || "Mandant";
          const anschr  = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
          const zeile   = [name, anschr].filter(Boolean).join(", ");
          const anrede  = anredeNorm(b.anrede);
          const rolleBez = mehrereK
            ? (anrede === "frau" ? `Klägerin zu ${i + 1})` : `Kläger zu ${i + 1})`)
            : (anrede === "frau" ? "Klägerin" : "Kläger");
          return <RubrumZeile key={b.id || i} links={zeile} rolle={rolleBez} />;
        })}

        {klaeger.length > 0 && (
          <div style={{ fontFamily: PLEX, fontSize: "0.875rem", color: "#2d2a1e", margin: "0.5rem 0" }}>
            Prozessbevollmächtigte: Koch, Schatz &amp; Kollegen, Tulpenhofstr. 1, 63067 Offenbach
          </div>
        )}

        {klaeger.length > 0 && beklagteG.length > 0 && (
          <div style={{
            textAlign: "center", padding: "0.6rem 0", margin: "0.5rem 0",
            fontSize: "0.875rem", letterSpacing: "0.15em", color: T.textFaint,
            borderTop: `1px solid ${T.borderSoft}`, borderBottom: `1px solid ${T.borderSoft}`,
          }}>
            g e g e n
          </div>
        )}

        {/* Beklagte */}
        {beklagteG.length === 0 ? (
          <div style={{ color: "#92400e", fontSize: "0.875rem" }}>⚠ Keine Beklagten ausgewählt.</div>
        ) : beklagteG.map((b, i) => {
          const istPerson  = istPersonPartei(b);
          const name       = parteiAnzeigeName(b);
          const anschr     = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
          const ist_firma  = !istPerson && !!(b.versicherung || b.firma || b.name);
          const vertr      = b.vertreter_name
            ? `, vertreten durch ${b.vertreter_funktion || organBezeichnung(name)} ${b.vertreter_name}`
            : ist_firma ? `, vertreten durch ${organBezeichnung(name)}` : "";
          const schadenNr  = _schadenNrBereinigt(b.schaden_nr);
          const schadenSfx = schadenNr ? `, zur Schadennummer ${schadenNr}` : "";
          const nr_suffix  = mehrereB ? ` zu ${i + 1})` : "";
          const zeile      = [name, anschr].filter(Boolean).join(", ") + vertr + schadenSfx;
          const warn       = ist_firma && !b.vertreter_name;
          const maennlich  = istPerson && anredeNorm(b.anrede) === "herr";
          return <RubrumZeile key={b.id || i} links={zeile}
            rolle={`Beklagte${maennlich ? "r" : ""}${nr_suffix}`} warn={warn}
            onLookup={warn && onVertreterLookup ? () => onVertreterLookup(b.id, name) : undefined}
            lookupLaeuft={!!(vertreterLookup && vertreterLookup[b.id]?.laden)} />;
        })}
      </div>
    </div>
  );
}

// ── Step 3: Aktivlegitimation / Sachverhalt ────────────────────────────────────

export function StepAktLeg({
  aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
  aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
  klaeger,
  // Neu: kombinierter Sachverhalt
  vorsteuer, unfalldatum, unfallort, beklagte,
  auslandsunfall, onAuslandsunfall, auslandsunfallText,
  sachverhaltText, onSachverhaltText,
  sachverhaltManuell, onSachverhaltManuell,
}) {
  const brauchtFreigabe = aktLegTyp !== "eigentum";

  function buildAuto() {
    return buildSachverhaltText({
      klaeger, vorsteuer, unfalldatum, unfallort,
      beklagte,
      aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer,
      auslandsunfall, auslandsunfallText,
    });
  }

  useEffect(() => {
    if (sachverhaltManuell) return;
    if (onSachverhaltText) onSachverhaltText(buildAuto());
  }, [aktLegTyp, aktLegFreigabe, aktLegDatum, mandantIstFahrer, auslandsunfall, auslandsunfallText]); // eslint-disable-line

  function handleReset() {
    onSachverhaltManuell(false);
    if (onSachverhaltText) onSachverhaltText(buildAuto());
  }

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
                      background: T.cardBg, color: T.navy,
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

        <button
          onClick={handleReset}
          style={{
            padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy,
            marginTop: "1.5rem",
          }}
        >
          ↻ Neu generieren
        </button>
      </div>

      <EditorMitDiff
        autoText={buildAuto()}
        warnung={brauchtFreigabe && aktLegFreigabe === "ungeklaert"}
        text={sachverhaltText}
        onText={val => { onSachverhaltManuell(true); onSachverhaltText(val); }}
      />
    </div>
  );
}

// ── Step 3: Unfallhergang ──────────────────────────────────────────────────────

export function ersetzeMandantDurchKlaeger(text, weiblich) {
  if (!text) return text || "";
  let t = text;
  t = t.replace(/\bDer Mandant\b/g, weiblich ? "Die Klägerin" : "Der Kläger");
  t = t.replace(/\bDem Mandanten\b/g, weiblich ? "Der Klägerin" : "Dem Kläger");
  t = t.replace(/\bDen Mandanten\b/g, weiblich ? "Die Klägerin" : "Den Kläger");
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

  const autoText = ersetzeMandantDurchKlaeger(schilderungOriginal || "", weiblich);

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
            onClick={() => onUnfalltextEdit(ersetzeMandantDurchKlaeger(schilderungOriginal, weiblich))}
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
            fontFamily: PLEX, fontSize: "0.8rem", color: T.amberText,
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

      <EditorMitDiff autoText={autoText} text={unfalltextEdit} onText={onUnfalltextEdit} />
    </div>
  );
}

// ── Step 4: Schadenpositionen ──────────────────────────────────────────────────

export function StepSchaden({ positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind, abrechnungen, az, kl_nom,
                               hq = 100, hqTyp = "gegnerisch" }) {
  const [showSgDialog, setShowSgDialog] = useState(false);
  const klagebetrag = berechneKlagebetrag(positionen, hq, hqTyp);

  // KW-07: unbezifferter SG-Antrag (mitSG) und bezifferte SG-Position schliessen
  // sich aus - sonst wird Schmerzensgeld doppelt geltend gemacht.
  useEffect(() => {
    if (!mitSG) return;
    const sgPos = positionen.find(p => p.key === "schmerzensgeld");
    if (sgPos?.checked) onTogglePos("schmerzensgeld");
  }, [mitSG, positionen, onTogglePos]);

  // Provenance-Map: position_key → { gesamt, quellen[] }
  // DB-Rohdaten verwenden die echten Schaden-Feldnamen; KLAGE_KEY_MAP normalisiert
  // alles, was zum Fahrzeugschaden gehört, auf den Wizard-Key "fahrzeugschaden".
  const provenanceMap = {};
  (abrechnungen || []).forEach(ab => {
    (ab.positionen || []).forEach(rp => {
      const rawKey = rp.position_key;
      const k      = KLAGE_KEY_MAP[rawKey] || rawKey;
      const betrag = parseFloat(rp.betrag_reguliert) || 0;
      if (!k || betrag === 0) return;
      if (!provenanceMap[k]) provenanceMap[k] = { gesamt: 0, quellen: [] };
      provenanceMap[k].gesamt = Math.round((provenanceMap[k].gesamt + betrag) * 100) / 100;
      provenanceMap[k].quellen.push({
        datum:        ab.datum       || "",
        versicherung: ab.versicherung || "",
        betrag,
      });
    });
  });

  // Regulierungsstand: nach Datum+Versicherung gruppieren, Null-Einträge weglassen
  const regulGruppen = (() => {
    const map = new Map();
    for (const ab of (abrechnungen || [])) {
      const betrag = parseFloat(ab.gesamt_reguliert) || 0;
      if (betrag <= 0.005) continue;
      const key = `${ab.datum || ""}|${(ab.versicherung || "").trim()}`;
      if (map.has(key)) {
        map.get(key).summe += betrag;
      } else {
        map.set(key, { datum: ab.datum, versicherung: ab.versicherung || "", summe: betrag });
      }
    }
    return Array.from(map.values()).sort((a, b) => (b.datum || "").localeCompare(a.datum || ""));
  })();
  const regulGesamt = regulGruppen.reduce((s, g) => s + g.summe, 0);

  return (
    <div>
      <div style={{ marginBottom: "1.25rem" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ background: T.surface }}>
              {["☑", "Position", "Gefordert", "Reguliert", "Klageanteil"].map((h, i) => (
                <th key={h} style={{
                  padding: "5px 8px", fontFamily: PLEX,
                  fontSize: "0.72rem", fontWeight: 700, color: T.textMuted,
                  textTransform: "uppercase", letterSpacing: "0.06em",
                  textAlign: i === 0 ? "center" : i >= 2 ? "right" : "left",
                  width: i === 0 ? 32 : "auto",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positionen.map(p => {
              const prov     = provenanceMap[p.key];
              const reg      = prov?.gesamt || 0;
              const vollReg  = reg > 0 && (p.betrag || 0) <= 0.005;
              const gefordert = p.betragOriginal ?? ((p.betrag || 0) + reg);
              const sgGesperrt = mitSG && p.key === "schmerzensgeld";
              return (
                <tr key={p.key}
                  style={{ borderBottom: `1px solid ${T.borderSoft}`,
                    opacity: p.checked ? 1 : 0.55, cursor: sgGesperrt ? "not-allowed" : "pointer" }}
                  onClick={() => { if (!sgGesperrt) onTogglePos(p.key); }}>
                  <td style={{ padding: "8px", textAlign: "center" }}>
                    <input type="checkbox" checked={!!p.checked}
                      disabled={sgGesperrt}
                      onChange={() => { if (!sgGesperrt) onTogglePos(p.key); }}
                      onClick={e => e.stopPropagation()}
                      style={{ accentColor: T.navy,
                        cursor: sgGesperrt ? "not-allowed" : "pointer", width: 15, height: 15 }} />
                  </td>
                  <td style={{ padding: "8px", fontFamily: PLEX, fontSize: "0.9rem",
                    color: p.checked ? T.navy : T.text, fontWeight: p.checked ? 600 : 400 }}>
                    {p.label}
                    {vollReg && (
                      <span style={{ marginLeft: 8, fontSize: "0.72rem",
                        color: T.green, fontWeight: 600 }}>✓ vollst. reguliert</span>
                    )}
                    {sgGesperrt && (
                      <div style={{ fontSize: "0.72rem", color: T.textMuted, fontStyle: "italic", marginTop: 2 }}>
                        Wird als unbezifferter Antrag geltend gemacht (Schmerzensgeld-Toggle aktiv)
                      </div>
                    )}
                  </td>
                  <td style={{ padding: "8px", textAlign: "right",
                    fontFamily: MONO, fontSize: "0.875rem", color: T.textMuted }}>
                    {fmtEuro(gefordert)}
                  </td>
                  <td style={{ padding: "8px", textAlign: "right",
                    fontFamily: MONO, fontSize: "0.875rem",
                    color: reg > 0 ? T.green : T.textFaint }}>
                    {reg > 0 ? fmtEuro(reg) : "—"}
                  </td>
                  <td style={{ padding: "8px", textAlign: "right",
                    fontFamily: MONO, fontSize: "0.9rem",
                    fontWeight: p.checked ? 700 : 400,
                    color: p.checked ? T.navy : T.textMuted }}>
                    {fmtEuro(p.betrag)}
                  </td>
                </tr>
              );
            })}
            <tr style={{ borderTop: `2px solid ${T.border}`, background: T.surface }}>
              <td colSpan={4} style={{ padding: "8px 8px 8px 0",
                fontFamily: PLEX, fontSize: "0.875rem",
                fontWeight: 700, color: T.navy, textAlign: "right" }}>
                Klagebetrag (angehakte Positionen)
              </td>
              <td style={{ padding: "8px", textAlign: "right",
                fontFamily: MONO, fontSize: "0.975rem",
                fontWeight: 700, color: T.navy }}>
                {fmtEuro(klagebetrag)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {regulGruppen.length > 0 && (
        <div style={{ marginBottom: "1.25rem", padding: "0.75rem 1rem",
          background: T.surface, borderRadius: 8, border: `1px solid ${T.borderSoft}` }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
            marginBottom: "0.5rem" }}>
            Bisheriger Regulierungsstand
          </div>
          {regulGruppen.map((g, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between",
              fontFamily: MONO, fontSize: "0.825rem", padding: "2px 0" }}>
              <span style={{ color: T.textMuted }}>
                {g.datum ? (() => {
                  try { const [y,m,d] = g.datum.split("-"); return `${d}.${m}.${y}`; }
                  catch { return g.datum; }
                })() : "—"}
                {g.versicherung && <span style={{ marginLeft: 8 }}>{g.versicherung}</span>}
              </span>
              <span style={{ color: T.green, fontWeight: 600 }}>{fmtEuro(g.summe)}</span>
            </div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between",
            borderTop: `1px solid ${T.border}`, marginTop: 4, paddingTop: 4,
            fontFamily: MONO, fontSize: "0.875rem", fontWeight: 700, color: T.navy }}>
            <span>Summe reguliert</span>
            <span>{fmtEuro(regulGesamt)}</span>
          </div>
        </div>
      )}

      <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem",
        border: `1px solid ${T.borderSoft}`, marginBottom: "1rem" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.5rem" }}>Klagebetrag</div>
        <div style={{ fontFamily: MONO, fontSize: "1.25rem", fontWeight: 700, color: T.navy }}>
          {fmtEuro(klagebetrag + (mitSG ? sgMind : 0))}
        </div>
        {mitSG && sgMind > 0 && (
          <div style={{ fontFamily: PLEX, fontSize: "0.78rem", color: T.textMuted }}>
            Sachschaden {fmtEuro(klagebetrag)} + SG {fmtEuro(sgMind)}
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
                background: T.cardBg, color: T.navy,
              }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>€</span>
          </div>
        )}
        <div style={{ marginTop: "0.75rem" }}>
          <button
            onClick={() => setShowSgDialog(true)}
            style={{
              padding: "7px 14px", background: T.navy, color: "#fff",
              border: "none", borderRadius: 7, cursor: "pointer",
              fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600,
            }}>
            Schmerzensgeld-Assistent
          </button>
        </div>
      </div>
      {showSgDialog && az && (
        <SchmerzensgelDialog
          az={az}
          kl_nom={kl_nom || "Der Kläger"}
          onClose={() => setShowSgDialog(false)}
          onUebernehmen={({ mitSG: sg, sgMind: mind }) => {
            onMitSG(sg);
            onSGMind(mind);
            setShowSgDialog(false);
          }}
        />
      )}
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

export function EinwaendeAuswahl({ abrechnungen, kuerzungsarten, beklagte, onUebernehmen, platzhalterKontext = null }) {
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

    const zuSuffix = versichererSuffix(beklagte);

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
      const eur      = fmtEuro(abzug);
      const istLetzt = selected.length > 1 && i === selected.length - 1;
      const betragsatz = abzug > 0
        ? (istLetzt ? EINLEITUNG_LETZT(zuSuffix, eur) : EINLEITUNGS_VARIANTEN[i % 5](zuSuffix, eur))
        : "";
      const roh = (ka.textbaustein || ka.standard_gegenargument || "").trim();
      const baustein = platzhalterKontext
        ? ersetzePlatzhalter(roh, platzhalterKontext)
        : roh;
      return [
        `**${letter}) ${ka.bezeichnung}**`,
        betragsatz,
        baustein
          || `[FEHLT: Kein Textbaustein zur Kürzungsart „${ka.bezeichnung}“ hinterlegt]`,
      ].filter(Boolean).join("\n");
    });

    const gesamtKuerzung = selected.reduce((s, ka) => s + Math.max(0, kuerzungMap[ka.id] || 0), 0);
    const schlusssatz = gesamtKuerzung > 0
      ? `Insgesamt hat die Beklagte${zuSuffix} daher einen Betrag in Höhe von ${fmtEuro(gesamtKuerzung)} zu Unrecht einbehalten.`
      : "";

    const lines = [
      `Die Beklagte${zuSuffix} hat folgende Positionen zu Unrecht nicht oder nicht vollständig reguliert:`,
      "",
      ...bloecke,
      ...(schlusssatz ? ["", schlusssatz] : []),
    ];
    onUebernehmen(lines.join("\n\n"));
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      border: `1px solid ${T.borderSoft}`, borderRadius: 10,
      background: T.cardBg, maxHeight: 480, overflow: "hidden",
    }}>
      {/* Liste */}
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
                background: checked.has(ka.id) ? `${T.navy}06` : T.cardBg,
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
                        background: `${T.accent}22`, color: "#8a5800",
                        padding: "1px 7px", borderRadius: 10,
                      }}>gekürzt</span>
                    )}
                  </div>
                  {(ka.textbaustein || ka.standard_gegenargument) && (
                    <div style={{ fontFamily: PLEX, fontSize: "0.75rem",
                      color: T.textFaint, marginTop: 2, lineHeight: 1.55 }}>
                      {(() => {
                        const t = (ka.textbaustein || ka.standard_gegenargument).trim();
                        return t.length > 200 ? t.slice(0, 200) + " …" : t;
                      })()}
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
        flexShrink: 0, background: T.offWhite,
      }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted }}>
          {checked.size} ausgewählt
        </div>
        <button onClick={uebernehmen}
          style={{ padding: "8px 18px", borderRadius: 7, cursor: "pointer",
            border: "none", background: T.navy,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 700, color: "#fff" }}>
          Text übernehmen
        </button>
      </div>
    </div>
  );
}

// ── Step 7: Rechtliche Würdigung ───────────────────────────────────────────────

export function StepRw({ hq, onHq, hqTyp = "gegnerisch", onHqTyp, hb, onHb, abrechnungen, weiblich,
                  rwText, onRwText, beklagte,
                  onKiHaftung, kiLaedt, onEinwaendeReset, standardtexte }) {
  const gesamtReg = (abrechnungen || []).reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0);

  function neuGenerieren() {
    if (!standardtexte) return;
    onRwText(buildRwVorschau(hb, hq, gesamtReg, weiblich, hqTyp, beklagte, standardtexte));
    onEinwaendeReset && onEinwaendeReset();
  }

  function fallauswaehlen(neuerTyp) {
    onHqTyp(neuerTyp);
    if (!standardtexte) return;
    onRwText(buildRwVorschau(hb, hq, gesamtReg, weiblich, neuerTyp, beklagte, standardtexte));
    onEinwaendeReset && onEinwaendeReset();
  }

  return (
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
                background: T.cardBg, color: T.navy,
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

        {hq < 100 && (
          <div>
            <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 6 }}>
              Fallauswahl
            </div>
            {[
              { value: "gegnerisch", label: "Gegnerische Quote (nur Darstellung — Beträge bleiben 100 %)" },
              { value: "eigen",      label: "Eigene Quote (kürzt Klagebetrag und Gebührenbasis)" },
            ].map(opt => (
              <label key={opt.value} style={{ display: "flex", alignItems: "flex-start", gap: 8,
                cursor: "pointer", fontFamily: PLEX, fontSize: "0.82rem",
                color: hqTyp === opt.value ? T.navy : T.text, fontWeight: hqTyp === opt.value ? 600 : 400,
                marginBottom: 6 }}>
                <input type="radio" checked={hqTyp === opt.value}
                  onChange={() => fallauswaehlen(opt.value)}
                  style={{ accentColor: T.navy, cursor: "pointer", marginTop: 2 }} />
                {opt.label}
              </label>
            ))}
          </div>
        )}

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
              background: T.cardBg, color: T.navy,
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
            {gesamtReg > 0 ? fmtEuro(gesamtReg) : "keine"}
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
            border: `1.5px solid ${T.accent}`, background: `${T.accent}12`,
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

        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: "auto" }}>
          Vorschau der Grundhaftung. Einwände und Feinschliff folgen in Schritt 8 — dort ist der Text editierbar.
        </div>
      </div>

      <DokumentCard text={rwText} />
    </div>
  );
}

// ── Step 8: Einwände ───────────────────────────────────────────────────────────

export function StepEinwaende({ abrechnungen, kuerzungsarten, beklagte,
                                rwText, onRwText,
                                einwaendeBlock, onEinwaendeBlock,
                                grundhaftungsText, platzhalterKontext = null }) {
  const erfasst = (abrechnungen || []).some(ab =>
    (ab.positionen || []).some(p => p.kuerzungsart_id != null));

  function uebernehmen(neuerText) {
    if (!neuerText) return;
    if (einwaendeBlock && rwText && rwText.includes(einwaendeBlock)) {
      onRwText(rwText.replace(einwaendeBlock, neuerText));
    } else {
      onRwText((rwText ? rwText + "\n\n" : "") + neuerText);
    }
    onEinwaendeBlock(neuerText);
  }

  const autoText = einwaendeBlock ? `${grundhaftungsText}\n\n${einwaendeBlock}` : grundhaftungsText;

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 340px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Kürzungen & Einwände" />
        {erfasst ? (
          <EinwaendeAuswahl abrechnungen={abrechnungen} kuerzungsarten={kuerzungsarten}
            beklagte={beklagte} onUebernehmen={uebernehmen}
            platzhalterKontext={platzhalterKontext} />
        ) : (
          <div style={{ background: T.surface, border: `1px solid ${T.borderSoft}`,
            borderRadius: 8, padding: "0.9rem 1rem",
            fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted, lineHeight: 1.6 }}>
            Keine Kürzungen der Versicherung erfasst. Sie können direkt mit „Weiter" fortfahren.
          </div>
        )}
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: "auto" }}>
          Rechts steht der vollständige Text der rechtlichen Würdigung — hier finalisieren.
        </div>
      </div>
      <EditorMitDiff autoText={autoText} text={rwText} onText={onRwText} />
    </div>
  );
}

// ── Step 9: Verzug & Kosten ────────────────────────────────────────────────────

export function buildVerzugAutoText(dokDatum, eintrittDatum, texte) {
  const vDat = fmtDatumDe(eintrittDatum);
  const bDat = fmtDatumDe(dokDatum);
  if (!vDat) return texte.verzug_rechtshaengigkeit;
  const basis = ersetzePlatzhalter(texte.verzug_mit_datum, { VERZUGSDATUM: vDat });
  if (!bDat) return basis;
  return `${basis}\n\nBEWEIS: ${ersetzePlatzhalter(texte.verzug_beweis_schreiben, { SCHREIBEN_DATUM: bDat })}`;
}

export function StepVerzug({ zinsenAb, weiblich,
                      wizardVerzugDatum, onWizardVerzugDatum,
                      wizardVerzugDokDatum, onWizardVerzugDokDatum,
                      wizardVerzugText, onWizardVerzugText,
                      manuelleBearbeitung, onManuelleBearbeitung,
                      verzugDokListe, verzugDokId, onVerzugDokId,
                      standardtexte }) {
  const pickerEinRef  = useRef(null);
  const pickerDokRef  = useRef(null);

  function datumZuIso(de) {
    const m = (de || "").match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    return m ? `${m[3]}-${m[2].padStart(2,"0")}-${m[1].padStart(2,"0")}` : "";
  }
  function isoZuDatum(iso) {
    if (!iso) return "";
    const [y, mo, d] = iso.split("-");
    return `${d}.${mo}.${y}`;
  }

  function rebuildText(dokDat, einDat) {
    if (manuelleBearbeitung || !standardtexte) return;
    onWizardVerzugText(buildVerzugAutoText(dokDat, einDat, standardtexte));
  }

  function handleEintrittChange(val) {
    onWizardVerzugDatum(val);
    rebuildText(wizardVerzugDokDatum, val);
  }

  function handleDokDatumChange(val) {
    onWizardVerzugDokDatum(val);
    rebuildText(val, wizardVerzugDatum);
  }

  function handleReset() {
    onManuelleBearbeitung(false);
    if (!standardtexte) return;
    onWizardVerzugText(buildVerzugAutoText(wizardVerzugDokDatum, wizardVerzugDatum, standardtexte));
  }

  const CalIcon = () => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="3" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M1 7h14" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 1v3M11 1v3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );

  const calBtnStyle = {
    padding: "6px 9px", borderRadius: 7, cursor: "pointer",
    border: `1.5px solid ${T.border}`, background: T.cardBg,
    color: T.textMuted, fontSize: "1rem", lineHeight: 1,
    display: "flex", alignItems: "center", flexShrink: 0,
  };

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>

        {/* ── Verzugsbegründendes Schreiben ── */}
        <AbschnittLabel text="Verzugsbegründendes Schreiben" />

        {/* Dokument-Auswahl */}
        {(verzugDokListe?.length || 0) > 0 && (
          <div>
            <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
              Schreiben auswählen
            </div>
            <select
              value={verzugDokId ?? ""}
              onChange={e => onVerzugDokId(e.target.value ? parseInt(e.target.value) : null)}
              style={{
                width: "100%", padding: "7px 8px", borderRadius: 7,
                border: `1.5px solid ${T.border}`, fontFamily: PLEX,
                fontSize: "0.825rem", background: T.cardBg,
              }}
            >
              <option value="">– kein Dokument –</option>
              {verzugDokListe.map(d => (
                <option key={d.id} value={d.id}>{d.dateiname}</option>
              ))}
            </select>
          </div>
        )}

        {/* Datum des Schreibens */}
        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Datum des Schreibens <span style={{ color: T.textFaint }}>(für BEWEIS-Zeile)</span>
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", position: "relative" }}>
            <input
              type="text"
              value={wizardVerzugDokDatum}
              onChange={e => handleDokDatumChange(e.target.value)}
              placeholder="TT.MM.JJJJ"
              style={{
                flex: 1, padding: "7px 10px", borderRadius: 7,
                border: `1.5px solid ${wizardVerzugDokDatum ? T.navy : T.border}`,
                fontFamily: MONO, fontSize: "0.875rem",
                color: wizardVerzugDokDatum ? T.navy : T.textMuted,
                background: T.cardBg, boxSizing: "border-box",
              }}
            />
            <button type="button" onClick={() => pickerDokRef.current?.showPicker?.()}
              title="Kalender öffnen" style={calBtnStyle}>
              <CalIcon />
            </button>
            <input ref={pickerDokRef} type="date"
              value={datumZuIso(wizardVerzugDokDatum)}
              onChange={e => handleDokDatumChange(isoZuDatum(e.target.value))}
              style={{ position: "absolute", opacity: 0, pointerEvents: "none", width: 0, height: 0, right: 0 }}
              tabIndex={-1} />
          </div>
          {wizardVerzugDokDatum && (
            <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint, marginTop: 3 }}>
              → BEWEIS: Schreiben vom {fmtDatumDe(wizardVerzugDokDatum)}
            </div>
          )}
        </div>

        <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "0.75rem" }}>
          {/* ── Verzugseintritt ── */}
          <AbschnittLabel text="Verzugseintritt" />
          <div style={{ fontFamily: PLEX, fontSize: "0.75rem", color: T.textMuted, margin: "4px 0 6px" }}>
            Tag nach Fristablauf oder Ablehnungsschreiben (leer = Rechtshängigkeit)
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", position: "relative" }}>
            <input
              type="text"
              value={wizardVerzugDatum}
              onChange={e => handleEintrittChange(e.target.value)}
              placeholder="TT.MM.JJJJ"
              style={{
                flex: 1, padding: "7px 10px", borderRadius: 7,
                border: `1.5px solid ${wizardVerzugDatum ? T.navy : T.amber}`,
                fontFamily: MONO, fontSize: "0.875rem",
                color: wizardVerzugDatum ? T.navy : T.textMuted,
                background: T.cardBg, boxSizing: "border-box",
              }}
            />
            <button type="button" onClick={() => pickerEinRef.current?.showPicker?.()}
              title="Kalender öffnen" style={calBtnStyle}>
              <CalIcon />
            </button>
            <input ref={pickerEinRef} type="date"
              value={datumZuIso(wizardVerzugDatum)}
              onChange={e => handleEintrittChange(isoZuDatum(e.target.value))}
              style={{ position: "absolute", opacity: 0, pointerEvents: "none", width: 0, height: 0, right: 0 }}
              tabIndex={-1} />
          </div>
          {!wizardVerzugDatum && (
            <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.amber, marginTop: 3 }}>
              Fallback: Rechtshängigkeit
            </div>
          )}
        </div>

        <div style={{ borderTop: `1px solid ${T.borderSoft}`, paddingTop: "0.75rem" }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, lineHeight: 1.7 }}>
            <div>Zinsen ab: <span style={{ fontFamily: MONO, color: T.navy }}>
              {zinsenAb === "verzug" ? "Verzugseintritt" : "Rechtshängigkeit"}
            </span></div>
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

      <EditorMitDiff autoText={standardtexte ? buildVerzugAutoText(wizardVerzugDokDatum, wizardVerzugDatum, standardtexte) : ""}
        text={wizardVerzugText}
        onText={val => { onManuelleBearbeitung(true); onWizardVerzugText(val); }} />
    </div>
  );
}

// ── Step 10: Zusammenfassung + Generieren ──────────────────────────────────────

export function StepZusammenfassung({ gericht, beklagte, positionen, mitSG, sgMind,
                               rvgAussergData, rvgAussergOv,
                               aktLegTyp, aktLegFreigabe,
                               zinsenAb, wizardVerzugDatum,
                               laedt, onGenerieren, fehler,
                               akteId, vorschauCfgFn, onVorschauEdit,
                               lgGrenzwert, swAusserg, antraegeText, gebuehrenText,
                               antraegeVeraltet, onAntraegeNeuGenerieren, onAntraegeBehalten,
                               antraegeAuto,
                               onVertreterLookup, vertreterLookup,
                               unfallort, unfalldatum,
                               hq = 100, hqTyp = "gegnerisch" }) {
  const klagebetrag  = berechneKlagebetrag(positionen, hq, hqTyp);
  const rvgAussGes   = parseBetragOderNull(rvgAussergOv) ?? (rvgAussergData?.gesamt || 0);
  const swGerichtlich = klagebetrag + (mitSG && sgMind > 0 ? sgMind : 0);
  const istAmtsgericht = gericht && /amtsgericht/i.test(gericht.name || "");
  const lgWarnung = lgGrenzwert > 0 && swGerichtlich > lgGrenzwert && istAmtsgericht;
  const klaeger     = beklagte?.filter(b => b.rolle_klage === "klaeger") || [];
  const beklagteG   = kanonischeBeklagte(beklagte);

  const firmenOhneVertreter = ermittleFirmenOhneVertreter(beklagte);
  const keinPositionen = positionen.filter(p => p.checked).length === 0;
  const keinGericht    = !gericht;
  const keineBeklagten = beklagteG.length === 0;
  const antraegeFinal  = komponiereAntraege(antraegeText, gebuehrenText);
  const hatPlatzhalter = !!antraegeFinal && antraegeFinal.includes(ANTRAEGE_PLACEHOLDER);
  const gesperrt       = laedt || keinGericht || keinPositionen || keineBeklagten || firmenOhneVertreter.length > 0 || hatPlatzhalter;

  const aktLegLabel = { eigentum: "Eigentum", finanziert: "Finanziert", geleast: "Geleast" }[aktLegTyp] || aktLegTyp;
  const freigabeLabel = { freigabe: "Freigabeerklärung", bedingungen: "Aus Bedingungen", ungeklaert: "⚠ Ungeklärt" }[aktLegFreigabe] || "";

  const vorschauDaten = (akteId && vorschauCfgFn) ? vorschauCfgFn() : null;

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
      <TextVeraltetBadge sichtbar={antraegeVeraltet}
        onNeuGenerieren={onAntraegeNeuGenerieren} onBehalten={onAntraegeBehalten}
        autoText={antraegeAuto} aktuellerText={antraegeText} />
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
          wert={beklagteG.length > 0 ? beklagteG.map(b => b.versicherung || b.firma || b.name || "–").join(", ") : "— keine —"}
          warn={keineBeklagten} />
        <ZeileZusammenfassung icon="⚖" label="Klagebetrag"
          wert={fmtEuro(klagebetrag + (mitSG && sgMind > 0 ? sgMind : 0))} warn={keinPositionen} />
        <ZeileZusammenfassung icon="⏱" label="Zinsen ab"
          wert={wizardVerzugDatum ? `Verzugseintritt ${fmtDatumDe(wizardVerzugDatum)}` : "Rechtshängigkeit"} />
        <ZeileZusammenfassung icon="🏠" label="Aktivlegitimation"
          wert={aktLegFreigabe === "ungeklaert"
            ? `${aktLegLabel} – ⚠ ungeklärt`
            : `${aktLegLabel}${aktLegTyp !== "eigentum" ? ` · ${freigabeLabel}` : ""}`}
          warn={aktLegFreigabe === "ungeklaert"} />
        <ZeileZusammenfassung icon="⚖" label="Gerichtlicher Streitwert (Gegenstandswert)"
          wert={fmtEuro(swGerichtlich)} />
        <ZeileZusammenfassung icon="💶" label={`Nr. 2300 VV RVG außergerichtlich (SW: ${fmtEuro(swAusserg || 0)})`}
          wert={rvgAussGes > 0 ? fmtEuro(rvgAussGes) : "–"} warn={rvgAussGes === 0} />
      </div>

      {(keinGericht || keinPositionen || keineBeklagten || firmenOhneVertreter.length > 0 || aktLegFreigabe === "ungeklaert" || lgWarnung || hatPlatzhalter || !unfallort || !unfalldatum) && (
        <div style={{ marginBottom: "1rem" }}>
          {hatPlatzhalter && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Der Antragstext enthält noch den Platzhalter für die außergerichtlichen Anwaltsgebühren.
            Bitte Schritt 10 (Gebühren) aufrufen, damit der RVG-Antrag eingesetzt wird.
          </div>}
          {keinGericht && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Kein Gericht gewählt.
          </div>}
          {keinPositionen && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Keine Schadenpositionen ausgewählt.
          </div>}
          {keineBeklagten && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Keine Beklagten ausgewählt – bitte im Parteien-Bereich mindestens einen Beklagten anhaken.
          </div>}
          {firmenOhneVertreter.length > 0 && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6,
            display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <span>⚠ Firmen ohne Vertreter:</span>
            {firmenOhneVertreter.map((b, i) => {
              const fname = b.versicherung || b.firma;
              return (
                <span key={b.id || i} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <strong>{fname}</strong>
                  {onVertreterLookup && (
                    <button onClick={() => onVertreterLookup(b.id, fname)}
                      disabled={!!(vertreterLookup && vertreterLookup[b.id]?.laden)}
                      title="Vertretung online nachschlagen – ohne den Wizard zu verlassen"
                      style={{ background: T.cardBg, border: `1px solid ${T.red}`, borderRadius: 5,
                        padding: "1px 8px", cursor: "pointer", fontSize: "0.76rem", fontWeight: 600, color: T.red }}>
                      {vertreterLookup && vertreterLookup[b.id]?.laden ? "⟳ sucht …" : "🔍 Lookup"}
                    </button>
                  )}
                </span>
              );
            })}
          </div>}
          {aktLegFreigabe === "ungeklaert" && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.amber,
            padding: "7px 12px", background: `${T.amber}12`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Aktivlegitimation ungeklärt – der Abschnitt enthält keinen Auto-Text; Ihr Sachverhaltstext wird unverändert übernommen.
          </div>}
          {!unfallort && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.amber,
            padding: "7px 12px", background: `${T.amber}12`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Kein Unfallort in der Akte – die Einleitung nennt keinen Ort.
          </div>}
          {!unfalldatum && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.amber,
            padding: "7px 12px", background: `${T.amber}12`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Kein Unfalldatum in der Akte – die Einleitung nennt kein Datum.
          </div>}
          {lgWarnung && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: "#c05c00",
            padding: "7px 12px", background: "#c05c0015", borderRadius: 7, marginBottom: 6, border: "1px solid #c05c0030" }}>
            ⚠ Streitwert {fmtEuro(swGerichtlich)} überschreitet die LG-Grenze von {fmtEuro(lgGrenzwert)} – zuständig ist das <strong>Landgericht</strong>, nicht das Amtsgericht.
          </div>}
        </div>
      )}

      {fehler && (
        <div style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.red,
          padding: "8px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: "1rem" }}>
          {fehler}
        </div>
      )}

      {akteId && vorschauCfgFn && (
        <div style={{ marginBottom: "1rem", padding: "1rem 1.25rem",
          background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
            marginBottom: "0.75rem" }}>
            Gesamtvorschau
          </div>
          <KlageGesamtvorschau
            akteId={akteId}
            cfg={vorschauDaten.cfg}
            overrides={vorschauDaten.overrides}
            onEditAbschnitt={onVorschauEdit}
          />
        </div>
      )}

      <button onClick={onGenerieren} disabled={gesperrt}
        style={{
          width: "100%", padding: "14px 0",
          background: gesperrt ? T.border : T.accent,
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
            background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 8,
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
                    background: T.cardBg, transition: "background 0.1s" }}
                  onMouseEnter={e => e.currentTarget.style.background = T.surface}
                  onMouseLeave={e => e.currentTarget.style.background = T.cardBg}>
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
export const ANTRAEGE_PLACEHOLDER = "[Außergerichtliche Anwaltsgebühren – wird in Schritt 10 ergänzt]";

export function komponiereAntraege(antraegeText, gebuehrenText) {
  if (!antraegeText || !gebuehrenText) return antraegeText;
  if (!antraegeText.includes(ANTRAEGE_PLACEHOLDER)) return antraegeText;
  return antraegeText.replace(ANTRAEGE_PLACEHOLDER, gebuehrenText);
}

export function antraegeBasis(opts) {
  const o = opts || {};
  return JSON.stringify({
    pos: (o.positionen || []).filter(p => p.checked).map(p => [p.key, p.betrag]),
    mitSG: !!o.mitSG,
    sgMind: o.mitSG ? (o.sgMind ?? null) : null,
    bek: (o.beklagte || []).map(b => [b.id, b.checked !== false, b.rolle_klage || null]),
    weiblich: o.weiblich ?? null,
    zinsenAb: o.zinsenAb ?? null,
    verzug: o.verzug ?? null,
    unfalldatum: o.unfalldatum ?? null,
    mitFestSg: !!o.mitFestSg,
    mitFestSach: !!o.mitFestSach,
    hq: o.hq ?? 100,
    hqTyp: o.hqTyp ?? "gegnerisch",
  });
}

export function AntraegeSync({ step, opts, antraegeText, manuell, basisStand, onAntraegeText, onAntraegeBasis }) {
  const basisAktuell = antraegeBasis(opts);
  useEffect(() => {
    if (step < 6) return;
    if (!antraegeText || (!manuell && basisAktuell !== basisStand)) {
      onAntraegeText(baueAntraegeText(opts));
      onAntraegeBasis(basisAktuell);
    }
  }, [step, basisAktuell]); // eslint-disable-line
  return null;
}

export function TextVeraltetBadge({ sichtbar, onNeuGenerieren, onBehalten, autoText, aktuellerText }) {
  const [zeigeDiff, setZeigeDiff] = useState(false);
  if (!sichtbar) return null;
  const mitDiff = autoText !== undefined && aktuellerText !== undefined;
  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <div style={{ background: `${T.amber}12`, border: `1px solid ${T.amber}50`,
        borderRadius: 7, padding: "0.5rem 0.75rem",
        display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amberText, flex: 1 }}>
          ⚠ Text veraltet – Eingaben haben sich geändert.
        </span>
        {mitDiff && (
          <button onClick={() => setZeigeDiff(v => !v)}
            style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
              border: `1.5px solid ${T.border}`, background: T.cardBg,
              fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.navy }}>
            {zeigeDiff ? "✎ Ausblenden" : "⇄ Änderungen anzeigen"}
          </button>
        )}
        <button onClick={onNeuGenerieren}
          style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: T.cardBg,
            fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.navy }}>
          ↻ Neu generieren
        </button>
        <button onClick={onBehalten}
          style={{ padding: "5px 10px", borderRadius: 6, cursor: "pointer",
            border: `1.5px solid ${T.border}`, background: T.cardBg,
            fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.textMuted }}>
          Behalten
        </button>
      </div>
      {mitDiff && zeigeDiff && (
        <div style={{ marginTop: 6, display: "flex" }}>
          <DiffAnsicht autoText={autoText} aktuellerText={aktuellerText} />
        </div>
      )}
    </div>
  );
}

export function EntwurfStatusLeiste({ dirty, gespeichertAm, fehler, laeuft, onSpeichern }) {
  let status = "";
  let statusFarbe = T.textMuted;
  if (fehler) { status = fehler; statusFarbe = T.red; }
  else if (dirty) { status = "Ungespeicherte Änderungen"; statusFarbe = T.amberText; }
  else if (gespeichertAm) {
    status = `Gespeichert ${formatGespeichertAm(gespeichertAm)}`;
    statusFarbe = T.green;
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
      <button onClick={onSpeichern} disabled={laeuft}
        style={{ padding: "5px 10px", borderRadius: 6, cursor: laeuft ? "wait" : "pointer",
          border: `1.5px solid ${T.navy}`, background: T.cardBg,
          fontFamily: PLEX, fontSize: "0.78rem", fontWeight: 600, color: T.navy }}>
        💾 Entwurf speichern
      </button>
      {status && <span style={{ fontFamily: PLEX, fontSize: "0.78rem", color: statusFarbe }}>{status}</span>}
    </div>
  );
}

export function EntwurfAenderungenBox({ aenderungen, onSchliessen }) {
  if (!aenderungen || aenderungen.length === 0) return null;
  return (
    <div style={{ background: T.amberMid, border: `1px solid ${T.amber}`,
      borderRadius: 8, padding: "0.75rem 1rem", margin: "0.75rem 1.5rem 0",
      display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
      <div style={{ flex: 1 }}>
        <b style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.amberText }}>Seit dem Entwurf geändert:</b>
        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.2rem" }}>
          {aenderungen.map((a, i) => (
            <li key={i} style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amberText }}>{a}</li>
          ))}
        </ul>
      </div>
      <button onClick={onSchliessen} aria-label="✕"
        style={{ background: "none", border: "none", cursor: "pointer",
          fontSize: "1rem", lineHeight: 1, color: T.amberText }}>✕</button>
    </div>
  );
}

export function baueAntraegeText(opts) {
  const { positionen, mitSG, sgMind, beklagte, weiblich, zinsenAb, verzug,
          unfalldatum, mitFestSg, mitFestSach, hq = 100, hqTyp = "gegnerisch" } = opts;

  const klagebetrag = berechneKlagebetrag(positionen, hq, hqTyp);
  const g           = beklagtenGrammatik(beklagte);
  const kl_akk      = weiblich ? "die Klägerin"  : "den Kläger";  // Akkusativ: zahlen an…
  const kl_dat      = weiblich ? "der Klägerin"  : "dem Kläger";  // Dativ: verpflichtet…zu ersetzen
  const zinsDat     = zinsenAb === "verzug" && verzug ? `seit dem ${fmtDatumDe(verzug)}` : "seit Rechtshängigkeit";
  const udStr       = unfalldatum || "TT.MM.JJJJ";
  const fNr         = (n) => n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

  const antraege = [];

  // 1. Hauptantrag
  antraege.push(
    `${g.verurteilt}, an ${kl_akk} ${fNr(klagebetrag)} ` +
    `nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz ` +
    `${zinsDat} zu zahlen.`
  );

  // 2. Schmerzensgeld
  if (mitSG) {
    if (sgMind > 0) {
      antraege.push(
        `${g.verurteilt}, an ${kl_akk} ein angemessenes, ` +
        `vom Gericht festzulegendes Schmerzensgeld zu zahlen, wobei die Höhe nicht ` +
        `weniger als ${fNr(sgMind)} betragen sollte, nebst Zinsen von 5 Prozentpunkten ` +
        `über dem Basiszinssatz ${zinsDat}.`
      );
    } else {
      antraege.push(
        `${g.verurteilt}, an ${kl_akk} ein angemessenes, ` +
        `vom Gericht nach billigem Ermessen festzulegendes Schmerzensgeld zu zahlen, ` +
        `nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz ${zinsDat}.`
      );
    }
  }

  // 3. Feststellungsantrag Personenschaden
  if (mitSG && mitFestSg) {
    antraege.push(
      `Es wird festgestellt, dass ${g.verpflichtet}, ` +
      `${kl_dat} sämtliche künftigen materiellen und immateriellen Schäden zu ersetzen, ` +
      `die aus dem Unfallereignis vom ${udStr} noch entstehen werden, soweit Ansprüche ` +
      `nicht auf Sozialversicherungsträger oder sonstige Dritte übergegangen sind oder ` +
      `noch übergehen werden.`
    );
  }

  // 4. Feststellungsantrag Sachschaden
  if (mitFestSach) {
    antraege.push(
      `Es wird festgestellt, dass ${g.verpflichtet}, ` +
      `${kl_dat} sämtliche weiteren materiellen Schäden zu ersetzen, die aus dem ` +
      `Unfallereignis vom ${udStr} noch entstehen werden.`
    );
  }

  // Platzhalter für RVG-Antrag (Step 9)
  antraege.push(ANTRAEGE_PLACEHOLDER);

  // Kostentragung
  antraege.push(g.kosten);

  return antraege.map((t, i) => `${i + 1}.\t${t}`).join("\n\n");
}

export function StepAntraege({ positionen, mitSG, sgMind, beklagte, weiblich,
                        zinsenAb, verzug, unfalldatum,
                        mitFestSg, onMitFestSg, mitFestSach, onMitFestSach,
                        antraegeText, onAntraegeText, onAntraegeManuell, gebuehrenText,
                        antraegeVeraltet, onNeuGenerieren, onBehalten, antraegeAuto,
                        hq = 100, hqTyp = "gegnerisch" }) {
  const klagebetrag   = berechneKlagebetrag(positionen, hq, hqTyp);
  const sgGesamt      = mitSG && sgMind > 0 ? klagebetrag + sgMind : klagebetrag;
  const zinsDat       = zinsenAb === "verzug" && verzug ? `seit dem ${fmtDatumDe(verzug)}` : "seit Rechtshängigkeit";
  const antraegeFinal  = komponiereAntraege(antraegeText, gebuehrenText);
  const hatPlatzhalter = !!antraegeFinal && antraegeFinal.includes(ANTRAEGE_PLACEHOLDER);

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
            {fmtEuro(sgGesamt)}
          </div>
          {mitSG && sgMind > 0 && (
            <div style={{ fontFamily: PLEX, fontSize: "0.75rem", color: T.textMuted, marginTop: 2 }}>
              Sachschaden {fmtEuro(klagebetrag)} + SG {fmtEuro(sgMind)}
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

        <button onClick={onNeuGenerieren}
          style={{ padding: "9px 12px", borderRadius: 8, cursor: "pointer",
            border: `1.5px solid ${T.navy}`, background: `${T.navy}08`,
            fontFamily: PLEX, fontSize: "0.85rem", fontWeight: 600, color: T.navy, marginTop: "auto" }}>
          ↻ Anträge neu generieren
        </button>

        {hatPlatzhalter ? (
          <div style={{ background: `${T.amber}12`, border: `1px solid ${T.amber}50`,
            borderRadius: 7, padding: "0.5rem 0.75rem",
            fontFamily: PLEX, fontSize: "0.76rem", color: T.amberText }}>
            ⏳ RVG-Antrag: Platzhalter aktiv – wird in Schritt 10 ersetzt.
          </div>
        ) : (
          <div style={{ background: `${T.green}10`, border: `1px solid ${T.green}40`,
            borderRadius: 7, padding: "0.5rem 0.75rem",
            fontFamily: PLEX, fontSize: "0.76rem", color: T.green }}>
            ✓ RVG-Antrag eingefügt (Schritt 10).
          </div>
        )}
      </div>

      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <TextVeraltetBadge sichtbar={antraegeVeraltet} onNeuGenerieren={onNeuGenerieren} onBehalten={onBehalten}
          autoText={antraegeAuto} aktuellerText={antraegeText} />
        <EditorMitDiff autoText={antraegeAuto} text={antraegeText}
          onText={val => { onAntraegeManuell(true); onAntraegeText(val); }} />
      </div>
    </div>
  );
}

// ── Step 9: Außergerichtliche Gebühren ─────────────────────────────────────────

const VG_OPTIONEN = [
  { value: "keine",    label: "Kein Personenschaden" },
  { value: "leicht",   label: "Leicht (HWS, AU ≤ 14 Tage)" },
  { value: "schwer",   label: "Schwer (Knochenbruch, OP)" },
  { value: "schwerst", label: "Schwerst / Dauerschaden" },
];

export function StepGebuehren({ swAusserg, rvgAussergData, onRvgAussergData,
                         rvgAussergOv, onRvgAussergOv,
                         rvgBereitsGezahlt, onRvgBereitsGezahlt,
                         gebuehrenText, onGebuehrenText,
                         gebuehrenManuell, onGebuehrenManuell,
                         beklagte, weiblich,
                         zinsenAb, verzug,
                         antraegeText, onAntraegeText,
                         gespeichertGb, onGespeichertGb, akteId }) {
  const g            = beklagtenGrammatik(beklagte);
  const kl_akk       = weiblich ? "die Klägerin" : "den Kläger";
  const zinsDat      = zinsenAb === "verzug" && verzug ? `seit dem ${fmtDatumDe(verzug)}` : "seit Rechtshängigkeit";
  const rvgGesamt    = parseBetragOderNull(rvgAussergOv) ?? (rvgAussergData?.gesamt || 0);
  const bereitsGez   = parseFloat(rvgBereitsGezahlt) || 0;
  const rvgNetto     = Math.max(0, rvgGesamt - bereitsGez);

  // PRD-28: Inline-Assistent State (Modus B)
  const [gbAntworten, setGbAntworten]   = useState({});
  const [gbAnalysiert, setGbAnalysiert] = useState(false);
  const [gbVorschlag, setGbVorschlag]   = useState(null);
  const [gbAnalyseLaedt, setGbAnalyseLaedt] = useState(false);
  const [gbSpeichertLaedt, setGbSpeichertLaedt] = useState(false);

  const gbAnalysieren = async () => {
    if (!akteId) return;
    setGbAnalyseLaedt(true);
    try {
      const res = await apiGebuehren.analysieren(akteId, {
        ...gbAntworten,
        streitwert: swAusserg,
      });
      setGbVorschlag(res.vorschlag);
      const neuerFaktor = res.vorschlag?.faktor ?? 1.3;
      // RVG mit neuem Faktor vom Backend neu berechnen
      onRvgAussergData({ ...res.rvg, faktor: neuerFaktor });
      setGbAnalysiert(true);
    } catch (e) {
      // Stille Fehlerbehandlung – Anwalt sieht leere Tabelle
    } finally {
      setGbAnalyseLaedt(false);
    }
  };

  const gbUebernehmen = async () => {
    if (!akteId || !gbVorschlag) return;
    setGbSpeichertLaedt(true);
    try {
      const faktorFinal = rvgAussergData?.faktor ?? gbVorschlag.faktor;
      await apiGebuehren.speichern(akteId, {
        kriterien:       gbAntworten,
        vuregel_id:      gbVorschlag.vuregel_id,
        faktor_vorschlag:gbVorschlag.faktor,
        faktor_final:    faktorFinal,
        begruendung:     gbVorschlag.begruendung,
      });
      onGespeichertGb && onGespeichertGb({
        faktor_final: faktorFinal,
        vuregel_id:   gbVorschlag.vuregel_id,
        begruendung:  gbVorschlag.begruendung,
      });
    } catch {
      // Nicht kritisch – Wizard läuft weiter
    } finally {
      setGbSpeichertLaedt(false);
    }
  };

  function baueGebuehrenAntrag(betrag) {
    const b = betrag !== undefined ? betrag : rvgNetto;
    return (
      `${g.verurteilt}, an ${kl_akk} weitere ` +
      `${b.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} € ` +
      `nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz ` +
      `${zinsDat} zu zahlen.`
    );
  }

  useEffect(() => {
    if (gebuehrenManuell) return;
    if (rvgGesamt > 0) onGebuehrenText(baueGebuehrenAntrag());
  }, [rvgGesamt, bereitsGez]); // eslint-disable-line

  function handleGebuehrenReset() {
    onGebuehrenManuell(false);
    onGebuehrenText(baueGebuehrenAntrag());
  }

  const fNr = (v) => (v || 0).toLocaleString("de-DE",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "stretch" }}>
      <div style={{ flex: "0 0 260px", display: "flex", flexDirection: "column", gap: "0.9rem" }}>
        <AbschnittLabel text="Vorgerichtliche Kosten" />

        {/* ── Modus A: Gebühren-Tab bereits ausgefüllt ── */}
        {gespeichertGb && (
          <div style={{ background: T.greenBg, border: `1px solid ${T.green}44`,
                        borderRadius: 8, padding: "0.6rem 0.85rem",
                        fontFamily: PLEX, fontSize: "0.78rem" }}>
            <div style={{ fontWeight: 700, color: T.green, marginBottom: 3 }}>
              ✓ Aus Gebühren-Tab übernommen
            </div>
            <div style={{ color: T.textMid }}>
              {gespeichertGb.vuregel_id && (
                <span style={{ fontWeight: 600 }}>{gespeichertGb.vuregel_id} · </span>
              )}
              Faktor {String(gespeichertGb.faktor_final || 1.3).replace(".", ",")}
            </div>
            <div style={{ color: T.textFaint, marginTop: 3, fontSize: "0.72rem" }}>
              Zum Ändern: Tab „Gebühren" öffnen
            </div>
          </div>
        )}

        {/* ── Modus B: Inline-Assistent (kein gespeicherter Eintrag) ── */}
        {!gespeichertGb && !gbAnalysiert && (
          <div style={{ background: T.amberBg, border: `1px solid #f59e0b44`,
                        borderRadius: 8, padding: "0.75rem 0.85rem",
                        fontFamily: PLEX, fontSize: "0.78rem" }}>
            <div style={{ fontWeight: 700, color: T.amberText, marginBottom: 6 }}>
              Gebühren-Analyse
            </div>
            <div style={{ marginBottom: 8, color: T.textMid }}>
              Verletzungsgrad des Mandanten?
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
              {VG_OPTIONEN.map(o => (
                <button key={o.value}
                  onClick={() => setGbAntworten(a => ({ ...a, verletzungsgrad: o.value }))}
                  style={{
                    padding: "4px 10px", border: `1px solid`,
                    borderColor: gbAntworten.verletzungsgrad === o.value ? T.navy : T.border,
                    borderRadius: 6, cursor: "pointer", fontSize: "0.78rem",
                    background: gbAntworten.verletzungsgrad === o.value ? T.navy : T.surface,
                    color: gbAntworten.verletzungsgrad === o.value ? "#fff" : T.textMid,
                    fontFamily: PLEX, textAlign: "left",
                  }}>
                  {o.label}
                </button>
              ))}
            </div>
            <button
              onClick={gbAnalysieren}
              disabled={gbAnalyseLaedt}
              style={{ width: "100%", padding: "5px 0", background: T.navy, color: "#fff",
                       border: "none", borderRadius: 6, cursor: "pointer",
                       fontSize: "0.82rem", fontWeight: 700, fontFamily: PLEX }}>
              {gbAnalyseLaedt ? "…" : "Analysieren →"}
            </button>
          </div>
        )}

        {/* Ergebnis nach Modus-B-Analyse */}
        {!gespeichertGb && gbAnalysiert && gbVorschlag && (
          <div style={{ background: T.surface, border: `1px solid ${T.borderSoft}`,
                        borderRadius: 8, padding: "0.6rem 0.85rem",
                        fontFamily: PLEX, fontSize: "0.78rem" }}>
            <div style={{ fontWeight: 700, color: T.navy, marginBottom: 3 }}>
              {gbVorschlag.vuregel_id} · Faktor {String(gbVorschlag.faktor).replace(".", ",")}
            </div>
            <div style={{ color: T.textFaint, fontSize: "0.72rem", marginBottom: 8,
                          lineHeight: 1.4 }}>
              {gbVorschlag.leitentscheidung}
            </div>
            <button
              onClick={gbUebernehmen}
              disabled={gbSpeichertLaedt}
              style={{ width: "100%", padding: "4px 0", background: T.green, color: "#fff",
                       border: "none", borderRadius: 6, cursor: "pointer",
                       fontSize: "0.78rem", fontWeight: 700, fontFamily: PLEX }}>
              {gbSpeichertLaedt ? "…" : "✓ Speichern"}
            </button>
          </div>
        )}

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
            background: T.cardBg, border: `1px solid ${T.borderSoft}`, borderRadius: 8,
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
            <div style={{ fontSize: "0.68rem", color: T.textFaint, textAlign: "right", marginTop: 5 }}>
              § 13 RVG – {rvgAussergData.rvg_version === "2025"
                ? "2. KostRMoG (ab 01.06.2025)"
                : "KostRÄG 2021 (bis 31.05.2025)"}
            </div>
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
                if (e.target.value) onGebuehrenText(baueGebuehrenAntrag(
                  Math.max(0, parseFloat(e.target.value) - bereitsGez)
                ));
              }}
              placeholder={rvgAussergData ? rvgAussergData.gesamt.toFixed(2) : ""}
              style={{ width: 120, padding: "6px 8px",
                border: `1.5px solid ${T.border}`, borderRadius: 7,
                fontFamily: MONO, fontSize: "0.9rem", outline: "none",
                background: T.cardBg, color: T.navy }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>€</span>
          </div>
        </div>

        <div>
          <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.textMuted, marginBottom: 4 }}>
            Bereits gezahlt (abziehen)
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="number" min="0" step="0.01"
              value={rvgBereitsGezahlt}
              onChange={e => onRvgBereitsGezahlt(e.target.value)}
              placeholder="0,00"
              style={{ width: 120, padding: "6px 8px",
                border: `1.5px solid ${bereitsGez > 0 ? T.amber : T.border}`, borderRadius: 7,
                fontFamily: MONO, fontSize: "0.9rem", outline: "none",
                background: T.cardBg, color: T.navy }} />
            <span style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.textMuted }}>€</span>
          </div>
          {bereitsGez > 0 && (
            <div style={{ fontFamily: MONO, fontSize: "0.72rem", color: T.navy,
              fontWeight: 700, marginTop: 4 }}>
              Klageanteil: {fNr(rvgNetto)}
            </div>
          )}
        </div>

        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", color: T.textFaint }}>
          Text erscheint als Klageantrag. Wird automatisch in Schritt 6 eingefügt.
        </div>

        <button
          onClick={handleGebuehrenReset}
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

      <EditorMitDiff autoText={rvgGesamt > 0 && gebuehrenText ? baueGebuehrenAntrag() : gebuehrenText}
        text={gebuehrenText}
        onText={val => { onGebuehrenManuell(true); onGebuehrenText(val); }} />
    </div>
  );
}

export function SchliessenGuardDialog({ onEntwurfSpeichern, onClose, onZurueck }) {
  const [laeuft, setLaeuft] = useState(false);
  const speichernUndSchliessen = async () => {
    setLaeuft(true);
    const ok = await onEntwurfSpeichern();
    setLaeuft(false);
    if (ok) onClose();
    else onZurueck();
  };
  const knopf = {
    padding: "9px 16px", borderRadius: 8, cursor: laeuft ? "wait" : "pointer",
    fontFamily: PLEX, fontSize: "0.875rem", fontWeight: 600,
  };
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9500 }}>
      <div style={{ background: T.cardBg, borderRadius: 12, padding: "1.75rem",
        maxWidth: "27rem", width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 0.6rem", fontFamily: PLEX, fontSize: "1.1rem",
          fontWeight: 700, color: T.navy }}>
          Wizard schließen?
        </h3>
        <p style={{ margin: 0, fontFamily: PLEX, fontSize: "0.9rem", color: T.text, lineHeight: 1.55 }}>
          Es gibt <strong>ungespeicherte Änderungen</strong> am Entwurf. Beim Schließen ohne
          Speichern gehen diese verloren.
        </p>
        <div style={{ display: "flex", gap: "0.6rem", justifyContent: "flex-end",
          marginTop: "1.5rem", flexWrap: "wrap" }}>
          <button onClick={onZurueck} disabled={laeuft}
            style={{ ...knopf, border: `1.5px solid ${T.border}`, background: T.cardBg, color: T.text }}>
            Zurück zum Wizard
          </button>
          <button onClick={onClose} disabled={laeuft}
            style={{ ...knopf, border: `1.5px solid ${T.red}`, background: T.cardBg, color: T.red }}>
            Verwerfen &amp; schließen
          </button>
          <button onClick={speichernUndSchliessen} disabled={laeuft}
            style={{ ...knopf, border: "none", background: T.navy, color: "#fff" }}>
            💾 Speichern &amp; schließen
          </button>
        </div>
      </div>
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
  sachverhaltManuell, onSachverhaltManuell,
  auslandsunfall, onAuslandsunfall,
  mandantVorsteuer,
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
  wizardAntraegeManuell, onAntraegeManuell,
  wizardAntraegeBasis, onAntraegeBasis,
  // Step 7 (Rechtliche Würdigung)
  wizardHq, onWizardHq, wizardHqTyp, onWizardHqTyp, wizardHb, onWizardHb,
  wizardRwText, onWizardRwText, kuerzungsarten,
  onKiHaftung, kiLaedt,
  wizardEinwaendeBlock, onWizardEinwaendeBlock,
  // Step 8 (Verzug)
  wizardVerzugText, onWizardVerzugText,
  wizardVerzugDatum, onWizardVerzugDatum,
  wizardVerzugDokDatum, onWizardVerzugDokDatum,
  wizardVerzugManuell, onWizardVerzugManuell,
  verzugDokListe, verzugDokId, onVerzugDokId,
  // Step 9 (Außergerichtl. Gebühren)
  swAusserg,
  wizardRvgAussergData, onRvgAussergData,
  wizardRvgAussergOv, onRvgAussergOv,
  wizardRvgBereitsGezahlt, onRvgBereitsGezahlt,
  wizardGebuehrenText, onGebuehrenText,
  wizardGebuehrenManuell, onGebuehrenManuell,
  gespeichertGb, onGespeichertGb,
  wizardAkteId,
  // Shared
  beklagte, zinsenAb,
  lgGrenzwert,
  onVertreterLookup, vertreterLookup,
  // Generieren
  laedt, onGenerieren, fehler,
  // Gesamtvorschau (Schritt 11)
  akteId, vorschauCfgFn, onVorschauEdit,
  // Entwurf speichern
  onEntwurfSpeichern, entwurfDirty, entwurfGespeichertAm, entwurfFehler, entwurfLaeuft,
  entwurfAenderungen, onAenderungenGelesen,
}) {
  const backdropRef = useRef(null);
  const [zeigeSchliessenGuard, setZeigeSchliessenGuard] = useState(false);
  const schliessenAnfordern = () => {
    if (entwurfDirty) setZeigeSchliessenGuard(true);
    else onClose();
  };

  const [standardtexte, setStandardtexte] = useState(null);
  useEffect(() => {
    apiStandardtexte.aufgeloest()
      .then(r => setStandardtexte(r.texte))
      .catch(() => setStandardtexte(null));
  }, []);

  useEffect(() => {
    const handler = e => { if (e.key === "Escape" && !laedt) schliessenAnfordern(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [laedt, schliessenAnfordern]);

  const klaegerObj = beklagte?.find(b => b.rolle_klage === "klaeger");
  const klaeger    = (klaegerObj?.anrede || "").toLowerCase() === "frau" ? "Die Klägerin" : "Der Kläger";
  const weiblich   = klaeger.startsWith("Die");

  const gesamtReg = (abrechnungen || []).reduce((s, ab) => s + (parseFloat(ab.gesamt_reguliert) || 0), 0);
  const grundhaftungsText = standardtexte
    ? buildRwVorschau(wizardHb, wizardHq, gesamtReg, weiblich, wizardHqTyp, beklagte, standardtexte)
    : "";

  const antraegeOpts = {
    positionen, mitSG, sgMind, beklagte, weiblich,
    zinsenAb, verzug: wizardVerzugDatum, unfalldatum,
    mitFestSg: wizardMitFestSg, mitFestSach: wizardMitFestSach,
    hq: wizardHq, hqTyp: wizardHqTyp,
  };
  const antraegeVeraltet = wizardAntraegeManuell && antraegeBasis(antraegeOpts) !== wizardAntraegeBasis;
  const antraegeAuto = baueAntraegeText(antraegeOpts);
  const hatPlatzhalter = komponiereAntraege(wizardAntraegeText, wizardGebuehrenText)
    .includes(ANTRAEGE_PLACEHOLDER);
  const statusCtx = { step, maxStep: wizardMaxStep, gerichtBestaetigt, positionen,
    beklagte, antraegeVeraltet, hatPlatzhalter };
  const antraegeNeuGenerieren = () => {
    onAntraegeText(baueAntraegeText(antraegeOpts));
    onAntraegeBasis(antraegeBasis(antraegeOpts));
    onAntraegeManuell(false);
  };
  const antraegeBehalten = () => onAntraegeBasis(antraegeBasis(antraegeOpts));

  const kannWeiter = () => !schrittBlockiert(step, { gerichtBestaetigt, positionen });
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
        onClick={e => { if (e.target === backdropRef.current && !laedt) schliessenAnfordern(); }}
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
          background: T.cardBg, borderRadius: 16,
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
            <button onClick={() => !laedt && schliessenAnfordern()} disabled={laedt}
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: "1.3rem", color: T.textMuted, padding: "4px 8px",
                borderRadius: 6, lineHeight: 1, opacity: laedt ? 0.3 : 1,
              }}>✕</button>
          </div>

          <EntwurfAenderungenBox aenderungen={entwurfAenderungen}
            onSchliessen={onAenderungenGelesen} />

          {/* Body */}
          <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem" }}>
            {standardtexte === null && (
              <div style={{
                background: `${T.amber}10`, border: `1.5px solid ${T.amber}50`,
                borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1rem",
                fontFamily: PLEX, fontSize: "0.85rem", color: T.amberText,
              }}>
                Standardtexte werden geladen … Sollte diese Meldung bestehen bleiben, bitte Seite neu laden.
              </div>
            )}
            <Fortschrittsbalken step={step} maxStep={wizardMaxStep} onStepChange={onStepChange}
              springenErlaubt={(nr) => kannSpringen(nr, step, { gerichtBestaetigt, positionen })}
              statusFuer={(nr) => schrittStatus(nr, statusCtx)} />

            <AntraegeSync step={step} opts={antraegeOpts}
              antraegeText={wizardAntraegeText} manuell={wizardAntraegeManuell}
              basisStand={wizardAntraegeBasis}
              onAntraegeText={onAntraegeText} onAntraegeBasis={onAntraegeBasis} />

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
              <StepRubrum beklagte={beklagte} onClose={onClose}
                onVertreterLookup={onVertreterLookup} vertreterLookup={vertreterLookup} />
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
                sachverhaltManuell={sachverhaltManuell}
                onSachverhaltManuell={onSachverhaltManuell}
                vorsteuer={mandantVorsteuer}
                unfalldatum={unfalldatum}
                unfallort={unfallort}
                beklagte={beklagte}
                auslandsunfall={auslandsunfall}
                onAuslandsunfall={onAuslandsunfall}
                auslandsunfallText={standardtexte?.sachverhalt_auslandsunfall}
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
                az={wizardAkteId}
                kl_nom={klaeger}
                hq={wizardHq}             hqTyp={wizardHqTyp}
              />
            )}

            {step === 6 && (
              <StepAntraege
                positionen={positionen}   mitSG={mitSG}   sgMind={sgMind}
                beklagte={beklagte}       weiblich={weiblich}
                zinsenAb={zinsenAb}       verzug={wizardVerzugDatum}
                unfalldatum={unfalldatum}
                mitFestSg={wizardMitFestSg}   onMitFestSg={onMitFestSg}
                mitFestSach={wizardMitFestSach} onMitFestSach={onMitFestSach}
                antraegeText={wizardAntraegeText} onAntraegeText={onAntraegeText}
                onAntraegeManuell={onAntraegeManuell}
                gebuehrenText={wizardGebuehrenText}
                antraegeVeraltet={antraegeVeraltet}
                antraegeAuto={antraegeAuto}
                onNeuGenerieren={antraegeNeuGenerieren}
                onBehalten={antraegeBehalten}
                hq={wizardHq}             hqTyp={wizardHqTyp}
              />
            )}

            {step === 7 && (
              <StepRw
                hq={wizardHq}             onHq={onWizardHq}
                hqTyp={wizardHqTyp}       onHqTyp={onWizardHqTyp}
                hb={wizardHb}             onHb={onWizardHb}
                abrechnungen={abrechnungen}
                weiblich={weiblich}
                rwText={wizardRwText}     onRwText={onWizardRwText}
                beklagte={beklagte}
                onKiHaftung={onKiHaftung} kiLaedt={kiLaedt}
                onEinwaendeReset={() => onWizardEinwaendeBlock("")}
                standardtexte={standardtexte}
              />
            )}

            {step === 8 && (
              <StepEinwaende
                abrechnungen={abrechnungen}
                kuerzungsarten={kuerzungsarten}
                beklagte={beklagte}
                rwText={wizardRwText}       onRwText={onWizardRwText}
                einwaendeBlock={wizardEinwaendeBlock}
                onEinwaendeBlock={onWizardEinwaendeBlock}
                grundhaftungsText={grundhaftungsText}
                platzhalterKontext={genusKontext(weiblich)}
              />
            )}

            {step === 9 && (
              <StepVerzug
                zinsenAb={zinsenAb}
                weiblich={weiblich}
                wizardVerzugDatum={wizardVerzugDatum}
                onWizardVerzugDatum={onWizardVerzugDatum}
                wizardVerzugDokDatum={wizardVerzugDokDatum}
                onWizardVerzugDokDatum={onWizardVerzugDokDatum}
                wizardVerzugText={wizardVerzugText}
                onWizardVerzugText={onWizardVerzugText}
                manuelleBearbeitung={wizardVerzugManuell}
                onManuelleBearbeitung={onWizardVerzugManuell}
                verzugDokListe={verzugDokListe}
                verzugDokId={verzugDokId}       onVerzugDokId={onVerzugDokId}
                standardtexte={standardtexte}
              />
            )}

            {step === 10 && (
              <StepGebuehren
                swAusserg={swAusserg}
                rvgAussergData={wizardRvgAussergData} onRvgAussergData={onRvgAussergData}
                rvgAussergOv={wizardRvgAussergOv}     onRvgAussergOv={onRvgAussergOv}
                rvgBereitsGezahlt={wizardRvgBereitsGezahlt} onRvgBereitsGezahlt={onRvgBereitsGezahlt}
                gebuehrenText={wizardGebuehrenText}   onGebuehrenText={onGebuehrenText}
                gebuehrenManuell={wizardGebuehrenManuell} onGebuehrenManuell={onGebuehrenManuell}
                beklagte={beklagte}                   weiblich={weiblich}
                zinsenAb={zinsenAb}                   verzug={wizardVerzugDatum}
                antraegeText={wizardAntraegeText}     onAntraegeText={onAntraegeText}
                gespeichertGb={gespeichertGb}         onGespeichertGb={onGespeichertGb}
                akteId={wizardAkteId}
              />
            )}

            {step === 11 && (
              <StepZusammenfassung
                gericht={gericht}           beklagte={beklagte}
                positionen={positionen}     mitSG={mitSG}          sgMind={sgMind}
                rvgAussergData={wizardRvgAussergData} rvgAussergOv={wizardRvgAussergOv}
                aktLegTyp={aktLegTyp}       aktLegFreigabe={aktLegFreigabe}
                zinsenAb={zinsenAb}         wizardVerzugDatum={wizardVerzugDatum}
                laedt={laedt}               onGenerieren={onGenerieren}
                fehler={fehler}
                akteId={akteId}             vorschauCfgFn={vorschauCfgFn}
                onVorschauEdit={onVorschauEdit}
                lgGrenzwert={lgGrenzwert}   swAusserg={swAusserg}
                antraegeText={wizardAntraegeText}
                gebuehrenText={wizardGebuehrenText}
                antraegeVeraltet={antraegeVeraltet}
                antraegeAuto={antraegeAuto}
                onAntraegeNeuGenerieren={antraegeNeuGenerieren}
                onAntraegeBehalten={antraegeBehalten}
                onVertreterLookup={onVertreterLookup} vertreterLookup={vertreterLookup}
                unfallort={unfallort}       unfalldatum={unfalldatum}
                hq={wizardHq}               hqTyp={wizardHqTyp}
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
                border: `1.5px solid ${T.border}`, background: T.cardBg,
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

            <EntwurfStatusLeiste dirty={entwurfDirty} gespeichertAm={entwurfGespeichertAm}
              fehler={entwurfFehler} laeuft={entwurfLaeuft} onSpeichern={onEntwurfSpeichern} />

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

      {zeigeSchliessenGuard && (
        <SchliessenGuardDialog
          onEntwurfSpeichern={onEntwurfSpeichern}
          onClose={() => { setZeigeSchliessenGuard(false); onClose(); }}
          onZurueck={() => setZeigeSchliessenGuard(false)}
        />
      )}

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
