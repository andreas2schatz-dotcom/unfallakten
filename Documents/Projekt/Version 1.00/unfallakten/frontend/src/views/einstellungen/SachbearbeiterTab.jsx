import React, { useEffect, useState } from "react";
import T from "../../config/theme.js";
import { Card, Btn } from "../../components/common.jsx";
import { apiEinstellungen } from "../../api.js";

const ROLLEN  = [["anwalt", "Anwalt/Anwältin"], ["refa", "ReFa"]];
const ANREDEN = [["", "—"], ["herr", "Herr"], ["frau", "Frau"]];

const feldStil = {
  width: "100%", padding: "5px 7px", border: `1px solid ${T.border}`,
  borderRadius: 5, fontFamily: T.fontBody, fontSize: "0.9rem",
};

export default function SachbearbeiterTab() {
  const [eintraege, setEintraege] = useState([]);
  const [entwurf, setEntwurf]     = useState({});
  const [meldung, setMeldung]     = useState(null);
  const [fehler, setFehler]       = useState(null);

  const laden = () => apiEinstellungen.sachbearbeiter()
    .then(r => {
      setEintraege(r.eintraege || []);
      setEntwurf(Object.fromEntries((r.eintraege || []).map(e => [e.kuerzel, { ...e }])));
    })
    .catch(e => setFehler(`Laden fehlgeschlagen: ${e.message}`));

  useEffect(() => { laden(); }, []);

  const setzeFeld = (kuerzel, feld, wert) =>
    setEntwurf(prev => ({ ...prev, [kuerzel]: { ...prev[kuerzel], [feld]: wert } }));

  const speichern = async (kuerzel) => {
    const e = entwurf[kuerzel];
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterSpeichern(kuerzel, {
        name: e.name, titel: e.titel, anrede: e.anrede, rolle: e.rolle,
        aktiv: !!e.aktiv, dashboard_vorauswahl: !!e.dashboard_vorauswahl,
        kalender_name: e.kalender_name || "", sortierung: e.sortierung,
      });
      setMeldung(`${kuerzel} gespeichert.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };

  return (
    <Card>
      <div style={{ fontSize: "0.9rem", color: T.textMuted, marginBottom: 14 }}>
        Kürzel, Namen und Titel gelten für die Tagesübersicht <b>und</b> für die
        Unterschriftszeile in allen Schreiben. Ausgeschiedene Kolleginnen und Kollegen
        bitte auf „aktiv“ verzichten statt löschen — sonst zeigen Altakten nur noch das Kürzel.
      </div>

      {fehler  && <div role="alert" style={{ color: T.redText, marginBottom: 10 }}>{fehler}</div>}
      {meldung && <div style={{ color: T.green, marginBottom: 10 }}>{meldung}</div>}

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ textAlign: "left", color: T.textMuted }}>
            <th style={{ padding: "6px 8px" }}>Kürzel</th>
            <th style={{ padding: "6px 8px" }}>Name</th>
            <th style={{ padding: "6px 8px" }}>Titel</th>
            <th style={{ padding: "6px 8px" }}>Anrede</th>
            <th style={{ padding: "6px 8px" }}>Rolle</th>
            <th style={{ padding: "6px 8px" }}>aktiv</th>
            <th style={{ padding: "6px 8px" }}>vorausgewählt</th>
            <th style={{ padding: "6px 8px" }}>RA-MICRO-Kalender</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {eintraege.map(e => {
            const d = entwurf[e.kuerzel] || e;
            return (
              <tr key={e.kuerzel} style={{ borderTop: `1px solid ${T.border}`,
                opacity: d.aktiv ? 1 : 0.55 }}>
                <td style={{ padding: "6px 8px", fontWeight: 600 }}>
                  {e.kuerzel}
                  {!d.aktiv && <div style={{ fontSize: "0.75rem", color: T.textMuted }}>
                    ausgeschieden</div>}
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Name ${e.kuerzel}`} style={feldStil} value={d.name || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "name", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Titel ${e.kuerzel}`} style={feldStil} value={d.titel || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "titel", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <select aria-label={`Anrede ${e.kuerzel}`} style={feldStil} value={d.anrede || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "anrede", ev.target.value)}>
                    {ANREDEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
                  </select>
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <select aria-label={`Rolle ${e.kuerzel}`} style={feldStil} value={d.rolle || "anwalt"}
                    onChange={ev => setzeFeld(e.kuerzel, "rolle", ev.target.value)}>
                    {ROLLEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
                  </select>
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <input type="checkbox" aria-label={`aktiv ${e.kuerzel}`} checked={!!d.aktiv}
                    onChange={ev => setzeFeld(e.kuerzel, "aktiv", ev.target.checked)} />
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <input type="checkbox" aria-label={`vorausgewählt ${e.kuerzel}`}
                    checked={!!d.dashboard_vorauswahl}
                    onChange={ev => setzeFeld(e.kuerzel, "dashboard_vorauswahl", ev.target.checked)} />
                </td>
                <td style={{ padding: "6px 8px" }}>
                  <input aria-label={`Kalender ${e.kuerzel}`} style={feldStil}
                    value={d.kalender_name || ""}
                    onChange={ev => setzeFeld(e.kuerzel, "kalender_name", ev.target.value)} />
                </td>
                <td style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>
                  <Btn size="sm" onClick={() => speichern(e.kuerzel)}>Speichern</Btn>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
