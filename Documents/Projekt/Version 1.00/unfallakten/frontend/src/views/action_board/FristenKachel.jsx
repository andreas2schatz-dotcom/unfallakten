import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";
import { fmtDatumDe } from "../../config/utils";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, AbschnittLabel, ZeilenListe, tageBadgeText } from "./boardUi";

// Vorfristen sind eine Vorwarnung, kein Fristablauf. Sie bekommen deshalb
// kein Dringlichkeits-Badge und zaehlen nicht in "überfällig" mit -- sonst
// sieht die Lage dramatischer aus als sie ist.
function VorfristHinweis({ children }) {
  return (
    <span className="tabular-nums" style={{ fontSize: T.textXs, color: T.textMuted, whiteSpace: "nowrap" }}>
      Vorfrist · {children}
    </span>
  );
}

export default function FristenKachel({ status, eintraege, onOpenAkte, onRetry, retryLaeuft }) {
  const dringend   = eintraege.filter((e) => e.tage_bis <= 0);
  const demnaechst = eintraege.filter((e) => e.tage_bis > 0);

  const echte        = eintraege.filter((e) => !e.ist_vorfrist);
  const ueberfaellig = echte.filter((e) => e.tage_bis < 0).length;
  const heuteFaellig = echte.filter((e) => e.tage_bis === 0).length;
  const spaeter      = echte.filter((e) => e.tage_bis > 0).length;
  const vorfristen   = eintraege.length - echte.length;

  const zusammenfassung = status === "ok" && eintraege.length > 0 ? (
    <>
      {ueberfaellig > 0 && <b style={{ color: T.redText, fontWeight: 600 }}>{ueberfaellig} überfällig · </b>}
      {heuteFaellig} heute · {spaeter} demnächst
      {vorfristen > 0 && ` · ${vorfristen} ${vorfristen === 1 ? "Vorfrist" : "Vorfristen"}`}
    </>
  ) : null;

  return (
    <Kachel icon={Ic.scale} titel="Fristen" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Fristenkalender nicht erreichbar (E-Akte-Mount)"
        onRetry={onRetry}
        retryLaeuft={retryLaeuft}
        leer={eintraege.length === 0}
        leerText="Keine Fristen in den nächsten drei Werktagen"
      >
        {dringend.length > 0 && (
          <>
            <AbschnittLabel>Handlungsbedarf</AbschnittLabel>
            <ZeilenListe>
              {dringend.map((e, i) => {
                const stufe = e.ist_vorfrist ? undefined : (e.tage_bis < 0 ? "rot" : "gelb");
                return (
                  <Zeile
                    key={`${e.az}|${e.frist_datum}|${e.frist_art}|${i}`}
                    stufe={stufe}
                    onClick={() => onOpenAkte(e.az)}
                    links={
                      <ZeileText
                        titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                        meta={`${e.frist_art} · Frist ${fmtDatumDe(e.frist_datum)}`}
                        metaFarbe={stufe === "rot" ? T.redText : stufe === "gelb" ? T.amberText : undefined}
                        zusatz={e.bemerkung}
                      />
                    }
                    rechts={e.ist_vorfrist
                      ? <VorfristHinweis>{tageBadgeText(e.tage_bis)}</VorfristHinweis>
                      : <StufenBadge stufe={stufe}>{tageBadgeText(e.tage_bis)}</StufenBadge>}
                  />
                );
              })}
            </ZeilenListe>
          </>
        )}
        {demnaechst.length > 0 && (
          <>
            <AbschnittLabel abstandOben={dringend.length > 0}>Demnächst</AbschnittLabel>
            <ZeilenListe>
              {demnaechst.map((e, i) => (
                <Zeile
                  key={`${e.az}|${e.frist_datum}|${e.frist_art}|${i}`}
                  onClick={() => onOpenAkte(e.az)}
                  links={
                    <ZeileText
                      titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                      meta={e.frist_art}
                      zusatz={e.bemerkung}
                    />
                  }
                  rechts={e.ist_vorfrist
                    ? <VorfristHinweis>{fmtDatumDe(e.frist_datum)}</VorfristHinweis>
                    : <span className="tabular-nums" style={{ fontSize: T.textXs, color: T.textMuted, whiteSpace: "nowrap" }}>{fmtDatumDe(e.frist_datum)}</span>}
                />
              ))}
            </ZeilenListe>
          </>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
