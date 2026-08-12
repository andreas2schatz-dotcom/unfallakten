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
    return new Set(liste.filter((e) => e.dashboard_vorauswahl).map((e) => e.kuerzel));
  }
  const auswahl = new Set(gespeichert.filter((k) => gueltig.has(k)));
  if (bekanntVorher === null) return auswahl;
  const bekanntSet = new Set(bekanntVorher);
  for (const k of gueltig) {
    if (!bekanntSet.has(k)) auswahl.add(k);
  }
  return auswahl;
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

  function toggleSB(kuerzel) {
    setAktiveSB((prev) => {
      const next = new Set(prev || []);
      next.has(kuerzel) ? next.delete(kuerzel) : next.add(kuerzel);
      localStorage.setItem(SB_KEY, JSON.stringify([...next]));
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

      const bekanntVorher = gespeicherterBekanntBestand();
      const initial = initialeAuswahl(aktive, bekanntVorher);
      const neueKuerzel = bekanntVorher === null
        ? []
        : aktiveKuerzel.filter((k) => !bekanntVorher.includes(k));

      // prev === null: erster erfolgreicher Ladevorgang -> initiale Auswahl.
      // Sonst: neue Kürzel, die während der laufenden Sitzung dazukommen,
      // sofort in die bestehende Auswahl mergen (nicht erst nach Neuladen
      // der Seite sichtbar machen) -- ohne bereits abgewählte Kürzel
      // anzurühren.
      setAktiveSB((prev) => {
        if (prev === null) return initial;
        if (neueKuerzel.length === 0) return prev;
        const next = new Set(prev);
        neueKuerzel.forEach((k) => next.add(k));
        localStorage.setItem(SB_KEY, JSON.stringify([...next]));
        return next;
      });

      localStorage.setItem(BEKANNT_KEY, JSON.stringify(aktiveKuerzel));
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
  const fristen = daten.fristen.eintraege.filter(sbFilter);
  const termine = daten.termine.eintraege.filter(sbFilter);
  const wv      = daten.wv.wv.filter(sbFilter);
  const ohneWv  = daten.wv.ohne_wv.filter(sbFilter);

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

      {sbListe.length > 0 && aktiveSB && aktiveSB.size === 0 ? (
        <div style={{ background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 10, padding: "22px 16px", textAlign: "center", color: T.textMuted, fontSize: T.textSm }}>
          Kein Sachbearbeiter ausgewählt
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <JetztDranLeiste
            fristenStatus={daten.fristen.status}
            wvStatus={daten.wv.status}
            fristen={fristen}
            wv={wv}
            onOpenAkte={oeffneAkte}
          />
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,3fr) minmax(0,2fr)", gap: 16, alignItems: "start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
              <FristenKachel status={daten.fristen.status} eintraege={fristen} onOpenAkte={oeffneAkte} onRetry={laden} retryLaeuft={laedtGerade} />
              <WiedervorlagenKachel status={daten.wv.status} wv={wv} ohne_wv={ohneWv} onOpenAkte={oeffneAkte} onRetry={laden} onAlleOeffnen={onOpenWiedervorlage} retryLaeuft={laedtGerade} />
            </div>
            <TermineKachel status={daten.termine.status} eintraege={termine} onOpenAkte={oeffneAkte} onRetry={laden} retryLaeuft={laedtGerade} />
          </div>
        </div>
      )}
    </div>
  );
}
