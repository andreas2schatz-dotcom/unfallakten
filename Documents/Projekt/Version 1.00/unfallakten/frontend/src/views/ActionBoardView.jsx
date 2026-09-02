import React, { useCallback, useEffect, useState } from "react";
import { apiDashboard, apiEinstellungen } from "../api";
import T from "../config/theme";
import TermineKachel        from "./action_board/TermineKachel";
import FristenKachel        from "./action_board/FristenKachel";
import WiedervorlagenKachel from "./action_board/WiedervorlagenKachel";
import JetztDranLeiste      from "./action_board/JetztDranLeiste";

function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

const SB_KEY      = "dashboard.aktiveSB";
const BEKANNT_KEY = "dashboard.bekannteSB";
// Eigener Filter für die Termine-Kachel: Termine kommen aus den RA-MICRO-
// Kalendern, und gepflegt sind nur die Anwaltskalender. Fristen und
// Wiedervorlagen hängen dagegen am Sachbearbeiter der Akte -- beides darf
// sich nicht gegenseitig mitfiltern.
const KALENDER_KEY = "dashboard.aktiveKalenderSB";

function sbAusAz(az) {
  const m = (az || "").match(/([A-Z]{2,3})$/);
  return m ? m[1] : null;
}

function gespeicherteListe(key) {
  try {
    const arr = JSON.parse(localStorage.getItem(key));
    return Array.isArray(arr) ? arr : null;
  } catch {
    return null;
  }
}

function gespeicherteAuswahl() {
  return gespeicherteListe(SB_KEY);
}

function gespeicherterBekanntBestand() {
  return gespeicherteListe(BEKANNT_KEY);
}

// gespeichert === null: noch nie eine Auswahl getroffen (auch nicht bewusst
// geleert) → bisheriges Verhalten, nur die Vorauswahl ist aktiv.
// bekanntVorher === null: es gibt zwar eine gespeicherte Auswahl, aber noch
// keinen "bereits gesehen"-Bestand (Altzustand vor diesem Feature) → keine
// Kürzel gelten als neu, die gespeicherte Auswahl bleibt unangetastet.
// Sonst: gespeicherte Auswahl PLUS alle aktuellen Kürzel, die im Bestand
// noch nicht vorkamen (neu gepflegte Kürzel dürfen nie stillschweigend
// verschwinden, das trifft auch Fristen).
function initialeAuswahl(liste, bekanntVorher) {
  const gueltig     = new Set(liste.map((e) => e.kuerzel));
  const gespeichert = gespeicherteAuswahl();
  if (gespeichert === null) {
    const vorauswahl = new Set(liste.filter((e) => e.dashboard_vorauswahl).map((e) => e.kuerzel));
    // Keine gespeicherte Auswahl UND keine gepflegte Vorauswahl (Fallback-
    // Liste ohne dashboard_vorauswahl, oder alle Haken im Reiter entfernt)
    // -- lieber zu viel zeigen als eine Frist verschlucken: dann lieber
    // alle aktiven Kürzel auswählen als gar keines. Eine vom Nutzer selbst
    // geleerte Auswahl ist davon nicht betroffen, weil dann gespeichert
    // nicht null ist.
    return vorauswahl.size > 0 ? vorauswahl : gueltig;
  }
  const auswahl = new Set(gespeichert.filter((k) => gueltig.has(k)));
  if (bekanntVorher === null) return auswahl;
  const bekanntSet = new Set(bekanntVorher);
  for (const k of gueltig) {
    if (!bekanntSet.has(k)) auswahl.add(k);
  }
  return auswahl;
}

// Vergleicht eine Set-Auswahl mit dem rohen localStorage-Wert (Array oder
// null), damit der Mount-Pfad nur dann in localStorage schreibt, wenn sich
// initialeAuswahl() tatsächlich von der gespeicherten Auswahl unterscheidet
// (z. B. weil neue Kürzel gemergt wurden).
function auswahlWeichtAb(auswahl, gespeichert) {
  const gespeichertArr = gespeichert || [];
  if (auswahl.size !== gespeichertArr.length) return true;
  return gespeichertArr.some((k) => !auswahl.has(k));
}

const START = {
  termine: { status: "laedt", eintraege: [] },
  fristen: { status: "laedt", eintraege: [] },
  wv:      { status: "laedt", wv: [], ohne_wv: [] },
};

