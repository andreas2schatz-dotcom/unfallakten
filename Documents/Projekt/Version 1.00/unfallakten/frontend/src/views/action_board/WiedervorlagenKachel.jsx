import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, AbschnittLabel, MehrKnopf, ZeilenListe } from "./boardUi";

const OHNE_WV_LIMIT = 5;

export default function WiedervorlagenKachel({ status, wv, ohne_wv, onOpenAkte, onRetry, onAlleOeffnen }) {
  const ueberfaellig = (wv || []).filter((e) => e.tage_bis < 0);
  const heute        = (wv || []).filter((e) => e.tage_bis === 0);
  const alleOhneWv   = ohne_wv || [];
  const ohneWvSicht  = alleOhneWv.slice(0, OHNE_WV_LIMIT);
  const ohneWvRest   = alleOhneWv.length - ohneWvSicht.length;
  const hatInhalt    = ueberfaellig.length > 0 || heute.length > 0 || alleOhneWv.length > 0;

  const zusammenfassung = status === "ok" && hatInhalt ? (
    <>
      {ueberfaellig.length > 0 && <b style={{ color: T.redText, fontWeight: 600 }}>{ueberfaellig.length} überfällig · </b>}
      {heute.length} heute
    </>
  ) : null;

  function wvZeile(e) {
    const stufe = e.tage_bis < 0 ? "rot" : "gelb";
    return (
      <Zeile
        key={e.az + e.datum}
        stufe={stufe}
        onClick={() => onOpenAkte(e.az)}
        links={
          <ZeileText
            titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant || e.az}</>}
            meta={e.grund || "Wiedervorlage"}
            metaFarbe={stufe === "rot" ? T.redText : T.amberText}
          />
        }
        rechts={<StufenBadge stufe={stufe}>{e.tage_bis < 0 ? `−${Math.abs(e.tage_bis)} T` : "heute"}</StufenBadge>}
      />
    );
  }

  return (
    <Kachel icon={Ic.refresh} titel="Wiedervorlagen" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Wiedervorlagen konnten nicht geladen werden"
        onRetry={onRetry}
        leer={!hatInhalt}
        leerText="Alle Wiedervorlagen erledigt"
      >
        {ueberfaellig.length > 0 && (
          <>
            <AbschnittLabel>Überfällig</AbschnittLabel>
            <ZeilenListe>{ueberfaellig.map(wvZeile)}</ZeilenListe>
          </>
        )}
        {heute.length > 0 && (
          <>
            <AbschnittLabel abstandOben={ueberfaellig.length > 0}>Heute fällig</AbschnittLabel>
            <ZeilenListe>{heute.map(wvZeile)}</ZeilenListe>
          </>
        )}
        {alleOhneWv.length > 0 && (
          <>
            <AbschnittLabel abstandOben={ueberfaellig.length > 0 || heute.length > 0}>Keine Wiedervorlage gesetzt</AbschnittLabel>
            <ZeilenListe>
              {ohneWvSicht.map((e) => (
                <Zeile
                  key={e.az}
                  onClick={() => onOpenAkte(e.az)}
                  links={<ZeileText titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant || ""}</>} meta="keine WV gesetzt" />}
                />
              ))}
            </ZeilenListe>
          </>
        )}
        {(ohneWvRest > 0 || hatInhalt) && (
          <MehrKnopf onClick={onAlleOeffnen}>
            {ohneWvRest > 0 ? `+ ${ohneWvRest} weitere · Alle Wiedervorlagen öffnen` : "Alle Wiedervorlagen öffnen"}
          </MehrKnopf>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
