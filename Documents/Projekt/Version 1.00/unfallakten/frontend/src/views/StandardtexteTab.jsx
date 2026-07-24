import { useEffect, useMemo, useState } from "react";
import T from "../config/theme.js";
import { Card, CardHead, Btn } from "../components/common.jsx";
import TextbausteinEditor, { pruefePlatzhalter } from "../components/TextbausteinEditor.jsx";
import { apiStandardtexte } from "../api.js";

const ABSCHNITT_REIHENFOLGE = ["antraege", "sachverhalt", "unfallhergang", "schaden",
  "wuerdigung", "schmerzensgeld", "verzug", "gebuehren", "schluss"];

export default function StandardtexteTab() {
  const [bausteine, setBausteine] = useState([]);
  const [suche, setSuche] = useState("");
  const [offen, setOffen] = useState(null);
  const [entwurf, setEntwurf] = useState("");
  const [meldung, setMeldung] = useState(null);

  const laden = () => apiStandardtexte.liste()
    .then(r => setBausteine(r.bausteine || []))
    .catch(e => setMeldung(`Laden fehlgeschlagen: ${e.message}`));
  useEffect(() => { laden(); }, []);

  const gruppen = useMemo(() => {
    const q = suche.trim().toLowerCase();
    const passend = bausteine.filter(b => !q
      || b.key.includes(q)
      || b.beschreibung.toLowerCase().includes(q)
      || (b.override_text || b.standard_text).toLowerCase().includes(q));
    return ABSCHNITT_REIHENFOLGE
      .map(a => ({ abschnitt: a,
                   label: passend.find(b => b.abschnitt === a)?.abschnitt_label,
                   eintraege: passend.filter(b => b.abschnitt === a) }))
      .filter(g => g.eintraege.length > 0);
  }, [bausteine, suche]);

  const oeffnen = (b) => {
    setOffen(b.key === offen ? null : b.key);
    setEntwurf(b.override_text ?? b.standard_text);
    setMeldung(null);
  };

  const speichern = async (b) => {
    const pflicht = b.platzhalter.filter(p => p.pflicht).map(p => p.key);
    const fehlend = pflicht.filter(k => !entwurf.includes(`<${k}>`));
    let bestaetigt = false;
    if (fehlend.length > 0) {
      bestaetigt = window.confirm(
        `Pflicht-Platzhalter fehlen: ${fehlend.map(k => `<${k}>`).join(", ")}.\n` +
        `Der Wert erscheint dann nicht mehr im Dokument. Trotzdem speichern?`);
      if (!bestaetigt) return;
    }
    try {
      await apiStandardtexte.speichern(b.key, entwurf, bestaetigt);
      setMeldung("Gespeichert.");
      laden();
    } catch (e) {
      setMeldung(`Speichern fehlgeschlagen: ${e.message}`);
    }
  };

  const zuruecksetzen = async (b) => {
    await apiStandardtexte.reset(b.key);
    setEntwurf(b.standard_text);
    setMeldung("Auf Standard zurückgesetzt.");
    laden();
  };

  return (
    <div>
      <div style={{ marginBottom: "1.25rem" }}>
        <h3 style={{ fontFamily: T.fontDisplay, fontSize: "1.05rem", fontWeight: 700,
          color: T.navy, margin: "0 0 6px" }}>Standardtexte Klageschrift</h3>
        <p style={{ fontFamily: T.fontBody, fontSize: "0.9rem", color: T.textMuted,
          margin: 0, lineHeight: 1.55 }}>
          Feste Rahmen- und Kernsätze der Klageschrift. Geänderte Bausteine gelten
          sofort für neue Dokumente; der Reset-Button je Baustein stellt den
          Programmtext wieder her.
        </p>
      </div>

      <input placeholder="Suche (Beschreibung, Text, Kennung)…" value={suche}
             onChange={e => setSuche(e.target.value)}
             style={{ width: "100%", marginBottom: "1.25rem", padding: "8px 10px",
               border: `1.5px solid ${T.border}`, borderRadius: 7,
               fontFamily: T.fontBody, fontSize: "0.925rem", color: T.text,
               background: T.surface, outline: "none", boxSizing: "border-box" }} />

      {meldung && (
        <div style={{ marginBottom: "1rem", fontFamily: T.fontBody, fontSize: "0.875rem",
          color: T.textMid, background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 7, padding: "6px 12px" }}>
          {meldung}
        </div>
      )}

      {gruppen.map(g => (
        <div key={g.abschnitt} style={{ marginBottom: "1.25rem" }}>
          <h4 style={{ fontFamily: T.fontDisplay, fontSize: "0.85rem", fontWeight: 700,
            color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.06em",
            margin: "0 0 8px" }}>{g.label}</h4>
          <Card style={{ overflow: "visible" }}>
            {g.eintraege.map((b, i) => {
              const istOffen = offen === b.key;
              const pruefung = istOffen
                ? pruefePlatzhalter(entwurf, b.platzhalter.map(p => p.key))
                : { ok: true };
              return (
                <div key={b.key} style={{ borderTop: i === 0 ? "none" : `1px solid ${T.border}` }}>
                  <div onClick={() => oeffnen(b)}
                    style={{ display: "flex", alignItems: "center", gap: 8,
                      padding: "0.85rem 1.25rem", cursor: "pointer" }}>
                    <strong style={{ fontFamily: T.fontBody, fontSize: "0.925rem",
                      color: T.text, fontWeight: 600 }}>{b.beschreibung}</strong>
                    {b.override_text != null && (
                      <span style={{ fontFamily: T.fontBody, fontSize: "0.75rem",
                        fontWeight: 600, padding: "2px 8px", borderRadius: 10,
                        background: T.amberBg, color: T.amberText }}>geändert</span>
                    )}
                    <span style={{ marginLeft: "auto", fontFamily: "ui-monospace,monospace",
                      fontSize: "0.75rem", color: T.textFaint }}>{b.key}</span>
                  </div>
                  {istOffen && (
                    <div style={{ padding: "0 1.25rem 1.25rem" }}>
                      <TextbausteinEditor
                        wert={entwurf}
                        onChange={setEntwurf}
                        platzhalter={b.platzhalter}
                        onVorschau={async (t) => (await apiStandardtexte.vorschau(b.key, t)).vorschau}
                        standardText={b.override_text != null ? b.standard_text : null}
                        onReset={b.override_text != null ? () => zuruecksetzen(b) : null}
                      />
                      <details style={{ margin: "10px 0", fontFamily: T.fontBody,
                        fontSize: "0.85rem", color: T.textMid }}>
                        <summary style={{ cursor: "pointer", color: T.textMuted }}>
                          Standardtext anzeigen
                        </summary>
                        <pre style={{ whiteSpace: "pre-wrap", fontFamily: T.fontBody,
                          fontSize: "0.85rem", color: T.textMid, background: T.surface,
                          border: `1px solid ${T.border}`, borderRadius: 7,
                          padding: "8px 10px", marginTop: 6 }}>{b.standard_text}</pre>
                      </details>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <Btn onClick={() => speichern(b)} disabled={!pruefung.ok}>
                          Speichern
                        </Btn>
                        {b.geaendert_am && (
                          <span style={{ fontFamily: T.fontBody, fontSize: "0.8rem",
                            color: T.textFaint }}>geändert am {b.geaendert_am}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </Card>
        </div>
      ))}
    </div>
  );
}