export default function ActionBoardView({ onOpenAkte, onOpenWiedervorlage }) {
  const [daten,       setDaten]       = useState(START);
  const [ladeZeit,    setLadeZeit]    = useState(null);
  const [laedtGerade, setLaedtGerade] = useState(false);
  const [sbListe,     setSbListe]     = useState([]);
  const [aktiveSB,    setAktiveSB]    = useState(null);
  const [aktiveKalenderSB, setAktiveKalenderSB] = useState(null);

  function toggleSB(kuerzel) {
    setAktiveSB((prev) => {
      const next = new Set(prev || []);
      next.has(kuerzel) ? next.delete(kuerzel) : next.add(kuerzel);
      localStorage.setItem(SB_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  function toggleKalenderSB(kuerzel) {
    setAktiveKalenderSB((prev) => {
      const next = new Set(prev || []);
      next.has(kuerzel) ? next.delete(kuerzel) : next.add(kuerzel);
      localStorage.setItem(KALENDER_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  async function laden() {
    setLaedtGerade(true);
    const [r1, r2, r3] = await Promise.allSettled([
      apiDashboard.termineHeute(),
      apiDashboard.fristen(),
      apiDashboard.wiedervorlagen(),
    ]);
    setDaten((prev) => ({
      termine: r1.status === "fulfilled" ? { status: "ok", eintraege: r1.value?.eintraege ?? [] } : { ...prev.termine, status: "fehler" },
      fristen: r2.status === "fulfilled" ? { status: "ok", eintraege: r2.value?.eintraege ?? [] } : { ...prev.fristen, status: "fehler" },
      wv:      r3.status === "fulfilled" ? { status: "ok", wv: r3.value?.wv ?? [], ohne_wv: r3.value?.ohne_wv ?? [] } : { ...prev.wv, status: "fehler" },
    }));
    setLadeZeit(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    setLaedtGerade(false);

    const [r4] = await Promise.allSettled([apiEinstellungen.sachbearbeiter()]);
    if (r4.status === "fulfilled") {
      const aktive = (r4.value?.eintraege ?? []).filter((e) => e.aktiv && !e.ignoriert);
      const aktiveKuerzel = aktive.map((e) => e.kuerzel);
      setSbListe(aktive);

      // Eine leere Kürzelliste (HTTP 204, leere Tabelle, alle Zeilen
      // inaktiv/ignoriert) darf weder die Auswahl noch den Bestand
      // anfassen -- sonst verwirft initialeAuswahl() eine gespeicherte
      // Auswahl als "ungültig" (gueltig ist leer) und überschreibt sie
      // mit einer leeren Menge, die wegen der bewusst klebrigen leeren
      // Auswahl (Randbedingung "abgewählt bleibt abgewählt") nie mehr
      // zurückkommt. Die Ansicht filtert in dieser Situation ohnehin
      // nicht: sbListe ist dann leer, also ist auch das lokale
      // bekannteSB in sbFilter leer.
      if (aktiveKuerzel.length > 0) {
        const gespeichert   = gespeicherteAuswahl();
        const bekanntVorher = gespeicherterBekanntBestand();
        const initial       = initialeAuswahl(aktive, bekanntVorher);
        const neueKuerzel   = bekanntVorher === null
          ? []
          : aktiveKuerzel.filter((k) => !bekanntVorher.includes(k));

        // prev === null: erster erfolgreicher Ladevorgang -> initiale
        // Auswahl; weicht sie von der gespeicherten Auswahl ab (z. B.
        // weil neue Kürzel gemergt wurden), wird das sofort persistiert
        // -- sonst geht das neue Kürzel beim nächsten Seitenaufruf
        // wieder verloren (bekannteSB kennt es dann schon, aktiveSB nie).
        // Sonst: neue Kürzel, die während der laufenden Sitzung
        // dazukommen, sofort in die bestehende Auswahl mergen (nicht
        // erst nach Neuladen der Seite sichtbar machen) -- ohne bereits
        // abgewählte Kürzel anzurühren.
        setAktiveSB((prev) => {
          if (prev === null) {
            if (auswahlWeichtAb(initial, gespeichert)) {
              localStorage.setItem(SB_KEY, JSON.stringify([...initial]));
            }
            return initial;
          }
          if (neueKuerzel.length === 0) return prev;
          const next = new Set(prev);
          neueKuerzel.forEach((k) => next.add(k));
          localStorage.setItem(SB_KEY, JSON.stringify([...next]));
          return next;
        });

        localStorage.setItem(BEKANNT_KEY, JSON.stringify(aktiveKuerzel));
      }

      // Kalenderfilter: nur Sachbearbeiter mit gepflegtem Kalendernamen.
      // Ohne gespeicherten Stand sind alle aktiv -- lieber einen Termin zu
      // viel zeigen als einen Gerichtstermin verschlucken.
      const kalenderKuerzel = aktive
        .filter((e) => (e.kalender_name || "").trim())
        .map((e) => e.kuerzel);
      if (kalenderKuerzel.length > 0) {
        const gespeichert = gespeicherteListe(KALENDER_KEY);
        setAktiveKalenderSB((prev) => {
          if (prev !== null) return prev;
          return new Set(gespeichert === null
            ? kalenderKuerzel
            : gespeichert.filter((k) => kalenderKuerzel.includes(k)));
        });
      }
    }
  }

  useEffect(() => { laden(); }, []);

  const oeffneAkte = useCallback((az) => {
    onOpenAkte({ az: baseAz(az), az_roh: az });
  }, [onOpenAkte]);

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  const bekannteSB = new Set(sbListe.map((e) => e.kuerzel));
  const sbFilter = (e) => {
    if (!aktiveSB) return true;
    const sb = sbAusAz(e.az);
    return !sb || !bekannteSB.has(sb) || aktiveSB.has(sb);
  };

  // Termine tragen ihr Kürzel im Feld sb (aus dem Kalendernamen). Es aus dem
  // Aktenzeichen abzuleiten geht bei Terminen ohne Akte schief -- die
  // rutschten dann durch jeden Filter.
  const kalenderSbListe = sbListe.filter((e) => (e.kalender_name || "").trim());
  const kalenderKuerzel = new Set(kalenderSbListe.map((e) => e.kuerzel));
  const terminFilter = (e) => {
    if (!aktiveKalenderSB) return true;
    const sb = (e.sb || "").trim();
    return !sb || !kalenderKuerzel.has(sb) || aktiveKalenderSB.has(sb);
  };

  const fristen = daten.fristen.eintraege.filter(sbFilter);
  const termine = daten.termine.eintraege.filter(terminFilter);
  const wv      = daten.wv.wv.filter(sbFilter);
  const ohneWv  = daten.wv.ohne_wv.filter(sbFilter);

  const keinSbGewaehlt = sbListe.length > 0 && aktiveSB && aktiveSB.size === 0;

  return (
    <div style={{ flex: 1, overflow: "auto", background: T.offWhite, padding: "20px 24px 26px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <div style={{ fontFamily: T.fontDisplay, fontSize: T.textXl, fontWeight: 700, color: T.text, lineHeight: 1.2 }}>Tagesübersicht</div>
          <div style={{ fontSize: T.textSm, color: T.textMuted, marginTop: 2 }}>{heute}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.05em", color: T.textMuted, marginRight: 3 }}>SB</span>
            {sbListe.map((sb) => {
              const aktiv = !!aktiveSB?.has(sb.kuerzel);
              return (
                <button
                  key={sb.kuerzel}
                  type="button"
                  title={sb.titel ? `${sb.name} · ${sb.titel}` : sb.name}
                  aria-pressed={aktiv}
                  onClick={() => toggleSB(sb.kuerzel)}
                  style={{
                    fontSize: "0.6875rem", fontWeight: 600, padding: "3px 9px", borderRadius: 999,
                    cursor: "pointer",
                    background: aktiv ? T.navy : "transparent",
                    color: aktiv ? "#FFFFFF" : T.textMuted,
                    border: `1px solid ${aktiv ? T.navy : T.borderSoft || T.border}`,
                  }}
                >
                  {sb.kuerzel}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={laden}
            disabled={laedtGerade}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: T.textXs, color: T.textMuted, padding: "5px 10px", border: `1px solid ${T.border}`, borderRadius: 7, background: T.cardBg, cursor: "pointer", opacity: laedtGerade ? 0.5 : 1 }}
          >
            {laedtGerade ? "Lädt …" : "Aktualisieren"}
            {ladeZeit && !laedtGerade && <span className="tabular-nums">· Stand {ladeZeit}</span>}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {!keinSbGewaehlt && (
          <JetztDranLeiste
            fristenStatus={daten.fristen.status}
            wvStatus={daten.wv.status}
            fristen={fristen}
            wv={wv}
            onOpenAkte={oeffneAkte}
          />
        )}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,3fr) minmax(0,2fr)", gap: 16, alignItems: "start" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            {keinSbGewaehlt ? (
              <div style={{ background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 10, padding: "22px 16px", textAlign: "center", color: T.textMuted, fontSize: T.textSm }}>
                Kein Sachbearbeiter ausgewählt
              </div>
            ) : (
              <>
                <FristenKachel status={daten.fristen.status} eintraege={fristen} onOpenAkte={oeffneAkte} onRetry={laden} retryLaeuft={laedtGerade} />
                <WiedervorlagenKachel status={daten.wv.status} wv={wv} ohne_wv={ohneWv} onOpenAkte={oeffneAkte} onRetry={laden} onAlleOeffnen={onOpenWiedervorlage} retryLaeuft={laedtGerade} />
              </>
            )}
          </div>
          <TermineKachel
            status={daten.termine.status}
            eintraege={termine}
            onOpenAkte={oeffneAkte}
            onRetry={laden}
            retryLaeuft={laedtGerade}
            kalenderSbListe={kalenderSbListe}
            aktiveKalenderSb={aktiveKalenderSB}
            onToggleKalenderSb={toggleKalenderSB}
          />
        </div>
      </div>
    </div>
  );
}
