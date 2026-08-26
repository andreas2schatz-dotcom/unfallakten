import React, { useMemo, useState } from "react";
import T from "../config/theme.js";
import { fmtEuro } from "../config/utils.js";
import { Btn } from "./common.jsx";

// Die Regulierungs-Tabelle fuehrt Sammelzeilen, die das Backend so nicht
// kennt: "fahrzeugschaden_netto" buendelt alle Fahrzeugschaden-Keys,
// "extra_wdm_ssN" ist die Anzeigeform von "sonstiges_wdm_N".
export function vorschlagBackendKey(zeilenKey) {
  if (zeilenKey === "fahrzeugschaden_netto") return "fahrzeugschaden";
  const wdm = /^extra_wdm_ss(\d+)$/.exec(zeilenKey || "");
  if (wdm) return `sonstiges_wdm_${wdm[1]}`;
  return zeilenKey;
}

// Der Vorschlag liefert Backend-Keys, die Auswahl zeigt Tabellenzeilen.
function zeilenKeyFuer(backendKey, optionen) {
  if (!backendKey) return "";
  const direkt = optionen.find(o => o.value === backendKey);
  if (direkt) return direkt.value;
  const ueberBackend = optionen.find(o => vorschlagBackendKey(o.value) === backendKey);
  if (ueberBackend) return ueberBackend.value;
  // kostenpauschale und unkostenpauschale sind in der Tabelle eine Zeile
  if (backendKey === "kostenpauschale") {
    const pausch = optionen.find(o => o.value === "unkostenpauschale");
    if (pausch) return pausch.value;
  }
  return "";
}

function zuZahl(wert) {
  if (typeof wert === "number") return wert;
  const norm = String(wert ?? "").replace(/\./g, "").replace(",", ".").trim();
  const zahl = parseFloat(norm);
  return Number.isFinite(zahl) ? zahl : 0;
}

