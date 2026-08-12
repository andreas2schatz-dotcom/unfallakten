import React, { useEffect, useRef, useState } from "react";
import T from "../../config/theme.js";
import { Card, Btn } from "../../components/common.jsx";
import { apiEinstellungen } from "../../api.js";

const ROLLEN  = [["anwalt", "Anwalt/Anwältin"], ["refa", "ReFa"]];
const ANREDEN = [["", "—"], ["herr", "Herr"], ["frau", "Frau"]];

const LEER_NEU = { kuerzel: "", name: "", titel: "", anrede: "", rolle: "anwalt",
                   aktiv: true, dashboard_vorauswahl: false, kalender_name: "", sortierung: 100 };

const feldStil = {
  width: "100%", padding: "5px 7px", border: `1px solid ${T.border}`,
  borderRadius: 5, fontFamily: T.fontBody, fontSize: "0.9rem",
};

export default function SachbearbeiterTab() {
  const [eintraege, setEintraege] = useState([]);
  const [entwurf, setEntwurf]     = useState({});
  const [meldung, setMeldung]     = useState(null);
  const [fehler, setFehler]       = useState(null);
  const [neu, setNeu]             = useState(null);
  const schmutzigeZeilen          = useRef(new Set());

  const laden = () => apiEinstellungen.sachbearbeiter()
    .then(r => {
      const liste = r.eintraege || [];
      setEintraege(liste);
      setEntwurf(prev => Object.fromEntries(liste.map(e => [
        e.kuerzel,
        schmutzigeZeilen.current.has(e.kuerzel) ? (prev[e.kuerzel] || { ...e }) : { ...e },
      ])));
    })
    .catch(e => setFehler(`Laden fehlgeschlagen: ${e.message}`));

  useEffect(() => { laden(); }, []);

  const setzeFeld = (kuerzel, feld, wert) => {
    schmutzigeZeilen.current.add(kuerzel);
    setEntwurf(prev => ({ ...prev, [kuerzel]: { ...prev[kuerzel], [feld]: wert } }));
  };

  const speichern = async (kuerzel) => {
    const e = entwurf[kuerzel];
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterSpeichern(kuerzel, {
        name: e.name, titel: e.titel, anrede: e.anrede, rolle: e.rolle,
        aktiv: !!e.aktiv, dashboard_vorauswahl: !!e.dashboard_vorauswahl,
        kalender_name: e.kalender_name || "", sortierung: e.sortierung,
      });
      schmutzigeZeilen.current.delete(kuerzel);
      setMeldung(`${kuerzel} gespeichert.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };

  const anlegen = async () => {
    const kuerzel = (neu.kuerzel || "").trim().toUpperCase();
    setFehler(null);
    if (!/^[A-Z]{2}$/.test(kuerzel)) {
      setFehler("Das Kürzel muss aus genau zwei Großbuchstaben bestehen.");
      return;
    }
    if (!(neu.name || "").trim()) {
      setFehler("Bitte einen Namen eintragen.");
      return;
    }
    try {
      await apiEinstellungen.sachbearbeiterAnlegen({ ...neu, kuerzel });
      setNeu(null);
      setMeldung(`${kuerzel} angelegt.`);
      await laden();
    } catch (err) {
      setFehler(err.message);
    }
  };

  const loeschen = async (kuerzel) => {
    if (!window.confirm(
      `${kuerzel} wirklich löschen? Altakten mit diesem Kürzel zeigen danach nur noch ` +
      `[${kuerzel}] statt des Namens. Sicherer ist es, den Haken bei „aktiv“ zu entfernen.`)) {
      return;
    }
    setFehler(null);
    try {
      await apiEinstellungen.sachbearbeiterLoeschen(kuerzel);
      setMeldung(`${kuerzel} gelöscht.`);
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
                  <Btn size="sm" onClick={() => speichern(e.kuerzel)}>Speichern</Btn>{" "}
                  <Btn variant="danger" size="sm" onClick={() => loeschen(e.kuerzel)}>Löschen</Btn>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {neu ? (
        <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap",
          alignItems: "center" }}>
          <input aria-label="Neues Kürzel" placeholder="XY" maxLength={2}
            style={{ ...feldStil, width: 70 }} value={neu.kuerzel}
            onChange={ev => setNeu({ ...neu, kuerzel: ev.target.value.toUpperCase() })} />
          <input aria-label="Neuer Name" placeholder="Vorname Nachname"
            style={{ ...feldStil, width: 220 }} value={neu.name}
            onChange={ev => setNeu({ ...neu, name: ev.target.value })} />
          <input aria-label="Neuer Titel" placeholder="Rechtsanwältin"
            style={{ ...feldStil, width: 220 }} value={neu.titel}
            onChange={ev => setNeu({ ...neu, titel: ev.target.value })} />
          <select aria-label="Neue Rolle" style={{ ...feldStil, width: 160 }} value={neu.rolle}
            onChange={ev => setNeu({ ...neu, rolle: ev.target.value })}>
            {ROLLEN.map(([w, l]) => <option key={w} value={w}>{l}</option>)}
          </select>
          <Btn onClick={anlegen}>Anlegen</Btn>
          <Btn variant="secondary" onClick={() => { setNeu(null); setFehler(null); }}>Abbrechen</Btn>
        </div>
      ) : (
        <div style={{ marginTop: 14 }}>
          <Btn onClick={() => { setNeu({ ...LEER_NEU }); setMeldung(null); }}>
            + Sachbearbeiter
          </Btn>
        </div>
      )}
    </Card>
  );
}
