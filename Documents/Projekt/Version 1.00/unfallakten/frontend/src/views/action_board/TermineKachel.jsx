import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";
import { Kachel, KachelInhalt, Zeile, ZeileText, AbschnittLabel, ZeilenListe } from "./boardUi";

export default function TermineKachel({ status, eintraege, onOpenAkte, onRetry }) {
  const heute  = eintraege.filter((e) => e.tage_bis === 0);
  const morgen = eintraege.filter((e) => e.tage_bis === 1);

  const zusammenfassung = status === "ok" && eintraege.length > 0
    ? `${heute.length} heute · ${morgen.length} morgen`
    : null;

  function terminZeile(e) {
    return (
      <Zeile
        key={e.az + e.termin_datum + (e.uhrzeit || "")}
        onClick={() => onOpenAkte(e.az)}
        links={
          <ZeileText
            titel={<>{e.termin_art || "Termin"} — {e.kurzbezeichnung || e.mandant}</>}
            meta={<><b className="tabular-nums">{e.az}</b></>}
          />
        }
        rechts={<span className="tabular-nums" style={{ fontSize: T.textSm, fontWeight: 600, color: T.textMid, whiteSpace: "nowrap" }}>{e.uhrzeit || ""}</span>}
      />
    );
  }

  return (
    <Kachel icon={Ic.clock} titel="Termine" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Termine konnten nicht geladen werden"
        onRetry={onRetry}
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
    </Kachel>
  );
}