function AbrechnungVorschlagDialog({ vorschlag, positionsOptionen = [],
                                     onUebernehmen, onAbbrechen, speichert = false }) {
  const [zeilen, setZeilen] = useState(() =>
    (vorschlag.positionen || []).map((p, i) => {
      const zeilenKey = zeilenKeyFuer(p.position_key, positionsOptionen);
      return {
        id: i,
        rohLabel: p.roh_label || "—",
        zeilenKey,
        gezahlt: String(p.betrag_reguliert ?? 0).replace(".", ","),
        aktiv: Boolean(zeilenKey),
      };
    }));

  const setZeile = (id, changes) =>
    setZeilen(prev => prev.map(z => z.id === id ? { ...z, ...changes } : z));

  const gefordertFuer = (zeilenKey) =>
    positionsOptionen.find(o => o.value === zeilenKey)?.gefordert ?? 0;

  const aktive = zeilen.filter(z => z.aktiv && z.zeilenKey);
  const summe = aktive.reduce((s, z) => s + zuZahl(z.gezahlt), 0);

  const uebernehmen = () => {
    onUebernehmen({
      dokument_id:  vorschlag.dokument_id,
      datum:        vorschlag.datum,
      versicherung: vorschlag.versicherung,
      referenz_nr:  vorschlag.referenz_nr,
      positionen: aktive.map(z => ({
        position_key:     vorschlagBackendKey(z.zeilenKey),
        betrag_gefordert: Math.round(gefordertFuer(z.zeilenKey) * 100) / 100,
        betrag_reguliert: Math.round(zuZahl(z.gezahlt) * 100) / 100,
      })),
    });
  };

  const sZelle = { padding: "7px 10px", fontFamily: T.fontBody, fontSize: "0.85rem" };

  return (
    <>
      <div onClick={onAbbrechen}
        style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.4)", zIndex: 950 }} />
      <div role="dialog" aria-label="Abrechnungsschreiben übernehmen"
        style={{ position: "fixed", top: "8%", left: "50%", transform: "translateX(-50%)",
          width: "min(920px, 92vw)", maxHeight: "84vh", zIndex: 951,
          background: T.cardBg, borderRadius: 12, display: "flex", flexDirection: "column",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)", overflow: "hidden" }}>

        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.border}`, background: T.surface }}>
          <div style={{ fontFamily: T.fontBody, fontSize: "0.95rem", fontWeight: 700, color: T.navy }}>
            {vorschlag.bezeichnung}
          </div>
          <div style={{ marginTop: 3, fontSize: "0.8rem", color: T.textMuted }}>
            {[vorschlag.versicherung,
              vorschlag.referenz_nr ? `Schaden-Nr. ${vorschlag.referenz_nr}` : null,
              vorschlag.gesamtbetrag != null ? `Gesamt ${fmtEuro(vorschlag.gesamtbetrag)}` : null,
            ].filter(Boolean).join(" · ")}
          </div>
        </div>

        <div style={{ padding: "12px 20px", overflowY: "auto", flex: 1 }}>
          <div style={{ fontSize: "0.82rem", color: T.textMid, marginBottom: 10 }}>
            Aus dem Schreiben ausgelesen – bitte Zuordnung und Beträge prüfen. Erst mit
            „Übernehmen“ werden sie als Abrechnung gebucht.
          </div>

          {(vorschlag.warnungen || []).map((w, i) => (
            <div key={i} role="alert"
              style={{ marginBottom: 8, padding: "7px 10px", borderRadius: 7,
                background: T.amberBg, border: `1px solid ${T.amber}55`,
                fontSize: "0.8rem", color: T.text }}>
              ⚠ {w}
            </div>
          ))}

          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: T.surface, borderBottom: `1px solid ${T.border}` }}>
                {["", "Im Schreiben", "Schadenposition", "Gefordert", "Gezahlt"].map((h, i) => (
                  <th key={h + i} style={{ ...sZelle, textAlign: i >= 3 ? "right" : "left",
                    fontSize: "0.74rem", fontWeight: 600, color: T.textMuted,
                    textTransform: "uppercase", letterSpacing: "0.06em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {zeilen.map(z => {
                const gefordert = gefordertFuer(z.zeilenKey);
                return (
                  <tr key={z.id} data-testid={`vorschlagzeile-${z.rohLabel}`}
                    style={{ borderBottom: `1px solid ${T.borderSoft}`,
                      opacity: z.aktiv ? 1 : 0.55 }}>
                    <td style={{ ...sZelle, width: 34 }}>
                      <input type="checkbox" checked={z.aktiv}
                        aria-label={`${z.rohLabel} übernehmen`}
                        disabled={!z.zeilenKey}
                        onChange={e => setZeile(z.id, { aktiv: e.target.checked })} />
                    </td>
                    <td style={{ ...sZelle, color: T.text }}>{z.rohLabel}</td>
                    <td style={sZelle}>
                      <select value={z.zeilenKey}
                        aria-label={`Schadenposition für ${z.rohLabel}`}
                        onChange={e => setZeile(z.id, {
                          zeilenKey: e.target.value,
                          aktiv: z.aktiv && Boolean(e.target.value),
                        })}
                        style={{ width: "100%", padding: "5px 7px", borderRadius: 6,
                          border: `1px solid ${z.zeilenKey ? T.border : T.amber}`,
                          fontFamily: T.fontBody, fontSize: "0.83rem",
                          background: T.surface, color: T.text }}>
                        <option value="">— nicht zugeordnet —</option>
                        {positionsOptionen.map(o => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ ...sZelle, textAlign: "right", fontFamily: "ui-monospace,monospace",
                      color: T.textMuted }}>
                      {z.zeilenKey ? fmtEuro(gefordert) : "—"}
                    </td>
                    <td style={{ ...sZelle, textAlign: "right", width: 120 }}>
                      <input value={z.gezahlt} aria-label="Gezahlt"
                        onChange={e => setZeile(z.id, { gezahlt: e.target.value })}
                        style={{ width: "100%", padding: "5px 7px", borderRadius: 6,
                          border: `1px solid ${T.border}`, textAlign: "right",
                          fontFamily: "ui-monospace,monospace", fontSize: "0.85rem",
                          background: T.surface, color: T.text }} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div style={{ padding: "12px 20px", borderTop: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: T.surface }}>
          <span style={{ fontFamily: T.fontBody, fontSize: "0.85rem", color: T.textMid }}>
            {aktive.length} von {zeilen.length} Positionen ·{" "}
            <strong style={{ fontFamily: "ui-monospace,monospace", color: T.navy }}>
              {fmtEuro(summe)}
            </strong>
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn size="sm" variant="ghost" onClick={onAbbrechen}>Abbrechen</Btn>
            <Btn size="sm" variant="gold" onClick={uebernehmen}
              disabled={aktive.length === 0 || speichert}>
              {speichert ? "…" : "Übernehmen"}
            </Btn>
          </div>
        </div>
      </div>
    </>
  );
}

export default AbrechnungVorschlagDialog;
