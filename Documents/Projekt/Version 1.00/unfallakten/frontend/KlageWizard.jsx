/**
 * KlageWizard.jsx – PRD-24
 * ─────────────────────────────────────────────────────────────────
 * 3-Step Modal-Wizard für die Klageschrift-Generierung.
 * Reine Präsentationskomponente – alle States in KlageSection.
 *
 * Step 1: Aktivlegitimation (2-spaltig: Auswahl + Live-Vorschau)
 * Step 2: Schadenpositionen + Personenschaden
 * Step 3: Zusammenfassung + Generieren
 *
 * Design: IBM Plex Sans/Mono, Navy dominant, Gold als Akzent,
 *         Dokument-Card Schreibmaschinen-Ästhetik, slide/fade-Transition
 */

import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";

// ── Konstanten ─────────────────────────────────────────────────────────────────

const STEPS = [
  { nr: 1, label: "Aktivlegitimation" },
  { nr: 2, label: "Schadenpositionen" },
  { nr: 3, label: "Vorschau & Generieren" },
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
 * Aktivlegitimations-Vorschautext – client-seitige Spiegelung von
 * klage_service.get_aktivlegitimation_text(). Nur für Vorschau,
 * nicht für die eigentliche Generierung maßgeblich.
 */
function buildVorschauText(typ, freigabe, datum, mkz, mandantIstFahrer, klaeger = "Der Kläger") {
  const mkzSatz = mkz ? ` mit dem amtlichen Kennzeichen ${mkz}` : "";
  const weiblich = klaeger.startsWith("Die");
  const eigen    = weiblich ? "Eigentümerin" : "Eigentümer";
  const pronAkk  = weiblich ? "sie" : "ihn";

  if (typ === "eigentum") {
    let text = `${klaeger} ist ${eigen} des Fahrzeugs${mkzSatz}.`;
    if (mandantIstFahrer) {
      text += `\nFür ${pronAkk} streitet bereits § 1006 BGB, da ${klaeger} zum Zeitpunkt des Unfalls das Fahrzeug selbst fuhr.`;
    }
    return text;
  }

  if (freigabe === "ungeklaert") return null; // Fall G

  const finTyp       = typ === "finanziert" ? "Bank" : "Leasinggeberin";
  const eigentuemer  = typ === "finanziert" ? "finanzierenden Bank" : "Leasinggeberin";
  const bedingTyp    = typ === "finanziert" ? "Finanzierungsbedingungen" : "Leasingbedingungen";

  const basis = `Das Fahrzeug${mkzSatz} befindet sich im Eigentum der ${eigentuemer}. ${klaeger} ist jedoch aufgrund `;

  if (freigabe === "freigabe") {
    const datumStr = datum || "TT.MM.JJJJ";
    return (
      basis +
      `der vorliegenden Freigabeerklärung der ${finTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: Freigabeerklärung vom ${datumStr}, Anlage K1`
    );
  }
  // bedingungen
  return (
    basis +
    `der ${bedingTyp} aktivlegitimiert, den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen.\n\nBEWEIS: ${bedingTyp} in Kopie, Anlage K1`
  );
}

// ── Teilkomponenten ────────────────────────────────────────────────────────────

function Fortschrittsbalken({ step }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "1.75rem" }}>
      {STEPS.map((s, i) => {
        const aktiv    = s.nr === step;
        const erledigt = s.nr < step;
        return (
          <React.Fragment key={s.nr}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              {/* Kreis */}
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: erledigt ? T.navy : aktiv ? T.gold : T.surface,
                border: `2px solid ${erledigt ? T.navy : aktiv ? T.gold : T.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: MONO, fontSize: "0.8rem", fontWeight: 700,
                color: (erledigt || aktiv) ? "#fff" : T.textMuted,
                transition: "all 0.25s",
                boxShadow: aktiv ? `0 0 0 4px ${T.gold}28` : "none",
              }}>
                {erledigt ? "✓" : s.nr}
              </div>
              {/* Label */}
              <div style={{
                fontFamily: PLEX, fontSize: "0.72rem", fontWeight: aktiv ? 700 : 400,
                color: aktiv ? T.gold : erledigt ? T.navy : T.textMuted,
                marginTop: 5, textAlign: "center", whiteSpace: "nowrap",
                transition: "color 0.25s",
              }}>
                {s.label}
              </div>
            </div>
            {/* Verbindungslinie */}
            {i < STEPS.length - 1 && (
              <div style={{
                height: 2, flex: 1, marginBottom: 18,
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

/** Stilisierte Dokument-Card für die Aktivlegitimations-Vorschau */
function DokumentCard({ text, warnung }) {
  if (warnung) {
    return (
      <div style={{
        flex: 1, background: `${T.amber}10`,
        border: `1.5px solid ${T.amber}50`, borderRadius: 10,
        padding: "1.25rem", display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 8,
        minHeight: 160,
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
      minHeight: 160,
    }}>
      {/* Dezentes Linien-Muster */}
      <div style={{
        position: "absolute", inset: 0, opacity: 0.04,
        backgroundImage: "repeating-linear-gradient(0deg, #000 0px, #000 1px, transparent 1px, transparent 24px)",
        pointerEvents: "none",
      }} />
      <div style={{ position: "relative" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.68rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
          marginBottom: "0.75rem" }}>
          Vorschau Klageschrift
        </div>
        <div style={{ fontFamily: MONO, fontSize: "0.825rem", color: "#2d2a1e",
          lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
          {text || <span style={{ color: T.textFaint, fontStyle: "italic" }}>Kein Text für diesen Fall.</span>}
        </div>
      </div>
    </div>
  );
}

// ── Steps ──────────────────────────────────────────────────────────────────────

function Step1({ aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
                 aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
                 klaeger = "Der Kläger" }) {

  const brauchtFreigabe = aktLegTyp !== "eigentum";
  const vorschauText    = buildVorschauText(
    aktLegTyp, aktLegFreigabe, aktLegDatum, mandantKz, mandantIstFahrer, klaeger
  );

  return (
    <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
      {/* ── Linke Spalte: Optionen ── */}
      <div style={{ flex: "0 0 280px" }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.75rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.75rem" }}>
          Fahrzeugeigentum
        </div>
        <RadioOption checked={aktLegTyp === "eigentum"} onChange={() => onAktLegTyp("eigentum")}
          label="Eigentum des Klägers" sub="Standardfall – § 1006 BGB wenn selbst gefahren" />
        <RadioOption checked={aktLegTyp === "finanziert"} onChange={() => onAktLegTyp("finanziert")}
          label="Finanziert" sub="Fahrzeug im Eigentum der Bank" />
        <RadioOption checked={aktLegTyp === "geleast"} onChange={() => onAktLegTyp("geleast")}
          label="Geleast" sub="Fahrzeug im Eigentum der Leasinggeberin" />

        {brauchtFreigabe && (
          <div style={{ marginTop: "1.25rem" }}>
            <div style={{ fontFamily: PLEX, fontSize: "0.75rem", fontWeight: 700,
              color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
              marginBottom: "0.75rem" }}>
              Nachweis der Aktivlegitimation
            </div>
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
                <input
                  type="date"
                  value={(() => {
                    if (!aktLegDatum) return "";
                    const m = aktLegDatum.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                    if (m) return `${m[3]}-${m[2].padStart(2,"0")}-${m[1].padStart(2,"0")}`;
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

      {/* ── Rechte Spalte: Vorschau ── */}
      <DokumentCard
        text={vorschauText}
        warnung={brauchtFreigabe && aktLegFreigabe === "ungeklaert"}
      />
    </div>
  );
}

function Step2({ positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind }) {
  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);

  return (
    <div>
      {/* Schadenpositionen */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
          marginBottom: "0.75rem" }}>
          <div style={{ fontFamily: PLEX, fontSize: "0.75rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em" }}>
            Schadenpositionen
          </div>
          <div style={{ fontFamily: MONO, fontSize: "0.95rem", fontWeight: 700, color: T.navy }}>
            Klagebetrag: {fmtEur(klagebetrag)}
          </div>
        </div>
        {positionen.length === 0 ? (
          <div style={{ fontFamily: PLEX, fontSize: "0.875rem", color: T.amber,
            padding: "0.75rem", background: `${T.amber}10`, borderRadius: 8 }}>
            ⚠ Keine Schadenpositionen erfasst.
          </div>
        ) : positionen.map(p => (
          <div key={p.key}
            onClick={() => onTogglePos(p.key)}
            style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "9px 12px", borderRadius: 8, cursor: "pointer",
              border: `1.5px solid ${p.checked ? T.navy : T.borderSoft}`,
              background: p.checked ? `${T.navy}06` : T.white,
              marginBottom: 6, transition: "all 0.12s",
            }}>
            <input type="checkbox" checked={!!p.checked}
              onChange={() => onTogglePos(p.key)}
              onClick={e => e.stopPropagation()}
              style={{ accentColor: T.navy, width: 15, height: 15, cursor: "pointer", flexShrink: 0 }} />
            <div style={{ flex: 1, fontFamily: PLEX, fontSize: "0.9rem",
              color: p.checked ? T.text : T.textMuted, fontWeight: p.checked ? 500 : 400 }}>
              {p.label}
            </div>
            <div style={{ fontFamily: MONO, fontSize: "0.9rem", fontWeight: 600,
              color: p.checked ? T.navy : T.textMuted, flexShrink: 0 }}>
              {fmtEur(p.betrag)}
            </div>
          </div>
        ))}
      </div>

      {/* Personenschaden */}
      <div style={{
        borderTop: `1.5px solid ${T.borderSoft}`, paddingTop: "1.25rem",
      }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.75rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: "0.75rem" }}>
          Personenschaden
        </div>
        <div style={{ display: "flex", gap: "1rem", marginBottom: mitSG ? "0.75rem" : 0 }}>
          {[{ val: false, label: "Kein Schmerzensgeld" }, { val: true, label: "Schmerzensgeld" }]
            .map(opt => (
              <label key={String(opt.val)}
                style={{ display: "flex", alignItems: "center", gap: 8,
                  cursor: "pointer", fontFamily: PLEX, fontSize: "0.9rem",
                  color: mitSG === opt.val ? T.navy : T.text, fontWeight: mitSG === opt.val ? 600 : 400 }}>
                <input type="radio" checked={mitSG === opt.val}
                  onChange={() => onMitSG(opt.val)}
                  style={{ accentColor: T.navy, cursor: "pointer" }} />
                {opt.label}
              </label>
            ))}
        </div>
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

function Step3({ gericht, beklagte, positionen, mitSG, sgMind,
                 rvgData, rvgOverride, aktLegTyp, aktLegFreigabe,
                 zinsenAb, verzug,
                 laedt, onGenerieren, fehler }) {

  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0);
  const rvgGesamt   = rvgOverride ? parseFloat(rvgOverride) : (rvgData?.gesamt || 0);

  const klaeger   = beklagte?.filter(b => b.rolle_klage === "klaeger") || [];
  const beklagteG = beklagte?.filter(b => b.rolle_klage !== "klaeger" && b.checked) || [];

  const firmenOhneVertreter = beklagteG.filter(b =>
    (b.versicherung || b.firma) && !b.vertreter_name
  );
  const keinPositionen = positionen.filter(p => p.checked).length === 0;
  const keinGericht    = !gericht;
  const gesperrt       = laedt || keinGericht || keinPositionen || firmenOhneVertreter.length > 0;

  const aktLegLabel = {
    eigentum:   "Eigentum des Klägers",
    finanziert: "Finanziert",
    geleast:    "Geleast",
  }[aktLegTyp] || aktLegTyp;

  const freigabeLabel = {
    freigabe:    "Freigabeerklärung liegt vor",
    bedingungen: "Aus Bedingungen",
    ungeklaert:  "⚠ Ungeklärt",
  }[aktLegFreigabe] || "";

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
      {/* Zusammenfassung */}
      <div style={{ background: T.surface, borderRadius: 10, padding: "1rem 1.25rem",
        marginBottom: "1.25rem", border: `1px solid ${T.border}` }}>
        <div style={{ fontFamily: PLEX, fontSize: "0.72rem", fontWeight: 700,
          color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.1em",
          marginBottom: "0.75rem" }}>
          Zusammenfassung
        </div>

        <ZeileZusammenfassung icon="📍"
          label="Gericht"
          wert={gericht ? gericht.name : "— nicht gewählt —"}
          warn={keinGericht} />
        <ZeileZusammenfassung icon="👤"
          label="Kläger"
          wert={klaeger.map(b => b.vorname ? `${b.vorname} ${b.name}` : b.name || b.firma || "–").join(", ") || "–"} />
        <ZeileZusammenfassung icon="⚔"
          label="Beklagte"
          wert={beklagteG.map(b => b.versicherung || b.firma || b.name || "–").join(", ") || "–"} />
        <ZeileZusammenfassung icon="⚖"
          label="Klagebetrag"
          wert={fmtEur(klagebetrag + (mitSG && sgMind > 0 ? sgMind : 0))}
          warn={keinPositionen} />
        <ZeileZusammenfassung icon="⏱"
          label="Zinsen ab"
          wert={zinsenAb === "verzug" && verzug
            ? `Verzugseintritt ${verzug}`
            : "Rechtshängigkeit"} />
        <ZeileZusammenfassung icon="🏠"
          label="Aktivlegitimation"
          wert={aktLegFreigabe === "ungeklaert"
            ? `${aktLegLabel} – ⚠ ungeklärt`
            : `${aktLegLabel}${aktLegTyp !== "eigentum" ? ` · ${freigabeLabel}` : ""}`}
          warn={aktLegFreigabe === "ungeklaert"} />
        <ZeileZusammenfassung icon="💶"
          label="RVG (Nebenforderung)"
          wert={fmtEur(rvgGesamt)} />
      </div>

      {/* Warnungen */}
      {(keinGericht || keinPositionen || firmenOhneVertreter.length > 0 || aktLegFreigabe === "ungeklaert") && (
        <div style={{ marginBottom: "1rem" }}>
          {keinGericht && (
            <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
              padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
              ⚠ Kein Gericht gewählt – bitte zurückgehen und Gericht auswählen.
            </div>
          )}
          {keinPositionen && (
            <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
              padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
              ⚠ Keine Schadenpositionen ausgewählt.
            </div>
          )}
          {firmenOhneVertreter.length > 0 && (
            <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
              padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
              ⚠ Firmen ohne Vertreter: {firmenOhneVertreter.map(b => b.versicherung || b.firma).join(", ")}
            </div>
          )}
          {aktLegFreigabe === "ungeklaert" && (
            <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.amber,
              padding: "7px 12px", background: `${T.amber}12`, borderRadius: 7, marginBottom: 6 }}>
              ⚠ Aktivlegitimation nicht nachgewiesen – kein Text wird generiert. Bitte vor Einreichung klären.
            </div>
          )}
        </div>
      )}

      {fehler && (
        <div style={{ fontFamily: PLEX, fontSize: "0.85rem", color: T.red,
          padding: "8px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: "1rem" }}>
          {fehler}
        </div>
      )}

      {/* Generieren-Button */}
      <button
        onClick={onGenerieren}
        disabled={gesperrt}
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
        ) : (
          "📄 Als Word generieren"
        )}
      </button>
    </div>
  );
}

// ── Hauptkomponente ────────────────────────────────────────────────────────────

export default function KlageWizard({
  step, onStepChange, onClose,
  // Step 1
  aktLegTyp, onAktLegTyp, aktLegFreigabe, onAktLegFreigabe,
  aktLegDatum, onAktLegDatum, mandantIstFahrer, mandantKz,
  // Step 2
  positionen, onTogglePos, mitSG, onMitSG, sgMind, onSGMind,
  // Step 3
  gericht, beklagte, rvgData, rvgOverride, zinsenAb, verzug,
  // Generieren
  laedt, onGenerieren, fehler,
}) {
  const backdropRef = useRef(null);

  // Escape-Taste schließt den Wizard
  useEffect(() => {
    const handler = e => { if (e.key === "Escape" && !laedt) onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [laedt, onClose]);

  // Kläger-Bezeichnung für Vorschau ableiten
  const klaegerObj = beklagte?.find(b => b.rolle_klage === "klaeger");
  const klaeger    = (klaegerObj?.anrede || "").toLowerCase() === "frau"
    ? "Die Klägerin" : "Der Kläger";

  // Step-Navigation
  const kannWeiter = () => {
    if (step === 2 && positionen.filter(p => p.checked).length === 0) return false;
    return true;
  };
  const weiter  = () => { if (kannWeiter()) onStepChange(step + 1); };
  const zurueck = () => onStepChange(step - 1);

  return (
    <>
      {/* Backdrop */}
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

        {/* Modal */}
        <div style={{
          background: "#fff", borderRadius: 16,
          width: "100%", maxWidth: step === 1 ? 760 : 560,
          maxHeight: "92vh", overflow: "hidden",
          display: "flex", flexDirection: "column",
          boxShadow: "0 24px 80px rgba(0,0,0,0.28), 0 4px 16px rgba(0,0,0,0.12)",
          animation: "slideUp 0.22s cubic-bezier(0.16,1,0.3,1)",
          transition: "max-width 0.3s ease",
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
            <button onClick={() => !laedt && onClose()}
              disabled={laedt}
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: "1.3rem", color: T.textMuted, padding: "4px 8px",
                borderRadius: 6, lineHeight: 1,
                opacity: laedt ? 0.3 : 1,
              }}>
              ✕
            </button>
          </div>

          {/* Body */}
          <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem" }}>
            <Fortschrittsbalken step={step} />

            {step === 1 && (
              <Step1
                aktLegTyp={aktLegTyp}       onAktLegTyp={onAktLegTyp}
                aktLegFreigabe={aktLegFreigabe} onAktLegFreigabe={onAktLegFreigabe}
                aktLegDatum={aktLegDatum}   onAktLegDatum={onAktLegDatum}
                mandantIstFahrer={mandantIstFahrer}
                mandantKz={mandantKz}
                klaeger={klaeger}
              />
            )}
            {step === 2 && (
              <Step2
                positionen={positionen} onTogglePos={onTogglePos}
                mitSG={mitSG}           onMitSG={onMitSG}
                sgMind={sgMind}         onSGMind={onSGMind}
              />
            )}
            {step === 3 && (
              <Step3
                gericht={gericht}     beklagte={beklagte}
                positionen={positionen}
                mitSG={mitSG}         sgMind={sgMind}
                rvgData={rvgData}     rvgOverride={rvgOverride}
                aktLegTyp={aktLegTyp} aktLegFreigabe={aktLegFreigabe}
                zinsenAb={zinsenAb}   verzug={verzug}
                laedt={laedt}         onGenerieren={onGenerieren}
                fehler={fehler}
              />
            )}
          </div>

          {/* Footer Navigation */}
          {step < 3 && (
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

              {step === 2 && positionen.filter(p => p.checked).length === 0 && (
                <div style={{ fontFamily: PLEX, fontSize: "0.8rem", color: T.amber }}>
                  ⚠ Bitte mindestens eine Position auswählen
                </div>
              )}

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
            </div>
          )}
        </div>
      </div>

      {/* CSS Animationen */}
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
