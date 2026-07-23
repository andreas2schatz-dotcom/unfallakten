/**
 * ReviewQueueView.jsx — S1.8 Review-UI-Rohbau
 * ============================================
 * Zweispaltige Ansicht:
 *   Links:  Queue (bereit_zur_review + pipeline_fehler),
 *           Sortierung Alter aufsteigend, dann Konfidenz absteigend.
 *   Rechts: Detail-Panel (PDF im iframe, Felder editierbar, Klasse,
 *           Akten-Kandidaten, Freigabe-Dialog mit Ereignis-Vorschlaegen
 *           (K-2) und ersetzt-Auswahl (K-M2b)).
 *
 * Bounding-Boxen im PDF-Overlay sind Stufe 2 (PDF.js). Hier reicht ein
 * iframe.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import T from "../config/theme.js";
import { apiIntake, API_BASE, tokenStore } from "../api.js";
import AktenLiveSuche from "../components/AktenLiveSuche.jsx";
import SplitDialog from "./SplitDialog.jsx";
import { istAufteilbar } from "./splitLogik.js";

// Fallback nur fuer den Fehlerfall des Klassen-Endpoints (BUG-26): im
// Normalbetrieb laedt die View die Klassen dynamisch aus der Registry.
const KLASSEN_FALLBACK = [
  "gutachten",
  "abrechnungsschreiben",
  "pruefbericht",
  "rechnung",
  "sv_rechnung",
  "abschlepprechnung",
  "standkostenrechnung",
  "sonstiges",
];

const GRUND_LABELS = {
  rauschen: "Rauschen",
  spam: "Spam",
  duplikat: "Duplikat",
  nicht_relevant: "Nicht relevant",
  falsche_kanzlei: "Falsche Kanzlei",
  aufgeteilt: "Aufgeteilt",
  sonstiges: "Sonstiges",
};

export function grundLabel(grund) {
  if (!grund) return "";
  return GRUND_LABELS[grund] || grund;
}

export function gruppiereQueue(eintraege) {
  const nachZust = new Map();
  eintraege.forEach(e => {
    if (e.zustellung_id != null) nachZust.set(e.zustellung_id, e);
  });
  const gruppen = [];
  const zuKind = new Map();
  eintraege.forEach(e => {
    const p = e.parent_zustellung_id;
    if (p != null && nachZust.has(p)) {
      if (!zuKind.has(p)) zuKind.set(p, []);
      zuKind.get(p).push(e);
    }
  });
  const istKind = new Set();
  zuKind.forEach(kinder => kinder.forEach(k => istKind.add(k.id)));
  eintraege.forEach(e => {
    if (istKind.has(e.id)) return;
    gruppen.push({ eintrag: e, kinder: zuKind.get(e.zustellung_id) || [] });
  });
  return gruppen;
}

export function TextVorschau({ text }) {
  return (
    <pre style={{
      whiteSpace: "pre-wrap", wordBreak: "break-word",
      fontFamily: T.fontBody, fontSize: T.textSm, color: T.text,
      background: T.offWhite, border: `1px solid ${T.border}`,
      borderRadius: 6, padding: 12, maxHeight: "60vh", overflow: "auto",
    }}>{text || "(kein Text)"}</pre>
  );
}

export function EmailKontextBox({ eltern }) {
  if (!eltern) return null;
  return (
    <div style={{
      border: `1px solid ${T.accent}`, background: T.accentPale,
      borderRadius: 8, padding: 12, marginBottom: 12, fontSize: T.textSm,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>📧 Kam mit E-Mail</div>
      <div><strong>Absender:</strong> {eltern.absender || "—"}</div>
      <div><strong>Betreff:</strong> {eltern.betreff || "—"}</div>
      <div><strong>Datum:</strong> {eltern.empfangen_am || "—"}</div>
      {eltern.akte_az && (
        <div><strong>Aktenzeichen:</strong> {eltern.akte_az}</div>
      )}
      <details style={{ marginTop: 6 }}>
        <summary style={{ cursor: "pointer" }}>E-Mail-Text anzeigen</summary>
        <TextVorschau text={eltern.text} />
      </details>
    </div>
  );
}

function StatusBadge({ status, fristPrio }) {
  const stil = status === "pipeline_fehler"
    ? { background: T.redBg, color: T.redText, border: `1px solid ${T.redLight}` }
    : { background: T.greenBg, color: T.greenText, border: `1px solid ${T.greenLight}` };
  return (
    <span style={{
      ...stil, padding: "2px 8px", borderRadius: 10,
      fontSize: T.textXs, fontFamily: T.fontMono, whiteSpace: "nowrap",
    }}>
      {status === "pipeline_fehler" ? "Fehler" : "Bereit"}
      {fristPrio ? ` · Frist` : ""}
    </span>
  );
}

// N-02: OCR-Qualitaets-Signal. ratio_salat hoch = schlecht, quote_woerter
// niedrig = schlecht. Schwellen spiegeln text_extraktion (0.30 / 0.10). Nur
// bei fragwuerdiger Qualitaet ein Badge -- gute Dokumente bleiben unmarkiert.
export function ocrQualitaet(item) {
  const ratio = item?.ocr_ratio_salat;
  const quote = item?.ocr_quote_woerter;
  if (ratio == null && quote == null) return null;

  const schlecht = (ratio != null && ratio > 0.30) ||
                   (quote != null && quote < 0.10);
  const mittel = (ratio != null && ratio > 0.15) ||
                 (quote != null && quote < 0.30);
  if (schlecht) {
    return {
      stufe: "schlecht",
      titel: "Schlechte OCR-Qualitaet — Text pruefen: viel Zeichensalat " +
             "oder kaum erkennbare Woerter.",
    };
  }
  if (mittel) {
    return {
      stufe: "mittel",
      titel: "Mittlere OCR-Qualitaet — Text stichprobenartig pruefen.",
    };
  }
  return null;
}

function OcrBadge({ item }) {
  const q = ocrQualitaet(item);
  if (!q) return null;
  const farbe = q.stufe === "schlecht" ? T.red : T.amber;
  return (
    <span title={q.titel} style={{
      background: farbe + "22", color: farbe, padding: "1px 7px",
      borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
      whiteSpace: "nowrap",
    }}>
      OCR {q.stufe === "schlecht" ? "⚠" : "~"}
    </span>
  );
}

export function istDegradiert(item) {
  return item?.llm_degradiert === 1;
}

function DegradationBadge({ item }) {
  if (!istDegradiert(item)) return null;
  return (
    <span title="Feld-Extraktion ohne KI (nur Regex) — Felder bitte manuell prüfen."
      style={{
        background: T.amber + "22", color: T.amber, padding: "1px 7px",
        borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
        whiteSpace: "nowrap",
      }}>
      nur Regex
    </span>
  );
}

export function bildseiten(item) {
  const n = item?.bildseiten_anzahl;
  if (!n || n < 1) return null;
  return n;
}

function BildseitenBadge({ item }) {
  const n = bildseiten(item);
  if (!n) return null;
  return (
    <span title={`${n} Seite(n) als Foto/Bild erkannt — nicht durch KI-OCR.`}
      style={{
        background: T.textMuted + "22", color: T.textMuted, padding: "1px 7px",
        borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
        whiteSpace: "nowrap",
      }}>
      🖼 {n}
    </span>
  );
}

function KonfidenzChip({ wert }) {
  if (wert == null) return null;
  const prozent = Math.round(wert * 100);
  const farbe = wert >= 0.8 ? T.green : wert >= 0.5 ? T.amber : T.red;
  return (
    <span style={{
      background: farbe + "22", color: farbe, padding: "1px 7px",
      borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
    }}>{prozent}%</span>
  );
}

function QueueEintrag({ item, aktiv, onClick, onVerwerfen, eingerueckt }) {
  const kandidat = item.akte_kandidat_top;
  return (
    <div onClick={onClick}
      style={{
        padding: "10px 12px",
        marginLeft: eingerueckt ? 26 : 0,
        borderBottom: `1px solid ${T.border}`,
        cursor: "pointer",
        background: aktiv ? T.accentPale : "transparent",
        borderLeft: aktiv
          ? `3px solid ${T.accent}`
          : eingerueckt ? `2px solid ${T.accent}40` : "3px solid transparent",
        position: "relative",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <StatusBadge status={item.queue_status} fristPrio={item.prioritaet_frist} />
        <KonfidenzChip wert={item.konfidenz} />
        <OcrBadge item={item} />
        <DegradationBadge item={item} />
        <BildseitenBadge item={item} />
        {item.klasse_quelle === "manuell" && (
          <span style={{ fontSize: T.textXs, color: T.textMuted }}>manuell</span>
        )}
        <div style={{ flex: 1 }} />
        <button
          onClick={e => { e.stopPropagation(); onVerwerfen(item); }}
          title="Dokument aus der Queue verwerfen (Soft-Delete)"
          aria-label="Dokument verwerfen"
          style={{
            border: `1px solid ${T.redLight}`,
            background: T.redBg,
            color: T.redText,
            cursor: "pointer",
            padding: "3px 8px",
            fontSize: T.textXs,
            fontWeight: 600,
            borderRadius: 4,
            lineHeight: 1.1,
          }}
        >Verwerfen</button>
      </div>
      <div style={{ fontSize: T.textSm, fontFamily: T.fontBody, color: T.text }}>
        {eingerueckt && <span title="Anhang">📎 </span>}
        {item.payload_typ === "text" && <span title="E-Mail">📧 </span>}
        <strong>{item.klasse || "unbekannt"}</strong>
      </div>
      {item.payload_typ === "text" && (item.absender || item.betreff) && (
        <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 2 }}>
          {item.absender || ""}{item.betreff ? ` · ${item.betreff}` : ""}
        </div>
      )}
      <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 3 }}>
        {kandidat
          ? <>Akte: <code>{kandidat.akte_az}</code> · Score {kandidat.score}</>
          : <>Keine Akten-Vorschläge</>}
      </div>
      <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 2 }}>
        #{item.id} · {item.erstellt_am}
      </div>
      {item.fehler_detail && (
        <div style={{ fontSize: T.textXs, color: T.redText, marginTop: 4 }}>
          {item.fehler_detail}
        </div>
      )}
    </div>
  );
}

const VERWERFEN_GRUENDE = [
  { wert: "spam",            label: "Spam" },
  { wert: "duplikat",        label: "Duplikat" },
  { wert: "nicht_relevant",  label: "Nicht relevant" },
  { wert: "falsche_kanzlei", label: "Falsche Kanzlei" },
  { wert: "sonstiges",       label: "Sonstiges" },
];

function VerwerfenDialog({ dokument, onConfirm, onCancel, laeuft }) {
  const [grund, setGrund] = useState("spam");
  const [kommentar, setKommentar] = useState("");
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 900,
    }}>
      <div style={{
        background: T.cardBg, width: 480,
        borderRadius: 10, padding: 24,
        boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
      }}>
        <h3 style={{ margin: "0 0 6px", fontFamily: T.fontDisplay, color: T.navy }}>
          Dokument verwerfen
        </h3>
        <div style={{ color: T.textMuted, marginBottom: 16, fontSize: T.textSm }}>
          Dokument #{dokument.id}
          {dokument.klasse ? <> (<strong>{dokument.klasse}</strong>)</> : null}
          {" "}verschwindet aus der Queue. PDF bleibt am Filesystem,
          Zeile bleibt in der DB.
        </div>

        <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
          Grund
        </label>
        <select
          value={grund}
          onChange={e => setGrund(e.target.value)}
          disabled={laeuft}
          style={{
            width: "100%", boxSizing: "border-box",
            padding: "6px 8px", marginBottom: 14,
            border: `1px solid ${T.border}`, borderRadius: 4,
            fontSize: T.textSm, background: T.cardBg,
          }}>
          {VERWERFEN_GRUENDE.map(g => (
            <option key={g.wert} value={g.wert}>{g.label}</option>
          ))}
        </select>

        <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
          Kommentar <span style={{ fontWeight: 400, color: T.textMuted }}>(optional)</span>
        </label>
        <textarea
          value={kommentar}
          onChange={e => setKommentar(e.target.value)}
          disabled={laeuft}
          placeholder="z.B. kam gestern schon"
          rows={3}
          style={{
            width: "100%", boxSizing: "border-box",
            padding: "6px 10px", marginBottom: 18,
            border: `1px solid ${T.border}`, borderRadius: 4,
            fontFamily: T.fontBody, fontSize: T.textSm,
          }}
        />

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onCancel} disabled={laeuft}
            style={{
              padding: "8px 16px", background: T.offWhite,
              border: `1px solid ${T.border}`, borderRadius: 4,
              cursor: laeuft ? "wait" : "pointer",
            }}>
            Abbrechen
          </button>
          <button
            onClick={() => onConfirm({ grund, kommentar: kommentar.trim() || undefined })}
            disabled={laeuft}
            style={{
              padding: "8px 16px", background: T.red || T.redText,
              color: T.white, border: "none", borderRadius: 4,
              cursor: laeuft ? "wait" : "pointer", fontWeight: 600,
            }}>
            {laeuft ? "Verwerfe…" : "Verwerfen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function FelderEditor({ felder, onChange }) {
  const eintraege = Object.entries(felder || {});
  if (!eintraege.length) {
    return <div style={{ color: T.textMuted, fontSize: T.textSm }}>Keine Felder extrahiert.</div>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: T.textSm }}>
      <tbody>
        {eintraege.map(([k, v]) => (
          <tr key={k}>
            <td style={{ padding: "4px 8px 4px 0", color: T.textMid, verticalAlign: "top", width: 160 }}>
              {k}
            </td>
            <td style={{ padding: "4px 0" }}>
              <input
                value={v == null ? "" : String(v)}
                onChange={e => onChange(k, e.target.value)}
                style={{
                  width: "100%", boxSizing: "border-box",
                  padding: "4px 8px", border: `1px solid ${T.border}`,
                  borderRadius: 4, fontFamily: T.fontMono,
                  fontSize: T.textSm, background: T.cardBg,
                }}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KandidatenList({ kandidaten, ausgewaehlt, onWaehle }) {
  if (!kandidaten?.length) {
    return <div style={{ color: T.textMuted, fontSize: T.textSm }}>Keine Kandidaten aus Matching.</div>;
  }
  return (
    <div>
      {kandidaten.map((k, i) => (
        <label key={i} style={{
          display: "flex", gap: 8, alignItems: "center",
          padding: "6px 8px", borderRadius: 4,
          background: ausgewaehlt === k.akte_az ? T.accentPale : "transparent",
          cursor: "pointer",
        }}>
          <input type="radio" name="akte" checked={ausgewaehlt === k.akte_az}
            onChange={() => onWaehle(k.akte_az)} />
          <code style={{ flex: 1 }}>{k.akte_az}</code>
          <span style={{ fontSize: T.textXs, color: T.textMuted }}>
            {k.quelle} · {k.score}
          </span>
        </label>
      ))}
    </div>
  );
}

export function initialeEreignisse(defaultTyp) {
  return defaultTyp ? [{ typ: defaultTyp }] : [];
}

// Reine Logik fuer den Druckbutton: PDF -> native Viewer-URL, E-Mail-Text ->
// dedizierte Textansicht. Der eigentliche window.open/print-Aufruf bleibt
// browserseitig (nicht unit-testbar) im DetailPanel.
export function druckZiel(detail, pdfSrc) {
  if (detail?.payload_typ === "text") {
    return { typ: "text", text: detail?.parse?.text_gesamt ?? "" };
  }
  return { typ: "pdf", url: pdfSrc };
}

// Effektive Dokumentenbezeichnung: gespeicherter Wert hat Vorrang vor dem
// automatisch generierten Vorschlag (PRD-37).
export function effektiveBezeichnung(detail) {
  return detail?.bezeichnung ?? detail?.bezeichnung_vorschlag ?? "";
}

// True, wenn der eingegebene Titel vom aktuell angezeigten (gespeicherten oder
// vorgeschlagenen) Wert abweicht — nur dann wird gespeichert. Verhindert, dass
// ein bloßes Fokussieren+Verlassen den lebendigen Vorschlag als manuellen Wert
// einfriert.
export function bezeichnungGeaendert(detail, wert) {
  return (wert || "").trim() !== (effektiveBezeichnung(detail) || "").trim();
}

// Form-Defaults aus dem geladenen Detail. `skipFormReset` (Hintergrund-Poll
// waehrend `wartAufWorker`) liefert null: dann bleiben offene Dialog-Eingaben
// (Akte/Ereignisse/Feld-Korrekturen) erhalten statt vom Poll-Tick ueberschrieben.
export function naechsterFormState(detail, { skipFormReset = false } = {}) {
  if (skipFormReset) return null;
  return {
    gewaehlteAkte: detail?.parse?.akten_kandidaten?.[0]?.akte_az || "",
    ereignisse: initialeEreignisse(detail?.default_ereignistyp),
    bezeichnung: effektiveBezeichnung(detail),
    dirty: {},
  };
}

// Pollt den Worker bis Endstatus, Timeout oder Unmount (BUG-30). Reine Logik
// mit injizierten Abhaengigkeiten, damit sie ohne React testbar ist und der
// Poll nach Unmount/Dokumentwechsel (`istMontiert` -> false) sofort stoppt,
// statt weiter Detail-Requests + setState auf einer toten Komponente zu feuern.
export async function polleWorkerBisFertig(
  { tick, istMontiert, sleep, jetzt, timeoutMs = 30000 },
) {
  const start = jetzt();
  while (jetzt() - start < timeoutMs) {
    await sleep(1500);
    if (!istMontiert()) return { status: "abgebrochen" };
    const d = await tick();
    if (!istMontiert()) return { status: "abgebrochen" };
    if (!d) return { status: "fehler" };
    if (d.queue_status !== "neu" && d.queue_status !== "laeuft") {
      return { status: "fertig", detail: d };
    }
  }
  return { status: "timeout" };
}

export function abschnittHatAufgabe(felder) {
  return (felder || []).some(f => f.ist_leer || f.konflikt);
}

// Editierbar sind nur leere und abweichende Felder. Default-Wert: leer -> geparst,
// Konflikt -> Akten-Wert (bleibt, bis der SB "Bogen uebernehmen" klickt).
function editierbareFelder(felder) {
  return (felder || []).filter(f => f.ist_leer || f.konflikt);
}

export function initialUebernahme(abschnitte) {
  const aktive = [];
  const collapsed = [];
  const werte = {};
  (abschnitte || []).forEach(a => {
    if (!a.felder || !a.felder.length) return;
    aktive.push(a.key);
    if (!abschnittHatAufgabe(a.felder)) collapsed.push(a.key);
    const w = {};
    editierbareFelder(a.felder).forEach(f => {
      w[f.feld] = f.ist_leer ? (f.geparst ?? "") : (f.akte_wert ?? "");
    });
    werte[a.key] = w;
  });
  return { aktive, collapsed, werte };
}

export function baueUebernahmePayload(abschnitte, state) {
  const werte = {};
  (abschnitte || []).forEach(a => {
    if (!state.aktive.includes(a.key)) return;
    werte[a.key] = { ...(state.werte[a.key] || {}) };
  });
  return { abschnitte: [...state.aktive], werte };
}

export function FragebogenUebernahme({ abschnitte, state, onToggle, onFeld, onAdopt }) {
  const sichtbar = (abschnitte || []).filter(a => a.felder && a.felder.length);
  if (!sichtbar.length) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: T.textSm, fontWeight: 600, marginBottom: 6 }}>
        Fragebogen-Übernahme
      </div>
      <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
        {sichtbar.map(a => {
          const aktiv = state.aktive.includes(a.key);
          const zu = state.collapsed.includes(a.key);
          const felder = a.felder;
          return (
            <div key={a.key} style={{ borderTop: `1px solid ${T.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8,
                            padding: "8px 10px", background: T.surface, cursor: "pointer" }}
                   onClick={() => onToggle(a.key, "collapsed")}>
                <input type="checkbox" checked={aktiv}
                       onClick={e => e.stopPropagation()}
                       onChange={() => onToggle(a.key, "aktiv")} />
                <strong style={{ fontSize: T.textSm }}>{a.label}</strong>
                <span style={{ marginLeft: "auto", fontSize: T.textXs, color: T.textMuted }}>
                  {zu ? "▸" : "▾"}
                </span>
              </div>
              {aktiv && !zu && (
                <div style={{ padding: "6px 10px", display: "grid", gap: 6 }}>
                  {felder.map(f => {
                    if (!f.ist_leer && !f.konflikt) {
                      return (
                        <div key={f.feld} style={{ display: "grid",
                             gridTemplateColumns: "110px 1fr", gap: 8, alignItems: "start" }}>
                          <label style={{ fontSize: T.textXs, color: T.textMid, paddingTop: 6 }}>
                            {f.label}
                          </label>
                          <div style={{ padding: "5px 8px", fontSize: T.textSm,
                                        border: `1px dashed ${T.border}`, borderRadius: 4,
                                        background: T.surface, color: T.textMuted }}>
                            {f.akte_wert}
                            <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 2 }}>
                              🔒 bereits in Akte
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return (
                    <div key={f.feld} style={{ display: "grid",
                         gridTemplateColumns: "110px 1fr", gap: 8, alignItems: "start" }}>
                      <label style={{ fontSize: T.textXs, color: T.textMid, paddingTop: 6 }}>
                        {f.label}
                      </label>
                      <div>
                        <input
                          value={state.werte[a.key]?.[f.feld] ?? ""}
                          onChange={e => onFeld(a.key, f.feld, e.target.value)}
                          style={{ width: "100%", boxSizing: "border-box",
                                   padding: "5px 8px", fontSize: T.textSm,
                                   border: `1px solid ${f.konflikt ? T.amber : T.greenLight}`,
                                   borderRadius: 4,
                                   background: f.konflikt ? T.amberBg : T.cardBg }}
                        />
                        {f.konflikt && (
                          <div style={{ display: "flex", gap: 8, alignItems: "center",
                                        marginTop: 3, fontSize: T.textXs, color: T.amberText }}>
                            <span>⚠ Akte: {f.akte_wert} · Bogen: {f.geparst}</span>
                            <button type="button" onClick={() => onAdopt(a.key, f.feld, f.geparst)}
                              style={{ fontSize: T.textXs, border: `1px solid ${T.amber}`,
                                       background: "transparent", color: T.amberText,
                                       borderRadius: 4, padding: "1px 6px", cursor: "pointer" }}>
                              Bogen übernehmen
                            </button>
                          </div>
                        )}
                        {f.ist_leer && (
                          <div style={{ fontSize: T.textXs, color: T.greenText, marginTop: 3 }}>
                            leer → wird gefüllt
                          </div>
                        )}
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FreigabeDialog({ dokument, akteAz, ereignisse, ersetztIds,
                          ereignistypen, onEreignisChange,
                          onErsetztChange, onEreignisAdd, onEreignisDel,
                          onConfirm, onCancel, laeuft,
                          fbVorschau, fbState, onFbToggle, onFbFeld, onFbAdopt }) {
  // Nur eingehende Typen anzeigen -- Review-Queue enthaelt eingegangene
  // Dokumente. Ausgehend/intern sind fachlich unpassend.
  const typenListe = (ereignistypen || []).filter(t => t.richtung === "eingehend");
  const typLabel = (typ) => {
    const eintrag = (ereignistypen || []).find(t => t.typ === typ);
    return eintrag ? eintrag.label : typ;
  };
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 900,
    }}>
      <div style={{
        background: T.cardBg, width: 640, maxHeight: "85vh",
        borderRadius: 10, padding: 24, overflow: "auto",
        boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
      }}>
        <h3 style={{ margin: "0 0 6px", fontFamily: T.fontDisplay, color: T.navy }}>
          Freigabe an Akte
        </h3>
        <div style={{ color: T.textMuted, marginBottom: 16, fontSize: T.textSm }}>
          Dokument #{dokument.id} wird als <strong>{dokument.klasse}</strong> in
          Akte <code>{akteAz}</code> uebernommen.
        </div>

        {fbVorschau && fbState && (
          <FragebogenUebernahme
            abschnitte={fbVorschau} state={fbState}
            onToggle={onFbToggle} onFeld={onFbFeld} onAdopt={onFbAdopt} />
        )}

        {/* K-2: Ereignis-Vorschläge */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: T.textSm, fontWeight: 600, marginBottom: 6 }}>
            Ereignis-Vorschlaege (K-2)
          </div>
          <div style={{ fontSize: T.textXs, color: T.textMuted, marginBottom: 8 }}>
            Der bestaetigte Ereignistyp wird ins Positionsmodell gebucht.
            Betraege werden nur uebernommen, wenn sie eindeutig im Dokument
            stehen (Gutachten, Rechnungen); sonst wird das Ereignis als
            Faktum ohne Betrag festgehalten.
          </div>
          {ereignisse.map((ev, i) => (
            <div key={i} style={{
              padding: "8px 10px", border: `1px solid ${T.border}`,
              borderRadius: 4, marginBottom: 6, display: "flex",
              alignItems: "center", gap: 8,
            }}>
              <select
                value={ev.typ || ""}
                onChange={e => onEreignisChange(i, { ...ev, typ: e.target.value })}
                style={{
                  flex: 1, padding: "4px 6px",
                  border: `1px solid ${T.border}`, borderRadius: 4,
                  fontSize: T.textSm, background: T.cardBg,
                }}>
                {!typenListe.some(t => t.typ === ev.typ) && ev.typ && (
                  <option value={ev.typ}>{typLabel(ev.typ)} (unbekannt)</option>
                )}
                {typenListe.map(t => (
                  <option key={t.typ} value={t.typ}>{t.label}</option>
                ))}
              </select>
              <button onClick={() => onEreignisDel(i)}
                title="Ereignis entfernen"
                style={{ border: "none", background: "transparent", cursor: "pointer",
                          color: T.redText, fontSize: 14, padding: "2px 6px" }}>
                ✕
              </button>
            </div>
          ))}
          <button onClick={onEreignisAdd}
            disabled={!typenListe.length}
            style={{
              padding: "4px 10px", fontSize: T.textXs,
              background: T.offWhite, border: `1px solid ${T.border}`,
              borderRadius: 4,
              cursor: typenListe.length ? "pointer" : "default",
            }}>
            + Ereignis-Vorschlag hinzufuegen
          </button>
        </div>

        {/* K-M2b: „ersetzt ..." */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: T.textSm, fontWeight: 600, marginBottom: 6 }}>
            Ersetzt (K-M2b)
          </div>
          <div style={{ fontSize: T.textXs, color: T.textMuted, marginBottom: 6 }}>
            IDs bestehender Ereignisse/Positionen, die von dieser Freigabe abgeloest werden.
          </div>
          <input
            value={ersetztIds}
            onChange={e => onErsetztChange(e.target.value)}
            placeholder="z.B. 12, 34"
            style={{
              width: "100%", boxSizing: "border-box",
              padding: "6px 10px", border: `1px solid ${T.border}`,
              borderRadius: 4, fontSize: T.textSm, fontFamily: T.fontMono,
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onCancel} disabled={laeuft}
            style={{
              padding: "8px 16px", background: T.offWhite,
              border: `1px solid ${T.border}`, borderRadius: 4,
              cursor: laeuft ? "wait" : "pointer",
            }}>
            Abbrechen
          </button>
          <button onClick={onConfirm} disabled={laeuft}
            style={{
              padding: "8px 16px", background: T.accent, color: T.white,
              border: "none", borderRadius: 4,
              cursor: laeuft ? "wait" : "pointer", fontWeight: 600,
            }}>
            {laeuft ? "Freigebe…" : "Freigeben"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailPanel({ id, onFreigegeben, onOpenAkte, onVerwerfen,
                       ereignistypen, klassen }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [meldung, setMeldung] = useState("");
  const [dirty, setDirty] = useState({});
  const [gewaehlteAkte, setGewaehlteAkte] = useState("");
  const [zeigeFreigabe, setZeigeFreigabe] = useState(false);
  const [ereignisse, setEreignisse] = useState([]);
  const [ersetztIds, setErsetztIds] = useState("");
  const [aktion, setAktion] = useState(false);
  const [pollAktiv, setPollAktiv] = useState(false);
  const [fbVorschau, setFbVorschau] = useState(null);
  const [fbState, setFbState] = useState(null);
  const [splitOffen, setSplitOffen] = useState(false);
  const [bezeichnung, setBezeichnung] = useState("");

  const laden = useCallback(async ({ skipFormReset = false } = {}) => {
    try {
      setError(null);
      const d = await apiIntake.detail(id);
      setDetail(d);
      const form = naechsterFormState(d, { skipFormReset });
      if (form) {
        setDirty(form.dirty);
        setGewaehlteAkte(form.gewaehlteAkte);
        setEreignisse(form.ereignisse);
        setBezeichnung(form.bezeichnung);
      }
      return d;
    } catch (e) { setError(e.message); return null; }
  }, [id]);

  useEffect(() => { if (id) laden(); }, [id, laden]);

  // Fragebogen-Vorschau: nur laden, wenn Dokument ein Fragebogen ist und eine
  // Akte gewaehlt wurde; neu laden bei Akten-Wechsel.
  useEffect(() => {
    if (!detail?.ist_fragebogen || !gewaehlteAkte) { setFbVorschau(null); setFbState(null); return; }
    let aktiv = true;
    apiIntake.fragebogenVorschau(id, gewaehlteAkte)
      .then(d => { if (!aktiv) return;
        setFbVorschau(d.abschnitte);
        setFbState(initialUebernahme(d.abschnitte)); })
      .catch(() => { if (aktiv) { setFbVorschau(null); setFbState(null); } });
    return () => { aktiv = false; };
  }, [id, detail?.ist_fragebogen, gewaehlteAkte]);

  // Mount-Flag: der key-Re-Mount bei Dokumentwechsel unmountet dieses Panel;
  // ein laufender wartAufWorker-Poll muss dann sofort stoppen (BUG-30).
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Polling: nach Reklassifikation/Reparse den Worker abwarten (bis 30s).
  const wartAufWorker = useCallback(async () => {
    setPollAktiv(true);
    const ergebnis = await polleWorkerBisFertig({
      tick: () => laden({ skipFormReset: true }),
      istMontiert: () => mountedRef.current,
      sleep: (ms) => new Promise(r => setTimeout(r, ms)),
      jetzt: () => Date.now(),
    });
    if (!mountedRef.current) return;  // abgebrochen: kein setState nach Unmount
    setPollAktiv(false);
    if (ergebnis.status === "fertig") {
      const d = ergebnis.detail;
      setMeldung(d.queue_status === "pipeline_fehler"
        ? "Re-Parse fehlgeschlagen: " + (d.fehler_detail || "unbekannt")
        : "Re-Parse fertig.");
      setTimeout(() => setMeldung(""), 4000);
    } else if (ergebnis.status !== "abgebrochen") {
      setMeldung("Worker antwortet nicht (30s Timeout).");
      setTimeout(() => setMeldung(""), 5000);
    }
  }, [laden]);

  if (!id) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center",
                     justifyContent: "center", color: T.textMuted }}>
        Waehle ein Dokument aus der Queue.
      </div>
    );
  }
  if (error) {
    return <div style={{ padding: 20, color: T.redText }}>Fehler: {error}</div>;
  }
  if (!detail) {
    return <div style={{ padding: 20, color: T.textMuted }}>Lade…</div>;
  }

  const felderMerged = { ...(detail.parse.felder || {}), ...dirty };
  const feldChange = (k, v) => setDirty(prev => ({ ...prev, [k]: v }));

  const pdfSrc = (() => {
    // iframe auf die PDF-Datei -- Auth per Token in URL geht ueber SSE-Fallback
    // im Middleware. Wenn kein direkter PDF-Endpunkt existiert, laesst der
    // Browser das iframe leer.
    const token = tokenStore.getAccess();
    if (!token) return "about:blank";
    return `${API_BASE}/intake/dokument/${id}/pdf?token=${encodeURIComponent(token)}`;
  })();

  const thumbUrl = (n) => {
    const token = tokenStore.getAccess();
    if (!token) return "about:blank";
    return `${API_BASE}/intake/dokument/${id}/seite/${n}/thumbnail?token=${encodeURIComponent(token)}`;
  };

  const speichereKlasse = async (neueKlasse) => {
    if (!neueKlasse || neueKlasse === detail.klasse) return;
    setAktion(true);
    try {
      await apiIntake.setKlasse(id, neueKlasse);
      setMeldung(`Klasse auf "${neueKlasse}" gesetzt — Worker parst neu…`);
      await laden();
      wartAufWorker();
    } catch (e) { setError(e.message); }
    finally { setAktion(false); }
  };

  const erneutParsen = async () => {
    setAktion(true);
    try {
      await apiIntake.reparse(id);
      setMeldung("Re-Parse angestoßen — Worker läuft…");
      await laden();
      wartAufWorker();
    } catch (e) { setError(e.message); }
    finally { setAktion(false); }
  };

  const speichereFelder = async () => {
    const changed = Object.entries(dirty).reduce((acc, [k, v]) => {
      const alt = (detail.parse.felder || {})[k] ?? null;
      if (alt !== v) acc[k] = { alt, neu: v };
      return acc;
    }, {});
    if (!Object.keys(changed).length) return;
    setAktion(true);
    try {
      await apiIntake.setFelder(id, changed);
      await laden();
    } catch (e) { setError(e.message); }
    finally { setAktion(false); }
  };

  const speichereBezeichnung = async () => {
    if (!bezeichnungGeaendert(detail, bezeichnung)) return;
    const wert = (bezeichnung || "").trim();
    try {
      await apiIntake.setBezeichnung(id, wert);
      await laden({ skipFormReset: true });
    } catch (e) { setError(e.message); }
  };

  const doFreigabe = async () => {
    const ids = ersetztIds
      .split(",").map(s => s.trim()).filter(Boolean)
      .map(s => Number(s)).filter(n => !Number.isNaN(n));
    setAktion(true);
    try {
      await apiIntake.freigabe(id, {
        akte_az: gewaehlteAkte,
        kandidaten_ereignisse: ereignisse,
        ersetzt_ids: ids,
        fragebogen_uebernahme: (fbVorschau && fbState)
          ? baueUebernahmePayload(fbVorschau, fbState) : undefined,
      });
      setZeigeFreigabe(false);
      onFreigegeben && onFreigegeben(gewaehlteAkte);
    } catch (e) { setError(e.message); }
    finally { setAktion(false); }
  };

  // Drucken: PDF im nativen Viewer (druckt zuverlaessig), E-Mail-Text in einem
  // dedizierten Druckfenster. Blockiert bewusst nicht pollAktiv/aktion.
  const handleDrucken = () => {
    const ziel = druckZiel(detail, pdfSrc);
    if (ziel.typ === "pdf") {
      window.open(ziel.url, "_blank", "noopener");
      return;
    }
    const w = window.open("", "_blank");
    if (!w) return;
    const esc = (ziel.text || "").replace(/[&<>]/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    w.document.write(
      `<!doctype html><meta charset="utf-8"><title>Dokument #${detail.id}</title>` +
      `<pre style="white-space:pre-wrap;word-break:break-word;` +
      `font-family:system-ui,sans-serif;font-size:13px;padding:16px">${esc}</pre>`,
    );
    w.document.close();
    w.focus();
    w.print();
  };

  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
      {/* Vorschau: E-Mail-Text oder PDF-iframe */}
      <div style={{ flex: 1, background: T.offWhite, borderRight: `1px solid ${T.border}`,
        overflow: "auto" }}>
        {detail.eltern_email && (
          <div style={{ padding: 12 }}>
            <EmailKontextBox eltern={detail.eltern_email} />
          </div>
        )}
        {detail.payload_typ === "text" ? (
          <div style={{ padding: 12 }}>
            <TextVorschau text={detail.parse?.text_gesamt} />
          </div>
        ) : (
          <iframe title={`intake-${id}`} src={pdfSrc}
            style={{ width: "100%", height: "100%", border: "none" }} />
        )}
      </div>

      {/* Formular-Panel */}
      <div style={{ width: 440, overflow: "auto", padding: 16 }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ margin: 0, fontFamily: T.fontDisplay, color: T.navy }}>
              Dokument #{detail.id}
            </h3>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button onClick={() => setSplitOffen(true)}
                disabled={!istAufteilbar(detail)}
                title={istAufteilbar(detail)
                  ? "Dokument aufteilen"
                  : "Nur PDF-Dokumente koennen aufgeteilt werden"}
                style={{
                  padding: "4px 10px", fontSize: T.textXs, fontWeight: 600,
                  background: T.offWhite, color: T.navy,
                  border: `1px solid ${T.border}`, borderRadius: 4,
                  cursor: istAufteilbar(detail) ? "pointer" : "not-allowed",
                  whiteSpace: "nowrap",
                  opacity: istAufteilbar(detail) ? 1 : 0.5,
                }}>
                ✂ Aufteilen
              </button>
              <button onClick={handleDrucken}
                title="Dokument drucken"
                style={{
                  padding: "4px 10px", fontSize: T.textXs, fontWeight: 600,
                  background: T.offWhite, color: T.navy,
                  border: `1px solid ${T.border}`, borderRadius: 4,
                  cursor: "pointer", whiteSpace: "nowrap",
                }}>
                🖨 Drucken
              </button>
              <StatusBadge status={detail.queue_status} fristPrio={detail.prioritaet_frist} />
            </div>
          </div>
          <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 4 }}>
            sha256: <code>{detail.sha256?.slice(0, 16)}…</code>
            {detail.textquelle && <> · {detail.textquelle}</>}
            {detail.registry_version && <> · reg {detail.registry_version.slice(0, 8)}</>}
          </div>
        </div>

        <section style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
            Dokumentenbezeichnung
          </label>
          <input
            type="text"
            value={bezeichnung}
            onChange={e => setBezeichnung(e.target.value)}
            onBlur={speichereBezeichnung}
            placeholder={detail.bezeichnung_vorschlag || ""}
            disabled={aktion}
            style={{
              width: "100%", padding: "6px 8px", boxSizing: "border-box",
              border: `1px solid ${T.border}`, borderRadius: 4,
              fontSize: T.textSm, background: T.cardBg,
            }} />
          <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 4 }}>
            Vorschlag automatisch aus Klasse/Aussteller/Datum/Betrag. Editierbar; wird bei Freigabe übernommen.
          </div>
        </section>

        {(meldung || pollAktiv) && (
          <div style={{
            padding: "8px 12px", marginBottom: 12,
            background: pollAktiv ? T.blueBg : T.greenBg,
            color: pollAktiv ? T.blueText : T.greenText,
            border: `1px solid ${pollAktiv ? T.blue : T.greenLight}`,
            borderRadius: 4, fontSize: T.textSm,
            display: "flex", alignItems: "center", gap: 8,
          }}>
            {pollAktiv && <span style={{ fontSize: "1.1rem" }}>⏳</span>}
            <span>{meldung}</span>
          </div>
        )}

        <section style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
            Klasse
          </label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              value={detail.klasse || ""}
              onChange={e => speichereKlasse(e.target.value)}
              disabled={aktion || pollAktiv}
              style={{
                flex: 1, padding: "6px 8px",
                border: `1px solid ${T.border}`, borderRadius: 4,
                fontSize: T.textSm, background: T.cardBg,
              }}>
              <option value="">— unbekannt —</option>
              {(klassen && klassen.length ? klassen : KLASSEN_FALLBACK)
                .map(k => <option key={k} value={k}>{k}</option>)}
            </select>
            <KonfidenzChip wert={detail.konfidenz} />
            <button
              onClick={erneutParsen}
              disabled={aktion || pollAktiv}
              title="Klassifikator + Feld-Extraktion erneut ausführen"
              style={{
                padding: "6px 12px",
                background: T.navy, color: T.white,
                border: "none", borderRadius: 4,
                fontSize: T.textXs, fontWeight: 600,
                cursor: (aktion || pollAktiv) ? "wait" : "pointer",
                whiteSpace: "nowrap",
              }}
            >🔄 Erneut parsen</button>
          </div>
          {detail.parse.klassifikation?.hinweise?.length ? (
            <ul style={{ margin: "6px 0 0", padding: 0, listStyle: "none", fontSize: T.textXs, color: T.textMuted }}>
              {detail.parse.klassifikation.hinweise.map((h, i) => (
                <li key={i}>· {h}</li>
              ))}
            </ul>
          ) : null}
          {detail.parse?.degradation?.llm_extraktion === "ausgefallen" && (
            <div role="alert" style={{
              marginTop: 8, padding: "6px 10px", borderRadius: 4,
              background: T.amberBg, color: T.amberText,
              fontSize: T.textXs, border: `1px solid ${T.amber}`,
            }}>
              ⚠ Extraktion ohne KI (nur Regex) — Felder bitte manuell prüfen.
            </div>
          )}
          {detail.parse.llm_konflikt && (
            <div style={{ marginTop: 6, padding: "6px 10px",
              background: T.amberBg, color: T.amberText,
              border: `1px solid ${T.amber}`, borderRadius: 4,
              fontSize: T.textXs }}>
              LLM/Regex-Diskrepanz: {JSON.stringify(detail.parse.llm_konflikt)}
            </div>
          )}
        </section>

        <section style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <label style={{ fontSize: T.textSm, fontWeight: 600 }}>Extrahierte Felder</label>
            <button onClick={speichereFelder}
              disabled={aktion || !Object.keys(dirty).length}
              style={{
                padding: "3px 10px", fontSize: T.textXs,
                background: Object.keys(dirty).length ? T.accent : T.border,
                color: T.white, border: "none", borderRadius: 4,
                cursor: Object.keys(dirty).length ? "pointer" : "default",
              }}>
              Speichern
            </button>
          </div>
          <FelderEditor felder={felderMerged} onChange={feldChange} />
        </section>

        <section style={{ marginBottom: 16 }}>
          <label style={{ fontSize: T.textSm, fontWeight: 600, display: "block", marginBottom: 6 }}>
            Akte zuordnen
          </label>
          <KandidatenList
            kandidaten={detail.parse.akten_kandidaten}
            ausgewaehlt={gewaehlteAkte}
            onWaehle={setGewaehlteAkte}
          />
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: T.textXs, color: T.textFaint, marginBottom: 4 }}>
              Live-Suche nach Mandantenname oder Aktenzeichen (RA-Micro):
            </div>
            <AktenLiveSuche onWaehle={setGewaehlteAkte} />
          </div>
          <input
            value={gewaehlteAkte}
            onChange={e => setGewaehlteAkte(e.target.value)}
            placeholder="oder Aktenzeichen eintippen"
            style={{
              width: "100%", boxSizing: "border-box",
              padding: "6px 10px", marginTop: 8,
              border: `1px solid ${T.border}`, borderRadius: 4,
              fontFamily: T.fontMono, fontSize: T.textSm,
            }}
          />
        </section>

        <section style={{ marginBottom: 16 }}>
          <label style={{ fontSize: T.textSm, fontWeight: 600, display: "block", marginBottom: 6 }}>
            Zustellungshistorie ({detail.zustellungen.length})
          </label>
          {detail.zustellungen.map(z => (
            <div key={z.id} style={{
              padding: "4px 8px", background: T.surface,
              border: `1px solid ${T.borderSoft}`, borderRadius: 4,
              marginBottom: 3, fontSize: T.textXs,
            }}>
              <strong>{z.quelle}</strong> · {z.absender || "—"} · {z.empfangen_am || "?"}
              {z.betreff && <div style={{ color: T.textMuted }}>{z.betreff}</div>}
            </div>
          ))}
          {!detail.zustellungen.length && (
            <div style={{ color: T.textFaint, fontSize: T.textXs }}>Keine Zustellungen erfasst.</div>
          )}
        </section>

        <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
          <button onClick={() => onVerwerfen && onVerwerfen(detail)}
            disabled={aktion}
            title="Dokument aus der Queue verwerfen (Soft-Delete)"
            style={{
              padding: "10px 16px",
              background: T.redBg, color: T.redText,
              border: `1px solid ${T.redLight}`, borderRadius: 4,
              cursor: aktion ? "wait" : "pointer",
              fontWeight: 600,
            }}>
            Verwerfen
          </button>
          <button onClick={() => setZeigeFreigabe(true)}
            disabled={aktion || !gewaehlteAkte}
            style={{
              flex: 1, padding: "10px 16px",
              background: gewaehlteAkte ? T.green : T.border,
              color: T.white, border: "none", borderRadius: 4,
              cursor: gewaehlteAkte && !aktion ? "pointer" : "default",
              fontWeight: 600,
            }}>
            Freigeben →
          </button>
        </div>

        {zeigeFreigabe && (
          <FreigabeDialog
            dokument={detail}
            akteAz={gewaehlteAkte}
            ereignisse={ereignisse}
            ersetztIds={ersetztIds}
            ereignistypen={ereignistypen}
            fbVorschau={fbVorschau}
            fbState={fbState}
            onFbToggle={(key, art) => setFbState(s => {
              if (art === "aktiv") {
                const an = s.aktive.includes(key);
                return { ...s, aktive: an ? s.aktive.filter(k => k !== key) : [...s.aktive, key] };
              }
              const zu = s.collapsed.includes(key);
              return { ...s, collapsed: zu ? s.collapsed.filter(k => k !== key) : [...s.collapsed, key] };
            })}
            onFbFeld={(sec, feld, wert) => setFbState(s => ({
              ...s, werte: { ...s.werte, [sec]: { ...s.werte[sec], [feld]: wert } } }))}
            onFbAdopt={(sec, feld, wert) => setFbState(s => ({
              ...s, werte: { ...s.werte, [sec]: { ...s.werte[sec], [feld]: wert } } }))}
            onErsetztChange={setErsetztIds}
            onEreignisAdd={() => {
              // Sinnvoller Default: <klasse>_eingegangen, wenn die Registry
              // den Typ kennt; sonst der erste eingehende Typ.
              const eingehende = (ereignistypen || [])
                .filter(t => t.richtung === "eingehend");
              const kandidat = `${(detail.klasse || "").toLowerCase()}_eingegangen`;
              const passt = eingehende.find(t => t.typ === kandidat);
              const default_typ = passt ? passt.typ
                                   : (eingehende[0]?.typ || kandidat);
              setEreignisse(prev => [...prev,
                { typ: default_typ, positionen: [] }]);
            }}
            onEreignisChange={(i, neu) => setEreignisse(prev =>
              prev.map((e, j) => j === i ? neu : e))}
            onEreignisDel={i => setEreignisse(prev => prev.filter((_, j) => j !== i))}
            onConfirm={doFreigabe}
            onCancel={() => setZeigeFreigabe(false)}
            laeuft={aktion}
          />
        )}

        {splitOffen && (
          <SplitDialog
            docId={id}
            thumbUrl={thumbUrl}
            onClose={() => setSplitOffen(false)}
            onDone={() => { setSplitOffen(false); onFreigegeben && onFreigegeben(); }}
          />
        )}
      </div>
    </div>
  );
}

