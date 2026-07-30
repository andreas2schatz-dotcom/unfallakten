import React from "react";
import T from "../../config/theme";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, ZeilenListe } from "./boardUi";

export function jetztDranEintraege(fristen, wv) {
  const f = (fristen || []).filter((e) => e.tage_bis <= 0).map((e) => ({
    az: e.az, tage: e.tage_bis, prio: 0,
    titel: e.kurzbezeichnung || e.mandant || e.az,
    art: e.frist_art,
  }));
  const w = (wv || []).filter((e) => e.tage_bis <= 0).map((e) => ({
    az: e.az, tage: e.tage_bis, prio: 1,
    titel: e.kurzbezeichnung || e.mandant || e.az,
    art: e.grund ? `Wiedervorlage: ${e.grund}` : "Wiedervorlage",
  }));
  return [...f, ...w].sort((a, b) => (a.tage - b.tage) || (a.prio - b.prio)).slice(0, 3);
}

function badgeText(tage) {
  if (tage === 0) return "heute fällig";
  const t = Math.abs(tage);
  return t === 1 ? "1 Tag überfällig" : `${t} Tage überfällig`;
}

export default function JetztDranLeiste({ fristenStatus, wvStatus, fristen, wv, onOpenAkte }) {
  if (fristenStatus !== "ok" || wvStatus !== "ok") return null;
  const eintraege = jetztDranEintraege(fristen, wv);

  const punkt = <span style={{ width: 8, height: 8, borderRadius: "50%", background: T.accent, display: "inline-block" }} />;
  const zusammenfassung = eintraege.length > 0
    ? (eintraege.length === 1 ? "1 Vorgang braucht Sie zuerst" : `${eintraege.length} Vorgänge brauchen Sie zuerst`)
    : null;

  return (
    <Kachel icon={punkt} titel="Jetzt dran" zusammenfassung={zusammenfassung}>
      <KachelInhalt status="ok" leer={eintraege.length === 0} leerText="Keine überfälligen Vorgänge">
        <ZeilenListe>
          {eintraege.map((e) => {
            const stufe = e.tage < 0 ? "rot" : "gelb";
            return (
              <Zeile
                key={e.prio + e.az + e.tage}
                stufe={stufe}
                onClick={() => onOpenAkte(e.az)}
                links={
                  <ZeileText
                    titel={<><b className="tabular-nums">{e.az}</b> · {e.titel}</>}
                    meta={e.art}
                    metaFarbe={stufe === "rot" ? T.redText : T.amberText}
                  />
                }
                rechts={<StufenBadge stufe={stufe}>{badgeText(e.tage)}</StufenBadge>}
              />
            );
          })}
        </ZeilenListe>
      </KachelInhalt>
    </Kachel>
  );
}
