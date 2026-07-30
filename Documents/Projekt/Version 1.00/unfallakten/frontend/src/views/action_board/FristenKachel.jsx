import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";
import { fmtDatumDe } from "../../config/utils";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, AbschnittLabel, ZeilenListe } from "./boardUi";

function badgeText(tage) {
  if (tage === 0) return "heute";
  return tage < 0 ? `−${-tage} T` : `+${tage} T`;
}

export default function FristenKachel({ status, eintraege, onOpenAkte, onRetry }) {
  const dringend    = eintraege.filter((e) => e.tage_bis <= 0);
  const demnaechst  = eintraege.filter((e) => e.tage_bis > 0);
  const ueberfaellig = dringend.filter((e) => e.tage_bis < 0).length;
  const heuteFaellig = dringend.length - ueberfaellig;

  const zusammenfassung = status === "ok" && eintraege.length > 0 ? (
    <>
      {ueberfaellig > 0 && <b style={{ color: T.redText, fontWeight: 600 }}>{ueberfaellig} überfällig · </b>}
      {heuteFaellig} heute · {demnaechst.length} demnächst
    </>
  ) : null;

  return (
    <Kachel icon={Ic.scale} titel="Fristen" zusammenfassung={zusammenfassung}>
      <KachelInhalt
        status={status}
        fehlerText="Fristen konnten nicht geladen werden"
        onRetry={onRetry}
        leer={eintraege.length === 0}
        leerText="Keine Fristen in den nächsten 14 Tagen"
      >
        {dringend.length > 0 && (
          <>
            <AbschnittLabel>Handlungsbedarf</AbschnittLabel>
            <ZeilenListe>
              {dringend.map((e) => {
                const stufe = e.tage_bis < 0 ? "rot" : "gelb";
                return (
                  <Zeile
                    key={e.az + e.frist_datum}
                    stufe={stufe}
                    onClick={() => onOpenAkte(e.az)}
                    links={
                      <ZeileText
                        titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                        meta={`${e.frist_art} · Frist ${fmtDatumDe(e.frist_datum)}`}
                        metaFarbe={stufe === "rot" ? T.redText : T.amberText}
                      />
                    }
                    rechts={<StufenBadge stufe={stufe}>{badgeText(e.tage_bis)}</StufenBadge>}
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
              {demnaechst.map((e) => (
                <Zeile
                  key={e.az + e.frist_datum}
                  onClick={() => onOpenAkte(e.az)}
                  links={
                    <ZeileText
                      titel={<><b className="tabular-nums">{e.az}</b> · {e.kurzbezeichnung || e.mandant}</>}
                      meta={e.frist_art}
                    />
                  }
                  rechts={<span className="tabular-nums" style={{ fontSize: T.textXs, color: T.textMuted, whiteSpace: "nowrap" }}>{fmtDatumDe(e.frist_datum)}</span>}
                />
              ))}
            </ZeilenListe>
          </>
        )}
      </KachelInhalt>
    </Kachel>
  );
}
