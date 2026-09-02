import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";
import { Kachel, KachelInhalt, Zeile, ZeileText, AbschnittLabel, ZeilenListe } from "./boardUi";

function terminTitel(e) {
  const betreff = e.betreff || e.kurzbezeichnung || e.mandant || "";
  return [e.termin_art, betreff].filter(Boolean).join(" — ") || "Termin";
}

export default function TermineKachel({
  status, eintraege, onOpenAkte, onRetry, retryLaeuft,
  kalenderSbListe = [], aktiveKalenderSb, onToggleKalenderSb,
}) {
  const heute  = eintraege.filter((e) => e.tage_bis === 0);
  const morgen = eintraege.filter((e) => e.tage_bis === 1);
  const keinKalender = kalenderSbListe.length > 0 && aktiveKalenderSb && aktiveKalenderSb.size === 0;

  const zusammenfassung = status === "ok" && !keinKalender && eintraege.length > 0
    ? `${heute.length} heute · ${morgen.length} morgen`
    : null;

  function terminZeile(e, i) {
    return (
      <Zeile
        key={`${e.az}|${e.termin_datum}|${e.uhrzeit || ""}|${e.termin_art || ""}|${i}`}
        onClick={e.az ? () => onOpenAkte(e.az) : undefined}
        links={
          <ZeileText
            titel={terminTitel(e)}
            meta={(e.az || e.ort) ? (
              <>
                {e.az && <b className="tabular-nums">{e.az}</b>}
                {e.az && e.ort && " · "}
                {e.ort}
              </>
            ) : null}
            zusatz={e.bemerkung || null}
          />
        }
        rechts={<span className="tabular-nums" style={{ fontSize: T.textSm, fontWeight: 600, color: T.textMid, whiteSpace: "nowrap" }}>{e.uhrzeit || ""}</span>}
      />
    );
  }

  return (
    <Kachel icon={Ic.clock} titel="Termine" zusammenfassung={zusammenfassung}>
      {kalenderSbListe.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap", marginBottom: 11 }}>
          <span style={{ fontSize: "0.65625rem", fontWeight: 600, letterSpacing: "0.05em", color: T.textMuted, marginRight: 2 }}>KALENDER</span>
          {kalenderSbListe.map((sb) => {
            const aktiv = !!aktiveKalenderSb?.has(sb.kuerzel);
            return (
              <button
                key={sb.kuerzel}
                type="button"
                aria-label={`Kalender ${sb.kuerzel}`}
                title={sb.titel ? `${sb.name} · ${sb.titel}` : sb.name}
                aria-pressed={aktiv}
                onClick={() => onToggleKalenderSb(sb.kuerzel)}
                style={{
                  fontSize: "0.6875rem", fontWeight: 600, padding: "2px 8px", borderRadius: 999,
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
      )}

      {keinKalender ? (
        <div style={{ fontSize: T.textSm, color: T.textMuted, padding: "10px 2px" }}>
          Kein Kalender ausgewählt
        </div>
      ) : (
        <KachelInhalt
          status={status}
          fehlerText="Termine konnten nicht geladen werden"
          onRetry={onRetry}
          retryLaeuft={retryLaeuft}
          leer={eintraege.length === 0}
          leerText="Heute keine Termine"
        >
          {heute.length > 0 && (
            <>
              <AbschnittLabel>Heute</AbschnittLabel>
              <ZeilenListe>{heute.map(terminZeile)}</ZeilenListe>
            </>
          )}
          {morgen.length > 0 && (
            <>
              <AbschnittLabel abstandOben={heute.length > 0}>Morgen</AbschnittLabel>
              <ZeilenListe>{morgen.map(terminZeile)}</ZeilenListe>
            </>
          )}
        </KachelInhalt>
      )}
    </Kachel>
  );
}