export default function ReviewQueueView({ onOpenAkte }) {
  const [queue, setQueue] = useState([]);
  const [aktivId, setAktivId] = useState(null);
  const [ladeError, setLadeError] = useState(null);
  const [verwerfenDok, setVerwerfenDok] = useState(null);
  const [verwerfenLaeuft, setVerwerfenLaeuft] = useState(false);
  const [ereignistypen, setEreignistypen] = useState([]);
  const [klassen, setKlassen] = useState([]);
  const [ansicht, setAnsicht] = useState("queue");  // "queue" | "papierkorb"
  const [papierkorb, setPapierkorb] = useState([]);

  // Ereignistypen aus der Registry einmalig laden (fuer Freigabe-Dropdown).
  useEffect(() => {
    apiIntake.ereignistypen()
      .then(d => setEreignistypen(d.ereignistypen || []))
      .catch(() => setEreignistypen([]));  // Fallback: Dropdown zeigt roh
  }, []);

  // Dokumentklassen aus der Registry laden (BUG-26: nicht mehr hartcodiert).
  useEffect(() => {
    apiIntake.klassen()
      .then(d => setKlassen(d.klassen || []))
      .catch(() => setKlassen([]));  // Fallback: KLASSEN_FALLBACK im Dropdown
  }, []);

  const laden = useCallback(async () => {
    try {
      const d = await apiIntake.queue();
      setQueue(d.eintraege || []);
      setLadeError(null);
    } catch (e) { setLadeError(e.message); }
  }, []);

  useEffect(() => { laden(); }, [laden]);
  useEffect(() => {
    const t = setInterval(laden, 30000);
    return () => clearInterval(t);
  }, [laden]);

  const ladePapierkorb = useCallback(async () => {
    try {
      const d = await apiIntake.papierkorb();
      setPapierkorb(d.eintraege || []);
    } catch (e) { setLadeError(e.message); }
  }, []);

  useEffect(() => {
    if (ansicht === "papierkorb") ladePapierkorb();
  }, [ansicht, ladePapierkorb]);

  const doWiederherstellen = useCallback(async (id) => {
    try {
      await apiIntake.wiederherstellen(id);
      ladePapierkorb();
      laden();
    } catch (e) { setLadeError(e.message); }
  }, [ladePapierkorb, laden]);

  const doVerwerfen = useCallback(async ({ grund, kommentar }) => {
    if (!verwerfenDok) return;
    setVerwerfenLaeuft(true);
    try {
      await apiIntake.verwerfen(verwerfenDok.id, { grund, kommentar });
      const wegId = verwerfenDok.id;
      setVerwerfenDok(null);
      if (aktivId === wegId) setAktivId(null);
      laden();
    } catch (e) {
      setLadeError(e.message);
    } finally {
      setVerwerfenLaeuft(false);
    }
  }, [verwerfenDok, aktivId, laden]);

  const bereit = useMemo(
    () => queue.filter(q => q.queue_status === "bereit_zur_review"),
    [queue],
  );
  const fehler = useMemo(
    () => queue.filter(q => q.queue_status === "pipeline_fehler"),
    [queue],
  );

  const onFreigegeben = useCallback((akteAz) => {
    setAktivId(null);
    laden();
    if (akteAz && onOpenAkte) {
      onOpenAkte({ az: akteAz, az_roh: akteAz, label: akteAz });
    }
  }, [laden, onOpenAkte]);

  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden", background: T.offWhite }}>
      {/* Queue-Liste */}
      <div style={{
        width: 340, borderRight: `1px solid ${T.border}`,
        background: T.cardBg, display: "flex", flexDirection: "column",
      }}>
        <div style={{
          padding: "12px 14px", borderBottom: `1px solid ${T.border}`,
          background: T.navy, color: T.white,
        }}>
          <div style={{ fontSize: T.textXs, opacity: 0.7, letterSpacing: "0.1em" }}>
            REVIEW-QUEUE
          </div>
          <div style={{ fontSize: T.textLg, fontFamily: T.fontDisplay }}>
            {bereit.length} bereit · {fehler.length} fehlerhaft
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            {["queue", "papierkorb"].map(a => (
              <button key={a} onClick={() => setAnsicht(a)}
                style={{
                  flex: 1, padding: "4px 8px", fontSize: T.textXs,
                  fontWeight: 600, cursor: "pointer", borderRadius: 4,
                  border: `1px solid ${T.white}40`,
                  background: ansicht === a ? T.white : "transparent",
                  color: ansicht === a ? T.navy : T.white,
                }}>
                {a === "queue" ? "Queue" : "Papierkorb"}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflow: "auto" }}>
          {ladeError && (
            <div style={{ padding: 12, color: T.redText, background: T.redBg, fontSize: T.textSm }}>
              {ladeError}
            </div>
          )}
          {ansicht === "queue" && (
            <>
              {!queue.length && !ladeError && (
                <div style={{ padding: 20, color: T.textMuted, fontSize: T.textSm, textAlign: "center" }}>
                  Queue leer — alles freigegeben.
                </div>
              )}
              {gruppiereQueue(queue).map(gruppe => (
                <React.Fragment key={gruppe.eintrag.id}>
                  <QueueEintrag item={gruppe.eintrag}
                    aktiv={aktivId === gruppe.eintrag.id}
                    onClick={() => setAktivId(gruppe.eintrag.id)}
                    onVerwerfen={setVerwerfenDok} />
                  {gruppe.kinder.map(k => (
                    <QueueEintrag key={k.id} item={k} aktiv={aktivId === k.id}
                      onClick={() => setAktivId(k.id)}
                      onVerwerfen={setVerwerfenDok} eingerueckt />
                  ))}
                </React.Fragment>
              ))}
            </>
          )}
          {ansicht === "papierkorb" && !papierkorb.length && (
            <div style={{ padding: 20, color: T.textMuted, fontSize: T.textSm, textAlign: "center" }}>
              Papierkorb leer.
            </div>
          )}
          {ansicht === "papierkorb" && papierkorb.map(item => (
            <div key={item.id} style={{
              padding: "10px 12px", borderBottom: `1px solid ${T.border}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontSize: T.textXs, fontWeight: 600, color: T.textMuted,
                  border: `1px solid ${T.border}`, borderRadius: 4, padding: "1px 6px",
                }}>{grundLabel(item.verworfen_grund)}</span>
                <div style={{ flex: 1 }} />
                <button onClick={() => doWiederherstellen(item.id)}
                  style={{
                    border: `1px solid ${T.accent}`, background: T.accentPale,
                    color: T.accent, cursor: "pointer", padding: "3px 8px",
                    fontSize: T.textXs, fontWeight: 600, borderRadius: 4,
                  }}>Wiederherstellen</button>
              </div>
              <div style={{ fontSize: T.textSm, color: T.text }}>
                {item.payload_typ === "text" && <span title="E-Mail">📧 </span>}
                <strong>{item.klasse || "unbekannt"}</strong>
              </div>
              {(item.absender || item.betreff) && (
                <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 2 }}>
                  {item.absender || ""}{item.betreff ? ` · ${item.betreff}` : ""}
                </div>
              )}
              <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 2 }}>
                #{item.id} · verworfen {item.verworfen_am}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail-Panel -- key={aktivId} erzwingt sauberen Re-Mount bei
          Dokument-Wechsel, sonst bleiben Live-Suche-Query, gewaehlteAkte,
          Meldung etc. vom Vor-Dokument stehen. */}
      <DetailPanel key={aktivId || "leer"} id={aktivId}
                    onFreigegeben={onFreigegeben} onOpenAkte={onOpenAkte}
                    onVerwerfen={setVerwerfenDok}
                    ereignistypen={ereignistypen} klassen={klassen} />

      {verwerfenDok && (
        <VerwerfenDialog
          dokument={verwerfenDok}
          onConfirm={doVerwerfen}
          onCancel={() => setVerwerfenDok(null)}
          laeuft={verwerfenLaeuft}
        />
      )}
    </div>
  );
}
